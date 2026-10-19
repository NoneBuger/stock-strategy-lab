"""Best-effort A-share F10 snapshot for screening and risk warnings."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import pandas as pd


def _number(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).replace(",", "").replace("%", "").strip()
    multiplier = 1
    if text.endswith("亿"):
        multiplier, text = 100_000_000, text[:-1]
    elif text.endswith("万"):
        multiplier, text = 10_000, text[:-1]
    try:
        return float(text) * multiplier
    except (TypeError, ValueError):
        return None


def _pick(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if mapping.get(key) not in (None, "", "-", "--"):
            return mapping[key]
    return None


def _code_for_tushare(symbol: str) -> str:
    return f"{symbol}.SH" if symbol.startswith(("5", "6", "9")) else f"{symbol}.SZ"


def _from_akshare(symbol: str) -> dict[str, Any]:
    import akshare as ak

    frame = ak.stock_individual_info_em(symbol=symbol)
    info = dict(zip(frame["item"].astype(str), frame["value"]))
    return {
        "name": _pick(info, "股票简称", "名称"),
        "industry": _pick(info, "行业", "所属行业"),
        "market": _pick(info, "市场", "板块"),
        "list_date": _pick(info, "上市时间", "上市日期"),
        "pe_ttm": _number(_pick(info, "市盈率-动态", "市盈率")),
        "pb": _number(_pick(info, "市净率")),
        "market_cap": _pick(info, "总市值"),
        "circulating_market_cap": _pick(info, "流通市值"),
        "source": "AkShare stock_individual_info_em",
    }


def _from_tushare(symbol: str) -> dict[str, Any]:
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        raise RuntimeError("TUSHARE_TOKEN 未配置")
    import tushare as ts

    ts_code = _code_for_tushare(symbol)
    pro = ts.pro_api(token)
    basic = pro.stock_basic(ts_code=ts_code, fields="ts_code,name,industry,market,list_date")
    if basic.empty:
        raise ValueError("Tushare 未返回股票基本资料")
    row = basic.iloc[0].to_dict()
    end = date.today()
    daily = pd.DataFrame()
    for days in (0, 5, 15):
        daily = pro.daily_basic(
            ts_code=ts_code,
            start_date=(end - timedelta(days=days + 10)).strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            fields="trade_date,pe_ttm,pb,total_mv,circ_mv",
        )
        if not daily.empty:
            break
    quote = daily.sort_values("trade_date").iloc[-1].to_dict() if not daily.empty else {}
    indicator = pro.fina_indicator(ts_code=ts_code, fields="end_date,roe")
    roe = None if indicator.empty else _number(indicator.sort_values("end_date").iloc[-1].get("roe"))
    income = pro.income(ts_code=ts_code, fields="end_date,n_income_attr_p")
    net_profit = None if income.empty else _number(income.sort_values("end_date").iloc[-1].get("n_income_attr_p"))
    return {
        "name": row.get("name"), "industry": row.get("industry"), "market": row.get("market"),
        "list_date": row.get("list_date"), "pe_ttm": _number(quote.get("pe_ttm")),
        "pb": _number(quote.get("pb")), "market_cap": quote.get("total_mv"),
        "circulating_market_cap": quote.get("circ_mv"), "roe": roe,
        "net_profit": net_profit, "source": "Tushare stock_basic/daily_basic/fina_indicator/income",
    }


def fetch_fundamental_snapshot(symbol: str) -> dict[str, Any]:
    """Return F10 fields and explicit screening warnings; never invent missing values."""
    errors: list[str] = []
    snapshot: dict[str, Any] = {"symbol": symbol, "roe": None, "net_profit": None}
    for loader in (_from_tushare, _from_akshare):
        try:
            snapshot.update(loader(symbol))
            break
        except Exception as exc:
            errors.append(str(exc))
    if not snapshot.get("source"):
        raise RuntimeError("；".join(errors) or "暂无基本面数据")

    warnings: list[str] = []
    pe = snapshot.get("pe_ttm")
    roe = snapshot.get("roe")
    net_profit = snapshot.get("net_profit")
    if net_profit is not None and net_profit < 0:
        warnings.append("最近可用归母净利润为负，存在亏损风险")
    if pe is not None and pe <= 0:
        warnings.append("市盈率为负或无效，不能按普通PE估值")
    elif pe is not None and pe > 50:
        warnings.append("动态市盈率高于50，估值偏高，需防止追高")
    if roe is not None and roe < 10:
        warnings.append("ROE低于10%，盈利质量或资本回报偏弱")
    for error in errors:
        if error:
            warnings.append(f"部分数据源不可用：{error}")
    snapshot["warnings"] = warnings
    snapshot["is_loss"] = bool(net_profit is not None and net_profit < 0)
    return snapshot
