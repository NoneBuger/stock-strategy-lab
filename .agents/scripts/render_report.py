#!/usr/bin/env python3
"""Validate Codex-produced analysis state and render the TradingAgents report tree."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RATINGS = {"Buy", "Overweight", "Hold", "Underweight", "Sell"}


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content.rstrip() + "\n", encoding="utf-8")
    temporary.replace(path)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, ensure_ascii=False, indent=2)


def bullet_list(values: Any) -> str:
    if not values:
        return "- None stated"
    if isinstance(values, str):
        return values
    return "\n".join(f"- {text(value)}" for value in values)


def render_portfolio(decision: dict[str, Any]) -> str:
    rating = decision.get("rating")
    if rating not in RATINGS:
        raise ValueError(f"portfolio_decision.rating must be one of {sorted(RATINGS)}")
    confidence = decision.get("confidence")
    confidence_line = f"\n**Confidence:** {confidence}" if confidence is not None else ""
    return f"""## Portfolio Decision

**Rating:** {rating}

**Action:** {text(decision.get('action') or rating)}{confidence_line}

### Executive summary

{text(decision.get('executive_summary'))}

### Investment thesis

{text(decision.get('thesis'))}

### Position and timing guidance

{text(decision.get('position_guidance'))}

### Key risks

{bullet_list(decision.get('key_risks'))}

### Invalidation conditions

{bullet_list(decision.get('invalidation_conditions'))}

### Monitoring plan

{bullet_list(decision.get('monitoring_plan'))}
""".strip()


def render_sources(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "## Sources\n\nNo external sources recorded."
    lines = ["## Sources", ""]
    for source in sources:
        title = source.get("title") or source.get("url") or "Source"
        url = source.get("url")
        published = source.get("date") or source.get("published_at")
        suffix = f" — {published}" if published else ""
        lines.append(f"- [{title}]({url}){suffix}" if url else f"- {title}{suffix}")
    return "\n".join(lines)


def write_optional(path: Path, value: Any) -> str | None:
    content = text(value)
    if not content:
        return None
    atomic_text(path, content)
    return content


def render(state: dict[str, Any], output_root: Path) -> dict[str, Any]:
    ticker = text(state.get("ticker"))
    analysis_date = text(state.get("analysis_date"))
    if not ticker or not analysis_date:
        raise ValueError("state requires ticker and analysis_date")
    portfolio = state.get("portfolio_decision")
    if not isinstance(portfolio, dict):
        raise ValueError("state requires portfolio_decision object")

    reports = output_root / "reports"
    sections: list[str] = [
        f"# TradingAgents Codex Native Report: {ticker}",
        f"**Analysis date:** {analysis_date}",
        f"**Generated:** {datetime.now(tz=timezone.utc).isoformat()}",
        "> Research output only. This report is not financial advice and does not place orders.",
    ]

    analyst_specs = (
        ("market_report", "Market Analyst", reports / "1_analysts" / "market.md"),
        ("sentiment_report", "Sentiment Analyst", reports / "1_analysts" / "sentiment.md"),
        ("news_report", "News Analyst", reports / "1_analysts" / "news.md"),
        ("fundamentals_report", "Fundamentals Analyst", reports / "1_analysts" / "fundamentals.md"),
    )
    analyst_parts: list[str] = []
    for key, title, path in analyst_specs:
        content = write_optional(path, state.get(key))
        if content:
            analyst_parts.append(f"### {title}\n\n{content}")
    if analyst_parts:
        sections.append("## I. Analyst Team Reports\n\n" + "\n\n".join(analyst_parts))

    research_parts: list[str] = []
    for key, title, filename in (
        ("bull_case", "Bull Researcher", "bull.md"),
        ("bear_case", "Bear Researcher", "bear.md"),
        ("research_manager", "Research Manager", "manager.md"),
    ):
        content = write_optional(reports / "2_research" / filename, state.get(key))
        if content:
            research_parts.append(f"### {title}\n\n{content}")
    if research_parts:
        sections.append("## II. Research Debate\n\n" + "\n\n".join(research_parts))

    trader = write_optional(reports / "3_trading" / "trader.md", state.get("trader_plan"))
    if trader:
        sections.append(f"## III. Trader Plan\n\n{trader}")

    risk_parts: list[str] = []
    for key, title, filename in (
        ("aggressive_risk", "Aggressive Risk Analyst", "aggressive.md"),
        ("neutral_risk", "Neutral Risk Analyst", "neutral.md"),
        ("conservative_risk", "Conservative Risk Analyst", "conservative.md"),
        ("risk_manager", "Risk Manager", "manager.md"),
    ):
        content = write_optional(reports / "4_risk" / filename, state.get(key))
        if content:
            risk_parts.append(f"### {title}\n\n{content}")
    if risk_parts:
        sections.append("## IV. Risk Debate\n\n" + "\n\n".join(risk_parts))

    portfolio_markdown = render_portfolio(portfolio)
    atomic_text(reports / "5_portfolio" / "decision.md", portfolio_markdown)
    sections.append("## V. Portfolio Management\n\n" + portfolio_markdown)
    sections.append(render_sources(state.get("sources") or []))

    complete = "\n\n---\n\n".join(sections)
    complete_path = reports / "complete_report.md"
    atomic_text(complete_path, complete)
    summary = {
        "status": "complete",
        "engine": "Codex Native (no external model API)",
        "ticker": ticker,
        "analysis_date": analysis_date,
        "asset_type": state.get("asset_type"),
        "rating": portfolio["rating"],
        "action": portfolio.get("action") or portfolio["rating"],
        "confidence": portfolio.get("confidence"),
        "reference_close": state.get("reference_close"),
        "benchmark_symbol": state.get("benchmark_symbol"),
        "report_path": str(complete_path),
        "source_count": len(state.get("sources") or []),
    }
    summary_path = reports / "run_summary.json"
    atomic_json(summary_path, summary)
    return {**summary, "summary_path": str(summary_path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        state = json.loads(args.state.expanduser().resolve().read_text(encoding="utf-8"))
        result = render(state, args.output_root.expanduser().resolve())
        print(json.dumps(result, ensure_ascii=False, indent=2))
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
