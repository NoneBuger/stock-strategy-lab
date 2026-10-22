"""Technical screening and position references for funds and indexes."""

from __future__ import annotations

import pandas as pd


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, float("nan")))


def build_fund_index_recommendation(data: pd.DataFrame, asset_type: str) -> dict:
    if len(data) < 65:
        raise ValueError("至少需要65个交易日才能计算中短期趋势")
    close = pd.to_numeric(data["收盘"], errors="coerce")
    sma20, sma60 = close.rolling(20).mean(), close.rolling(60).mean()
    rsi = _rsi(close).iloc[-1]
    current = float(close.iloc[-1])
    ma20, ma60 = float(sma20.iloc[-1]), float(sma60.iloc[-1])
    returns = close.pct_change().dropna()
    volatility = float(returns.tail(60).std() * (252 ** 0.5))
    rolling_high = close.rolling(60).max().iloc[-1]
    drawdown = current / float(rolling_high) - 1
    trend_ok = current > ma20 > ma60
    rsi_ok = 45 <= float(rsi) <= 70
    if trend_ok and rsi_ok:
        signal, action = "分批建仓候选", "趋势向上，可分2～3次建仓，避免一次性追高"
    elif current >= ma60 and float(rsi) < 45:
        signal, action = "回撤观察", "接近趋势线，等待止跌确认后再小仓位试探"
    elif current < ma60:
        signal, action = "暂不建仓", "价格低于60日均线，先规避趋势走弱风险"
    else:
        signal, action = "持有/观察", "趋势尚未形成共振，等待均线和强弱指标确认"
    stop_pct, target_pct = (0.08, 0.15) if asset_type == "基金" else (0.07, 0.12)
    entry = min(current, ma20 * 1.01) if signal == "分批建仓候选" else ma20
    return {
        "signal": signal, "action": action, "price": current,
        "sma20": ma20, "sma60": ma60, "rsi": float(rsi),
        "volatility": volatility, "drawdown": drawdown,
        "entry": entry, "stop": entry * (1 - stop_pct),
        "target": entry * (1 + target_pct),
        "reasons": [
            f"收盘价{'高于' if current > ma20 else '低于'}SMA20",
            f"SMA20{'高于' if ma20 > ma60 else '低于'}SMA60",
            f"RSI(14)={float(rsi):.1f}",
            f"近60日最大回撤={drawdown:.1%}",
        ],
    }
