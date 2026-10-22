"""Centralized strategy model and parameter configuration page."""

import streamlit as st

from navigation import render_navigation, render_top_navigation
from strategy_config import STRATEGY_NAMES, get_strategy_config


st.set_page_config(page_title="策略模型配置", page_icon="⚙️", layout="wide")
render_top_navigation()
st.markdown("""
<style>
@media (max-width: 768px) {
  h1 {font-size: 1.6rem !important;} [data-testid="stHeader"] {display:none;}
  .block-container {padding: 1rem .7rem 2rem .7rem;}
}
</style>
""", unsafe_allow_html=True)
render_navigation("策略模型配置")

st.title("⚙️ 策略模型与参数配置")
st.caption("这里调整的参数会同步到 AI 智能分析页面当前会话。")

selected_strategy = st.selectbox("选择策略模型", STRATEGY_NAMES, key="config_strategy_model")
config = get_strategy_config(selected_strategy)
st.markdown(f"**适用周期：** {config['suitable_period']}  \n{config['description']}")

short_label = "EMA快线" if selected_strategy in {"短线动量", "超跌反弹"} else "SMA快线"
long_label = "EMA慢线" if selected_strategy in {"短线动量", "超跌反弹"} else "SMA慢线"
with st.form(f"strategy_config_form_{selected_strategy}"):
    col1, col2 = st.columns(2)
    with col1:
        short_window = st.slider(short_label, 2, 120, config["short_window"], key=f"ai_short_{selected_strategy}")
        long_window = st.slider(long_label, 5, 250, config["long_window"], key=f"ai_long_{selected_strategy}")
        rsi_period = st.slider("RSI周期", 2, 50, config["rsi_period"], key=f"ai_rsi_{selected_strategy}")
    with col2:
        macd_fast = st.slider("MACD快速EMA", 2, 50, config["macd_fast"], key=f"ai_macd_fast_{selected_strategy}")
        macd_slow = st.slider("MACD慢速EMA", 5, 100, config["macd_slow"], key=f"ai_macd_slow_{selected_strategy}")
        macd_signal = st.slider("MACD信号线EMA", 2, 30, config["macd_signal_period"], key=f"ai_macd_signal_{selected_strategy}")
    submitted = st.form_submit_button("保存当前模型参数", type="primary", use_container_width=True)

if short_window >= long_window:
    st.error("短期均线周期必须小于长期均线周期。")
elif macd_fast >= macd_slow:
    st.error("MACD快速EMA必须小于慢速EMA。")
elif submitted:
    st.session_state[f"strategy_saved_{selected_strategy}"] = True
    st.success("参数已保存，打开 AI 智能分析即可使用。")

st.divider()
st.subheader("模型规则与风控摘要")
st.markdown(
    f"- **均线：** {short_window}/{long_window}\n"
    f"- **RSI：** {rsi_period}\n"
    f"- **MACD：** {macd_fast}/{macd_slow}/{macd_signal}\n"
    f"- **止损参考：** {config['stop_loss_pct']:.0%}\n"
    f"- **止盈参考：** {config['take_profit_pct']:.0%}"
)
