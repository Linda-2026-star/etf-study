
import streamlit as st
import pandas as pd
import time
from datetime import datetime
from typing import Dict

from signal_engine import SignalEngine
from data_fetcher import DataFetcher
from etf_pool import ETF_POOL
from market_analyzer import MarketStyleAnalyzer
from ui_components import inject_global_css, metric_card, display_market_analysis

# ---------- 页面配置 ----------
st.set_page_config(page_title="ETF 右侧波段", page_icon="📊", layout="wide")

# ---------- 初始化 Session State ----------
def init_session_state():
    defaults = {
        'positions': {},
        'scan_results': [],
        'market_style': MarketStyleAnalyzer().analyze(),
        'manual_style_override': False,
        'scan_loading': False,
        'current_page': "市场分析",
        'theme_mode': "dark"
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session_state()

# ---------- 应用全局主题 ----------
inject_global_css(st.session_state.theme_mode)

# ---------- 数据获取（缓存）----------
@st.cache_data(ttl=300)
def cached_fetch_history(code, days=200):
    return DataFetcher().fetch_history(code, days)

@st.cache_data(ttl=60)
def cached_fetch_realtime(watchlist_tuple):
    return DataFetcher().fetch_realtime(list(watchlist_tuple))

# ---------- 调仓建议生成 ----------
def generate_trade_advice(signal: dict, current_shares: int, params: Dict, capital: float = 100000) -> str:
    pos_level = signal['position']
    action = signal['action']
    price = signal['close']
    test_ratio = params['test_ratio']
    main_ratio = params['main_ratio']

    if pos_level == 0 and current_shares > 0:
        return f"🔴 强制清仓，卖出 {current_shares} 股"
    if pos_level == 0:
        target = 0
    elif pos_level == 1:
        target = int(capital * test_ratio / price // 100) * 100
    else:
        target = int(capital * main_ratio / price // 100) * 100

    diff = target - current_shares

    if action == '试探建仓':
        return f"🟡 试探建仓，买入 {target} 股"
    elif action == '加仓至主升':
        return f"🟢 主升加仓，加仓 {diff} 股"
    elif action == '清仓离场':
        return f"🔴 清仓离场，卖出 {current_shares} 股"
    else:
        return f"⚪ 继续持有 {current_shares} 股"

# ---------- 侧边栏：页面导航与全局设置 ----------
with st.sidebar:
    st.header("📍 导航")
    page = st.radio(
        "选择页面",
        ["市场分析", "自选持仓", "寻找机会", "设置"],
        index=["市场分析", "自选持仓", "寻找机会", "设置"].index(st.session_state.current_page)
    )
    if page != st.session_state.current_page:
        st.session_state.current_page = page
        st.rerun()

    st.divider()
    st.header("⚙️ 全局设置")
    default_list = "512890,510300,513100,588000,159876"
    watchlist_input = st.text_area("自选 ETF 代码", value=default_list)
    watchlist_input = watchlist_input.replace("，", ",")
    watchlist = [c.strip() for c in watchlist_input.split(",") if c.strip()]

    if st.button("🔄 刷新所有数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ---------- 加载核心数据 ----------
market_info = st.session_state.market_style
params = market_info['params']
if st.session_state.manual_style_override:
    from market_analyzer import MarketStyleAnalyzer
    params = MarketStyleAnalyzer()._get_style_params(st.session_state.get('final_style', market_info['style']))
final_style = st.session_state.get('final_style', market_info['style'])

engine = SignalEngine(params=params)
realtime = cached_fetch_realtime(tuple(watchlist))

signals = []
for code in watchlist:
    hist = cached_fetch_history(code)
    if hist is None:
        continue
    if code in realtime:
        hist.loc[hist.index[-1], 'close'] = realtime[code]['lastPrice']
    sig_df = engine.compute(hist)
    sig = engine.get_signal_summary(sig_df, code, realtime.get(code, {}).get('name', f'ETF{code}'))
    signals.append(sig)

# ---------- 页面路由 ----------
current_page = st.session_state.current_page

if current_page == "市场分析":
    display_market_analysis(market_info, final_style, params)

elif current_page == "自选持仓":
    st.header("自选持仓与信号")

    # 持仓汇总
    total_value = 0
    for sig in signals:
        code = sig['code']
        shares = st.session_state.positions.get(code, 0)
        total_value += shares * sig['close']
    metric_card("持仓总市值", f"¥ {total_value:,.0f}")

    # 信号列表
    for sig in signals:
        code = sig['code']
        shares = st.session_state.positions.get(code, 0)

        with st.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                icon = "🟢" if sig['position'] == 2 else ("🟡" if sig['position'] == 1 else "🔴")
                st.subheader(f"{icon} {code} - {sig['name']}")
                st.caption(f"现价 {sig['close']:.3f} | {sig['trend']} | 持仓 {shares} 股")
            with col2:
                st.markdown(f"**操作建议**\n{generate_trade_advice(sig, shares, params)}")

            # 持仓输入
            new_shares = st.number_input(f"调整 {code} 持仓", min_value=0, value=shares, step=100, key=f"pos_{code}")
            st.session_state.positions[code] = new_shares
            st.divider()

elif current_page == "寻找机会":
    st.header("寻找交易机会")

    if st.button("🚀 开始全市场扫描", use_container_width=True):
        with st.spinner("扫描中..."):
            results = SignalEngine.scan_all_etfs(ETF_POOL, DataFetcher(), params=params)
            st.session_state.scan_results = results
            st.rerun()

    if st.session_state.scan_results:
        st.subheader(f"发现 {len(st.session_state.scan_results)} 个机会")
        df = pd.DataFrame(st.session_state.scan_results)
        st.dataframe(df[['code', 'name', 'category', 'close', 'vol_ratio', 'score']], use_container_width=True)
    else:
        st.info("暂无符合条件的 ETF，可点击上方按钮扫描。")

elif current_page == "设置":
    st.header("应用设置")

    # 主题切换
    theme = st.selectbox("选择主题", ["dark", "light"], index=0 if st.session_state.theme_mode == "dark" else 1)
    if st.button("应用主题"):
        st.session_state.theme_mode = theme
        st.rerun()

    st.divider()

    # 策略风格覆盖
    st.subheader("策略风格")
    manual = st.checkbox("手动覆盖风格", value=st.session_state.manual_style_override)
    if manual:
        final = st.selectbox("选择风格", ["保守", "标准", "激进"], index=["保守", "标准", "激进"].index(final_style))
        if st.button("应用风格"):
            st.session_state.manual_style_override = True
            st.session_state.final_style = final
            st.rerun()
    else:
        st.session_state.manual_style_override = False
