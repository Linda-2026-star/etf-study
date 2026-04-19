import streamlit as st
import pandas as pd
import time
import random
from datetime import datetime
from typing import Dict, List, Optional

import threading
import schedule
import time


from signal_engine import SignalEngine
from data_fetcher import DataFetcher
from etf_pool import ETF_POOL
from market_analyzer import MarketStyleAnalyzer

# ---------- 页面配置 ----------
st.set_page_config(page_title="ETF右侧波段", page_icon="📊", layout="wide")

# ---------- 主题配色配置 ----------
THEMES = {
    "炭黑 × 落日橙": {
        "bg": "#1A1A1D",
        "sidebar_bg": "#2A2A2F",
        "accent": "#FF9B00",
        "accent_hover": "#E08600",
        "text": "#F5F1E9",
        "text_secondary": "#D2A2DD",
        "card_bg": "#2A2A2F",
        "border": "#FF9B00",
    },
    "柠黄 × 紫灰": {
        "bg": "#1E1E1E",
        "sidebar_bg": "#2C2C2C",
        "accent": "#FFC700",
        "accent_hover": "#E6B300",
        "text": "#F0F0F0",
        "text_secondary": "#8A7E97",
        "card_bg": "#2A2A2A",
        "border": "#FFC700",
    },
    "橙 × 雾霾蓝": {
        "bg": "#1C1C1E",
        "sidebar_bg": "#282A2E",
        "accent": "#FF7D43",
        "accent_hover": "#E56830",
        "text": "#EAEAEA",
        "text_secondary": "#6888B0",
        "card_bg": "#2C2E33",
        "border": "#FF7D43",
    },
}

# ---------- 初始化 session state ----------
def init_session_state():
    if 'positions' not in st.session_state:
        st.session_state.positions = {}
    if 'scan_results' not in st.session_state:
        st.session_state.scan_results = []
    if 'market_style' not in st.session_state:
        analyzer = MarketStyleAnalyzer()
        st.session_state.market_style = analyzer.analyze()
    if 'manual_style_override' not in st.session_state:
        st.session_state.manual_style_override = False
    if 'scan_loading' not in st.session_state:
        st.session_state.scan_loading = False

init_session_state()

# ---------- 侧边栏（包含主题切换）----------
with st.sidebar:
    st.header("🎨 界面主题")
    theme_name = st.selectbox("选择配色", list(THEMES.keys()), index=0)
    theme = THEMES[theme_name]

    # 注入动态 CSS 变量
    st.markdown(f"""
    <style>
        :root {{
            --bg: {theme['bg']};
            --sidebar-bg: {theme['sidebar_bg']};
            --accent: {theme['accent']};
            --accent-hover: {theme['accent_hover']};
            --text: {theme['text']};
            --text-secondary: {theme['text_secondary']};
            --card-bg: {theme['card_bg']};
            --border: {theme['border']};
        }}
        .stApp {{
            background-color: var(--bg);
            color: var(--text);
        }}
        .main > div {{
            padding-bottom: 80px;
        }}
        section[data-testid="stSidebar"] {{
            background-color: var(--sidebar-bg) !important;
            border-right: 2px solid var(--border) !important;
        }}
        section[data-testid="stSidebar"] * {{
            color: var(--text) !important;
        }}
        section[data-testid="stSidebar"] button {{
            background-color: var(--accent) !important;
            color: #1A1A1D !important;
            font-weight: bold;
            border: none;
            transition: all 0.2s ease;
        }}
        section[data-testid="stSidebar"] button:hover {{
            background-color: var(--accent-hover) !important;
            transform: scale(1.02);
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: var(--accent) !important;
            font-weight: 600;
        }}
        hr {{
            border-color: var(--border);
            opacity: 0.3;
        }}
        .stButton > button {{
            background-color: var(--accent) !important;
            color: #1A1A1D !important;
            font-weight: bold;
            border: none;
            transition: all 0.2s;
            border-radius: 8px;
        }}
        .stButton > button:hover {{
            background-color: var(--accent-hover) !important;
            transform: scale(1.02);
        }}
        div[data-testid="metric-container"] {{
            background-color: var(--card-bg);
            border-radius: 8px;
            padding: 8px;
            border-bottom: 3px solid var(--accent);
        }}
        div[data-testid="metric-container"] label {{
            color: var(--text-secondary) !important;
        }}
        div[data-testid="metric-container"] div[data-testid="stMetricValue"] {{
            color: var(--accent) !important;
            font-size: 28px !important;
        }}
        div[data-testid="stDataFrame"] {{
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
        }}
        .stDataFrame thead tr th {{
            background-color: var(--accent) !important;
            color: #1A1A1D !important;
        }}
        div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {{
            background-color: var(--card-bg);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            border-left: 4px solid var(--border);
        }}
        .fixed-bottom-bar {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background-color: var(--sidebar-bg);
            border-top: 2px solid var(--border);
            padding: 12px 24px;
            display: flex;
            justify-content: center;
            gap: 20px;
            z-index: 999;
            box-shadow: 0 -4px 12px rgba(0,0,0,0.5);
        }}
        .fixed-bottom-bar button {{
            background-color: var(--accent) !important;
            color: #1A1A1D !important;
            font-weight: bold;
            font-size: 18px;
            padding: 12px 32px;
            border-radius: 40px;
            border: none;
            min-width: 160px;
            transition: all 0.2s ease;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }}
        .fixed-bottom-bar button:hover {{
            background-color: var(--accent-hover) !important;
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0,0,0,0.5);
        }}
        @media (max-width: 768px) {{
            .fixed-bottom-bar {{
                padding: 8px 12px;
                gap: 10px;
            }}
            .fixed-bottom-bar button {{
                font-size: 14px;
                padding: 8px 16px;
                min-width: 100px;
            }}
            .main > div {{
                padding-bottom: 70px;
            }}
        }}
        /* 隐藏原生 Streamlit 按钮，仅保留自定义底部栏 */
        div[data-testid="column"]:has(button[key="hidden_scan"]),
        div[data-testid="column"]:has(button[key="hidden_refresh"]),
        div[data-testid="column"]:has(button[key="hidden_clear"]) {{
            display: none;
        }}
    </style>
    """, unsafe_allow_html=True)

    st.caption("👈 点击左上角 `>` 可收起侧边栏")

    st.header("🎛️ 策略风格")
    market_info = st.session_state.market_style
    auto_style = market_info['style']

    col1, col2 = st.columns([3, 1])
    with col1:
        st.metric("当前风格", auto_style)
    with col2:
        if st.button("🔄 重分析"):
            analyzer = MarketStyleAnalyzer()
            st.session_state.market_style = analyzer.analyze(force_refresh=True)
            st.rerun()

    manual = st.checkbox("手动覆盖", value=st.session_state.manual_style_override)
    if manual:
        final_style = st.selectbox("选择风格", ["保守", "标准", "激进"],
                                   index=["保守","标准","激进"].index(auto_style))
        st.session_state.manual_style_override = True
        st.session_state.final_style = final_style
    else:
        final_style = auto_style
        st.session_state.manual_style_override = False

    params = market_info['params']
    if manual:
        from market_analyzer import MarketStyleAnalyzer
        params = MarketStyleAnalyzer()._get_style_params(final_style)

    with st.expander("📋 参数详情"):
        st.write(f"量比阈值: >{params['vol_ratio']}倍")
        st.write(f"波动率上限: <{params['atr_max']}%")
        st.write(f"试探仓: {params['test_ratio']*100:.0f}%")
        st.write(f"主升仓: {params['main_ratio']*100:.0f}%")

    st.header("📌 市场环境")
    st.caption(f"更新: {market_info['timestamp']}")
    st.write(f"估值分位: {market_info['valuation_level']:.1f}%")
    st.write(f"VIX分位: {market_info['vix_level']:.1f}%")
    st.write(f"成交热度: {market_info['turnover_avg']:.1f}万亿")

    st.header("⚙️ 自选池")
    default_list = "512890,510300,513100,588000,159876"
    watchlist_input = st.text_area("代码(逗号分隔)", value=default_list)
    watchlist_input = watchlist_input.replace("，", ",")
    watchlist = [c.strip() for c in watchlist_input.split(",") if c.strip()]

    st.header("💼 持仓")
    for code in watchlist:
        default_val = st.session_state.positions.get(code, 0)
        shares = st.number_input(f"{code}", min_value=0, value=default_val, step=100, key=f"pos_{code}")
        st.session_state.positions[code] = shares
    st.divider()
    st.header("🔄 自迭代优化")

    with st.expander("反馈与优化", expanded=False):
        if st.button("📊 生成绩效报告"):
            from feedback_loop import TradeLogger, PerformanceEvaluator

            logger = TradeLogger()
            trades_df = logger.get_closed_trades()
            if not trades_df.empty:
                evaluator = PerformanceEvaluator()
                metrics = evaluator.calculate_metrics(trades_df)
                st.session_state.performance_metrics = metrics
                st.success("报告生成成功")
            else:
                st.warning("暂无交易记录")

        if st.button("🔍 参数优化建议"):
            with st.spinner("正在搜索最优参数...（可能需要1-2分钟）"):
                from feedback_loop import ParameterOptimizer
                from data_fetcher import DataFetcher
                from etf_pool import ETF_POOL

                optimizer = ParameterOptimizer(DataFetcher(), ETF_POOL)
                param_ranges = {
                    'vol_ratio': [1.0, 1.2, 1.5],
                    'atr_max': [2.5, 3.0, 3.5],
                    'test_ratio': [0.10, 0.12, 0.15],
                }
                results = optimizer.grid_search(param_ranges)

                if results:
                    st.session_state.optimization_results = results[:5]
                    st.success(f"优化完成，找到 {len(results)} 组有效参数")
                else:
                    st.warning("优化未产生有效结果。可能原因：\n"
                               "- 数据源获取失败\n"
                               "- 回测期内无任何交易信号\n"
                               "- ETF池标的数据不足\n"
                               "请检查终端日志。")
                    st.session_state.optimization_results = []


        if st.button("💾 保存当前参数为版本"):
            from feedback_loop import StrategyVersionManager

            manager = StrategyVersionManager()
            version_id = manager.save_version(
                params=params,
                metrics=st.session_state.get('performance_metrics', {}),
                notes=f"{final_style}风格-手动保存"
            )
            st.success(f"已保存为版本 V{version_id}")

        # 显示优化建议
        if st.session_state.get('optimization_results'):
            st.subheader("📈 优化建议（Top 3）")
            for i, r in enumerate(st.session_state.optimization_results[:3]):
                with st.container():
                    st.markdown(f"**方案 {i + 1}** 综合评分: {r['score']}")
                    st.caption(
                        f"量比>{r['params']['vol_ratio']} | 波动<{r['params']['atr_max']}% | 仓位{r['params']['test_ratio'] * 100:.0f}%")
                    st.caption(f"回测收益: {r['total_return']}% | 回撤: {r['max_drawdown']}% | 胜率: {r['win_rate']}%")
                    if st.button(f"应用方案 {i + 1}", key=f"apply_{i}"):
                        st.session_state.manual_style_override = True
                        st.session_state.final_style = "自定义"
                        st.session_state.custom_params = r['params']
                        st.rerun()

# ---------- 缓存数据获取 ----------
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
    name = signal['name']
    test_ratio = params['test_ratio']
    main_ratio = params['main_ratio']

    if pos_level == 0 and current_shares > 0:
        return f"🔴 **强制清仓** {name} 建议立即卖出 {current_shares} 股"
    if pos_level == 0:
        target = 0
    elif pos_level == 1:
        target = int(capital * test_ratio / price // 100) * 100
    else:
        target = int(capital * main_ratio / price // 100) * 100

    diff = target - current_shares
    if signal.get('surge_warning') and current_shares > 0:
        reduce = int(current_shares * 0.5 // 100) * 100
        return f"⚠️ **加速冲顶** 建议减仓 {reduce} 股"

    if action == '试探建仓':
        return f"🟡 **试探建仓** 买入 {target} 股" if current_shares == 0 else f"🟡 **补足试探** 加仓 {diff} 股"
    elif action == '加仓至主升':
        return f"🟢 **主升加仓** 加仓 {diff} 股"
    elif action == '清仓离场':
        return f"🔴 **清仓** 卖出全部 {current_shares} 股" if current_shares > 0 else "⚪ 空仓等待"
    elif action == '减仓至试探':
        target_reduce = int(capital * test_ratio / price // 100) * 100
        return f"🟠 **减仓** 卖出 {current_shares - target_reduce} 股"
    else:
        return f"🔵 持有 {current_shares} 股"

# ---------- 主界面：上方信息流 ----------
st.title("📊 右侧波段 · 智能监控")

# 扫描状态处理
if st.session_state.scan_loading:
    with st.spinner(f"扫描全市场（{final_style}风格）..."):
        fetcher = DataFetcher()
        results = SignalEngine.scan_all_etfs(ETF_POOL, fetcher, params=params)
        st.session_state.scan_results = results
        st.session_state.scan_loading = False
        st.rerun()

# 显示扫描结果
if st.session_state.get('scan_results'):
    count = len(st.session_state.scan_results)
    with st.expander(f"📊 扫描结果（{count}只符合）", expanded=True):
        if count > 0:
            df_scan = pd.DataFrame(st.session_state.scan_results)
            st.dataframe(df_scan[['code', 'name', 'category', 'close', 'vol_ratio', 'score']], use_container_width=True)
        else:
            st.info("暂无符合条件的ETF")

# 加载自选数据
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

st.header("📈 自选信号")
for sig in signals:
    code = sig['code']
    shares = st.session_state.positions.get(code, 0)
    col1, col2 = st.columns([2, 3])
    with col1:
        icon = "🟢" if sig['position']==2 else ("🟡" if sig['position']==1 else "🔴")
        st.metric(f"{icon} {code}", f"{sig['close']:.3f}", f"{sig['trend']} · 持仓{shares}股")
        hist = cached_fetch_history(code)
        if hist is not None:
            chart_df = engine.compute(hist)[['close', 'ma20', 'ma60']].tail(60)
            st.line_chart(chart_df, height=120)
    with col2:
        st.markdown(generate_trade_advice(sig, shares, params))
    st.divider()

# ---------- 底部固定按键栏（视觉层）----------
st.markdown("""
<div class="fixed-bottom-bar">
    <button id="scan-btn">🔍 全市场扫描</button>
    <button id="refresh-btn">🔄 手动刷新</button>
    <button id="clear-btn">🧹 清空持仓</button>
</div>
""", unsafe_allow_html=True)

# 隐藏的功能性按钮（供 JavaScript 触发）
col_b1, col_b2, col_b3 = st.columns(3)
with col_b1:
    if st.button("🔍 全市场扫描", key="hidden_scan", use_container_width=True):
        st.session_state.scan_loading = True
        st.session_state.scan_params = params
        st.rerun()
with col_b2:
    if st.button("🔄 手动刷新", key="hidden_refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with col_b3:
    if st.button("🧹 清空持仓", key="hidden_clear", use_container_width=True):
        for code in watchlist:
            st.session_state.positions[code] = 0
        st.rerun()

# 底部按键 JavaScript 事件绑定
st.markdown("""
<script>
    const scanBtn = document.getElementById('scan-btn');
    const refreshBtn = document.getElementById('refresh-btn');
    const clearBtn = document.getElementById('clear-btn');
    if(scanBtn) scanBtn.addEventListener('click', () => {
        document.querySelector('button[key="hidden_scan"]').click();
    });
    if(refreshBtn) refreshBtn.addEventListener('click', () => {
        document.querySelector('button[key="hidden_refresh"]').click();
    });
    if(clearBtn) clearBtn.addEventListener('click', () => {
        document.querySelector('button[key="hidden_clear"]').click();
    });
</script>
""", unsafe_allow_html=True)

# 自动刷新（如需要可在侧边栏添加开关，此处略）
if st.session_state.get('auto_refresh', False):
    time.sleep(60)
    st.cache_data.clear()
    st.rerun()

# 在 app.py 中添加

def auto_optimize():
    """每周自动优化"""
    while True:
        schedule.every().sunday.at("02:00").do(run_optimization)
        schedule.run_pending()
        time.sleep(3600)


def run_optimization():
    from feedback_loop import ParameterOptimizer, StrategyVersionManager
    from data_fetcher import DataFetcher
    from etf_pool import ETF_POOL

    optimizer = ParameterOptimizer(DataFetcher(), ETF_POOL)
    results = optimizer.grid_search({
        'vol_ratio': [1.0, 1.2, 1.5, 1.8],
        'atr_max': [2.0, 2.5, 3.0, 3.5],
        'test_ratio': [0.08, 0.10, 0.12, 0.15],
    })
    if results:
        manager = StrategyVersionManager()
        best = results[0]
        manager.save_version(best['params'], best, "每周自动优化")
        print(f"自动优化完成，最佳评分: {best['score']}")


# 在 app.py 启动时开启后台线程（仅一次）
if 'optimizer_thread_started' not in st.session_state:
    thread = threading.Thread(target=auto_optimize, daemon=True)
    thread.start()
    st.session_state.optimizer_thread_started = True