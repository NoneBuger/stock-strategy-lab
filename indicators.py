"""Technical indicators for stock price data."""

import numpy as np
import pandas as pd


def _closing_prices(data: pd.DataFrame, price_column: str) -> pd.Series:
    """Validate the input and return the selected price series."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data 必须是 pandas.DataFrame")
    if price_column not in data.columns:
        raise ValueError(f"DataFrame 中不存在价格列: {price_column}")

    prices = pd.to_numeric(data[price_column], errors="coerce")
    if prices.isna().all():
        raise ValueError(f"价格列 {price_column} 不包含有效数值")
    return prices


def calculate_sma(
    data: pd.DataFrame,
    window: int = 20,
    price_column: str = "收盘",
) -> pd.Series:
    """Calculate a simple moving average (SMA).

    Parameters
    ----------
    data:
        Stock data containing a price column.
    window:
        Number of observations in the moving window.
    price_column:
        Column used for the calculation; AkShare's default is ``收盘``.
    """
    if not isinstance(window, int) or window < 1:
        raise ValueError("window 必须是大于 0 的整数")

    prices = _closing_prices(data, price_column)
    return prices.rolling(window=window, min_periods=window).mean().rename(
        f"SMA_{window}"
    )


def calculate_rsi(
    data: pd.DataFrame,
    period: int = 14,
    price_column: str = "收盘",
) -> pd.Series:
    """Calculate the Relative Strength Index (RSI) using Wilder smoothing."""
    if not isinstance(period, int) or period < 1:
        raise ValueError("period 必须是大于 0 的整数")

    prices = _closing_prices(data, price_column)
    changes = prices.diff()
    gains = changes.clip(lower=0)
    losses = -changes.clip(upper=0)

    average_gain = gains.ewm(
        alpha=1 / period, adjust=False, min_periods=period
    ).mean()
    average_loss = losses.ewm(
        alpha=1 / period, adjust=False, min_periods=period
    ).mean()

    relative_strength = average_gain / average_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + relative_strength))
    rsi = rsi.where(average_loss.ne(0), 100.0)
    rsi = rsi.where(~((average_gain == 0) & (average_loss == 0)), 50.0)

    return rsi.rename(f"RSI_{period}")
