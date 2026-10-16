# Analysis state schema

Write UTF-8 JSON at `<run-root>/analysis_state.json`. Use plain Markdown strings for role reports.

```json
{
  "ticker": "NVDA",
  "analysis_date": "2026-07-11",
  "asset_type": "stock",
  "language": "Chinese",
  "reference_close": 0.0,
  "benchmark_symbol": "SPY",
  "market_report": "Markdown",
  "sentiment_report": "Markdown",
  "news_report": "Markdown",
  "fundamentals_report": "Markdown or empty for crypto",
  "bull_case": "Markdown",
  "bear_case": "Markdown",
  "research_manager": "Markdown",
  "trader_plan": "Markdown",
  "aggressive_risk": "Markdown",
  "neutral_risk": "Markdown",
  "conservative_risk": "Markdown",
  "risk_manager": "Markdown",
  "portfolio_decision": {
    "rating": "Buy|Overweight|Hold|Underweight|Sell",
    "action": "Conditional action",
    "confidence": "low|medium|high or a calibrated percentage",
    "executive_summary": "Markdown",
    "thesis": "Markdown",
    "position_guidance": "Markdown",
    "key_risks": ["Risk"],
    "invalidation_conditions": ["Condition"],
    "monitoring_plan": ["Metric or event"]
  },
  "sources": [
    {
      "title": "Source title",
      "url": "https://example.com/page",
      "date": "YYYY-MM-DD"
    }
  ]
}
```

Required fields for rendering are `ticker`, `analysis_date`, and `portfolio_decision`. For a complete TradingAgents-style run, populate every applicable role field.
