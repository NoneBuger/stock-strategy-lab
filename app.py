"""Interactive Streamlit dashboard with TradingView Lightweight Charts."""

import pandas as pd
import streamlit as st
from lightweight_charts_v5 import lightweight_charts_v5_component

from data_fetcher import fetch_stock_data
from indicators import calculate_rsi, calculate_sma
from recommendation import build_recommendation
from stock_search import search_stock_candidates
from strategy_config import STRATEGY_NAMES, get_strategy_config


st.set_page_config(page_title="股票行情分析", page_icon="📈", layout="wide")
st.title("股票行情分析")
st.sidebar.page_link("pages/ai_analysis_page.py", label="AI智能分析", icon="🤖")


@st.cache_data(ttl=3600, show_spinner=False)
def search_candidates(query: str) -> list[dict[str, str]]:
    return search_stock_candidates(query)

stock_query = st.text_input(
    "股票名称或代码",
    value="000001",
    help="支持输入六位代码或股票名称，例如 000001、平安银行。",
).strip()

if not stock_query:
    st.info("请输入股票名称或代码开始搜索。")
    st.stop()

with st.spinner("正在搜索股票..."):
    stock_candidates = search_candidates(stock_query)
if not stock_candidates:
    st.warning("没有找到匹配股票，请检查名称或代码。")
    st.stop()

if len(stock_candidates) > 1:
    selected_stock = st.selectbox(
        "匹配到多只股票，请选择",
        stock_candidates,
        format_func=lambda item: f"{item['code']} - {item['name']}",
    )
else:
    selected_stock = stock_candidates[0]
    st.caption(f"已匹配：{selected_stock['code']} - {selected_stock['name']}")

stock_code = selected_stock["code"]

with st.sidebar:
    st.header("图表参数")
    selected_model_name = st.selectbox("策略模型", STRATEGY_NAMES, key="strategy_model")
    selected_model = get_strategy_config(selected_model_name)
    st.caption(f"适用周期：{selected_model['suitable_period']}\n\n{selected_model['description']}")
    short_window = st.slider("短期均线周期", min_value=2, max_value=120,
                             value=selected_model["short_window"],
                             key=f"short_window_{selected_model_name}")
    long_window = st.slider("长期均线周期", min_value=5, max_value=250,
                            value=selected_model["long_window"],
                            key=f"long_window_{selected_model_name}")
    if short_window >= long_window:
        st.error("长期均线周期必须大于短期均线周期。")
        st.stop()

    st.subheader("MACD")
    macd_fast = st.slider("快速EMA", 2, 50, selected_model["macd_fast"], key=f"macd_fast_{selected_model_name}")
    macd_slow = st.slider("慢速EMA", 5, 100, selected_model["macd_slow"], key=f"macd_slow_{selected_model_name}")
    macd_signal_period = st.slider("信号线EMA", 2, 30, selected_model["macd_signal_period"], key=f"macd_signal_{selected_model_name}")
    if macd_fast >= macd_slow:
        st.error("MACD慢速EMA必须大于快速EMA。")
        st.stop()

    st.subheader("RSI")
    rsi_period = st.slider("RSI周期", 2, 50, selected_model["rsi_period"], key=f"rsi_period_{selected_model_name}")


@st.cache_data(ttl=3600, show_spinner=False)
def load_stock_data(symbol: str) -> pd.DataFrame:
    return fetch_stock_data(symbol)


try:
    with st.spinner(f"正在加载 {stock_code} 的历史数据..."):
        data = load_stock_data(stock_code).copy()
except Exception as error:
    st.error(f"获取股票数据失败：{error}")
    st.stop()


def _series_records(frame: pd.DataFrame, value_column: str) -> list[dict]:
    """Convert a date/value series to JSON-safe Lightweight Charts records."""
    records = frame[["日期", value_column]].dropna().copy()
    records["日期"] = pd.to_datetime(records["日期"]).dt.strftime("%Y-%m-%d")
    records[value_column] = pd.to_numeric(records[value_column], errors="coerce")
    records = records.dropna()
    return [
        {"time": row["日期"], "value": float(row[value_column])}
        for _, row in records.iterrows()
    ]


def _zero_line(dates: pd.Series) -> list[dict]:
    return [
        {"time": date, "value": 0.0}
        for date in pd.to_datetime(dates).dt.strftime("%Y-%m-%d")
    ]


data["短期均线"] = calculate_sma(data, window=short_window)
data["长期均线"] = calculate_sma(data, window=long_window)
close = pd.to_numeric(data["收盘"], errors="coerce")
data["EMA快速"] = close.ewm(span=macd_fast, adjust=False).mean()
data["EMA慢速"] = close.ewm(span=macd_slow, adjust=False).mean()
data["MACD"] = data["EMA快速"] - data["EMA慢速"]
data["MACD信号"] = data["MACD"].ewm(span=macd_signal_period, adjust=False).mean()
data["MACD柱"] = data["MACD"] - data["MACD信号"]
data["RSI"] = calculate_rsi(data, period=rsi_period)

try:
    recommendation = build_recommendation(
        data,
        short_window=short_window,
        long_window=long_window,
        rsi_period=rsi_period,
        macd_fast=macd_fast,
        macd_slow=macd_slow,
        macd_signal_period=macd_signal_period,
    )
except ValueError as error:
    st.warning(f"暂时无法生成投资建议：{error}")
    recommendation = None

price_records = []
for _, row in data.iterrows():
    values = [row[column] for column in ["开盘", "最高", "最低", "收盘"]]
    if any(pd.isna(value) for value in values):
        continue
    price_records.append(
        {
            "time": pd.to_datetime(row["日期"]).strftime("%Y-%m-%d"),
            "open": float(row["开盘"]),
            "high": float(row["最高"]),
            "low": float(row["最低"]),
            "close": float(row["收盘"]),
        }
    )

dates = data["日期"]
chart_theme = {
    "layout": {"background": {"color": "#111827"}, "textColor": "#D1D5DB"},
    "grid": {
        "vertLines": {"color": "#1F2937"},
        "horzLines": {"color": "#1F2937"},
    },
    "crosshair": {"mode": 1},
    "timeScale": {"borderColor": "#374151"},
}

charts = [
    {
        "chart": {**chart_theme, "height": 460},
        "series": [
            {
                "type": "Candlestick",
                "data": price_records,
                "options": {
                    "upColor": "#26a69a",
                    "downColor": "#ef5350",
                    "borderVisible": False,
                    "wickUpColor": "#26a69a",
                    "wickDownColor": "#ef5350",
                },
            },
            {
                "type": "Line",
                "data": _series_records(data, "短期均线"),
                "options": {"color": "#f59e0b", "lineWidth": 2},
                "label": f"SMA {short_window}",
            },
            {
                "type": "Line",
                "data": _series_records(data, "长期均线"),
                "options": {"color": "#60a5fa", "lineWidth": 2},
                "label": f"SMA {long_window}",
            },
        ],
        "height": 460,
        "title": f"{stock_code} 价格与均线",
    },
    {
        "chart": {**chart_theme, "timeScale": {"visible": False}},
        "series": [
            {
                "type": "Histogram",
                "data": [
                    {
                        "time": pd.to_datetime(row["日期"]).strftime("%Y-%m-%d"),
                        "value": float(row["成交量"]),
                        "color": "#26a69a" if row["收盘"] >= row["开盘"] else "#ef5350",
                    }
                    for _, row in data.dropna(subset=["成交量"]).iterrows()
                ],
                "options": {"priceFormat": {"type": "volume"}},
            }
        ],
        "height": 120,
        "title": "成交量",
    },
    {
        "chart": {**chart_theme, "timeScale": {"visible": False}},
        "series": [
            {
                "type": "Histogram",
                "data": [
                    {
                        **record,
                        "color": "#26a69a" if record["value"] >= 0 else "#ef5350",
                    }
                    for record in _series_records(data, "MACD柱")
                ],
                "options": {"priceLineVisible": False},
            },
            {
                "type": "Line",
                "data": _series_records(data, "MACD信号"),
                "options": {"color": "#f59e0b", "lineWidth": 1},
                "label": "Signal",
            },
            {
                "type": "Line",
                "data": _series_records(data, "MACD"),
                "options": {"color": "#60a5fa", "lineWidth": 1},
                "label": "MACD",
            },
            {
                "type": "Line",
                "data": _zero_line(dates),
                "options": {"color": "#6B7280", "lineWidth": 1},
            },
        ],
        "height": 150,
        "title": f"MACD({macd_fast},{macd_slow},{macd_signal_period})",
    },
    {
        "chart": {**chart_theme, "timeScale": {"visible": True}},
        "series": [
            {
                "type": "Line",
                "data": _series_records(data, "RSI"),
                "options": {"color": "#a78bfa", "lineWidth": 2},
                "label": f"RSI({rsi_period})",
            },
            {
                "type": "Line",
                "data": [{"time": date, "value": 70.0} for date in pd.to_datetime(dates).dt.strftime("%Y-%m-%d")],
                "options": {"color": "#ef5350", "lineWidth": 1, "lineStyle": 2},
            },
            {
                "type": "Line",
                "data": [{"time": date, "value": 30.0} for date in pd.to_datetime(dates).dt.strftime("%Y-%m-%d")],
                "options": {"color": "#26a69a", "lineWidth": 1, "lineStyle": 2},
            },
        ],
        "height": 150,
        "title": f"RSI({rsi_period})",
    },
]

st.subheader(f"{stock_code} 近一年日线行情")
lightweight_charts_v5_component(
    name=f"stock-{stock_code}",
    charts=charts,
    height=sum(chart["height"] for chart in charts),
    zoom_level=180,
    key=f"chart-{stock_code}-{short_window}-{long_window}-{macd_fast}-{macd_slow}-{rsi_period}",
)

st.dataframe(data.tail(20), use_container_width=True)

if recommendation:
    st.divider()
    st.subheader("📌 规则型投资建议")
    st.caption(
        f"数据日期：{recommendation['date']}；数据源：{data.attrs.get('data_source', '未知')}。"
        "建议由当前页面的均线、MACD、RSI参数计算，不依赖AI。"
    )
    signal_message = f"当前信号：{recommendation['signal']}（评分 {recommendation['score']}/100）"
    if recommendation["signal"] == "买入候选":
        st.success(signal_message)
    elif recommendation["signal"] == "卖出/规避":
        st.error(signal_message)
    else:
        st.warning(signal_message)
    metric_cols = st.columns(5)
    for column, label, value, fmt in zip(
        metric_cols,
        ["最新收盘", f"SMA{short_window}", f"SMA{long_window}", f"RSI{rsi_period}", "MACD柱"],
        [recommendation["price"], recommendation["sma_short"], recommendation["sma_long"], recommendation["rsi"], recommendation["macd_hist"]],
        ["%.2f", "%.2f", "%.2f", "%.1f", "%.4f"],
    ):
        column.metric(label, fmt % value)
    st.write(f"**操作建议：** {recommendation['action']}")
    st.write("**触发依据：** " + "；".join(recommendation["reasons"]))
    plan_cols = st.columns(3)
    if recommendation["signal"] == "买入候选":
        plan_cols[0].metric("参考成交价", f"{recommendation['entry']:.2f}")
        plan_cols[1].metric("风险止损价", f"{recommendation['stop']:.2f}")
        plan_cols[2].metric("参考止盈价", f"{recommendation['target']:.2f}")
    else:
        plan_cols[0].metric("当前建仓价", "不适用")
        plan_cols[1].metric("风险止损价", "等待建仓")
        plan_cols[2].metric("参考止盈价", "等待建仓")
        # ``get`` keeps the UI compatible with cached results generated by an
        # older recommendation module that did not expose watch_price.
        watch_price = recommendation.get("watch_price")
        if watch_price is not None:
            st.caption(
                f"观察/回踩参考价：{watch_price:.2f}（不是当前成交价，也不是建仓指令）"
            )
    st.info("建仓建议：若出现“买入候选”，先投入计划资金30%；回踩SMA短期均线并企稳再加30%；放量突破前高再考虑剩余40%。若不是买入候选，不主动追涨。")
    st.caption("模型按日线收盘价生成信号，未把手续费、滑点和涨跌停排队纳入报价；实际成交成本可能不同，不构成个性化投资建议。")
