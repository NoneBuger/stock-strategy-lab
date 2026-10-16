"""Streamlit page for the AI stock-analysis workflow."""

import time

import streamlit as st


st.set_page_config(layout="wide", page_title="AI智能分析", page_icon="🤖")

st.markdown(
    """
    <style>
    .main { background-color: #0e1117; }
    .st-emotion-cache-1y4p8pa { padding: 2rem 1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🤖 AI智能分析助手")
st.caption("基于多智能体辩论的深度股票分析")

st.sidebar.page_link("app.py", label="行情分析", icon="📈")
st.sidebar.page_link("ai_analysis_page.py", label="AI智能分析", icon="🤖")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("分析设置")
    stock_code = st.text_input(
        "股票代码",
        value="000001",
        max_chars=6,
        help="输入6位A股代码",
    ).strip()
    analysis_depth = st.select_slider(
        "分析深度",
        options=["快速", "标准", "深度"],
        value="标准",
    )
    with st.expander("高级选项"):
        enable_debate = st.checkbox("启用牛熊辩论", value=True)
        enable_risk = st.checkbox("启用风险评估", value=True)
        save_history = st.checkbox("保存历史记录", value=True)

with col2:
    st.subheader("操作")
    if st.button("🚀 开始AI分析", type="primary", use_container_width=True):
        if len(stock_code) != 6 or not stock_code.isdigit():
            st.error("请输入有效的6位A股股票代码。")
        else:
            st.session_state.analysis_requested = True
            st.session_state.stock_code = stock_code
            st.session_state.analysis_options = {
                "depth": analysis_depth,
                "debate": enable_debate,
                "risk": enable_risk,
                "save_history": save_history,
            }


if st.session_state.get("analysis_requested"):
    requested_code = st.session_state.get("stock_code", stock_code)
    options = st.session_state.get("analysis_options", {})
    with st.spinner(f"AI投研团队正在分析 {requested_code}... 这可能需要1-2分钟"):
        # TODO: Replace this demo output with the Codex-native skill runner.
        time.sleep(1)
        debate_text = (
            "- **多头观点**：需要结合最新财报、行业景气度和资金数据进一步确认。\n"
            "- **空头观点**：市场波动、估值变化和行业政策可能带来回撤。"
            if options.get("debate", True)
            else "- 牛熊辩论未启用。"
        )
        risk_text = (
            "- 市场系统性风险\n- 行业政策变化\n- 财务数据与市场预期偏差"
            if options.get("risk", True)
            else "- 风险评估未启用。"
        )
        st.session_state.report = f"""## {requested_code} AI分析报告

**分析深度**：{options.get("depth", "标准")}

### 投资评级

**Hold（待进一步确认）**

### 多空辩论摘要

{debate_text}

### 风险提示

{risk_text}

> 本页面当前展示的是交互流程示例，不构成投资建议。接入真实数据和AI技能后，应在报告中标注数据时间与来源。
"""
        st.session_state.analysis_requested = False


if st.session_state.get("report"):
    st.divider()
    st.subheader("📊 分析报告")
    st.markdown(st.session_state.report)
    st.download_button(
        label="📥 下载报告",
        data=st.session_state.report,
        file_name=f"{st.session_state.get('stock_code', 'stock')}_AI分析报告.md",
        mime="text/markdown",
    )
