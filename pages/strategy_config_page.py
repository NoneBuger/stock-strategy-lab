"""Centralized strategy model and parameter configuration page."""

import streamlit as st

from navigation import render_navigation, render_top_navigation
from fund_recommendation import FUND_STRATEGIES, FUND_STRATEGY_DEFAULTS
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
st.caption("股票参数同步到 AI 智能分析；基金/ETF参数同步到基金与指数页面当前会话。")

configuration_type = st.radio("配置类型", ["股票模型", "基金/ETF模型"], horizontal=True)
if configuration_type == "基金/ETF模型":
    selected_fund_strategy = st.selectbox("选择基金/ETF模型", FUND_STRATEGIES)
    defaults = FUND_STRATEGY_DEFAULTS[selected_fund_strategy]
    saved = st.session_state.get(f"fund_strategy_overrides_{selected_fund_strategy}", {})
    values = {**defaults, **saved}
    st.markdown(
        "基金模型使用风险调整收益和趋势指标，不把价格历史冒充PE/PB估值。"
    )
    with st.form(f"fund_strategy_config_form_{selected_fund_strategy}"):
        if selected_fund_strategy == "长期稳健型":
            trend_window = st.slider("长期趋势均线", 60, 250, int(values["trend_window"]))
            sharpe_min = st.slider("最低夏普比率", -1.0, 2.0, float(values["sharpe_min"]), 0.1)
            max_drawdown_limit = st.slider("最大回撤上限", 0.10, 0.60, float(values["max_drawdown_limit"]), 0.05)
            fund_overrides = {"trend_window": trend_window, "sharpe_min": sharpe_min, "max_drawdown_limit": max_drawdown_limit}
        elif selected_fund_strategy == "ETF趋势型":
            fast_window = st.slider("ETF快均线", 5, 60, int(values["fast_window"]))
            slow_window = st.slider("ETF慢均线", 20, 200, int(values["slow_window"]))
            rsi_max = st.slider("RSI上限", 60, 90, int(values["rsi_max"]))
            atr_stop_multiple = st.slider("ATR止损倍数", 1.0, 4.0, float(values["atr_stop_multiple"]), 0.5)
            fund_overrides = {"fast_window": fast_window, "slow_window": slow_window, "rsi_max": rsi_max, "atr_stop_multiple": atr_stop_multiple}
        else:
            trend_window = st.slider("定投趋势均线", 20, 120, int(values["trend_window"]))
            drawdown_trigger = st.slider("回撤加大定投阈值", 0.05, 0.50, float(values["drawdown_trigger"]), 0.05)
            momentum_window = st.slider("动量观察月数", 3, 24, int(values["momentum_window"]))
            fund_overrides = {"trend_window": trend_window, "drawdown_trigger": drawdown_trigger, "momentum_window": momentum_window}
        fund_submitted = st.form_submit_button("保存基金/ETF模型参数", type="primary", use_container_width=True)
    if fund_submitted:
        st.session_state[f"fund_strategy_overrides_{selected_fund_strategy}"] = fund_overrides
        st.success("基金/ETF模型参数已保存，返回基金或指数页面即可生效。")
    st.markdown("- **估值说明：** 当前未接入PE/PB历史分位数，指数定投模型不会输出虚假的估值结论。")
    st.stop()

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
