"""Central configuration for the selectable A-share strategy models."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


STRATEGY_MODELS: dict[str, dict[str, Any]] = {
    "短线动量": {
        "suitable_period": "1-10个交易日",
        "description": "捕捉短期趋势启动，强调均线快速上穿和成交量确认。",
        "short_window": 5, "long_window": 20, "rsi_period": 6,
        "macd_fast": 6, "macd_slow": 13, "macd_signal_period": 5,
        "volume_ratio": 1.5, "stop_loss_pct": 0.04, "take_profit_pct": 0.08,
        "initial_position_pct": 0.30, "add_position_pct": 0.30, "max_position_pct": 0.70,
        "logic": [
            "EMA/SMA短周期上穿长期均线",
            "MACD柱由负转正",
            "RSI6位于50至75之间",
            "成交量达到20日均量的1.5倍以上",
            "股价距离短期均线不超过3%时才追踪",
        ],
        "risk": ["单笔止损4%", "连续两日无法站稳短期均线则减仓", "不在放量长阳后追高"],
    },
    "超跌反弹": {
        "suitable_period": "1-5个交易日",
        "description": "在超跌和短期情绪极端时寻找技术性反弹，不判断长期趋势。",
        "short_window": 5, "long_window": 20, "rsi_period": 6,
        "macd_fast": 6, "macd_slow": 13, "macd_signal_period": 5,
        "volume_ratio": 1.0, "stop_loss_pct": 0.03, "take_profit_pct": 0.06,
        "initial_position_pct": 0.20, "add_position_pct": 0.20, "max_position_pct": 0.40,
        "logic": [
            "RSI6低于30后重新上穿30",
            "股价触及布林带下轨或较SMA20负乖离明显",
            "MACD柱收窄并出现拐头",
            "不要求长期均线向上，仅做反弹交易",
        ],
        "risk": ["单笔止损3%", "反弹达到目标或持仓5个交易日自动评估", "下跌趋势中只允许轻仓试错"],
    },
    "中线趋势": {
        "suitable_period": "2周-3个月",
        "description": "项目默认模型，使用双均线和MACD确认中期趋势。",
        "short_window": 20, "long_window": 60, "rsi_period": 14,
        "macd_fast": 12, "macd_slow": 26, "macd_signal_period": 9,
        "volume_ratio": 1.0, "stop_loss_pct": 0.08, "take_profit_pct": 0.15,
        "initial_position_pct": 0.30, "add_position_pct": 0.30, "max_position_pct": 0.95,
        "logic": [
            "SMA20位于SMA60上方",
            "MACD位于信号线之上且柱体不继续恶化",
            "RSI14处于50至70的健康区间",
            "股价较SMA20偏离不超过5%",
        ],
        "risk": ["单笔止损8%", "SMA20下穿SMA60或趋势破坏时退出", "遵守A股T+1和涨跌停限制"],
    },
    "中线突破": {
        "suitable_period": "1-3个月",
        "description": "寻找整理后的价格突破，并用成交量过滤假突破。",
        "short_window": 20, "long_window": 60, "rsi_period": 14,
        "macd_fast": 12, "macd_slow": 26, "macd_signal_period": 9,
        "volume_ratio": 1.5, "stop_loss_pct": 0.07, "take_profit_pct": 0.18,
        "initial_position_pct": 0.25, "add_position_pct": 0.25, "max_position_pct": 0.75,
        "logic": [
            "收盘价突破近20日高点或重要整理平台",
            "成交量达到20日均量1.5倍以上",
            "MACD柱为正且RSI14不高于75",
            "突破后回踩不跌破突破位才允许加仓",
        ],
        "risk": ["跌回突破位下方减仓", "单笔止损7%", "放量长上影线视为假突破风险"],
    },
    "基本面趋势": {
        "suitable_period": "3-12个月",
        "description": "用盈利质量和估值过滤趋势信号，适合低换手中长期持有。",
        "short_window": 60, "long_window": 120, "rsi_period": 14,
        "macd_fast": 12, "macd_slow": 26, "macd_signal_period": 9,
        "volume_ratio": 0.8, "stop_loss_pct": 0.10, "take_profit_pct": 0.25,
        "initial_position_pct": 0.30, "add_position_pct": 0.30, "max_position_pct": 0.80,
        "logic": [
            "ROE不低于10%",
            "PE分位数不高于50%",
            "SMA60位于SMA120上方",
            "回撤时不因单日波动轻易卖出",
        ],
        "risk": ["财报恶化或估值逻辑改变时退出", "单笔止损10%", "基本面数据缺失时不强行给出买入结论"],
    },
    "防守型": {
        "suitable_period": "1-6个月",
        "description": "优先控制回撤，只在长期趋势向上且波动可接受时持仓。",
        "short_window": 60, "long_window": 120, "rsi_period": 14,
        "macd_fast": 12, "macd_slow": 26, "macd_signal_period": 9,
        "volume_ratio": 0.8, "stop_loss_pct": 0.06, "take_profit_pct": 0.12,
        "initial_position_pct": 0.20, "add_position_pct": 0.20, "max_position_pct": 0.50,
        "logic": [
            "SMA60位于SMA120上方",
            "收盘价保持在长期均线之上",
            "RSI14不处于极端超买区",
            "优先选择波动率较低、回撤较小的标的",
        ],
        "risk": ["单笔止损6%", "跌破SMA120降低仓位", "总仓位上限50%，保留现金应对波动"],
    },
}

STRATEGY_NAMES = tuple(STRATEGY_MODELS)


def get_strategy_config(name: str) -> dict[str, Any]:
    """Return a copy so callers cannot mutate the shared defaults."""
    if name not in STRATEGY_MODELS:
        raise KeyError(f"未知策略模型：{name}")
    return deepcopy(STRATEGY_MODELS[name])


def format_strategy_prompt(name: str) -> str:
    """Format one strategy's rules for the AI analyst prompt."""
    config = get_strategy_config(name)
    logic = "\n".join(f"- {item}" for item in config["logic"])
    risk = "\n".join(f"- {item}" for item in config["risk"])
    return f"""策略模型：{name}
适用周期：{config['suitable_period']}
模型说明：{config['description']}
技术参数：短期均线 {config['short_window']}，长期均线 {config['long_window']}，RSI {config['rsi_period']}，MACD {config['macd_fast']}/{config['macd_slow']}/{config['macd_signal_period']}。
仓位参数：首次 {config['initial_position_pct']:.0%}，确认后加仓 {config['add_position_pct']:.0%}，最大仓位 {config['max_position_pct']:.0%}。
核心逻辑：
{logic}
风控建议：止损参考 {config['stop_loss_pct']:.0%}，目标收益参考 {config['take_profit_pct']:.0%}。
{risk}"""
