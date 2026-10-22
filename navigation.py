"""Consistent top-level navigation for the Streamlit multipage app."""

import streamlit as st


PAGES = {
    "股票行情": "app.py",
    "基金与指数": "pages/fund_index_page.py",
    "AI智能分析": "pages/ai_analysis_page.py",
    "策略模型配置": "pages/strategy_config_page.py",
}


def render_navigation(current_page: str) -> None:
    """Render a compact, discoverable page switcher in the sidebar."""
    with st.sidebar:
        st.markdown("### 🧭 功能导航")
        selected = st.radio(
            "选择功能页面", list(PAGES), index=list(PAGES).index(current_page),
            key=f"global_navigation_{current_page}", label_visibility="collapsed",
        )
        if selected != current_page:
            st.switch_page(PAGES[selected])
        st.divider()
