"""Fund and index analysis page."""

import plotly.graph_objects as go
import streamlit as st

from asset_fetcher import (
    fetch_fund_data,
    fetch_index_data,
    search_fund_candidates,
    search_index_candidates,
)
from fund_recommendation import FUND_STRATEGIES, build_fund_index_recommendation
from navigation import render_navigation, render_top_navigation


st.set_page_config(page_title="基金与指数分析", page_icon="📊", layout="wide")
requested_asset_type = st.session_state.pop("_asset_page_type", None)
current_page = "指数" if requested_asset_type == "指数" else "基金"
render_top_navigation()
st.markdown("""
<style>
@media (max-width: 768px) {
  h1 {font-size: 1.6rem !important;} [data-testid="stHeader"] {display:none;}
  .block-container {padding: 1rem .7rem 2rem .7rem;}
}
</style>
""", unsafe_allow_html=True)
render_navigation(current_page)

st.title("基金与指数分析")
st.caption("基于公开行情数据的趋势、风险和分批建仓参考；不构成投资建议。")

asset_type = st.sidebar.selectbox(
    "资产类型", ["基金", "指数"],
    index=1 if requested_asset_type == "指数" else 0,
)
strategy_name = st.sidebar.selectbox("投资模型", FUND_STRATEGIES, key=f"fund_strategy_{asset_type}")
strategy_overrides = st.session_state.get(f"fund_strategy_overrides_{strategy_name}", {})
with st.sidebar.expander("模型说明"):
    st.markdown(
        "- **长期稳健型：** 6/12个月动量、MA120、夏普和最大回撤。\n"
        "- **ETF趋势型：** MA20/MA60、3/6个月动量、RSI和ATR止损。\n"
        "- **指数定投型：** 根据回撤和MA60安排定投，不虚构PE/PB估值。"
    )
years = st.sidebar.slider("历史数据年数", 1, 10, 3)
query = st.text_input("搜索基金名称/代码或指数名称/代码", "沪深300" if asset_type == "指数" else "510300")

@st.cache_data(ttl=21600, show_spinner=False)
def cached_candidates(kind: str, text: str) -> list[dict[str, str]]:
    return search_fund_candidates(text) if kind == "基金" else search_index_candidates(text)


@st.cache_data(ttl=900, show_spinner=False)
def cached_asset_data(kind: str, code: str, history_years: int):
    return (fetch_fund_data(code, history_years) if kind == "基金"
            else fetch_index_data(code, history_years))


candidates = cached_candidates(asset_type, query)
if not candidates:
    st.warning("没有找到匹配项。基金搜索依赖 AkShare 基金列表；指数目前支持常用A股指数。")
    st.stop()
selected = st.selectbox(
    "选择标的", candidates, format_func=lambda item: f"{item['code']} - {item['name']}"
)

try:
    with st.spinner(f"正在加载 {selected['name']} 历史数据..."):
        data = cached_asset_data(asset_type, selected["code"], years)
    recommendation = build_fund_index_recommendation(
        data, asset_type, strategy_name, strategy_overrides
    )
except Exception as error:
    st.error(f"数据或指标计算失败：{error}")
    st.stop()

if recommendation["signal"] == "分批建仓候选":
    st.success(f"当前信号：{recommendation['signal']}｜{recommendation['action']}")
elif recommendation["signal"] == "暂不建仓":
    st.error(f"当前信号：{recommendation['signal']}｜{recommendation['action']}")
else:
    st.warning(f"当前信号：{recommendation['signal']}｜{recommendation['action']}")

metric_tabs = st.tabs(["投资建议", "行情图表", "数据明细"])
with metric_tabs[0]:
    st.markdown(f"**当前模型：** `{recommendation['strategy_name']}`")
    cols = st.columns(6)
    for col, label, value in zip(
        cols,
        ["最新价/净值", "年化收益", "年化波动", "夏普", "最大回撤", "近6月动量"],
        [recommendation["price"], recommendation["annualized_return"], recommendation["volatility"],
         recommendation["sharpe"], recommendation["drawdown"], recommendation["momentum_6m"]],
    ):
        if label in {"年化收益", "年化波动", "最大回撤", "近6月动量"}:
            display_value = f"{value:.1%}"
        else:
            display_value = f"{value:.2f}"
        col.metric(label, display_value)
    st.markdown(
        f"- **建议仓位：** `{recommendation['position']}`\n"
        f"- **第一批建仓：** `{recommendation['entry']:.3f}`\n"
        f"- **第二批建仓：** `{recommendation['second_entry']:.3f}`\n"
        f"- **止损参考：** `{recommendation['stop']:.3f}`\n"
        "- **止盈方式：** 趋势型模型不设固定止盈，跌破长期均线或趋势反转时退出\n"
        f"- **近一年回撤：** `{recommendation['drawdown_1y']:.1%}`\n"
        f"- **触发依据：** {'；'.join(recommendation['reasons'])}"
    )
    st.info(
        f"{recommendation['valuation_status']}。基金净值申购通常存在未知净值、申购费和确认日；"
        "指数本身不能直接买卖，实际操作应选择对应ETF或指数基金。"
    )

with metric_tabs[1]:
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=data["日期"], y=data["收盘"], name="收盘/净值"))
    figure.add_trace(go.Scatter(x=data["日期"], y=data["收盘"].rolling(20).mean(), name="SMA20"))
    figure.add_trace(go.Scatter(x=data["日期"], y=data["收盘"].rolling(60).mean(), name="SMA60"))
    figure.add_trace(go.Scatter(x=data["日期"], y=data["收盘"].rolling(120).mean(), name="SMA120"))
    figure.update_layout(height=520, margin=dict(l=10, r=10, t=30, b=10), hovermode="x unified")
    st.plotly_chart(figure, use_container_width=True)

with metric_tabs[2]:
    st.markdown(f"**数据源：** `{data.attrs.get('data_source', '未知')}`")
    st.dataframe(data.sort_values("日期", ascending=False).head(60), use_container_width=True)
