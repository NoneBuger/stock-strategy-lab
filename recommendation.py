"""Rule-based A-share entry and exit recommendations."""

from __future__ import annotations

from typing import Any

import pandas as pd


def build_recommendation(
    data: pd.DataFrame,
    short_window: int = 20,
    long_window: int = 60,
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal_period: int = 9,
) -> dict[str, Any]:
    """Return an explainable, non-AI trading plan from the displayed indicators."""
    required = {"日期", "开盘", "最高", "最低", "收盘", "成交量"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"行情数据缺少字段: {sorted(missing)}")
    frame = data.copy()
    close = pd.to_numeric(frame["收盘"], errors="coerce")
    volume = pd.to_numeric(frame["成交量"], errors="coerce")
    frame["sma_short"] = close.rolling(short_window, min_periods=short_window).mean()
    frame["sma_long"] = close.rolling(long_window, min_periods=long_window).mean()
    ema_fast = close.ewm(span=macd_fast, adjust=False).mean()
    ema_slow = close.ewm(span=macd_slow, adjust=False).mean()
    frame["macd"] = ema_fast - ema_slow
    frame["macd_signal"] = frame["macd"].ewm(span=macd_signal_period, adjust=False).mean()
    frame["macd_hist"] = frame["macd"] - frame["macd_signal"]
    changes = close.diff()
    gains = changes.clip(lower=0).ewm(alpha=1 / rsi_period, adjust=False, min_periods=rsi_period).mean()
    losses = -changes.clip(upper=0).ewm(alpha=1 / rsi_period, adjust=False, min_periods=rsi_period).mean()
    frame["rsi"] = 100 - 100 / (1 + gains / losses.replace(0, pd.NA))
    frame["rsi"] = frame["rsi"].where(losses.ne(0), 100.0)
    frame["volume_ratio"] = volume / volume.rolling(20, min_periods=5).mean()
    valid = frame.dropna(subset=["sma_short", "sma_long", "macd_hist", "rsi"])
    if len(valid) < 2:
        raise ValueError("有效数据不足，无法生成投资建议")
    latest, previous = valid.iloc[-1], valid.iloc[-2]
    price = float(latest["收盘"])
    sma_short = float(latest["sma_short"])
    sma_long = float(latest["sma_long"])
    rsi = float(latest["rsi"])
    macd_hist = float(latest["macd_hist"])
    golden_cross = previous["sma_short"] <= previous["sma_long"] and sma_short > sma_long
    death_cross = previous["sma_short"] >= previous["sma_long"] and sma_short < sma_long
    trend_up = sma_short > sma_long
    macd_bullish = latest["macd"] > latest["macd_signal"] and macd_hist >= float(previous["macd_hist"])
    rsi_healthy = 50 <= rsi <= 70
    deviation = price / sma_short - 1
    not_chasing = deviation <= 0.05
    score = sum((trend_up, macd_bullish, rsi_healthy, not_chasing, golden_cross)) * 20

    if death_cross or (not trend_up and macd_hist < 0 and rsi < 45):
        signal, action = "卖出/规避", "不建仓；已有仓位优先减仓或退出"
    elif trend_up and macd_bullish and rsi_healthy and not_chasing:
        signal, action = "买入候选", "分批建仓，不追高"
    elif trend_up and rsi > 70:
        signal, action = "持有观察", "趋势尚可但短线偏热，等待回踩"
    else:
        signal, action = "观望", "等待均线、MACD和RSI形成共振"

    entry = price if signal == "买入候选" else sma_short
    stop = min(entry * 0.92, sma_long * 0.98)
    target = entry * 1.15
    return {
        "date": pd.to_datetime(latest["日期"]).strftime("%Y-%m-%d"),
        "price": price, "sma_short": sma_short, "sma_long": sma_long,
        "rsi": rsi, "macd_hist": macd_hist, "deviation": deviation,
        "volume_ratio": float(latest["volume_ratio"]) if pd.notna(latest["volume_ratio"]) else None,
        "golden_cross": bool(golden_cross), "death_cross": bool(death_cross),
        "score": int(score), "signal": signal, "action": action,
        "entry": float(entry), "stop": float(stop), "target": float(target),
        "reasons": [
            f"SMA{short_window}{'上方' if trend_up else '下方'}SMA{long_window}",
            f"MACD柱{'偏强' if macd_bullish else '偏弱'}",
            f"RSI({rsi_period})={rsi:.1f}",
            f"股价较SMA{short_window}偏离{deviation:.1%}",
        ],
    }
