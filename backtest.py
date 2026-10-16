"""Backtest a dual moving-average crossover strategy."""

import pandas as pd

from indicators import calculate_sma


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
    print(details.tail())
    print(f"策略累计收益率: {total_return:.2%}")
