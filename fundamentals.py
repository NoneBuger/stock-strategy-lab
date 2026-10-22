"""Best-effort A-share F10 snapshot for screening and risk warnings."""

from __future__ import annotations

import os
import json
import re
import time
import urllib.parse
import urllib.request
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


def _eastmoney_code(symbol: str) -> str:
    return f"SH{symbol}" if symbol.startswith(("5", "6", "9")) else f"SZ{symbol}"


def _public_json(url: str, timeout: int = 8, retries: int = 1) -> Any:
    """Read a public JSON/JSONP endpoint with bounded retry and backoff."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; stock-strategy-lab/1.0)",
                    "Accept": "application/json,text/plain,*/*",
                    "Referer": "https://quote.eastmoney.com/",
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text = response.read().decode("utf-8-sig")
            # Some public endpoints return JSONP even without a callback parameter.
            text = (
                re.sub(r"^[^(]*\(", "", text).rsplit(")", 1)[0]
                if not text.lstrip().startswith(("{", "["))
                else text
            )
            return json.loads(text)
        except Exception as error:
            last_error = error
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"公开接口请求失败：{last_error}") from last_error


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        records: list[dict[str, Any]] = []
        if all(not isinstance(item, (dict, list)) for item in value.values()):
            records.append(value)
        for child in value.values():
            records.extend(_records(child))
        return records
    if isinstance(value, list):
        records = []
        for child in value:
            records.extend(_records(child))
        return records
    return []


def _find_in_records(records: list[dict[str, Any]], *keys: str) -> Any:
    aliases = {key.lower() for key in keys}
    for record in records:
        for key, value in record.items():
            normalized = str(key).replace("_", "").replace(" ", "").lower()
            if normalized in aliases and value not in (None, "", "-", "--"):
                return value
    return None


def _from_eastmoney(symbol: str) -> dict[str, Any]:
    """Read public Eastmoney quote/company/financial endpoints without a key."""
    secid = f"1.{symbol}" if symbol.startswith(("5", "6", "9")) else f"0.{symbol}"
    quote_url = (
        "https://push2.eastmoney.com/api/qt/stock/get?"
        + urllib.parse.urlencode({"secid": secid, "fields": "f57,f58,f116,f117,f162,f167"})
    )
    quote_payload = _public_json(quote_url)
    quote = quote_payload.get("data") if isinstance(quote_payload, dict) else None
    if not isinstance(quote, dict):
        raise ValueError("东方财富行情接口未返回股票数据")

    em_code = _eastmoney_code(symbol)
    industry = None
    name = quote.get("f58")
    try:
        survey_url = f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax?code={em_code}"
        survey_records = _records(_public_json(survey_url))
        industry = _find_in_records(survey_records, "INDUSTRYNAME", "INDUSTRY_NAME", "行业", "所属行业")
        name = name or _find_in_records(survey_records, "SECURITYNAMEABBR", "SECURITY_NAME_ABBR", "股票简称")
    except Exception:
        # Quote data remains useful when the F10 company page is unavailable.
        pass

    # Financial data is supplementary: an unavailable financial endpoint does
    # not invalidate the quote/company snapshot.
    roe = None
    net_profit = None
    try:
        finance_url = f"https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew?type=0&code={em_code}"
        finance_records = _records(_public_json(finance_url, timeout=15))
        roe = _number(_find_in_records(finance_records, "ROEJQ", "ROE", "净资产收益率"))
        net_profit = _number(_find_in_records(finance_records, "归母净利润", "归属于母公司股东的净利润", "净利润"))
    except Exception:
        pass
    return {
        "name": name,
        "industry": industry,
        "market": "上海证券交易所" if secid.startswith("1.") else "深圳证券交易所",
        "pe_ttm": _number(quote.get("f162")),
        "pb": _number(quote.get("f167")),
        "market_cap": quote.get("f116"),
        "circulating_market_cap": quote.get("f117"),
        "roe": roe,
        "net_profit": net_profit,
        "source": "东方财富公开行情/公司概况/财务接口",
    }


def _from_sina(symbol: str) -> dict[str, Any]:
    """Use Sina's public quote endpoint as a lightweight name fallback."""
    market = "sh" if symbol.startswith(("5", "6", "9")) else "sz"
    url = f"https://hq.sinajs.cn/list={market}{symbol}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        text = response.read().decode("gbk", errors="replace")
    match = re.search(r'="([^,]*)', text)
    if not match or not match.group(1).strip():
        raise ValueError("新浪公开行情未返回股票名称")
    return {"name": match.group(1).strip(), "source": "新浪公开行情名称接口"}


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


def fetch_fundamental_snapshot(symbol: str, fallback_name: str | None = None) -> dict[str, Any]:
    """Return F10 fields and explicit screening warnings; never invent missing values."""
    errors: list[str] = []
    usable_fallback_name = (
        fallback_name
        if fallback_name and "名称待数据源返回" not in str(fallback_name)
        else None
    )
    snapshot: dict[str, Any] = {
        "symbol": symbol, "name": usable_fallback_name, "roe": None, "net_profit": None
    }
    sources: list[str] = []
    loaders = [_from_tushare, _from_akshare, _from_eastmoney]
    if not snapshot.get("name"):
        loaders.append(_from_sina)
    for loader in loaders:
        try:
            result = loader(symbol)
            sources.append(str(result.get("source", loader.__name__)))
            for key, value in result.items():
                if key == "source":
                    continue
                if snapshot.get(key) in (None, "") and value not in (None, ""):
                    snapshot[key] = value
        except Exception as exc:
            errors.append(str(exc))
    if not sources and usable_fallback_name:
        sources.append("搜索结果名称兜底")
    if not sources:
        raise RuntimeError("；".join(errors) or "暂无基本面数据")
    snapshot["source"] = " + ".join(sources)
    if not snapshot.get("name") and usable_fallback_name:
        snapshot["name"] = usable_fallback_name

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
        if error and "未配置" not in error:
            warnings.append(f"部分数据源不可用：{error}")
    missing_fields = [
        label for key, label in (
            ("industry", "行业"),
            ("pe_ttm", "市盈率"),
            ("roe", "ROE"),
            ("net_profit", "归母净利润"),
        ) if snapshot.get(key) in (None, "")
    ]
    if missing_fields:
        warnings.append(f"部分F10字段暂无有效数据：{'、'.join(missing_fields)}")
    snapshot["warnings"] = warnings
    snapshot["source_errors"] = errors
    snapshot["data_status"] = "完整数据" if not missing_fields else "部分数据"
    snapshot["is_loss"] = bool(net_profit is not None and net_profit < 0)
    return snapshot
