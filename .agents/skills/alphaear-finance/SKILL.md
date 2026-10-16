---
name: alphaear-finance
description: >-
  Use AlphaEar Finance for programmatic financial research across A-share,
  Hong Kong, and US markets, including stock prices and fundamentals, finance
  news, sentiment, cached web search and local RAG, Kronos time-series
  forecasts, signal normalization, report construction, charts, and DeepEar
  Lite feeds. Trigger for requests involving market or company analysis,
  finance news monitoring, investment-signal research, quantitative forecasts,
  or Markdown research reports that need AlphaEar's local Python modules.
---

# AlphaEar Finance

Use the bundled Python modules as research tools. Treat outputs as evidence to analyze, not as guaranteed predictions or personalized investment advice.

## Start every task

1. Determine the skill directory from this `SKILL.md`; do not hard-code a user's home directory.
2. Read [references/api-reference.md](references/api-reference.md) when exact signatures, dependency tiers, environment variables, or known limitations matter.
3. Add `<skill-dir>/scripts` to `sys.path`.
4. Import canonical top-level packages only. Never import duplicate modules under `tracker/utils`, `reporter/utils`, or `predictor/utils` unless maintaining those internal packages.
5. Use an absolute SQLite path so execution does not depend on the current directory.
6. State the market-data timestamp and source in user-facing analysis. For current facts, retrieve fresh data rather than relying on model knowledge.

```python
import sys
from pathlib import Path

skill_dir = Path("/absolute/path/to/alphaear-finance")
scripts_dir = skill_dir / "scripts"
sys.path.insert(0, str(scripts_dir))

from core.database_manager import DatabaseManager

database_path = Path.cwd() / "data" / "alphaear-finance.sqlite3"
db = DatabaseManager(db_path=str(database_path.resolve()))
```

## Choose the lightest capability

- Use `core.stock_tools.StockTools` for ticker lookup, A-share data, fundamentals, and cached prices.
- Use direct `yfinance` for fresh US-stock price history.
- Use `news.news_tools.NewsNowTools` for finance headlines and `PolymarketTools` for prediction-market data.
- Use `sentiment.sentiment_tools.SentimentTools` only when sentiment scoring materially helps.
- Use `search.search_tools.SearchTools` for cached web search and `search.hybrid_search` for local retrieval.
- Use `predictor.kronos_predictor.KronosPredictorUtility` only when a quantitative forecast is requested and heavy dependencies are installed.
- Use `tracker.fin_agent.FinUtils` to normalize an existing signal JSON; do not present it as an autonomous trading decision.
- Use `reporter.report_agent.ReportUtils` to structure reports and references.
- Use `visualizer.visualizer.VisualizerTools` for charts and transmission graphs.
- Use `deepear.deepear_lite.DeepEarLiteTools` for the lightweight external signal feed.

## Execute safely

- Prefer reproducible scripts and save generated artifacts in the user's workspace, not inside the skill.
- Validate tickers, dates, currencies, exchange, splits, and missing rows before calculating returns.
- Separate observed data, model output, and analyst inference.
- Include assumptions and downside risks in forecasts and reports.
- Never fabricate unavailable prices, news, citations, fundamentals, or model results.
- If an external request fails after the module's retries, report the failure with its source and parameters. Do not silently substitute stale or unrelated data.
- Keep API keys in environment variables. Never print or commit them.
- Close `DatabaseManager` when the task finishes.

## Dependency selection

Use the repository environment:

```bash
uv sync
```

Install only the optional group needed by the task:

```bash
uv sync --extra research
uv sync --extra predictor
```

The `research` group enables LLM/search/sentiment/chart modules. The `predictor` group additionally installs PyTorch and Kronos dependencies. See the API reference for the exact environment variables.

## Report contract

For analytical deliverables, include:

1. Scope, ticker/exchange, and as-of time.
2. Data and news evidence with source links where available.
3. Calculations or model output, labeled explicitly.
4. Interpretation and competing explanations.
5. Risks, missing data, and limitations.
6. A non-advisory note when the output could be read as an investment recommendation.

Do not claim certainty from sentiment scores, prediction-market probabilities, or Kronos forecasts.
