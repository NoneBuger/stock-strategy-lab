"""Streamlit page for the real Codex-backed AI stock-analysis workflow."""

import sys
import time
import json
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from run_analysis import run_codex_analysis
from data_fetcher import fetch_stock_data
from indicators import calculate_rsi
from stock_search import search_stock_candidates
from strategy_config import STRATEGY_NAMES, get_strategy_config

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


@st.cache_data(ttl=3600, show_spinner=False)
def search_candidates(query: str) -> list[dict[str, str]]:
    return search_stock_candidates(query)


@st.cache_data(ttl=3600, show_spinner=False)
def load_local_analysis_data(symbol: str) -> pd.DataFrame:
    return fetch_stock_data(symbol)


def calculate_local_strategy_check(data: pd.DataFrame, strategy_name: str) -> dict:
    """Calculate a transparent local buy-condition check before AI analysis."""
    config = get_strategy_config(strategy_name)
    close = pd.to_numeric(data["收盘"], errors="coerce")
    volume = pd.to_numeric(data["成交量"], errors="coerce")
    use_ema = strategy_name in {"短线动量", "超跌反弹"}
    if use_ema:
        short = close.ewm(span=config["short_window"], adjust=False).mean()
        long = close.ewm(span=config["long_window"], adjust=False).mean()
    else:
        short = close.rolling(config["short_window"]).mean()
        long = close.rolling(config["long_window"]).mean()
    macd = close.ewm(span=config["macd_fast"], adjust=False).mean() - close.ewm(
        span=config["macd_slow"], adjust=False
    ).mean()
    signal = macd.ewm(span=config["macd_signal_period"], adjust=False).mean()
    rsi = calculate_rsi(data, period=config["rsi_period"])
    volume_ratio = volume / volume.rolling(20, min_periods=5).mean()
    frame = pd.DataFrame({"close": close, "short": short, "long": long,
                          "macd": macd, "signal": signal, "rsi": rsi,
                          "volume_ratio": volume_ratio}).dropna()
    if len(frame) < 2:
        raise ValueError("有效数据不足，无法完成本地策略检查")
    latest, previous = frame.iloc[-1], frame.iloc[-2]
    if strategy_name == "超跌反弹":
        rsi_ok = frame["rsi"].tail(5).min() < 30 and latest["rsi"] > previous["rsi"]
    elif strategy_name == "短线动量":
        rsi_ok = 50 <= latest["rsi"] <= 75
    else:
        rsi_ok = 50 <= latest["rsi"] <= 70
    checks = {
        "趋势/均线": latest["short"] > latest["long"],
        "MACD动能": latest["macd"] > latest["signal"] and latest["macd"] >= previous["macd"],
        f"RSI{config['rsi_period']}区间": rsi_ok,
        "价格未明显追高": latest["close"] / latest["short"] - 1 <= 0.05,
        "成交量条件": latest["volume_ratio"] >= config["volume_ratio"],
    }
    return {
        "checks": checks,
        "all_passed": all(checks.values()),
        "price": float(latest["close"]),
        "short": float(latest["short"]),
        "long": float(latest["long"]),
        "rsi": float(latest["rsi"]),
        "macd_hist": float(latest["macd"] - latest["signal"]),
        "date": pd.to_datetime(data.iloc[-1]["日期"]).strftime("%Y-%m-%d"),
    }


def run_analysis_request(stock_code: str, depth: str, enable_debate: bool,
                         enable_risk: bool, save_history: bool,
                         strategy_name: str) -> str:
    """Call the configured remote backend, or use the local Codex runner."""
    backend_url = os.getenv("AI_BACKEND_URL", "").rstrip("/")
    if not backend_url:
        return run_codex_analysis(
            stock_code, depth, enable_debate, enable_risk, save_history, strategy_name
        )
    payload = json.dumps({
        "stock_code": stock_code,
        "depth": depth,
        "enable_debate": enable_debate,
        "enable_risk": enable_risk,
        "save_history": save_history,
        "strategy_name": strategy_name,
    }).encode("utf-8")
    request = urllib.request.Request(f"{backend_url}/analyze", data=payload,
                                     headers={"Content-Type": "application/json"})
    token = os.getenv("AI_BACKEND_TOKEN", "")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            result = json.loads(response.read().decode("utf-8"))
        if "error" in result:
            return f"## AI分析失败\n\n{result['error']}"
        return result.get("report", "## AI分析失败\n\n后端未返回报告。")
    except (urllib.error.URLError, TimeoutError) as exc:
        return f"## AI分析失败\n\n无法连接 AI 后端：`{exc}`"


st.title("🤖 AI智能分析助手")
st.caption("基于多智能体辩论的深度股票分析")
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("分析设置")
    stock_query = st.text_input(
        "股票名称或代码", value="000001", help="支持输入六位代码或股票名称"
    ).strip()
    stock_candidates = search_candidates(stock_query) if stock_query else []
    if len(stock_candidates) > 1:
        selected_stock = st.selectbox(
            "匹配到多只股票，请选择",
            stock_candidates,
            format_func=lambda item: f"{item['code']} - {item['name']}",
            key="ai_stock_selection",
        )
    elif stock_candidates:
        selected_stock = stock_candidates[0]
        st.caption(f"已匹配：{selected_stock['code']} - {selected_stock['name']}")
    else:
        selected_stock = None
    stock_code = selected_stock["code"] if selected_stock else ""
    analysis_depth = st.select_slider("分析深度", options=["快速", "标准", "深度"], value="标准")
    selected_strategy = st.selectbox("策略模型", STRATEGY_NAMES, key="ai_strategy_model")
    with st.expander("高级选项"):
        enable_debate = st.checkbox("启用牛熊辩论", value=True)
        enable_risk = st.checkbox("启用风险评估", value=True)
        save_history = st.checkbox("保存历史记录", value=True)

with col2:
    st.subheader("操作")
    if st.button("🚀 开始AI分析", type="primary", use_container_width=True):
        if selected_stock is None:
            st.error("请输入可匹配的股票名称或代码。")
        elif st.session_state.get("analysis_future") is not None:
            st.warning("已有分析任务正在运行，请稍候。")
        else:
            stock_code = selected_stock["code"]
            st.session_state.stock_code = stock_code
            st.session_state.report = None
            st.session_state.analysis_future = get_executor().submit(
                run_analysis_request, stock_code, analysis_depth, enable_debate, enable_risk, save_history,
                selected_strategy,
            )
            st.rerun()

if selected_stock is not None:
    try:
        with st.spinner("正在计算本地策略条件..."):
            local_check = calculate_local_strategy_check(
                load_local_analysis_data(selected_stock["code"]), selected_strategy
            )
        st.divider()
        st.subheader("📍 本地规则检查")
        st.caption(f"数据日期：{local_check['date']}；该判断由 Pandas 本地计算，不依赖 AI。")
        if local_check["all_passed"]:
            st.success(f"{selected_strategy}：当前技术条件全部满足，属于买入候选。")
        else:
            failed = [name for name, passed in local_check["checks"].items() if not passed]
            st.error(f"{selected_strategy}：当前技术条件未全部满足，暂不判定为买入候选。未满足：{'、'.join(failed)}")
        st.markdown("\n".join(
            f"- {'✅' if passed else '❌'} **{name}**"
            for name, passed in local_check["checks"].items()
        ))
    except Exception as error:
        st.error(f"本地策略检查失败：{error}")

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

st.divider()
st.caption("免责声明：本页面内容由规则模型和可用数据生成，仅供研究和教育参考，不构成投资、买卖或收益保证。投资者应独立核实数据并自行承担决策风险。")
