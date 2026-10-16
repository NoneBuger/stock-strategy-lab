"""Fetch daily stock data from AkShare."""

from datetime import date
from dateutil.relativedelta import relativedelta

import akshare as ak
import pandas as pd


def fetch_stock_data(
    symbol: str = "000001",
    years: int = 1,
) -> pd.DataFrame:
    """Return the most recent ``years`` of daily data for an A-share stock.

    The default symbol is 000001 (Ping An Bank). AkShare's ``stock_zh_a_hist``
    API expects dates in ``YYYYMMDD`` format.
    """
    end_date = date.today()
    start_date = end_date - relativedelta(years=years)

    data = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
        adjust="",
    )

    if data.empty:
        raise ValueError(f"未获取到股票 {symbol} 的日线数据")

    if "日期" in data.columns:
        data["日期"] = pd.to_datetime(data["日期"])
        data = data.sort_values("日期")

    return data.reset_index(drop=True)


if __name__ == "__main__":
    stock_data = fetch_stock_data()
    print(stock_data)
