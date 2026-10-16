"""AKQuant backtest with Ashare MCP fundamental filters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from indicators import calculate_sma


def calculate_sharpe_ratio(
    daily_returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Calculate the annualized Sharpe ratio from daily strategy returns."""
    if not isinstance(daily_returns, pd.Series):
        raise TypeError("daily_returns 必须是 pandas.Series")
    if periods_per_year < 1:
        raise ValueError("periods_per_year 必须是大于 0 的整数")
    if risk_free_rate <= -1:
        raise ValueError("risk_free_rate 必须大于 -1")

    returns = pd.to_numeric(daily_returns, errors="coerce").dropna()
    if returns.empty:
        raise ValueError("daily_returns 不包含有效收益率")

    daily_risk_free_rate = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    excess_returns = returns - daily_risk_free_rate
    volatility = excess_returns.std(ddof=1)
    if pd.isna(volatility) or volatility == 0:
        return 0.0
    return float(excess_returns.mean() / volatility * periods_per_year**0.5)


def _load_ashare_mcp_tools() -> tuple[Any, Any, Any]:
    """Load the Ashare MCP tool wrappers lazily."""
    try:
        from ashare_mcp.tools.financial import get_financial_report
        from ashare_mcp.tools.market import get_realtime_quote, get_stock_info
    except ImportError as error:
        raise RuntimeError(
            "基本面过滤需要安装 ashare-mcp；请参考 requirements.txt 或配置 Ashare MCP 服务。"
        ) from error
    return get_realtime_quote, get_stock_info, get_financial_report


def _records(payload: Any) -> list[dict[str, Any]]:
    """Normalize an Ashare MCP response to a list of dictionaries."""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("data", payload)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
        if isinstance(rows, dict):
            return [rows]
    return []


def _number(row: Mapping[str, Any], *names: str) -> float | None:
    """Read the first numeric value from alternative MCP field names."""
    for name in names:
        value = row.get(name)
        if value is None or value == "":
            continue
        try:
            if isinstance(value, str):
                value = value.replace(",", "").replace("%", "").strip()
            number = float(value)
            if pd.notna(number):
                return number
        except (TypeError, ValueError):
            continue
    return None


def fetch_fundamental_metrics(
    symbol: str,
    price_data: pd.DataFrame,
    price_column: str = "收盘",
) -> dict[str, Any]:
    """Fetch ROE and PE percentile inputs through Ashare MCP.

    PE percentile is estimated from the supplied historical prices and the
    latest MCP-reported EPS. The approximation is reported in the result.
    """
    get_quote, get_stock_info, get_financial_report = _load_ashare_mcp_tools()

    quote_rows = _records(get_quote([symbol]))
    quote = quote_rows[0] if quote_rows else {}
    info_rows = _records(get_stock_info(symbol))
    info = info_rows[0] if info_rows else {}
    income_rows = _records(get_financial_report(symbol, "income", limit=1))
    balance_rows = _records(get_financial_report(symbol, "balance", limit=1))
    income = income_rows[0] if income_rows else {}
    balance = balance_rows[0] if balance_rows else {}

    net_profit = _number(
        income,
        "net_profit",
        "归属于母公司股东的净利润",
        "净利润",
    )
    equity = _number(
        balance,
        "total_equity",
        "owners_equity",
        "shareholders_equity",
        "所有者权益合计",
        "归属于母公司股东权益合计",
    )
    shares = _number(info, "total_shares", "总股本")
    if net_profit is None or equity is None or equity <= 0:
        raise ValueError("Ashare MCP 返回的数据不足以计算 ROE")

    roe = net_profit / equity * 100
    eps = net_profit / shares if shares and shares > 0 else None
    current_pe = _number(quote, "pe_ttm", "pe")
    prices = pd.to_numeric(price_data[price_column], errors="coerce").dropna()
    if current_pe is None and eps and eps > 0 and not prices.empty:
        current_pe = float(prices.iloc[-1] / eps)

    historical_pe = prices / eps if eps and eps > 0 else pd.Series(dtype=float)
    historical_pe = historical_pe.replace([float("inf"), -float("inf")], pd.NA).dropna()
    historical_pe = historical_pe[historical_pe > 0]
    pe_percentile = (
        float((historical_pe <= current_pe).mean() * 100)
        if current_pe is not None and not historical_pe.empty
        else None
    )
    return {
        "symbol": symbol,
        "roe": float(roe),
        "pe": current_pe,
        "pe_percentile": pe_percentile,
        "eps": eps,
        "source": "ashare-mcp",
        "pe_percentile_note": "基于回测区间价格与最新MCP财报EPS估算",
    }


def passes_fundamental_filters(
    metrics: Mapping[str, Any],
    min_roe: float = 10.0,
    max_pe_percentile: float = 50.0,
) -> bool:
    """Return whether ROE and PE percentile pass the strategy filters."""
    roe = _number(metrics, "roe")
    pe_percentile = _number(metrics, "pe_percentile")
    return (
        roe is not None
        and pe_percentile is not None
        and roe >= min_roe
        and pe_percentile <= max_pe_percentile
    )


def _engine_data(
    data: pd.DataFrame,
    symbol: str,
    short_window: int,
    long_window: int,
    price_column: str,
    fundamental_pass: bool,
) -> pd.DataFrame:
    """Translate the project's Chinese-column data into AKQuant's schema."""
    required = {"日期", "开盘", "最高", "最低", "收盘", "成交量"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"DataFrame 缺少 AKQuant 所需列: {sorted(missing)}")

    engine = data.rename(
        columns={
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
        }
    ).copy()
    engine["date"] = pd.to_datetime(engine["date"])
    engine["symbol"] = symbol
    engine["short_sma"] = calculate_sma(data, short_window, price_column).to_numpy()
    engine["long_sma"] = calculate_sma(data, long_window, price_column).to_numpy()
    engine["fundamental_pass"] = float(fundamental_pass)
    return engine[[
        "date", "open", "high", "low", "close", "volume", "symbol",
        "short_sma", "long_sma", "fundamental_pass",
    ]].dropna(subset=["open", "high", "low", "close", "volume"])


def run_dual_ma_backtest(
    data: pd.DataFrame,
    symbol: str = "000001",
    short_window: int = 20,
    long_window: int = 60,
    price_column: str = "收盘",
    initial_cash: float = 100_000.0,
    min_roe: float = 10.0,
    max_pe_percentile: float = 50.0,
    fundamental_metrics: Mapping[str, Any] | None = None,
) -> tuple[pd.DataFrame, float]:
    """Run a T+1 AKQuant dual-MA strategy with fundamental filters.

    The strategy opens a 95% long position only when the short SMA is above
    the long SMA and the Ashare MCP ROE/PE-percentile filters pass. Supplying
    ``fundamental_metrics`` is useful for offline tests; production callers
    should leave it unset so metrics are fetched through Ashare MCP.
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data 必须是 pandas.DataFrame")
    if not isinstance(short_window, int) or short_window < 1:
        raise ValueError("short_window 必须是大于 0 的整数")
    if not isinstance(long_window, int) or long_window <= short_window:
        raise ValueError("long_window 必须大于 short_window")
    if price_column not in data.columns:
        raise ValueError(f"DataFrame 中不存在价格列: {price_column}")

    metrics = dict(
        fundamental_metrics
        or fetch_fundamental_metrics(symbol, data, price_column)
    )
    fundamental_pass = passes_fundamental_filters(
        metrics, min_roe=min_roe, max_pe_percentile=max_pe_percentile
    )
    engine_data = _engine_data(
        data, symbol, short_window, long_window, price_column, fundamental_pass
    )

    try:
        import akquant as aq
    except ImportError as error:
        raise RuntimeError("回测需要安装 akquant>=0.3.66") from error

    class DualMovingAverageStrategy(aq.Strategy):
        def on_bar(self, bar: Any) -> None:
            short_sma = bar.extra.get("short_sma", float("nan"))
            long_sma = bar.extra.get("long_sma", float("nan"))
            allowed = bar.extra.get("fundamental_pass", 0.0) >= 1.0
            if (
                allowed
                and pd.notna(short_sma)
                and pd.notna(long_sma)
                and short_sma > long_sma
            ):
                self.order_target_percent(target_percent=0.95, symbol=bar.symbol)
            else:
                self.close_position(symbol=bar.symbol)

    start_time = engine_data["date"].min().strftime("%Y%m%d")
    end_time = engine_data["date"].max().strftime("%Y%m%d")
    ak_result = aq.run_backtest(
        data=engine_data,
        strategy=DualMovingAverageStrategy,
        initial_cash=initial_cash,
        commission_rate=0.0003,
        stamp_tax_rate=0.001,
        transfer_fee_rate=0.00001,
        min_commission=5.0,
        lot_size=100,
        t_plus_one=True,
        symbols=symbol,
        start_time=start_time,
        end_time=end_time,
        show_progress=False,
    )

    details = data.copy()
    details["短期均线"] = calculate_sma(details, short_window, price_column)
    details["长期均线"] = calculate_sma(details, long_window, price_column)
    details["基本面过滤通过"] = fundamental_pass
    details["持仓"] = (
        (details["短期均线"] > details["长期均线"]) & fundamental_pass
    ).astype(int)
    details["交易信号"] = details["持仓"].diff().map(
        {1.0: "买入", -1.0: "卖出"}
    ).fillna("持有/无信号")

    equity = pd.Series(ak_result.equity_curve, dtype=float)
    equity.index = pd.to_datetime(equity.index).tz_localize(None)
    dates = pd.to_datetime(details["日期"])
    aligned_equity = equity.reindex(dates).ffill().fillna(initial_cash)
    details["策略日收益率"] = aligned_equity.pct_change().fillna(0.0).to_numpy()
    details["策略累计收益率"] = (
        (aligned_equity / initial_cash) - 1.0
    ).to_numpy()
    details.attrs["fundamental_metrics"] = dict(metrics)
    details.attrs["akquant_metrics"] = {
        "total_return_pct": float(ak_result.metrics.total_return_pct),
        "sharpe_ratio": float(ak_result.metrics.sharpe_ratio),
    }
    cumulative_return = float(details["策略累计收益率"].iloc[-1])
    return details, cumulative_return


if __name__ == "__main__":
    from data_fetcher import fetch_stock_data

    history = fetch_stock_data()
    details, total_return = run_dual_ma_backtest(history)
    sharpe_ratio = calculate_sharpe_ratio(details["策略日收益率"])
    print(details.tail())
    print(f"策略累计收益率: {total_return:.2%}")
    print(f"策略夏普比率: {sharpe_ratio:.3f}")
