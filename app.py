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
st.markdown(
    """
    <style>
    @media (max-width: 768px) {
        h1 { font-size: 1.65rem !important; }
        h2 { font-size: 1.3rem !important; }
        h3 { font-size: 1.1rem !important; }
        [data-testid="stHeader"] { display: none; }
        [data-testid="stDataFrame"] { overflow-x: auto !important; }
        [data-testid="stDataFrame"] > div { min-width: 720px; }
        .block-container { padding: 1rem 0.7rem 2rem 0.7rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("股票行情分析")
st.sidebar.page_link("pages/ai_analysis_page.py", label="AI智能分析", icon="🤖")
st.page_link("pages/ai_analysis_page.py", label="打开 AI 智能分析", icon="🤖")


with st.sidebar:
    st.header("图表参数")
    st.markdown("模型建议将同时展示六种内置策略；以下参数用于行情图表。")
    short_window = st.slider("短期均线周期", min_value=2, max_value=120, value=20, key="chart_short_window")
    long_window = st.slider("长期均线周期", min_value=5, max_value=250, value=60, key="chart_long_window")
    if short_window >= long_window:
        st.markdown("> **参数错误：** 长期均线周期必须大于短期均线周期。")
        st.stop()

    st.subheader("MACD")
    macd_fast = st.slider("快速EMA", 2, 50, 12, key="chart_macd_fast")
    macd_slow = st.slider("慢速EMA", 5, 100, 26, key="chart_macd_slow")
    macd_signal_period = st.slider("信号线EMA", 2, 30, 9, key="chart_macd_signal")
    if macd_fast >= macd_slow:
        st.markdown("> **参数错误：** MACD慢速EMA必须大于快速EMA。")
        st.stop()

    st.subheader("RSI")
    rsi_period = st.slider("RSI周期", 2, 50, 14, key="chart_rsi_period")


@st.cache_data(ttl=3600, show_spinner=False)
def search_candidates(query: str) -> list[dict[str, str]]:
    return search_stock_candidates(query)

stock_query = st.text_input(
    "股票名称或代码",
    value="000001",
    help="支持输入六位代码或股票名称，例如 000001、平安银行。",
).strip()

if not stock_query:
    st.markdown("> 请输入股票名称或代码开始搜索。")
    st.stop()

with st.spinner("正在搜索股票..."):
    stock_candidates = search_candidates(stock_query)
if not stock_candidates:
    st.markdown("> 没有找到匹配股票，请检查名称或代码。")
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


@st.cache_data(ttl=3600, show_spinner=False)
def load_stock_data(symbol: str) -> pd.DataFrame:
    return fetch_stock_data(symbol)


try:
    with st.spinner(f"正在加载 {stock_code} 的历史数据..."):
        data = load_stock_data(stock_code).copy()
except Exception as error:
    st.markdown(f"> **获取股票数据失败：** `{error}`")
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

recommendations: dict[str, dict] = {}
recommendation_errors: dict[str, str] = {}
for model_name in STRATEGY_NAMES:
    model = get_strategy_config(model_name)
    try:
        recommendations[model_name] = build_recommendation(
            data,
            short_window=model["short_window"],
            long_window=model["long_window"],
            rsi_period=model["rsi_period"],
            macd_fast=model["macd_fast"],
            macd_slow=model["macd_slow"],
            macd_signal_period=model["macd_signal_period"],
            strategy_name=model_name,
            strategy_config=model,
        )
    except ValueError as error:
        recommendation_errors[model_name] = str(error)

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

st.divider()
st.subheader("📌 六模型投资建议参考")
st.markdown(
    f"数据日期：{max(item['date'] for item in recommendations.values()) if recommendations else '未知'}；"
    f"数据源：{data.attrs.get('data_source', '未知')}。以下结果由本地规则计算，不依赖 AI。"
)
model_tabs = st.tabs(list(STRATEGY_NAMES))
for model_tab, model_name in zip(model_tabs, STRATEGY_NAMES):
    with model_tab:
        model = get_strategy_config(model_name)
        st.markdown(
            f"**适用周期：** {model['suitable_period']}  \n"
            f"**参数：** 均线 {model['short_window']}/{model['long_window']}，"
            f"RSI {model['rsi_period']}，MACD {model['macd_fast']}/{model['macd_slow']}/{model['macd_signal_period']}"
        )
        recommendation = recommendations.get(model_name)
        if recommendation is None:
            st.error(f"{model_name} 暂时无法计算：{recommendation_errors.get(model_name, '数据不足')}")
            continue
        signal_message = f"当前信号：{recommendation['signal']}（评分 {recommendation['score']}/100）"
        if recommendation["signal"] == "买入候选":
            st.success(signal_message)
        elif recommendation["signal"] == "卖出/规避":
            st.error(signal_message)
        else:
            st.warning(signal_message)
        st.markdown(
            f"- 最新收盘：**{recommendation['price']:.2f}**\n"
            f"- 短期均线：**{recommendation['sma_short']:.2f}**\n"
            f"- 长期均线：**{recommendation['sma_long']:.2f}**\n"
            f"- RSI：**{recommendation['rsi']:.1f}**\n"
            f"- MACD柱：**{recommendation['macd_hist']:.4f}**\n"
            f"- 操作建议：**{recommendation['action']}**\n"
            f"- 触发依据：{'；'.join(recommendation['reasons'])}"
        )
        if recommendation["signal"] == "买入候选":
            st.markdown(
                f"**参考成交价：** {recommendation['entry']:.2f}　"
                f"**止损：** {recommendation['stop']:.2f}　"
                f"**止盈：** {recommendation['target']:.2f}"
            )
        elif recommendation.get("watch_price") is not None:
            st.markdown(f"**观察/回踩参考价：** {recommendation['watch_price']:.2f}（不是建仓指令）")
        st.markdown(
            f"> **风控：** 止损参考 {model['stop_loss_pct']:.0%}，"
            f"目标收益参考 {model['take_profit_pct']:.0%}；仅供研究，不构成投资建议。"
        )
