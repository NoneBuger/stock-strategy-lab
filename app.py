"""Streamlit dashboard for stock prices and moving averages."""

import re

import plotly.graph_objects as go
import streamlit as st

from data_fetcher import fetch_stock_data
from indicators import calculate_sma


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


@st.cache_data(ttl=3600, show_spinner=False)
def load_stock_data(symbol: str):
    return fetch_stock_data(symbol)


try:
    with st.spinner(f"正在加载 {stock_code} 的历史数据..."):
        data = load_stock_data(stock_code)
except Exception as error:
    st.error(f"获取股票数据失败：{error}")
    st.stop()


data = data.copy()
data["20日均线"] = calculate_sma(data, window=20)
data["60日均线"] = calculate_sma(data, window=60)

st.subheader(f"{stock_code} 近一年日线行情")

figure = go.Figure()
figure.add_trace(
    go.Candlestick(
        x=data["日期"],
        open=data["开盘"],
        high=data["最高"],
        low=data["最低"],
        close=data["收盘"],
        name="K线",
    )
)
figure.add_trace(
    go.Scatter(
        x=data["日期"],
        y=data["20日均线"],
        mode="lines",
        name="20日均线",
        line={"color": "orange", "width": 1.5},
    )
)
figure.add_trace(
    go.Scatter(
        x=data["日期"],
        y=data["60日均线"],
        mode="lines",
        name="60日均线",
        line={"color": "royalblue", "width": 1.5},
    )
)
figure.update_layout(
    height=650,
    hovermode="x unified",
    xaxis_title="日期",
    yaxis_title="价格",
    xaxis_rangeslider_visible=False,
)

st.plotly_chart(figure, use_container_width=True)
st.dataframe(data.tail(20), use_container_width=True)
