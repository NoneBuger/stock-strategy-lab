"""Streamlit page for the real Codex-backed AI stock-analysis workflow."""

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from run_analysis import run_codex_analysis

st.set_page_config(layout="wide", page_title="AI智能分析", page_icon="🤖")
st.markdown("""
<style>
.main { background-color: #0e1117; }
.st-emotion-cache-1y4p8pa { padding: 2rem 1rem; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_executor() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=1)


st.title("🤖 AI智能分析助手")
st.caption("基于多智能体辩论的深度股票分析")
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("分析设置")
    stock_code = st.text_input("股票代码", value="000001", max_chars=6, help="输入6位A股代码").strip()
    analysis_depth = st.select_slider("分析深度", options=["快速", "标准", "深度"], value="标准")
    with st.expander("高级选项"):
        enable_debate = st.checkbox("启用牛熊辩论", value=True)
        enable_risk = st.checkbox("启用风险评估", value=True)
        save_history = st.checkbox("保存历史记录", value=True)

with col2:
    st.subheader("操作")
    if st.button("🚀 开始AI分析", type="primary", use_container_width=True):
        if len(stock_code) != 6 or not stock_code.isdigit():
            st.error("请输入有效的6位A股股票代码。")
        elif st.session_state.get("analysis_future") is not None:
            st.warning("已有分析任务正在运行，请稍候。")
        else:
            st.session_state.stock_code = stock_code
            st.session_state.report = None
            st.session_state.analysis_future = get_executor().submit(
                run_codex_analysis, stock_code, analysis_depth, enable_debate, enable_risk, save_history
            )
            st.rerun()

future = st.session_state.get("analysis_future")
if future is not None:
    requested_code = st.session_state.get("stock_code", stock_code)
    if future.done():
        try:
            st.session_state.report = future.result()
        except Exception as exc:  # Defensive boundary for background tasks.
            st.session_state.report = f"## AI分析失败\n\n`{exc}`"
        del st.session_state.analysis_future
    else:
        st.info(f"AI投研团队正在分析 {requested_code}，请稍候。页面会自动刷新。")
        time.sleep(1)
        st.rerun()

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
