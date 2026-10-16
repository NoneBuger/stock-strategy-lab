#!/usr/bin/env python3
"""Collect a keyless point-in-time market snapshot from Yahoo Finance endpoints."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


USER_AGENT = "Mozilla/5.0 (compatible; TradingAgentsCodexNative/1.0)"
CRYPTO_QUOTES = ("USD", "USDT", "USDC")
COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "LINK": "chainlink",
    "LTC": "litecoin",
    "BCH": "bitcoin-cash",
    "SUI": "sui",
    "TON": "the-open-network",
    "TRX": "tron",
}


def normalize_symbol(raw: str) -> str:
    symbol = raw.strip().upper()
    aliases = {
        "XAUUSD": "GC=F",
        "XAGUSD": "SI=F",
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "JPY=X",
    }
    if symbol in aliases:
        return aliases[symbol]
    compact = symbol.replace("-", "").replace("_", "")
    for quote in CRYPTO_QUOTES:
        if compact.endswith(quote) and len(compact) > len(quote):
            base = compact[: -len(quote)]
            if 2 <= len(base) <= 12:
                return f"{base}-USD"
    return symbol


def is_crypto(symbol: str) -> bool:
    return symbol.endswith("-USD")


def default_benchmark(symbol: str) -> str:
    suffixes = {
        ".NS": "^NSEI",
        ".BO": "^BSESN",
        ".T": "^N225",
        ".HK": "^HSI",
        ".L": "^FTSE",
        ".TO": "^GSPTSE",
        ".AX": "^AXJO",
        ".SS": "000001.SS",
        ".SZ": "399001.SZ",
    }
    for suffix, benchmark in suffixes.items():
        if symbol.endswith(suffix):
            return benchmark
    return "SPY"


def http_json(url: str, timeout: float = 20.0) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        host = urllib.parse.urlparse(url).netloc
        raise RuntimeError(f"{host} returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        host = urllib.parse.urlparse(url).netloc
        raise RuntimeError(f"Could not reach {host}: {exc.reason}") from exc


def fetch_yahoo_chart(
    symbol: str,
    as_of: date,
    *,
    lookback_days: int = 550,
    timeout: float = 20.0,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    start = as_of - timedelta(days=lookback_days)
    end = as_of + timedelta(days=1)
    period1 = int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    period2 = int(datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    encoded = urllib.parse.quote(symbol, safe="")
    query = urllib.parse.urlencode(
        {
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "div,splits",
            "includeAdjustedClose": "true",
        }
    )
    payload = http_json(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?{query}", timeout
    )
    chart = payload.get("chart", {})
    if chart.get("error"):
        raise RuntimeError(f"Yahoo chart error: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise RuntimeError(f"No chart data returned for {symbol}")
    result = results[0]
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    adjusted = ((result.get("indicators") or {}).get("adjclose") or [{}])[0].get(
        "adjclose", []
    )
    bars: list[dict[str, Any]] = []
    for index, timestamp in enumerate(timestamps):
        bar_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
        if bar_date > as_of:
            continue
        close_values = adjusted or quote.get("close") or []
        close = close_values[index] if index < len(close_values) else None
        raw_close_values = quote.get("close") or []
        raw_close = raw_close_values[index] if index < len(raw_close_values) else close
        if close is None:
            continue
        def item(name: str):
            values = quote.get(name) or []
            return values[index] if index < len(values) else None

        bars.append(
            {
                "date": bar_date.isoformat(),
                "open": item("open"),
                "high": item("high"),
                "low": item("low"),
                "close": float(close),
                "raw_close": float(raw_close) if raw_close is not None else float(close),
                "volume": item("volume"),
            }
        )
    if not bars:
        raise RuntimeError(f"No usable bars returned for {symbol} on or before {as_of}")
    meta = result.get("meta") or {}
    meta["_data_source"] = "Yahoo Finance public chart endpoint"
    return meta, bars


def supports_nasdaq(symbol: str) -> bool:
    international_suffixes = (".HK", ".T", ".L", ".TO", ".AX", ".NS", ".BO", ".SS", ".SZ")
    return (
        bool(re.fullmatch(r"[A-Z][A-Z0-9.]{0,9}", symbol))
        and not symbol.endswith(international_suffixes)
        and not is_crypto(symbol)
    )


def parse_nasdaq_number(value: Any) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    if not cleaned or cleaned.lower() in {"n/a", "na", "--"}:
        return None
    return float(cleaned)


def fetch_nasdaq_chart(
    symbol: str,
    as_of: date,
    *,
    lookback_days: int = 550,
    timeout: float = 20.0,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    start = as_of - timedelta(days=lookback_days)
    encoded = urllib.parse.quote(symbol, safe="")
    last_error: Exception | None = None
    for asset_class in ("stocks", "etf"):
        query = urllib.parse.urlencode(
            {
                "assetclass": asset_class,
                "fromdate": start.isoformat(),
                "todate": as_of.isoformat(),
                "limit": 5000,
            }
        )
        try:
            payload = http_json(
                f"https://api.nasdaq.com/api/quote/{encoded}/historical?{query}", timeout
            )
            data = payload.get("data") or {}
            rows = ((data.get("tradesTable") or {}).get("rows") or [])
            bars: list[dict[str, Any]] = []
            for row in rows:
                try:
                    row_date = datetime.strptime(row.get("date", ""), "%m/%d/%Y").date()
                except ValueError:
                    continue
                if row_date > as_of:
                    continue
                close = parse_nasdaq_number(row.get("close"))
                if close is None:
                    continue
                bars.append(
                    {
                        "date": row_date.isoformat(),
                        "open": parse_nasdaq_number(row.get("open")),
                        "high": parse_nasdaq_number(row.get("high")),
                        "low": parse_nasdaq_number(row.get("low")),
                        "close": close,
                        "raw_close": close,
                        "volume": parse_nasdaq_number(row.get("volume")),
                    }
                )
            bars.sort(key=lambda item: item["date"])
            if bars:
                return (
                    {
                        "symbol": data.get("symbol") or symbol,
                        "instrumentType": asset_class.upper(),
                        "currency": "USD",
                        "fullExchangeName": "Nasdaq public historical endpoint",
                        "_data_source": f"Nasdaq public historical endpoint ({asset_class})",
                    },
                    bars,
                )
        except Exception as exc:
            last_error = exc
    if last_error:
        raise RuntimeError(f"Nasdaq fallback failed for {symbol}: {last_error}") from last_error
    raise RuntimeError(f"Nasdaq returned no historical rows for {symbol}")


def fetch_coingecko_chart(
    symbol: str,
    as_of: date,
    *,
    lookback_days: int = 550,
    timeout: float = 20.0,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    base = symbol.removesuffix("-USD")
    coin_id = COINGECKO_IDS.get(base)
    if not coin_id:
        raise RuntimeError(f"CoinGecko mapping is not configured for {base}")
    # CoinGecko's keyless public range endpoint is limited to roughly one year.
    start = as_of - timedelta(days=min(lookback_days, 364))
    end = as_of + timedelta(days=1)
    query = urllib.parse.urlencode(
        {
            "vs_currency": "usd",
            "from": int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp()),
            "to": int(datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc).timestamp()),
        }
    )
    payload = http_json(
        f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range?{query}",
        timeout,
    )
    grouped: dict[str, dict[str, Any]] = {}
    volumes_by_timestamp = {int(item[0]): item[1] for item in payload.get("total_volumes") or []}
    for timestamp_ms, price in payload.get("prices") or []:
        timestamp_ms = int(timestamp_ms)
        bar_date = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).date()
        if bar_date > as_of:
            continue
        key = bar_date.isoformat()
        value = float(price)
        current = grouped.get(key)
        if current is None:
            grouped[key] = {
                "date": key,
                "open": value,
                "high": value,
                "low": value,
                "close": value,
                "raw_close": value,
                "volume": volumes_by_timestamp.get(timestamp_ms),
            }
        else:
            current["high"] = max(current["high"], value)
            current["low"] = min(current["low"], value)
            current["close"] = value
            current["raw_close"] = value
            if timestamp_ms in volumes_by_timestamp:
                current["volume"] = volumes_by_timestamp[timestamp_ms]
    bars = [grouped[key] for key in sorted(grouped)]
    if not bars:
        raise RuntimeError(f"CoinGecko returned no usable data for {symbol}")
    return (
        {
            "symbol": symbol,
            "longName": coin_id,
            "instrumentType": "CRYPTOCURRENCY",
            "currency": "USD",
            "fullExchangeName": "CoinGecko aggregate market data",
            "_data_source": "CoinGecko public market-chart endpoint",
        },
        bars,
    )


def fetch_chart(
    symbol: str,
    as_of: date,
    *,
    lookback_days: int = 550,
    timeout: float = 20.0,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    errors: list[str] = []
    if is_crypto(symbol):
        try:
            return fetch_coingecko_chart(
                symbol, as_of, lookback_days=lookback_days, timeout=timeout
            )
        except RuntimeError as exc:
            errors.append(str(exc))
    if supports_nasdaq(symbol):
        try:
            return fetch_nasdaq_chart(
                symbol, as_of, lookback_days=lookback_days, timeout=timeout
            )
        except RuntimeError as exc:
            errors.append(str(exc))
    try:
        return fetch_yahoo_chart(symbol, as_of, lookback_days=lookback_days, timeout=timeout)
    except RuntimeError as exc:
        errors.append(str(exc))
    raise RuntimeError("; ".join(errors))


def simple_return(closes: list[float], periods: int) -> float | None:
    if len(closes) <= periods or closes[-periods - 1] == 0:
        return None
    return closes[-1] / closes[-periods - 1] - 1.0


def sma(values: list[float], periods: int) -> float | None:
    if len(values) < periods:
        return None
    return statistics.fmean(values[-periods:])


def ema(values: list[float], periods: int) -> float | None:
    if len(values) < periods:
        return None
    multiplier = 2.0 / (periods + 1.0)
    current = statistics.fmean(values[:periods])
    for value in values[periods:]:
        current = (value - current) * multiplier + current
    return current


def rsi(values: list[float], periods: int = 14) -> float | None:
    if len(values) <= periods:
        return None
    changes = [values[i] - values[i - 1] for i in range(len(values) - periods, len(values))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    avg_gain = statistics.fmean(gains)
    avg_loss = statistics.fmean(losses)
    if avg_loss == 0:
        return 100.0
    relative_strength = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))


def annualized_volatility(values: list[float], periods: int = 20) -> float | None:
    if len(values) <= periods:
        return None
    returns = [
        math.log(values[i] / values[i - 1])
        for i in range(len(values) - periods, len(values))
        if values[i - 1] > 0 and values[i] > 0
    ]
    if len(returns) < 2:
        return None
    return statistics.stdev(returns) * math.sqrt(252.0)


def atr(bars: list[dict[str, Any]], periods: int = 14) -> float | None:
    if len(bars) <= periods:
        return None
    ranges: list[float] = []
    for index in range(len(bars) - periods, len(bars)):
        high = bars[index].get("high")
        low = bars[index].get("low")
        previous = bars[index - 1]["raw_close"]
        if high is None or low is None:
            continue
        ranges.append(max(high - low, abs(high - previous), abs(low - previous)))
    return statistics.fmean(ranges) if ranges else None


def max_drawdown(values: list[float], periods: int = 252) -> float | None:
    selected = values[-periods:]
    if not selected:
        return None
    peak = selected[0]
    worst = 0.0
    for value in selected:
        peak = max(peak, value)
        if peak:
            worst = min(worst, value / peak - 1.0)
    return worst


def summarize_series(meta: dict[str, Any], bars: list[dict[str, Any]]) -> dict[str, Any]:
    closes = [bar["close"] for bar in bars]
    raw_closes = [bar["raw_close"] for bar in bars]
    volumes = [float(bar["volume"]) for bar in bars if bar.get("volume") is not None]
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    macd = ema12 - ema26 if ema12 is not None and ema26 is not None else None
    recent_year = closes[-252:]
    avg_volume_20 = statistics.fmean(volumes[-20:]) if len(volumes) >= 20 else None
    latest_volume = float(bars[-1]["volume"]) if bars[-1].get("volume") is not None else None
    returns = {str(period): simple_return(closes, period) for period in (1, 5, 20, 60, 252)}
    return {
        "name": meta.get("longName") or meta.get("shortName") or meta.get("symbol"),
        "instrument_type": meta.get("instrumentType"),
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
        "currency": meta.get("currency"),
        "timezone": meta.get("exchangeTimezoneName"),
        "first_bar": bars[0]["date"],
        "as_of_bar": bars[-1]["date"],
        "bar_count": len(bars),
        "close": closes[-1],
        "returns": returns,
        "sma": {str(period): sma(closes, period) for period in (20, 50, 200)},
        "macd": macd,
        "rsi_14": rsi(closes, 14),
        "atr_14": atr(bars, 14),
        "annualized_volatility_20": annualized_volatility(closes, 20),
        "max_drawdown_252": max_drawdown(closes, 252),
        "high_52w": max(recent_year) if recent_year else None,
        "low_52w": min(recent_year) if recent_year else None,
        "latest_volume": latest_volume,
        "average_volume_20": avg_volume_20,
        "volume_ratio_20": (
            latest_volume / avg_volume_20
            if latest_volume is not None and avg_volume_20 not in (None, 0)
            else None
        ),
        "recent_bars": bars[-10:],
        "raw_close": raw_closes[-1],
    }


def fetch_news(symbol: str, as_of: date, count: int, timeout: float) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    query = urllib.parse.urlencode(
        {
            "q": symbol,
            "quotesCount": 1,
            "newsCount": count,
            "enableFuzzyQuery": "false",
        }
    )
    try:
        payload = http_json(f"https://query1.finance.yahoo.com/v1/finance/search?{query}", timeout)
    except RuntimeError:
        return []
    news: list[dict[str, Any]] = []
    for item in payload.get("news") or []:
        published = item.get("providerPublishTime")
        published_date = (
            datetime.fromtimestamp(published, tz=timezone.utc).date() if published else None
        )
        if published_date and published_date > as_of:
            continue
        news.append(
            {
                "title": item.get("title"),
                "publisher": item.get("publisher"),
                "published_at": published_date.isoformat() if published_date else None,
                "url": item.get("link") or item.get("canonicalUrl", {}).get("url"),
            }
        )
    return news


def build_snapshot(
    requested_symbol: str,
    as_of: date,
    *,
    benchmark: str | None = None,
    lookback_days: int = 550,
    news_count: int = 0,
    timeout: float = 20.0,
) -> dict[str, Any]:
    symbol = normalize_symbol(requested_symbol)
    benchmark_symbol = normalize_symbol(benchmark) if benchmark else default_benchmark(symbol)
    meta, bars = fetch_chart(symbol, as_of, lookback_days=lookback_days, timeout=timeout)
    summary = summarize_series(meta, bars)
    benchmark_meta, benchmark_bars = fetch_chart(
        benchmark_symbol, as_of, lookback_days=lookback_days, timeout=timeout
    )
    benchmark_summary = summarize_series(benchmark_meta, benchmark_bars)
    alpha: dict[str, float | None] = {}
    for period in (5, 20, 60, 252):
        own = summary["returns"][str(period)]
        base = benchmark_summary["returns"][str(period)]
        alpha[str(period)] = own - base if own is not None and base is not None else None
    warnings: list[str] = []
    if symbol != requested_symbol.strip().upper():
        warnings.append(
            f"Normalized {requested_symbol} to {symbol} for Yahoo Finance compatibility."
        )
    market_source = meta.get("_data_source")
    benchmark_source = benchmark_meta.get("_data_source")
    if market_source != benchmark_source:
        warnings.append(
            f"Market and benchmark used different public sources: {market_source}; {benchmark_source}."
        )
    return {
        "source": {
            "market": market_source,
            "benchmark": benchmark_source,
            "news": "Yahoo Finance public search endpoint" if news_count else None,
            "credentials": "none",
        },
        "retrieved_at": datetime.now(tz=timezone.utc).isoformat(),
        "analysis_date": as_of.isoformat(),
        "requested_symbol": requested_symbol,
        "symbol": symbol,
        "asset_type": "crypto" if is_crypto(symbol) else "stock",
        "benchmark_symbol": benchmark_symbol,
        "warnings": warnings,
        "market": summary,
        "benchmark": {
            "name": benchmark_summary.get("name"),
            "symbol": benchmark_symbol,
            "returns": benchmark_summary["returns"],
        },
        "alpha": alpha,
        "news": fetch_news(symbol, as_of, news_count, timeout),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker")
    parser.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD cutoff date")
    parser.add_argument("--benchmark")
    parser.add_argument("--lookback-days", type=int, default=550)
    parser.add_argument(
        "--news-count",
        type=int,
        default=0,
        help="Optional Yahoo headline count; Codex web research is the default news source.",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        as_of = datetime.strptime(args.date, "%Y-%m-%d").date()
        if as_of > date.today():
            raise ValueError("analysis date cannot be in the future")
        if args.lookback_days < 30:
            raise ValueError("lookback-days must be at least 30")
        snapshot = build_snapshot(
            args.ticker,
            as_of,
            benchmark=args.benchmark,
            lookback_days=args.lookback_days,
            news_count=max(args.news_count, 0),
            timeout=args.timeout,
        )
        if args.output:
            write_json(args.output.expanduser().resolve(), snapshot)
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"status": "error", "error_type": type(exc).__name__, "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
