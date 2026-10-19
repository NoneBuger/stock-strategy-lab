"""A-share name/code search isolated from the historical data fetcher."""

from __future__ import annotations

import os

from stock_catalog import OFFLINE_STOCK_NAMES


def search_stock_candidates(query: str, limit: int = 20) -> list[dict[str, str]]:
    """Fuzzy-search A-share code/name pairs from available providers."""
    query = str(query).strip().lower()
    if not query:
        return []

    # Keep the controls usable when a quote provider is temporarily
    # unavailable. Historical data loading will still report its own error.
    if query.isdigit() and len(query) == 6:
        code_fallback = query
    else:
        code_fallback = None

    candidates: dict[str, str] = {}
    for code, name in OFFLINE_STOCK_NAMES.items():
        if query in code.lower() or query in name.lower():
            candidates[code] = name
    try:
        import akshare as ak

        frame = ak.stock_info_a_code_name()
        code_col = next((col for col in ("code", "代码") if col in frame.columns), None)
        name_col = next((col for col in ("name", "名称") if col in frame.columns), None)
        if code_col and name_col:
            for _, row in frame.iterrows():
                code, name = str(row[code_col]).zfill(6), str(row[name_col])
                if query in code.lower() or query in name.lower():
                    candidates[code] = name
    except Exception:
        pass

    token = os.getenv("TUSHARE_TOKEN")
    if token:
        try:
            import tushare as ts

            basic = ts.pro_api(token).stock_basic(
                exchange="", list_status="L", fields="ts_code,symbol,name"
            )
            for _, row in basic.iterrows():
                code, name = str(row["symbol"]).zfill(6), str(row["name"])
                if query in code.lower() or query in name.lower():
                    candidates[code] = name
        except Exception:
            pass

    results = [
        {"code": code, "name": name}
        for code, name in sorted(candidates.items())
    ][: max(1, limit)]
    if not results and code_fallback:
        return [{"code": code_fallback, "name": "代码匹配（名称待数据源返回）"}]
    return results
