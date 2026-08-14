#!/usr/bin/env python3
"""Generate a deterministic point-in-time buy-point observation bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stock_ai.buy_point_selection.historical_replay import (
    ReplayBundle,
    replay_observation_payload,
)


class ReplayGenerationError(RuntimeError):
    """Raised when a complete replay bundle cannot be produced."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            default=str,
        )
        + "\n"
    ).encode("utf-8")


def _write_bundle(bundle: ReplayBundle, output: Path) -> bool:
    output.mkdir(parents=True, exist_ok=True)
    dates_payload = [value.isoformat() for value in bundle.trading_dates]
    observations_payload = [
        replay_observation_payload(value) for value in bundle.replay.opportunities
    ]
    dates_bytes = _json_bytes(dates_payload)
    observations_bytes = _json_bytes(observations_payload)
    integrity = bundle.replay.integrity
    complete = integrity.complete and len(bundle.trading_dates) >= 630
    manifest = {
        "schema": "buy-point-replay-integrity-v1",
        "complete": complete,
        "rule_version": bundle.rule_version,
        "policy_hash": bundle.policy_hash,
        "trading_date_count": len(bundle.trading_dates),
        "trading_date_start": (
            bundle.trading_dates[0].isoformat() if bundle.trading_dates else None
        ),
        "trading_date_end": (
            bundle.trading_dates[-1].isoformat() if bundle.trading_dates else None
        ),
        "observation_count": len(observations_payload),
        "total_plans": integrity.total_plans,
        "emitted_plans": integrity.emitted_plans,
        "duplicate_structures": integrity.duplicate_structures,
        "pending_plans": integrity.pending_plans,
        "missing_sector_dates": [
            value.isoformat() for value in integrity.missing_sector_dates
        ],
        "missing_st_dates": [value.isoformat() for value in integrity.missing_st_dates],
        "missing_announcement_dates": [
            value.isoformat() for value in integrity.missing_announcement_dates
        ],
        "missing_market_dates": [
            value.isoformat() for value in integrity.missing_market_dates
        ],
        "rejection_counts": dict(sorted(bundle.rejection_counts.items())),
        "trading_dates_sha256": hashlib.sha256(dates_bytes).hexdigest(),
        "observations_sha256": hashlib.sha256(observations_bytes).hexdigest(),
    }
    (output / "trading-dates.json").write_bytes(dates_bytes)
    (output / "outcome-observations.json").write_bytes(observations_bytes)
    (output / "replay-integrity.json").write_bytes(_json_bytes(manifest))
    return complete


def _generate_from_mysql(start: date, end: date) -> ReplayBundle:
    from stock_ai.buy_point_selection.historical_replay_runtime import (
        generate_mysql_replay_bundle,
    )

    return generate_mysql_replay_bundle(start, end)


def main(
    argv: Sequence[str] | None = None,
    *,
    generate: Callable[[date, date], ReplayBundle] | None = None,
) -> int:
    args = _parser().parse_args(argv)
    if args.end < args.start:
        print("replay error: end date precedes start date", file=sys.stderr)
        return 2
    try:
        bundle = (generate or _generate_from_mysql)(args.start, args.end)
        complete = _write_bundle(bundle, args.out)
    except (OSError, ValueError, ReplayGenerationError, RuntimeError) as error:
        print(f"replay error: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "complete": complete,
                "trading_dates": len(bundle.trading_dates),
                "observations": len(bundle.replay.opportunities),
                "output": str(args.out),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
