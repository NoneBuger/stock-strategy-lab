"""Public AkShare adapters for Chinese funds, ETFs and broad-market indexes."""

from __future__ import annotations

from datetime import date
import inspect
from dateutil.relativedelta import relativedelta

import pandas as pd


COMMON_INDEXES = {
    "000001": "上证指数",
    "000300": "沪深300",
    "000905": "中证500",
    "000852": "中证1000",
    "399001": "深证成指",
    "399006": "创业板指",
    "000688": "科创50",
    "899050": "北证50",
}


def _clean_symbol(value: object) -> str:
    return str(value).strip().zfill(6)


def search_fund_candidates(query: str, limit: int = 20) -> list[dict[str, str]]:
    query = str(query).strip().lower()
    if not query:
        return []
    try:
        import akshare as ak

        frame = ak.fund_name_em()
        code_col = next((c for c in ("基金代码", "code") if c in frame.columns), None)
        name_col = next((c for c in ("基金简称", "name") if c in frame.columns), None)
        if code_col and name_col:
            result = []
            for _, row in frame.iterrows():
                code, name = _clean_symbol(row[code_col]), str(row[name_col])
                if query in code.lower() or query in name.lower():
                    result.append({"code": code, "name": name})
                    if len(result) >= limit:
                        break
            return result
    except Exception:
        pass
    if query.isdigit() and len(query) == 6:
        return [{"code": query, "name": "基金代码（名称待数据源返回）"}]
    return []


def search_index_candidates(query: str, limit: int = 20) -> list[dict[str, str]]:
    query = str(query).strip().lower()
    return [
        {"code": code, "name": name}
        for code, name in COMMON_INDEXES.items()
        if query in code.lower() or query in name.lower()
    ][:limit]


def _rename_history(frame: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "日期": "日期", "date": "日期", "净值日期": "日期", "交易日期": "日期",
        "开盘": "开盘", "开盘价": "开盘", "最高": "最高", "最高价": "最高",
        "最低": "最低", "最低价": "最低", "收盘": "收盘", "收盘价": "收盘",
        "单位净值": "收盘", "累计净值": "收盘", "成交量": "成交量", "成交额": "成交量",
    }
    renamed = frame.rename(columns={column: aliases.get(str(column), str(column)) for column in frame.columns})
    # Open-fund responses often contain both unit and accumulated NAV. Both
    # map to 收盘, so keep the first (unit NAV) column only.
    renamed = renamed.loc[:, ~renamed.columns.duplicated()]
    if "日期" not in renamed or "收盘" not in renamed:
        raise ValueError("数据源缺少日期或净值字段")
    for column in ("开盘", "最高", "最低", "成交量"):
        if column not in renamed:
            renamed[column] = renamed["收盘"] if column != "成交量" else 0
    result = renamed[["日期", "开盘", "最高", "最低", "收盘", "成交量"]].copy()
    result["日期"] = pd.to_datetime(result["日期"], errors="coerce")
    for column in ("开盘", "最高", "最低", "收盘", "成交量"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.dropna(subset=["日期", "收盘"]).sort_values("日期").drop_duplicates("日期")
    if result.empty:
        raise ValueError("数据源没有有效历史数据")
    return result.reset_index(drop=True)


def _fetch_fund_etf(symbol: str, start: date, end: date) -> pd.DataFrame:
    import akshare as ak

    frame = ak.fund_etf_hist_em(
        symbol=symbol, period="daily", start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"), adjust="",
    )
    return _rename_history(frame)


def _fetch_open_fund(symbol: str) -> pd.DataFrame:
    import akshare as ak

    endpoint = ak.fund_open_fund_info_em
    parameters = inspect.signature(endpoint).parameters
    kwargs = {"indicator": "单位净值走势"}
    # AkShare changed this argument from symbol to fund in some releases.
    # Select the supported spelling at runtime for Streamlit Cloud versions.
    if "symbol" in parameters:
        kwargs["symbol"] = symbol
    elif "fund" in parameters:
        kwargs["fund"] = symbol
    else:
        frame = endpoint(symbol, "单位净值走势")
        return _rename_history(frame)
    frame = endpoint(**kwargs)
    return _rename_history(frame)


def _fetch_index(symbol: str, start: date, end: date) -> pd.DataFrame:
    import akshare as ak

    frame = ak.index_zh_a_hist(
        symbol=symbol, period="daily", start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
    )
    return _rename_history(frame)


def fetch_fund_data(symbol: str, years: int = 3) -> pd.DataFrame:
    start, end = date.today() - relativedelta(years=years), date.today()
    errors = []
    for loader in (_fetch_fund_etf, _fetch_open_fund):
        try:
            data = loader(symbol, start, end) if loader is _fetch_fund_etf else loader(symbol)
            data.attrs["data_source"] = "AkShare基金历史净值/ETF行情"
            data.attrs["asset_type"] = "基金"
            return data
        except Exception as error:
            errors.append(str(error))
    raise RuntimeError(f"基金 {symbol} 暂无可用历史数据：{' | '.join(errors)}")


def fetch_index_data(symbol: str, years: int = 3) -> pd.DataFrame:
    start, end = date.today() - relativedelta(years=years), date.today()
    try:
        data = _fetch_index(symbol, start, end)
        data.attrs["data_source"] = "AkShare中国指数历史行情"
        data.attrs["asset_type"] = "指数"
        return data
    except Exception as error:
        raise RuntimeError(f"指数 {symbol} 暂无可用历史数据：{error}") from error
