"""Explainable, model-specific A-share investment recommendations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from strategy_config import get_strategy_config


def build_recommendation(
    data: pd.DataFrame,
    short_window: int = 20,
    long_window: int = 60,
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal_period: int = 9,
    strategy_name: str = "中线趋势",
    strategy_config: Mapping[str, Any] | None = None,
    fundamental_metrics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate a recommendation using the selected model's actual rules."""
    required = {"日期", "开盘", "最高", "最低", "收盘", "成交量"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"行情数据缺少字段: {sorted(missing)}")
    config = dict(strategy_config or get_strategy_config(strategy_name))
    frame = data.copy()
    close = pd.to_numeric(frame["收盘"], errors="coerce")
    volume = pd.to_numeric(frame["成交量"], errors="coerce")
    short_sma = close.rolling(short_window, min_periods=short_window).mean()
    long_sma = close.rolling(long_window, min_periods=long_window).mean()
    short_ema = close.ewm(span=short_window, adjust=False).mean()
    long_ema = close.ewm(span=long_window, adjust=False).mean()
    ema_fast = close.ewm(span=macd_fast, adjust=False).mean()
    ema_slow = close.ewm(span=macd_slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=macd_signal_period, adjust=False).mean()
    macd_hist = macd - macd_signal
    changes = close.diff()
    gains = changes.clip(lower=0).ewm(alpha=1 / rsi_period, adjust=False, min_periods=rsi_period).mean()
    losses = -changes.clip(upper=0).ewm(alpha=1 / rsi_period, adjust=False, min_periods=rsi_period).mean()
    rsi = 100 - 100 / (1 + gains / losses.replace(0, np.nan))
    rsi = rsi.where(losses.ne(0), 100.0)
    volume_ratio = volume / volume.rolling(20, min_periods=5).mean()
    middle = close.rolling(20, min_periods=20).mean()
    std = close.rolling(20, min_periods=20).std()
    bollinger_lower = middle - 2 * std
    breakout_level = close.shift(1).rolling(20, min_periods=20).max()
    volatility = close.pct_change().rolling(20, min_periods=20).std() * np.sqrt(252)

    use_ema = strategy_name in {"短线动量", "超跌反弹"}
    trend_short = short_ema if use_ema else short_sma
    trend_long = long_ema if use_ema else long_sma
    frame = pd.DataFrame({
        "日期": pd.to_datetime(data["日期"]), "price": close,
        "short": trend_short, "long": trend_long, "macd": macd,
        "macd_signal": macd_signal, "macd_hist": macd_hist, "rsi": rsi,
        "volume_ratio": volume_ratio, "bollinger_lower": bollinger_lower,
        "breakout_level": breakout_level, "volatility": volatility,
    }).dropna(subset=["price", "short", "long", "macd_hist", "rsi"])
    if len(frame) < 2:
        raise ValueError("有效数据不足，无法生成投资建议")

    latest, previous = frame.iloc[-1], frame.iloc[-2]
    price = float(latest["price"])
    short_value = float(latest["short"])
    long_value = float(latest["long"])
    rsi_value = float(latest["rsi"])
    macd_value = float(latest["macd_hist"])
    trend_up = latest["short"] > latest["long"]
    macd_bullish = latest["macd"] > latest["macd_signal"] and latest["macd_hist"] >= previous["macd_hist"]
    deviation = price / short_value - 1
    volume_ok = pd.notna(latest["volume_ratio"]) and latest["volume_ratio"] >= config["volume_ratio"]
    conditions: dict[str, bool] = {}
    reasons: list[str] = []

    if strategy_name == "短线动量":
        conditions = {
            f"EMA{short_window}上穿/位于EMA{long_window}": bool(trend_up),
            "MACD柱转强": bool(macd_bullish),
            f"RSI{rsi_period}处于50-75": 50 <= rsi_value <= 75,
            f"成交量达到20日均量{config['volume_ratio']:.1f}倍": bool(volume_ok),
            "价格未远离短期均线": deviation <= 0.03,
        }
        hard_sell = not trend_up and macd_value < 0
    elif strategy_name == "超跌反弹":
        recent_rsi = frame["rsi"].tail(5)
        oversold = bool(recent_rsi.min() < 30)
        conditions = {
            "RSI近期进入超卖区": oversold,
            "RSI出现反弹": bool(latest["rsi"] > previous["rsi"]),
            "MACD柱收窄/转强": bool(latest["macd_hist"] >= previous["macd_hist"]),
            "价格接近布林下轨": bool(pd.notna(latest["bollinger_lower"]) and price <= latest["bollinger_lower"] * 1.03),
        }
        hard_sell = rsi_value < 20 and macd_value < 0
    elif strategy_name == "中线突破":
        conditions = {
            "收盘突破20日高点": bool(pd.notna(latest["breakout_level"]) and price > latest["breakout_level"]),
            f"成交量达到20日均量{config['volume_ratio']:.1f}倍": bool(volume_ok),
            "MACD柱为正": macd_value > 0,
            "RSI不高于75": rsi_value <= 75,
        }
        hard_sell = pd.notna(latest["breakout_level"]) and price < latest["breakout_level"] * 0.97
    elif strategy_name == "基本面趋势":
        roe = fundamental_metrics.get("roe") if fundamental_metrics else None
        pe_percentile = fundamental_metrics.get("pe_percentile") if fundamental_metrics else None
        conditions = {
            "SMA趋势向上": bool(trend_up),
            "ROE不低于10%": roe is not None and float(roe) >= 10,
            "PE分位数不高于50%": pe_percentile is not None and float(pe_percentile) <= 50,
            "MACD动能未恶化": bool(macd_bullish),
        }
        hard_sell = not trend_up
    elif strategy_name == "防守型":
        conditions = {
            "长期均线趋势向上": bool(trend_up),
            "收盘价位于长期均线上方": price > long_value,
            "RSI未极端超买": rsi_value <= 70,
            "年化波动率低于35%": pd.notna(latest["volatility"]) and latest["volatility"] <= 0.35,
        }
        hard_sell = price < long_value
    else:  # 中线趋势 and compatible fallback
        conditions = {
            f"SMA{short_window}位于SMA{long_window}上方": bool(trend_up),
            "MACD动能偏强": bool(macd_bullish),
            f"RSI{rsi_period}处于50-70": 50 <= rsi_value <= 70,
            "价格未远离短期均线": deviation <= 0.05,
        }
        hard_sell = not trend_up and macd_value < 0 and rsi_value < 45

    passed = sum(bool(value) for value in conditions.values())
    all_passed = passed == len(conditions)
    if all_passed:
        signal, action = "买入候选", "满足该模型全部核心条件，按计划分批建仓"
    elif hard_sell:
        signal, action = "卖出/规避", "模型出现趋势破坏或风险条件，不建议建仓"
    else:
        signal, action = "观望", "当前未满足全部模型条件，不建议主动建仓"
    failed = [name for name, value in conditions.items() if not value]
    reasons.extend(f"满足：{name}" for name, value in conditions.items() if value)
    reasons.extend(f"未满足：{name}" for name in failed)

    is_entry_candidate = signal == "买入候选"
    stop_pct = float(config["stop_loss_pct"])
    target_pct = float(config["take_profit_pct"])
    entry = price if is_entry_candidate else None
    stop = price * (1 - stop_pct) if is_entry_candidate else None
    target = price * (1 + target_pct) if is_entry_candidate else None
    watch_price = short_value if signal == "观望" else None
    return {
        "model_name": strategy_name, "date": latest["日期"].strftime("%Y-%m-%d"),
        "price": price, "sma_short": short_value, "sma_long": long_value,
        "rsi": rsi_value, "macd_hist": macd_value,
        "deviation": deviation, "volume_ratio": float(latest["volume_ratio"]) if pd.notna(latest["volume_ratio"]) else None,
        "score": int(round(passed / len(conditions) * 100)), "signal": signal, "action": action,
        "entry": entry, "watch_price": watch_price, "stop": stop, "target": target,
        "conditions": conditions, "reasons": reasons,
        "failed_conditions": failed,
    }
