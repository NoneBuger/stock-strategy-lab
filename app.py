"""Interactive Streamlit dashboard with TradingView Lightweight Charts."""

import re

import pandas as pd
import streamlit as st
from lightweight_charts_v5 import lightweight_charts_v5_component

from data_fetcher import fetch_stock_data
from indicators import calculate_rsi, calculate_sma


st.set_page_config(page_title="股票行情分析", page_icon="📈", layout="wide")
st.title("股票行情分析")

stock_code = st.text_input(
    "股票代码",
    value="000001",
    max_chars=6,
    help="请输入6位A股股票代码，例如 000001。",
).strip()

if not re.fullmatch(r"\d{6}", stock_code):
    st.warning("请输入有效的6位股票代码。")
    st.stop()

with st.sidebar:
    st.header("图表参数")
    short_window = st.slider("短期均线周期", min_value=2, max_value=120, value=20)
    long_window = st.slider("长期均线周期", min_value=5, max_value=250, value=60)
    if short_window >= long_window:
        st.error("长期均线周期必须大于短期均线周期。")
        st.stop()

    st.subheader("MACD")
    macd_fast = st.slider("快速EMA", 2, 50, 12)
    macd_slow = st.slider("慢速EMA", 5, 100, 26)
    macd_signal_period = st.slider("信号线EMA", 2, 30, 9)
    if macd_fast >= macd_slow:
        st.error("MACD慢速EMA必须大于快速EMA。")
        st.stop()

    st.subheader("RSI")
    rsi_period = st.slider("RSI周期", 2, 50, 14)


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
