"""Backtest a dual moving-average crossover strategy."""

import pandas as pd

from indicators import calculate_sma


def calculate_sharpe_ratio(
    daily_returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Calculate the annualized Sharpe ratio from daily strategy returns.

    ``risk_free_rate`` is an annual rate expressed as a decimal. For example,
    ``0.03`` represents 3% per year. Returns with missing values are ignored.
    A zero-volatility series returns ``0.0`` because its Sharpe ratio is not
    defined.
    """
    if not isinstance(daily_returns, pd.Series):
        raise TypeError("daily_returns 必须是 pandas.Series")
    if periods_per_year < 1:
        raise ValueError("periods_per_year 必须是大于 0 的整数")
    if risk_free_rate <= -1:
        raise ValueError("risk_free_rate 必须大于 -1")

    returns = pd.to_numeric(daily_returns, errors="coerce").dropna()
    if returns.empty:
        raise ValueError("daily_returns 不包含有效收益率")

    daily_risk_free_rate = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    excess_returns = returns - daily_risk_free_rate
    volatility = excess_returns.std(ddof=1)
    if pd.isna(volatility) or volatility == 0:
        return 0.0

    return float(excess_returns.mean() / volatility * periods_per_year**0.5)


def run_dual_ma_backtest(
    data: pd.DataFrame,
    short_window: int = 20,
    long_window: int = 60,
    price_column: str = "收盘",
) -> tuple[pd.DataFrame, float]:
    """Run a long-only dual moving-average crossover backtest.

    A position is opened when the short SMA is above the long SMA and closed
    when it is below it. Signals are shifted by one row before returns are
    calculated, so a signal observed at today's close is executed the next
    trading day.

    Returns
    -------
    tuple[pandas.DataFrame, float]
        The first value contains the daily backtest details. The second value
        is the final cumulative return as a decimal (e.g. ``0.25`` means 25%).
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data 必须是 pandas.DataFrame")
    if not isinstance(short_window, int) or short_window < 1:
        raise ValueError("short_window 必须是大于 0 的整数")
    if not isinstance(long_window, int) or long_window < 1:
        raise ValueError("long_window 必须是大于 0 的整数")
    if short_window >= long_window:
        raise ValueError("short_window 必须小于 long_window")
    if price_column not in data.columns:
        raise ValueError(f"DataFrame 中不存在价格列: {price_column}")

    result = data.copy()
    prices = pd.to_numeric(result[price_column], errors="coerce")
    if prices.isna().all():
        raise ValueError(f"价格列 {price_column} 不包含有效数值")

    result["短期均线"] = calculate_sma(
        result, window=short_window, price_column=price_column
    )
    result["长期均线"] = calculate_sma(
        result, window=long_window, price_column=price_column
    )

    # Long-only position: 1 while the short SMA is above the long SMA.
    result["持仓"] = (result["短期均线"] > result["长期均线"]).astype(int)
    result["交易信号"] = result["持仓"].diff().map(
        {1.0: "买入", -1.0: "卖出"}
    ).fillna("持有/无信号")

    result["标的日收益率"] = prices.pct_change()
    result["策略日收益率"] = (
        result["持仓"].shift(1).fillna(0) * result["标的日收益率"]
    ).fillna(0)
    result["策略累计收益率"] = (
        (1 + result["策略日收益率"]).cumprod() - 1
    )

    cumulative_return = float(result["策略累计收益率"].iloc[-1])
    return result, cumulative_return


if __name__ == "__main__":
    from data_fetcher import fetch_stock_data

    history = fetch_stock_data()
    details, total_return = run_dual_ma_backtest(history)
    sharpe_ratio = calculate_sharpe_ratio(details["策略日收益率"])
    print(details.tail())
    print(f"策略累计收益率: {total_return:.2%}")
    print(f"策略夏普比率: {sharpe_ratio:.3f}")
