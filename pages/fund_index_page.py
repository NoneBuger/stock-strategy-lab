"""Fund and index analysis page."""

import plotly.graph_objects as go
import streamlit as st

from asset_fetcher import (
    fetch_fund_data,
    fetch_index_data,
    search_fund_candidates,
    search_index_candidates,
)
from fund_recommendation import build_fund_index_recommendation
from navigation import render_navigation


st.set_page_config(page_title="基金与指数分析", page_icon="📊", layout="wide")
st.markdown("""
<style>
@media (max-width: 768px) {
  h1 {font-size: 1.6rem !important;} [data-testid="stHeader"] {display:none;}
  .block-container {padding: 1rem .7rem 2rem .7rem;}
}
</style>
""", unsafe_allow_html=True)
render_navigation("基金与指数")

st.title("基金与指数分析")
st.caption("基于公开行情数据的趋势、风险和分批建仓参考；不构成投资建议。")

asset_type = st.sidebar.selectbox("资产类型", ["基金", "指数"])
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
    recommendation = build_fund_index_recommendation(data, asset_type)
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
    cols = st.columns(5)
    for col, label, value in zip(
        cols,
        ["最新价/净值", "SMA20", "SMA60", "RSI(14)", "年化波动率"],
        [recommendation["price"], recommendation["sma20"], recommendation["sma60"],
         recommendation["rsi"], recommendation["volatility"]],
    ):
        col.metric(label, f"{value:.2f}" if label != "年化波动率" else f"{value:.1%}")
    st.markdown(
        f"- **建仓参考：** `{recommendation['entry']:.3f}`（建议分2～3次，不追涨）\n"
        f"- **止损参考：** `{recommendation['stop']:.3f}`\n"
        f"- **止盈参考：** `{recommendation['target']:.3f}`\n"
        f"- **近60日回撤：** `{recommendation['drawdown']:.1%}`\n"
        f"- **触发依据：** {'；'.join(recommendation['reasons'])}"
    )
    st.info("基金净值申购通常存在未知净值、申购费和确认日；指数本身不能直接买卖，实际操作应选择对应ETF或指数基金。")

with metric_tabs[1]:
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=data["日期"], y=data["收盘"], name="收盘/净值"))
    figure.add_trace(go.Scatter(x=data["日期"], y=data["收盘"].rolling(20).mean(), name="SMA20"))
    figure.add_trace(go.Scatter(x=data["日期"], y=data["收盘"].rolling(60).mean(), name="SMA60"))
    figure.update_layout(height=520, margin=dict(l=10, r=10, t=30, b=10), hovermode="x unified")
    st.plotly_chart(figure, use_container_width=True)

with metric_tabs[2]:
    st.markdown(f"**数据源：** `{data.attrs.get('data_source', '未知')}`")
    st.dataframe(data.sort_values("日期", ascending=False).head(60), use_container_width=True)
