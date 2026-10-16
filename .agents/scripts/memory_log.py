#!/usr/bin/env python3
"""Maintain persistent Codex-native TradingAgents decision memory without API keys."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_path() -> Path:
    data = os.environ.get("PLUGIN_DATA")
    root = Path(data).expanduser() if data else Path.home() / ".tradingagents-codex-native"
    return root / "memory" / "decisions.jsonl"


def read_entries(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on line {line_number} of {path}") from exc
    return entries


def write_entries(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    content = "\n".join(json.dumps(entry, ensure_ascii=False) for entry in entries)
    temporary.write_text(content + ("\n" if content else ""), encoding="utf-8")
    temporary.replace(path)


def append_command(args: argparse.Namespace) -> int:
    state = json.loads(args.state.expanduser().resolve().read_text(encoding="utf-8"))
    portfolio = state.get("portfolio_decision") or {}
    entry = {
        "ticker": state.get("ticker"),
        "analysis_date": state.get("analysis_date"),
        "recorded_at": datetime.now(tz=timezone.utc).isoformat(),
        "rating": portfolio.get("rating"),
        "action": portfolio.get("action") or portfolio.get("rating"),
        "confidence": portfolio.get("confidence"),
        "thesis": portfolio.get("thesis"),
        "invalidation_conditions": portfolio.get("invalidation_conditions") or [],
        "reference_close": state.get("reference_close"),
        "benchmark_symbol": state.get("benchmark_symbol"),
        "outcome": None,
    }
    if not entry["ticker"] or not entry["analysis_date"] or not entry["rating"]:
        raise ValueError("analysis state is missing ticker, analysis_date, or portfolio rating")
    path = args.memory_path.expanduser().resolve()
    entries = read_entries(path)
    entries = [
        existing
        for existing in entries
        if not (
            existing.get("ticker") == entry["ticker"]
            and existing.get("analysis_date") == entry["analysis_date"]
        )
    ]
    entries.append(entry)
    write_entries(path, entries)
    print(json.dumps({"path": str(path), "entry": entry}, ensure_ascii=False, indent=2))
    return 0


def list_command(args: argparse.Namespace) -> int:
    path = args.memory_path.expanduser().resolve()
    entries = read_entries(path)
    if args.ticker:
        ticker = args.ticker.upper()
        entries = [entry for entry in entries if str(entry.get("ticker", "")).upper() == ticker]
    if args.limit:
        entries = entries[-args.limit :]
    print(json.dumps({"path": str(path), "entries": entries}, ensure_ascii=False, indent=2))
    return 0


def context_command(args: argparse.Namespace) -> int:
    path = args.memory_path.expanduser().resolve()
    entries = read_entries(path)
    ticker = args.ticker.upper()
    same = [entry for entry in entries if str(entry.get("ticker", "")).upper() == ticker]
    cross = [entry for entry in entries if str(entry.get("ticker", "")).upper() != ticker]
    payload = {
        "ticker": ticker,
        "same_ticker": same[-args.limit :],
        "cross_ticker_lessons": [entry for entry in cross if entry.get("outcome")][-args.limit :],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def outcome_command(args: argparse.Namespace) -> int:
    path = args.memory_path.expanduser().resolve()
    entries = read_entries(path)
    matched = False
    target_ticker = args.ticker.upper()
    for entry in entries:
        if (
            str(entry.get("ticker", "")).upper() == target_ticker
            and entry.get("analysis_date") == args.date
        ):
            entry["outcome"] = {
                "raw_return": args.raw_return,
                "alpha_return": args.alpha_return,
                "holding_days": args.holding_days,
                "reflection": args.reflection,
                "resolved_at": datetime.now(tz=timezone.utc).isoformat(),
            }
            matched = True
            break
    if not matched:
        raise ValueError(f"memory entry not found for {args.ticker} on {args.date}")
    write_entries(path, entries)
    print(json.dumps({"path": str(path), "updated": True}, ensure_ascii=False, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.set_defaults(memory_path=default_path())
    commands = parser.add_subparsers(dest="command", required=True)

    append = commands.add_parser("append")
    append.add_argument("--state", type=Path, required=True)
    append.add_argument("--memory-path", type=Path, default=default_path())
    append.set_defaults(handler=append_command)

    listing = commands.add_parser("list")
    listing.add_argument("--ticker")
    listing.add_argument("--limit", type=int, default=20)
    listing.add_argument("--memory-path", type=Path, default=default_path())
    listing.set_defaults(handler=list_command)

    context = commands.add_parser("context")
    context.add_argument("ticker")
    context.add_argument("--limit", type=int, default=5)
    context.add_argument("--memory-path", type=Path, default=default_path())
    context.set_defaults(handler=context_command)

    outcome = commands.add_parser("outcome")
    outcome.add_argument("ticker")
    outcome.add_argument("--date", required=True)
    outcome.add_argument("--raw-return", type=float, required=True)
    outcome.add_argument("--alpha-return", type=float)
    outcome.add_argument("--holding-days", type=int, default=5)
    outcome.add_argument("--reflection", required=True)
    outcome.add_argument("--memory-path", type=Path, default=default_path())
    outcome.set_defaults(handler=outcome_command)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return int(args.handler(args))
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
