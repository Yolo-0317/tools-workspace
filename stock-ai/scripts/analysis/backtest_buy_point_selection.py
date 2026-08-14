#!/usr/bin/env python3
"""Freeze and evaluate the buy-point selector without test-set tuning."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

from stock_ai.buy_point_selection.models import OutcomeLabel, SelectionPolicy, SetupType
from stock_ai.buy_point_selection.validation import (
    TradeObservation,
    ValidationError,
    build_outcome_calibrations,
    calibrations_payload,
    chronological_split,
    compute_metrics,
    evaluate_promotion,
    metrics_payload,
    outcome_calibrations_from_payload,
    policy_hash,
    resolve_outcome_calibration,
    write_artifact,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--research-train-validation", action="store_true")
    modes.add_argument("--freeze-profile", action="store_true")
    modes.add_argument("--run-test", action="store_true")
    parser.add_argument("--trading-dates", type=Path, required=True)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--profile", type=Path, default=Path("stock-ai/config/buy_point_selection_profile.json"))
    parser.add_argument("--artifact", type=Path, default=Path("stock-ai/config/buy_point_selection_validation.json"))
    parser.add_argument("--write-artifact", action="store_true")
    parser.add_argument("--point-in-time-complete", action="store_true")
    return parser


def _load_dates(path: Path) -> tuple[date, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(date.fromisoformat(str(value)) for value in payload)


def _load_observations(path: Path | None) -> tuple[TradeObservation, ...]:
    if path is None:
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = frozenset(
        {
            "exit_date",
            "setup_type",
            "sector_code",
            "net_return",
            "net_pnl",
            "outcome",
            "market_status",
            "sector_resonating",
            "mfe",
            "mae",
        }
    )
    observations: list[TradeObservation] = []
    for index, value in enumerate(payload):
        if not isinstance(value, dict):
            raise ValidationError(f"observation {index} must be an object")
        missing = sorted(required - set(value))
        if missing:
            raise ValidationError(
                f"observation {index} missing required fields: {','.join(missing)}"
            )
        observations.append(
            TradeObservation(
                exit_date=date.fromisoformat(str(value["exit_date"])),
                setup_type=SetupType(str(value["setup_type"])),
                sector_code=str(value["sector_code"]),
                net_return=Decimal(str(value["net_return"])),
                net_pnl=Decimal(str(value["net_pnl"])),
                outcome=OutcomeLabel(str(value["outcome"])),
                market_status=str(value["market_status"]),
                sector_resonating=bool(value["sector_resonating"]),
                mfe=(
                    Decimal(str(value["mfe"]))
                    if value["mfe"] is not None
                    else None
                ),
                mae=(
                    Decimal(str(value["mae"]))
                    if value["mae"] is not None
                    else None
                ),
                signal_date=(
                    date.fromisoformat(str(value["signal_date"]))
                    if value.get("signal_date") is not None
                    else None
                ),
                entry_date=(
                    date.fromisoformat(str(value["entry_date"]))
                    if value.get("entry_date") is not None
                    else None
                ),
                code=str(value.get("code") or ""),
                structure_id=str(value.get("structure_id") or ""),
                risk_fraction=Decimal(str(value.get("risk_fraction") or "0")),
            )
        )
    return tuple(observations)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_manifest(
    path: Path | None,
    *,
    trading_dates_path: Path,
    observations_path: Path | None,
    expected_rule_version: str,
    expected_policy_hash: str,
    point_in_time_complete: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    if path is None:
        if point_in_time_complete:
            raise ValidationError(
                "point-in-time complete mode requires a replay integrity manifest"
            )
        return None, None
    if observations_path is None:
        raise ValidationError("replay integrity manifest requires observations")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "buy-point-replay-integrity-v1":
        raise ValidationError("replay integrity manifest schema mismatch")
    if not payload.get("complete", False):
        raise ValidationError("point-in-time replay is incomplete")
    if payload.get("trading_dates_sha256") != _sha256(trading_dates_path):
        raise ValidationError("trading dates hash mismatch")
    if payload.get("observations_sha256") != _sha256(observations_path):
        raise ValidationError("observations hash mismatch")
    if payload.get("rule_version") != expected_rule_version:
        raise ValidationError("replay integrity rule version mismatch")
    if payload.get("policy_hash") != expected_policy_hash:
        raise ValidationError("replay integrity policy hash mismatch")
    return payload, _sha256(path)


def _split_bounds(split) -> dict[str, Any]:
    return {
        "train": [split.train[0].isoformat(), split.train[-1].isoformat(), len(split.train)],
        "validation": [
            split.validation[0].isoformat(),
            split.validation[-1].isoformat(),
            len(split.validation),
        ],
        "test": [split.test[0].isoformat(), split.test[-1].isoformat(), len(split.test)],
    }


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))


def _frozen_test_observations(
    observations: Sequence[TradeObservation],
    *,
    test_dates: Sequence[date],
    calibrations,
) -> tuple[TradeObservation, ...]:
    test_set = frozenset(test_dates)
    grouped: dict[date, list[tuple[TradeObservation, Any]]] = {}
    for value in observations:
        if value.signal_date is None:
            raise ValidationError("frozen replay observation missing signal_date")
        if value.signal_date not in test_set:
            continue
        if not value.code or not value.structure_id:
            raise ValidationError("frozen replay observation missing candidate identity")
        calibration = resolve_outcome_calibration(
            calibrations,
            value.setup_type,
            value.market_status,
            value.sector_resonating,
        )
        if calibration is None or not calibration.promoted:
            continue
        grouped.setdefault(value.signal_date, []).append((value, calibration))

    recommended: list[TradeObservation] = []
    for signal_date in sorted(grouped):
        used_sectors: set[str] = set()
        accepted = 0
        values = sorted(
            grouped[signal_date],
            key=lambda item: (
                -item[1].net_expectancy,
                -item[1].target_2r_rate,
                item[1].stop_first_rate,
                -item[1].positive_rolling_window_ratio,
                item[0].risk_fraction,
                item[0].code,
            ),
        )
        for value, _ in values:
            limit = 1 if value.market_status == "LIMITED" else 3
            if accepted >= limit or value.sector_code in used_sectors:
                continue
            recommended.append(value)
            accepted += 1
            used_sectors.add(value.sector_code)

    untriggered = [value for value in recommended if value.entry_date is None]
    triggered = sorted(
        (value for value in recommended if value.entry_date is not None),
        key=lambda value: (value.entry_date, value.signal_date, value.code),
    )
    accepted_triggered: list[TradeObservation] = []
    active: list[TradeObservation] = []
    for value in triggered:
        active = [item for item in active if item.exit_date >= value.entry_date]
        if len(active) >= 3:
            continue
        if any(item.sector_code == value.sector_code for item in active):
            continue
        accepted_triggered.append(value)
        active.append(value)
    return tuple(
        sorted(
            (*untriggered, *accepted_triggered),
            key=lambda value: (value.signal_date, value.code),
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    policy = SelectionPolicy()
    try:
        trading_dates = _load_dates(args.trading_dates)
        split = chronological_split(trading_dates)
        current_hash = policy_hash(policy)
        bounds = _split_bounds(split)
        manifest, manifest_hash = _load_manifest(
            args.manifest,
            trading_dates_path=args.trading_dates,
            observations_path=args.observations,
            expected_rule_version=policy.rule_version,
            expected_policy_hash=current_hash,
            point_in_time_complete=args.point_in_time_complete,
        )
        observations = _load_observations(args.observations)
        if manifest is not None:
            if int(manifest.get("observation_count", -1)) != len(observations):
                raise ValidationError("replay observation count mismatch")
            if any(
                value.signal_date is None
                or not value.code
                or not value.structure_id
                or value.risk_fraction <= 0
                for value in observations
            ):
                raise ValidationError("replay observation identity is incomplete")

        if args.freeze_profile:
            if manifest is not None:
                allowed = frozenset((*split.train, *split.validation))
                research = tuple(
                    value
                    for value in observations
                    if (value.signal_date or value.exit_date) in allowed
                    and value.exit_date <= split.validation[-1]
                )
                calibrations = build_outcome_calibrations(
                    research,
                    test_dates=split.validation,
                    trading_dates=(*split.train, *split.validation),
                )
                write_artifact(
                    args.profile,
                    {
                        "schema": "buy-point-selection-frozen-profile-v2",
                        "rule_version": policy.rule_version,
                        "policy_hash": current_hash,
                        "split_bounds": bounds,
                        "manifest_sha256": manifest_hash,
                        "calibrations": calibrations_payload(calibrations),
                    },
                )
                return 0
            write_artifact(
                args.profile,
                {
                    "schema": "buy-point-selection-frozen-profile-v1",
                    "rule_version": policy.rule_version,
                    "policy_hash": current_hash,
                    "split_bounds": bounds,
                },
            )
            return 0

        if args.research_train_validation:
            allowed = frozenset((*split.train, *split.validation))
            research = tuple(
                value
                for value in observations
                if (value.signal_date or value.exit_date) in allowed
                and value.exit_date <= split.validation[-1]
            )
            metrics = compute_metrics(
                research,
                test_dates=(),
                trading_dates=(*split.train, *split.validation),
                point_in_time_complete=args.point_in_time_complete,
            )
            calibrations = build_outcome_calibrations(
                research,
                test_dates=split.validation,
                trading_dates=(*split.train, *split.validation),
            )
            _print_json(
                {
                    "technical_core_metrics": metrics_payload(metrics),
                    "calibrations": calibrations_payload(calibrations),
                    "split_bounds": bounds,
                }
            )
            return 0

        if not args.profile.exists():
            raise ValidationError("frozen profile is required before --run-test")
        frozen_profile_hash = _sha256(args.profile)
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        profile_schema = profile.get("schema")
        if profile_schema not in {
            "buy-point-selection-frozen-profile-v1",
            "buy-point-selection-frozen-profile-v2",
        }:
            raise ValidationError("frozen profile schema mismatch")
        if profile.get("rule_version") != policy.rule_version:
            raise ValidationError("frozen profile rule version mismatch")
        if profile.get("policy_hash") != current_hash:
            raise ValidationError("frozen profile hash mismatch")
        if profile.get("split_bounds") != bounds:
            raise ValidationError("frozen profile split bounds mismatch")
        frozen_calibrations = None
        if profile_schema == "buy-point-selection-frozen-profile-v2":
            if manifest is None or manifest_hash is None:
                raise ValidationError("frozen profile v2 requires replay manifest")
            if profile.get("manifest_sha256") != manifest_hash:
                raise ValidationError("frozen profile manifest hash mismatch")
            frozen_calibrations = outcome_calibrations_from_payload(
                profile.get("calibrations")
            )
        if args.artifact.exists():
            existing = json.loads(args.artifact.read_text(encoding="utf-8"))
            if (
                existing.get("rule_version") == policy.rule_version
                and existing.get("policy_hash") == current_hash
                and existing.get("frozen_profile_sha256")
            ):
                raise ValidationError("frozen test already exists for this profile")
            if (
                existing.get("rule_version") == policy.rule_version
                and existing.get("policy_hash") != current_hash
            ):
                raise ValidationError("a different test hash already exists for this rule version")

        evaluated_observations = observations
        evaluated_dates = trading_dates
        if frozen_calibrations is not None:
            evaluated_observations = _frozen_test_observations(
                observations,
                test_dates=split.test,
                calibrations=frozen_calibrations,
            )
            evaluated_dates = split.test
        metrics = compute_metrics(
            evaluated_observations,
            test_dates=split.test,
            trading_dates=evaluated_dates,
            point_in_time_complete=args.point_in_time_complete,
        )
        decision = evaluate_promotion(metrics)
        calibrations = frozen_calibrations or build_outcome_calibrations(
            observations,
            test_dates=split.test,
            trading_dates=trading_dates,
        )
        payload = {
            "schema": "buy-point-selection-validation-v2",
            "rule_version": policy.rule_version,
            "policy_hash": current_hash,
            "frozen_profile_sha256": frozen_profile_hash,
            "manifest_sha256": manifest_hash,
            "split_bounds": bounds,
            "promoted": decision.promoted,
            "reasons": list(decision.reasons),
            "setup_decisions": {
                key: {"promoted": value.promoted, "reasons": list(value.reasons)}
                for key, value in decision.setup_decisions.items()
            },
            "technical_core_metrics": metrics_payload(metrics),
            "calibrations": calibrations_payload(calibrations),
            "selected_test_structure_ids": (
                [value.structure_id for value in evaluated_observations]
                if frozen_calibrations is not None
                else []
            ),
            "fully_gated_metrics": (
                metrics_payload(metrics) if args.point_in_time_complete else None
            ),
            "costs": {
                "commission_rate": "0.001",
                "minimum_commission": "5",
                "slippage_rate": "0.001",
                "sell_tax_rate": "0.001",
            },
        }
        if args.write_artifact:
            write_artifact(args.artifact, payload)
        else:
            _print_json(payload)
        return 0
    except (OSError, ValueError, json.JSONDecodeError, ValidationError) as error:
        print(f"validation error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
