# AlphaEar Finance API Reference

## Contents

1. Runtime bootstrap
2. Dependency tiers
3. Environment variables
4. Canonical modules
5. Known limitations

## Runtime bootstrap

Add the skill's `scripts` directory to `sys.path`, then import canonical top-level packages:

```python
import sys
from pathlib import Path

skill_dir = Path.home() / ".codex" / "skills" / "alphaear-finance"
scripts_dir = skill_dir / "scripts"
sys.path.insert(0, str(scripts_dir))

from core.database_manager import DatabaseManager
from core.stock_tools import EastMoneyDirect, StockTools
from news.news_tools import NewsNowTools, PolymarketTools
from sentiment.sentiment_tools import SentimentTools
from search.search_tools import JinaSearchEngine, SearchTools
from search.hybrid_search import HybridSearcher, InMemoryRAG, LocalNewsSearch
from predictor.kronos_predictor import KronosPredictorUtility
from predictor.forecast_agent import ForecastUtils
from tracker.fin_agent import FinUtils
from reporter.report_agent import ReportUtils
from visualizer.visualizer import VisualizerTools
from deepear.deepear_lite import DeepEarLiteTools

db = DatabaseManager(db_path=str((Path.cwd() / "data" / "alphaear.sqlite3").resolve()))
```

Do not import mirror copies under `tracker/utils`, `reporter/utils`, or `predictor/utils`.

## Dependency tiers

- Base: pandas, numpy, requests, loguru, PyYAML, python-dotenv, akshare, yfinance, BeautifulSoup and lxml.
- Research: agno, OpenAI, sentence-transformers, transformers, rank-bm25, scikit-learn, pyecharts, matplotlib and Markdown.
- Predictor: research dependencies plus torch, einops, huggingface-hub and tqdm.

Use `uv sync`, `uv sync --extra research`, or `uv sync --extra predictor`.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `openai` | Base model provider |
| `LLM_MODEL` | `gpt-4o` | Base model ID |
| `LLM_HOST` | none | Optional provider base URL |
| `REASONING_MODEL_PROVIDER`, `REASONING_MODEL_ID`, `REASONING_MODEL_HOST` | falls back to `LLM_*` | Reasoning override |
| `TOOL_MODEL_PROVIDER`, `TOOL_MODEL_ID`, `TOOL_MODEL_HOST` | falls back to reasoning | Tool-model override |
| `OPENAI_API_KEY` | none | OpenAI authentication |
| `DEEPSEEK_API_KEY` | none | DeepSeek authentication |
| `DASHSCOPE_API_KEY` | none | DashScope authentication |
| `OPENROUTER_API_KEY` | none | OpenRouter authentication |
| `ZAI_KEY_API` | none | Zhipu authentication |
| `UST_KEY_API`, `UST_URL` | none | UST provider |
| `JINA_API_KEY` | empty | Jina search and article extraction |
| `EMBEDDING_MODEL` | module-specific | SentenceTransformer model |
| `SENTIMENT_MODE` | `auto` | `auto`, `bert`, or `llm` |
| `BERT_SENTIMENT_MODEL` | Chinese RoBERTa model | Sentiment model ID |
| `SEARCH_CACHE_TTL` | `3600` | Search cache duration in seconds |

## Canonical modules

### `core.database_manager.DatabaseManager`

```python
DatabaseManager(db_path: str = "data/signal_flux.db")
save_daily_news(news_list: list[dict]) -> int
get_daily_news(source: str | None = None, limit: int = 100, days: int = 1) -> list[dict]
delete_news(news_id: str) -> bool
update_news_content(news_id: str, content: str | None = None, analysis: str | None = None) -> bool
close() -> None
```

Always pass an absolute database path.

### `core.stock_tools`

```python
StockTools(db: DatabaseManager, auto_update: bool = True)
StockTools.search_ticker(query: str, limit: int = 5) -> list[dict]
StockTools.get_stock_price(ticker: str, start_date: str | None = None,
                           end_date: str | None = None,
                           force_sync: bool = False) -> pandas.DataFrame
StockTools.get_stock_fundamentals(ticker: str) -> dict

EastMoneyDirect.fetch_kline(ticker: str, start_date: str, end_date: str) -> pandas.DataFrame
EastMoneyDirect.fetch_stock_list(market: str = "a") -> pandas.DataFrame
```

Use numeric tickers for A shares. For fresh US history, prefer `yfinance.Ticker(ticker).history(...)`.

### `news.news_tools`

```python
NewsNowTools(db: DatabaseManager)
NewsNowTools.fetch_hot_news(source_id: str, count: int = 15,
                            fetch_content: bool = False) -> list[dict]
NewsNowTools.fetch_news_content(url: str) -> str | None
NewsNowTools.get_unified_trends(sources: list[str] | None = None) -> str

PolymarketTools(db: DatabaseManager)
PolymarketTools.get_active_markets(limit: int = 20) -> list[dict]
PolymarketTools.get_market_summary(limit: int = 10) -> str
```

Common source IDs: `cls`, `wallstreetcn`, `xueqiu`, and `hackernews`.

### `sentiment.sentiment_tools.SentimentTools`

```python
SentimentTools(db: DatabaseManager, mode: str | None = None, ...)
analyze_sentiment(text: str) -> dict[str, float | str]
analyze_sentiment_llm(text: str) -> dict[str, float | str]
analyze_sentiment_bert(texts: list[str]) -> list[dict]
batch_update_news_sentiment(source: str | None = None, limit: int = 50,
                            use_bert: bool | None = None)
```

BERT mode may download a model. LLM mode requires the selected provider's API key.

### `search`

```python
JinaSearchEngine().search(query: str, max_results: int = 5) -> list[dict]

SearchTools(db: DatabaseManager)
SearchTools.search(query: str, engine: str | None = None,
                   max_results: int = 5, ttl: int | None = None) -> str
SearchTools.search_list(query: str, engine: str | None = None,
                        max_results: int = 5, ttl: int | None = None,
                        enrich: bool = True) -> list[dict]
SearchTools.aggregate_search(query: str, engines: list[str] | None = None,
                             max_results: int = 5) -> str

HybridSearcher(data: list[dict], text_fields: list[str], model_name: str | None)
InMemoryRAG.search(query: str, top_n: int = 3, use_vector: bool = True) -> list[dict]
LocalNewsSearch(db_manager).search(query: str, top_n: int = 5,
                                   use_vector: bool = True) -> list[dict]
```

### `predictor`

```python
KronosPredictorUtility(device: str | None = None)
KronosPredictorUtility.get_base_forecast(
    df: pandas.DataFrame,
    lookback: int = 20,
    pred_len: int = 5,
    news_text: str | None = None,
) -> list

ForecastUtils(db: DatabaseManager)
```

`KronosPredictorUtility` is a singleton. It needs torch, model weights, and usually Hugging Face downloads.

### `tracker.fin_agent.FinUtils`

```python
FinUtils(db: DatabaseManager)
sanitize_signal_output(json_data: dict, research_data: dict | None = None,
                       raw_signal: str = "") -> dict
```

### `reporter.report_agent.ReportUtils`

```python
ReportUtils(db: DatabaseManager)
build_bibliography(signals) -> tuple[list[dict], dict[int, list[str]]]
render_references_section(bib_entries: list[dict]) -> str
sanitize_json_chart_blocks(text: str) -> str
build_structured_report(report_md: str, signals: list[dict],
                        clusters: list[dict]) -> dict
```

### `visualizer.visualizer.VisualizerTools`

Creates pyecharts stock, loss, sentiment, radar, and transmission charts; renders charts or DrawIO XML to files.

### `deepear.deepear_lite.DeepEarLiteTools`

```python
DeepEarLiteTools.fetch_latest_signals()
```

This is a network-dependent raw signal feed and does not take a database argument.

## Known limitations

1. `StockTools.get_stock_price()` can return an empty DataFrame for stale caches or mismatched tickers.
2. Current US history is more reliable through direct `yfinance`.
3. Kronos construction requires torch and external model assets.
4. Relative database paths resolve against the caller's current directory.
5. Mirror modules exist in three agent packages; mixing them can produce duplicate-class confusion.
6. Search, news, article extraction, prices, and DeepEar depend on third-party services and can fail or rate-limit.
7. Some upstream modules catch errors and return empty values. Callers must validate result shape and freshness explicitly.
