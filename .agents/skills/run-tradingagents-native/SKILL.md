---
name: run-tradingagents-native
description: Run TradingAgents-style multi-agent financial research directly with the current Codex model, without external LLM API keys. Use for stock, international ticker, futures, forex, or crypto analysis; market/sentiment/news/fundamental analyst reports; bull-bear debate; trader planning; aggressive/neutral/conservative risk review; portfolio-manager ratings; historical point-in-time analysis; persistent decision memory; or complete saved research reports.
---

# Run TradingAgents Native

Run the reasoning workflow inside Codex. Do not call an external language-model provider and do not request a model API key.

## Resolve files

Resolve the plugin root as two directories above this `SKILL.md`. Use the bundled scripts with the current `python3`; they use only the standard library.

Read these references as needed:

- Read [roles.md](references/roles.md) before assigning analyst, debate, trader, risk, or manager roles.
- Read [evidence.md](references/evidence.md) before web research or historical analysis.
- Read [state-schema.md](references/state-schema.md) before writing `analysis_state.json`.

## Start or resume a run

1. Normalize the requested date to `YYYY-MM-DD`. Reject future dates.
2. Choose `stock` or `crypto`. Exclude the fundamentals analyst for crypto.
3. Create a run workspace unless the user supplied an existing `run_state.json`:

```bash
python3 <plugin-root>/scripts/run_workspace.py init <ticker> \
  --date <YYYY-MM-DD> --language <language> --asset-type <stock|crypto> \
  --output-dir <workspace-output-directory>
```

4. On resume, read `run_state.json` and continue from the first non-complete stage. Do not redo completed stages unless their evidence changed or the user requests a fresh run.
5. Read prior same-ticker decisions:

```bash
python3 <plugin-root>/scripts/memory_log.py context <ticker>
```

## Collect market evidence

Run the no-key market collector and save its JSON output:

```bash
python3 <plugin-root>/scripts/market_snapshot.py <ticker> \
  --date <YYYY-MM-DD> --output <run-root>/evidence/market_snapshot.json
```

Mark `market_data` complete after validating the symbol, as-of bar, benchmark, returns, indicators, and warnings. If the endpoint fails, use a current callable finance tool or primary market-data source and record the substitution in `sources.json`; never fabricate missing values.

Use web research for company filings, fundamentals, macro events, news, and sentiment. Financial research is accuracy-sensitive and current facts can change, so browse by default. Enforce the analysis-date cutoff from [evidence.md](references/evidence.md).

## Run the agent teams

Use real subagents when subagent tools are available. Give each agent only the raw evidence, cutoff date, role contract, and output path; do not leak another role's conclusion before independent work is complete.

Run in this order:

1. Spawn Market, Sentiment, News, and—when applicable—Fundamentals analysts in parallel.
2. Validate citations and save each report under `reports/1_analysts/`.
3. Spawn Bull and Bear researchers in parallel using the completed analyst reports.
4. Act as Research Manager to reconcile the strongest evidence and disagreements.
5. Act as Trader to translate the research plan into a conditional action, timing, and sizing proposal.
6. Spawn Aggressive, Neutral, and Conservative risk analysts in parallel.
7. Act as Risk Manager to reconcile exposure, liquidity, volatility, invalidation, and downside controls.
8. Act as Portfolio Manager to issue one five-tier rating: `Buy`, `Overweight`, `Hold`, `Underweight`, or `Sell`.

If subagent tools are unavailable, perform separate sequential role passes and disclose that the roles were simulated within one Codex context. Never claim independent agents ran when they did not.

After every stage, update the checkpoint:

```bash
python3 <plugin-root>/scripts/run_workspace.py mark \
  --state <run-root>/run_state.json --stage <stage> --status complete
```

## Build and render the report

Write `<run-root>/analysis_state.json` using [state-schema.md](references/state-schema.md). Include source URLs and dates, the snapshot reference close, benchmark, all role outputs, and the final structured portfolio decision.

Render the report tree:

```bash
python3 <plugin-root>/scripts/render_report.py \
  --state <run-root>/analysis_state.json --output-root <run-root>
```

Append the completed decision to persistent memory:

```bash
python3 <plugin-root>/scripts/memory_log.py append \
  --state <run-root>/analysis_state.json
```

Mark `report` and `memory` complete. Read `reports/run_summary.json` and `reports/complete_report.md` before replying.

## Present results

Lead with the rating, conditional action, confidence, and analysis-date cutoff. Then summarize:

- decisive evidence;
- strongest bull and bear points;
- key risks and invalidation conditions;
- monitoring plan;
- report and state paths.

State that the result is research, not financial advice, and that no order was placed.

## Guardrails

- Never request or use OpenAI, Anthropic, Google, or other model-provider keys. The current Codex task supplies reasoning.
- Never place trades, connect a broker, or imply simulated approval is real execution.
- Never use evidence published after a historical cutoff.
- Never invent citations, prices, filings, social sentiment, agent independence, or confidence.
- Preserve exchange suffixes and report any symbol normalization such as `BTCUSDT` to `BTC-USD`.
- Distinguish measured facts, sourced claims, role arguments, and the final judgment.
- Prefer abstention or a lower-confidence `Hold` when evidence is incomplete or contradictory.
