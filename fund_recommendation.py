"""Practical, transparent screening models for Chinese funds and indexes."""

from __future__ import annotations

import math

import pandas as pd


FUND_STRATEGIES = ["长期稳健型", "ETF趋势型", "指数定投型"]
FUND_STRATEGY_DEFAULTS = {
    "长期稳健型": {"trend_window": 120, "sharpe_min": 0.30, "max_drawdown_limit": 0.30},
    "ETF趋势型": {"fast_window": 20, "slow_window": 60, "rsi_max": 75, "atr_stop_multiple": 2.0},
    "指数定投型": {"trend_window": 60, "drawdown_trigger": 0.20, "momentum_window": 12},
}


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, float("nan")))


def _metrics(close: pd.Series) -> dict[str, float]:
    returns = close.pct_change().dropna()
    if returns.empty:
        raise ValueError("有效收益率数据不足")
    days = max(len(close), 1)
    annualized_return = (float(close.iloc[-1]) / float(close.iloc[0])) ** (252 / days) - 1
    recent_returns = returns.tail(252)
    volatility = float(recent_returns.std() * math.sqrt(252))
    risk_free_daily = (1.02 ** (1 / 252)) - 1
    sharpe = float((recent_returns - risk_free_daily).mean() / recent_returns.std() * math.sqrt(252)) if recent_returns.std() else 0.0
    drawdown_curve = close / close.cummax() - 1
    max_drawdown = float(drawdown_curve.min())
    calmar = annualized_return / abs(max_drawdown) if max_drawdown < 0 else 0.0
    return {"annualized_return": annualized_return, "volatility": volatility,
            "sharpe": sharpe, "max_drawdown": max_drawdown, "calmar": calmar}


def build_fund_index_recommendation(
    data: pd.DataFrame,
    asset_type: str,
    strategy_name: str = "长期稳健型",
    overrides: dict | None = None,
) -> dict:
    """Return a rule-based recommendation with risk-adjusted metrics.

    PE/PB valuation is deliberately not inferred from price history. A real
    valuation percentile must come from a separate fundamental data endpoint.
    """
    if strategy_name not in FUND_STRATEGIES:
        raise ValueError(f"不支持的基金策略：{strategy_name}")
    config = FUND_STRATEGY_DEFAULTS[strategy_name].copy()
    if overrides:
        config.update(overrides)
    close = pd.to_numeric(data["收盘"], errors="coerce").dropna().reset_index(drop=True)
    if len(close) < 65:
        raise ValueError("至少需要65个交易日才能计算基金风险和趋势指标")

    fast_window = int(config.get("fast_window", 20))
    slow_window = int(config.get("slow_window", 60))
    trend_window = int(config.get("trend_window", 120))
    sma20, sma60 = close.rolling(fast_window).mean(), close.rolling(slow_window).mean()
    sma120, sma250 = close.rolling(trend_window).mean(), close.rolling(250).mean()
    rsi = _rsi(close).iloc[-1]
    current = float(close.iloc[-1])
    ma20, ma60 = float(sma20.iloc[-1]), float(sma60.iloc[-1])
    ma120 = float(sma120.iloc[-1]) if pd.notna(sma120.iloc[-1]) else ma60
    ma250 = float(sma250.iloc[-1]) if pd.notna(sma250.iloc[-1]) else ma120
    metrics = _metrics(close)
    momentum = {
        "3m": current / float(close.iloc[-64]) - 1 if len(close) > 64 else 0.0,
        "6m": current / float(close.iloc[-127]) - 1 if len(close) > 127 else 0.0,
        "12m": current / float(close.iloc[-253]) - 1 if len(close) > 253 else metrics["annualized_return"],
    }
    custom_momentum_days = int(config.get("momentum_window", 12)) * 21
    custom_momentum = (
        current / float(close.iloc[-custom_momentum_days - 1]) - 1
        if len(close) > custom_momentum_days else metrics["annualized_return"]
    )
    atr = float(close.diff().abs().rolling(20).mean().iloc[-1])
    atr_pct = atr / current if current else 0.0
    drawdown_1y = current / float(close.tail(252).max()) - 1

    if strategy_name == "长期稳健型":
        trend_ok = current > ma120 and momentum["6m"] > 0 and momentum["12m"] > 0
        risk_ok = metrics["sharpe"] >= float(config["sharpe_min"]) and metrics["max_drawdown"] > -float(config["max_drawdown_limit"])
        if trend_ok and risk_ok:
            signal, action, position = "分批建仓候选", "长期趋势和风险调整收益较好，可分三批建仓", "30%～50%"
        elif current >= ma120 and momentum["6m"] > -0.05:
            signal, action, position = "轻仓/定投观察", "趋势尚可但收益或风险指标不足，优先定投", "10%～20%"
        else:
            signal, action, position = "暂不建仓", "长期趋势或风险收益比不理想，等待修复", "0%～10%"
        reasons = [f"收盘价{'高于' if current > ma120 else '低于'}MA120",
                   f"近6个月收益={momentum['6m']:.1%}",
                   f"近12个月收益={momentum['12m']:.1%}",
                   f"夏普={metrics['sharpe']:.2f}", f"最大回撤={metrics['max_drawdown']:.1%}"]
        entry_base = ma120
    elif strategy_name == "ETF趋势型":
        trend_ok = current > ma20 > ma60 and momentum["3m"] > 0 and momentum["6m"] > 0
        rsi_ok = float(rsi) < float(config["rsi_max"])
        if trend_ok and rsi_ok:
            signal, action, position = "趋势建仓候选", "ETF趋势向上，可按回踩分批买入，不追高", "30%～50%"
        elif current >= ma60 and momentum["3m"] > -0.05:
            signal, action, position = "回踩观察", "趋势未完全破坏，等待回到均线附近再确认", "10%～20%"
        else:
            signal, action, position = "暂不建仓", "短中期趋势未确认，规避弱势接飞刀", "0%～10%"
        reasons = [f"收盘价{'高于' if current > ma20 else '低于'}MA20",
                   f"MA20{'高于' if ma20 > ma60 else '低于'}MA60",
                   f"近3个月收益={momentum['3m']:.1%}",
                   f"近6个月收益={momentum['6m']:.1%}", f"RSI(14)={float(rsi):.1f}"]
        entry_base = ma20
    else:
        if drawdown_1y <= -float(config["drawdown_trigger"]) and current >= ma120:
            signal, action, position = "回撤定投候选", f"距一年高点回撤较大但未跌破MA{trend_window}，可分期定投", "20%～30%"
        elif current >= ma120 and custom_momentum > 0:
            signal, action, position = "正常定投", "趋势尚可，按固定周期投入，不一次性追涨", "10%～20%"
        else:
            signal, action, position = "暂停加仓", "趋势偏弱，等待重新站上MA60", "0%～10%"
        reasons = ["PE/PB分位数未接入，未将价格指标冒充估值",
                   f"距近一年高点={drawdown_1y:.1%}",
                   f"收盘价{'高于' if current >= ma120 else '低于'}MA{trend_window}",
                   f"近{int(config.get('momentum_window', 12))}个月收益={custom_momentum:.1%}"]
        entry_base = ma120

    entry = min(current, entry_base * 1.01)
    second_entry = entry * (1 - min(max(atr_pct, 0.03), 0.08))
    stop_multiple = float(config.get("atr_stop_multiple", 2.0))
    stop = max(entry - stop_multiple * atr, entry * 0.88)
    return {
        "strategy_name": strategy_name, "signal": signal, "action": action,
        "position": position, "price": current, "sma20": ma20, "sma60": ma60,
        "sma120": ma120, "sma250": ma250, "rsi": float(rsi),
        "volatility": metrics["volatility"], "annualized_return": metrics["annualized_return"],
        "sharpe": metrics["sharpe"], "calmar": metrics["calmar"],
        "drawdown": metrics["max_drawdown"], "drawdown_1y": drawdown_1y,
        "momentum_3m": momentum["3m"], "momentum_6m": momentum["6m"],
        "momentum_12m": momentum["12m"], "atr": atr, "entry": entry,
        "second_entry": second_entry, "stop": stop, "target": None,
        "valuation_status": "未接入PE/PB分位数；本次不做估值结论", "reasons": reasons,
        "parameters": config,
    }
