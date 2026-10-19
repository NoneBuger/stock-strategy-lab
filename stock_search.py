"""A-share name/code search isolated from the historical data fetcher."""

from __future__ import annotations

import os


def search_stock_candidates(query: str, limit: int = 20) -> list[dict[str, str]]:
    """Fuzzy-search A-share code/name pairs from available providers."""
    query = str(query).strip().lower()
    if not query:
        return []

    candidates: dict[str, str] = {}
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

    return [
        {"code": code, "name": name}
        for code, name in sorted(candidates.items())
    ][: max(1, limit)]
