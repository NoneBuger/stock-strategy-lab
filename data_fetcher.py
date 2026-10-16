"""Fetch A-share daily data with Tushare, AkShare and YFinance fallbacks."""

import os
from datetime import date
from dateutil.relativedelta import relativedelta

import pandas as pd


def _tushare_code(symbol: str) -> str:
    return f"{symbol}.SH" if symbol.startswith(("5", "6", "9")) else f"{symbol}.SZ"


def _fetch_tushare(symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        raise RuntimeError("TUSHARE_TOKEN 未配置")
    import tushare as ts

    pro = ts.pro_api(token)
    data = pro.daily(
        ts_code=_tushare_code(symbol),
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
    )
    if data.empty:
        raise ValueError("Tushare 未返回数据")
    return data.rename(columns={
        "trade_date": "日期", "open": "开盘", "high": "最高",
        "low": "最低", "close": "收盘", "vol": "成交量",
    })[["日期", "开盘", "最高", "最低", "收盘", "成交量"]]


def _fetch_akshare(symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
    import akshare as ak

    data = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
        adjust="",
    )
    if data.empty:
        raise ValueError("AkShare 未返回数据")
    return data


def _fetch_yfinance(symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
    import yfinance as yf

    suffix = ".SZ" if symbol.startswith(("0", "3")) else ".SS"
    data = yf.download(
        f"{symbol}{suffix}",
        start=start_date.isoformat(),
        end=(end_date + relativedelta(days=1)).isoformat(),
        auto_adjust=False,
        progress=False,
    )
    if data.empty:
        raise ValueError("YFinance 未返回数据")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data.reset_index().rename(columns={
        "Date": "日期", "Open": "开盘", "High": "最高",
        "Low": "最低", "Close": "收盘", "Volume": "成交量",
    })
    return data[["日期", "开盘", "最高", "最低", "收盘", "成交量"]]


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

    errors: list[str] = []
    for source, loader in (("Tushare", _fetch_tushare), ("AkShare", _fetch_akshare), ("YFinance", _fetch_yfinance)):
        try:
            data = loader(symbol, start_date, end_date)
            data["日期"] = pd.to_datetime(data["日期"])
            data = data.sort_values("日期").reset_index(drop=True)
            data.attrs["data_source"] = source
            return data
        except Exception as error:
            errors.append(f"{source}: {error}")
    raise RuntimeError(f"未获取到股票 {symbol} 的日线数据；数据源错误：{' | '.join(errors)}")


if __name__ == "__main__":
    stock_data = fetch_stock_data()
    print(stock_data)
