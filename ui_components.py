import streamlit as st


def inject_global_css(theme_mode: str = "dark"):
    """注入全局 CSS 样式，支持 Dark 和 Light 两种主题。"""

    if theme_mode == "dark":
        bg_color = "#0F0F0F"
        card_bg = "#1E1E1E"
        text_primary = "#FFFFFF"
        text_secondary = "#A0A0A0"
        accent_color = "#FF7D43"
        border_color = "#2A2A2A"
    else:
        bg_color = "#F5F5F5"
        card_bg = "#FFFFFF"
        text_primary = "#1A1A1A"
        text_secondary = "#6B6B6B"
        accent_color = "#FF7D43"
        border_color = "#E0E0E0"

    st.markdown(f"""
    <style>
        /* 全局样式 */
        .stApp {{
            background-color: {bg_color};
            padding-bottom: 80px;
        }}

        /* 隐藏默认的 Streamlit 元素 */
        header[data-testid="stHeader"] {{
            background-color: transparent;
        }}
        div[data-testid="stToolbar"] {{
            display: none;
        }}
        div[data-testid="stDecoration"] {{
            display: none;
        }}
        footer {{
            display: none;
        }}

        /* 卡片样式 */
        .custom-card {{
            background-color: {card_bg};
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 16px;
            border: 1px solid {border_color};
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        }}

        /* 指标卡片内的数字 */
        .metric-value {{
            font-size: 32px;
            font-weight: 700;
            color: {text_primary};
            line-height: 1.2;
        }}
        .metric-label {{
            font-size: 14px;
            color: {text_secondary};
            margin-bottom: 4px;
        }}
        .metric-delta-positive {{
            color: #10B981;
            font-size: 14px;
            font-weight: 500;
        }}
        .metric-delta-negative {{
            color: #EF4444;
            font-size: 14px;
            font-weight: 500;
        }}

        /* 底部导航栏 */
        .bottom-nav {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background-color: {card_bg};
            border-top: 1px solid {border_color};
            padding: 8px 16px;
            display: flex;
            justify-content: space-around;
            align-items: center;
            z-index: 999;
            height: 70px;
        }}
        .nav-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: {text_secondary};
            font-size: 12px;
            transition: color 0.2s;
            cursor: pointer;
            padding: 8px 16px;
            border-radius: 40px;
            background-color: transparent;
            border: none;
        }}
        .nav-item.active {{
            color: {accent_color};
            background-color: {accent_color}20;
            font-weight: 500;
        }}
        .nav-item i {{
            font-size: 22px;
            margin-bottom: 4px;
        }}

        /* 表格样式优化 */
        .stDataFrame {{
            border: none !important;
        }}
        .stDataFrame thead tr th {{
            background-color: {card_bg} !important;
            color: {text_primary} !important;
            border-bottom: 1px solid {border_color} !important;
        }}
        .stDataFrame tbody tr td {{
            background-color: {card_bg} !important;
            color: {text_primary} !important;
            border-bottom: 1px solid {border_color} !important;
        }}

        /* 按钮样式 */
        .stButton > button {{
            background-color: {accent_color};
            color: white;
            border: none;
            border-radius: 40px;
            padding: 10px 20px;
            font-weight: 600;
            transition: all 0.2s;
        }}
        .stButton > button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(255, 125, 67, 0.3);
        }}

        /* 标题 */
        h1, h2, h3 {{
            color: {text_primary} !important;
        }}
        p, span, div {{
            color: {text_primary};
        }}

        /* 选择框 */
        .stSelectbox > div > div {{
            background-color: {card_bg} !important;
            border-color: {border_color} !important;
            color: {text_primary} !important;
        }}
    </style>
    """, unsafe_allow_html=True)


def metric_card(label, value, delta=None, delta_positive=True):
    """渲染一个自定义的指标卡片。"""
    delta_html = ""
    if delta:
        color_class = "metric-delta-positive" if delta_positive else "metric-delta-negative"
        delta_html = f'<span class="{color_class}">▲ {delta}</span>' if delta_positive else f'<span class="{color_class}">▼ {delta}</span>'

    st.markdown(f"""
    <div class="custom-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def bottom_navigation():
    """渲染底部导航栏，并处理页面切换逻辑。"""
    if "current_page" not in st.session_state:
        st.session_state.current_page = "市场分析"

    pages = ["市场分析", "自选持仓", "寻找机会", "设置"]

    # 创建导航栏 HTML
    nav_html = '<div class="bottom-nav">'
    for page in pages:
        active_class = "active" if st.session_state.current_page == page else ""
        nav_html += f'''
        <div class="nav-item {active_class}" id="nav-{page}">
            <i class="material-icons">{get_icon(page)}</i>
            <span>{page}</span>
        </div>
        '''
    nav_html += '</div>'

    st.markdown(nav_html, unsafe_allow_html=True)

    # JavaScript 处理点击切换（简化版：通过隐藏的 Streamlit 按钮实现）
    # 为了代码简洁，这里我们用一个更简单的方法：在页面顶部用 st.radio 水平显示（并隐藏它），通过 session_state 同步。
    # 但为了视觉完美，我们通过 columns 隐藏按钮来模拟点击。
    cols = st.columns(len(pages))
    for i, page in enumerate(pages):
        with cols[i]:
            if st.button(page, key=f"nav_{page}", use_container_width=True):
                st.session_state.current_page = page
                st.rerun()


def get_icon(page_name):
    icons = {
        "市场分析": "📊",
        "自选持仓": "📈",
        "寻找机会": "🔍",
        "设置": "⚙️"
    }
    return icons.get(page_name, "📄")


def display_market_analysis(market_info, final_style, params):
    """市场分析页面内容。"""
    st.header("市场环境评估")

    # 主要指标卡片
    col1, col2, col3 = st.columns(3)
    with col1:
        metric_card("估值分位", f"{market_info['valuation_level']:.1f}%",
                    delta="偏高" if market_info['valuation_level'] > 70 else "正常", delta_positive=False)
    with col2:
        metric_card("VIX 分位", f"{market_info['vix_level']:.1f}%",
                    delta="恐慌" if market_info['vix_level'] > 70 else "冷静")
    with col3:
        metric_card("成交热度", f"{market_info['turnover_avg']:.1f}万亿")

    # 策略风格与参数
    st.subheader("策略风格")
    col1, col2 = st.columns(2)
    with col1:
        metric_card("当前风格", final_style)
    with col2:
        metric_card("更新时间", market_info['timestamp'][:10])

    st.subheader("当前参数")
    with st.expander("查看详情"):
        st.write(f"量比阈值: >{params['vol_ratio']}倍")
        st.write(f"波动率上限: <{params['atr_max']}%")
        st.write(f"试探仓: {params['test_ratio'] * 100:.0f}%")
        st.write(f"主升仓: {params['main_ratio'] * 100:.0f}%")