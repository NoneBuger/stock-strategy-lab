#!/usr/bin/env python3
"""Create and update resumable Codex-native TradingAgents run workspaces."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STAGES = (
    "market_data",
    "analysts",
    "research_debate",
    "trader",
    "risk_debate",
    "portfolio_manager",
    "report",
    "memory",
)
STATUSES = ("pending", "running", "complete", "failed", "skipped")


def safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._=-]+", "_", value.strip())[:48]
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("invalid ticker component")
    return cleaned


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def read_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"run state does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def command_init(args: argparse.Namespace) -> int:
    datetime.strptime(args.date, "%Y-%m-%d")
    ticker = safe_component(args.ticker.upper())
    if args.output_dir:
        root = args.output_dir.expanduser().resolve()
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        root = (Path.cwd() / "tradingagents_runs" / f"{ticker}_{args.date}_{stamp}").resolve()
    directories = {
        "evidence": root / "evidence",
        "analysts": root / "reports" / "1_analysts",
        "research": root / "reports" / "2_research",
        "trading": root / "reports" / "3_trading",
        "risk": root / "reports" / "4_risk",
        "portfolio": root / "reports" / "5_portfolio",
    }
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)
    state_path = root / "run_state.json"
    if state_path.exists() and not args.force:
        raise FileExistsError(f"run already exists: {state_path}; pass --force to recreate")
    state = {
        "schema_version": 1,
        "ticker": args.ticker,
        "analysis_date": args.date,
        "language": args.language,
        "asset_type": args.asset_type,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "root": str(root),
        "stages": {
            stage: {"status": "pending", "updated_at": None, "note": None}
            for stage in STAGES
        },
        "artifacts": {
            "market_snapshot": str(root / "evidence" / "market_snapshot.json"),
            "source_ledger": str(root / "evidence" / "sources.json"),
            "analysis_state": str(root / "analysis_state.json"),
            "complete_report": str(root / "reports" / "complete_report.md"),
            "run_summary": str(root / "reports" / "run_summary.json"),
        },
    }
    atomic_write(state_path, state)
    print(json.dumps({"run_root": str(root), "state_path": str(state_path), **state["artifacts"]}, ensure_ascii=False, indent=2))
    return 0


def command_mark(args: argparse.Namespace) -> int:
    path = args.state.expanduser().resolve()
    state = read_state(path)
    if args.stage not in state.get("stages", {}):
        raise ValueError(f"unknown stage: {args.stage}")
    state["stages"][args.stage] = {
        "status": args.status,
        "updated_at": utc_now(),
        "note": args.note,
    }
    state["updated_at"] = utc_now()
    atomic_write(path, state)
    print(json.dumps(state["stages"][args.stage], ensure_ascii=False, indent=2))
    return 0


def command_status(args: argparse.Namespace) -> int:
    state = read_state(args.state.expanduser().resolve())
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init")
    init.add_argument("ticker")
    init.add_argument("--date", required=True)
    init.add_argument("--language", default="Chinese")
    init.add_argument("--asset-type", choices=("stock", "crypto"), default="stock")
    init.add_argument("--output-dir", type=Path)
    init.add_argument("--force", action="store_true")
    init.set_defaults(handler=command_init)

    mark = commands.add_parser("mark")
    mark.add_argument("--state", type=Path, required=True)
    mark.add_argument("--stage", choices=STAGES, required=True)
    mark.add_argument("--status", choices=STATUSES, required=True)
    mark.add_argument("--note")
    mark.set_defaults(handler=command_mark)

    status = commands.add_parser("status")
    status.add_argument("--state", type=Path, required=True)
    status.set_defaults(handler=command_status)
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
