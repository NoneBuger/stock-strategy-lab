"""Public AkShare adapters for Chinese funds, ETFs and broad-market indexes."""

from __future__ import annotations

from datetime import date
import inspect
import json
import urllib.parse
import urllib.request
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


def _fetch_index_eastmoney(symbol: str, start: date, end: date) -> pd.DataFrame:
    """Fetch index candles from Eastmoney's public history endpoint."""
    market = "1" if symbol.startswith(("0", "5", "6", "8", "9")) and not symbol.startswith(("399", "899")) else "0"
    query = urllib.parse.urlencode({
        "secid": f"{market}.{symbol}",
        "klt": "101",
        "fqt": "0",
        "beg": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
    })
    url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?{query}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; stock-strategy-lab/1.0)"},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8-sig"))
    data = payload.get("data") if isinstance(payload, dict) else None
    klines = data.get("klines") if isinstance(data, dict) else None
    if not klines:
        raise ValueError("东方财富未返回指数K线")
    rows = []
    for line in klines:
        fields = str(line).split(",")
        if len(fields) < 6:
            continue
        rows.append({
            "日期": fields[0], "开盘": fields[1], "收盘": fields[2],
            "最高": fields[3], "最低": fields[4], "成交量": fields[5],
        })
    return _rename_history(pd.DataFrame(rows))


def _fetch_index_baostock(symbol: str, start: date, end: date) -> pd.DataFrame:
    """Optional no-token fallback for index history."""
    import baostock as bs

    market = "sh" if symbol.startswith(("0", "5", "6", "8", "9")) and not symbol.startswith(("399", "899")) else "sz"
    login = bs.login()
    if getattr(login, "error_code", "0") != "0":
        raise RuntimeError(f"Baostock登录失败：{getattr(login, 'error_msg', '未知错误')}")
    try:
        result = bs.query_history_k_data_plus(
            f"{market}.{symbol}", "date,open,high,low,close,volume",
            start_date=start.isoformat(), end_date=end.isoformat(),
            frequency="d", adjustflag="3",
        )
        if getattr(result, "error_code", "0") != "0":
            raise RuntimeError(f"Baostock指数查询失败：{getattr(result, 'error_msg', '未知错误')}")
        frame = result.get_data()
    finally:
        bs.logout()
    return _rename_history(frame.rename(columns={
        "date": "日期", "open": "开盘", "high": "最高", "low": "最低",
        "close": "收盘", "volume": "成交量",
    }))


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
    errors = []
    for source, loader in (
        ("东方财富公开指数K线", _fetch_index_eastmoney),
        ("Baostock指数历史行情", _fetch_index_baostock),
        ("AkShare中国指数历史行情", _fetch_index),
    ):
        try:
            data = loader(symbol, start, end)
            data.attrs["data_source"] = source
            data.attrs["asset_type"] = "指数"
            return data
        except Exception as error:
            errors.append(f"{source}: {error}")
    raise RuntimeError(f"指数 {symbol} 暂无可用历史数据：{' | '.join(errors)}")
