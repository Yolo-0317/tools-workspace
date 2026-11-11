from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, Sequence
from uuid import uuid4

from sqlalchemy import text

from .models import (
    CandidateRole, ChainMetrics, ChainScore, PriceLevels, RotationBucket,
    RotationCandidate, RotationRunResult, RotationState, SelectedChain,
)


class RotationRepository(Protocol):
    def start_run(self, *, observed_at: datetime, trade_date: date, edition: str, policy_version: str) -> str: ...
    def load_history(self, chain_codes: Sequence[str], limit: int = 3) -> dict[str, tuple[SelectedChain, ...]]: ...
    def save_success(self, result: RotationRunResult) -> None: ...
    def save_failure(self, run_id: str, code: str, message: str) -> None: ...
    def load_latest_result(self) -> RotationRunResult | None: ...


class MemoryRotationRepository:
    def __init__(self) -> None:
        self.results: list[RotationRunResult] = []
        self.failures: dict[str, tuple[str, str]] = {}

    def start_run(self, *, observed_at: datetime, trade_date: date, edition: str, policy_version: str) -> str:
        del observed_at, trade_date, edition, policy_version
        return uuid4().hex

    def load_history(self, chain_codes: Sequence[str], limit: int = 3) -> dict[str, tuple[SelectedChain, ...]]:
        output: dict[str, list[SelectedChain]] = {code: [] for code in chain_codes}
        for result in reversed(self.results):
            for chain in result.chains:
                if chain.chain_code in output and len(output[chain.chain_code]) < limit:
                    output[chain.chain_code].append(chain)
        return {key: tuple(value) for key, value in output.items()}

    def save_success(self, result: RotationRunResult) -> None:
        self.results.append(result)

    def save_failure(self, run_id: str, code: str, message: str) -> None:
        self.failures[run_id] = (code, message)

    def load_latest_result(self) -> RotationRunResult | None:
        return self.results[-1] if self.results else None


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _json_dump(value: Any) -> str:
    return json.dumps(_json_value(value), ensure_ascii=False, separators=(",", ":"))


class SQLRotationRepository:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def start_run(self, *, observed_at: datetime, trade_date: date, edition: str, policy_version: str) -> str:
        run_id = uuid4().hex
        self.connection.execute(text("""
            INSERT INTO sector_rotation_runs
                (run_id, trade_date, observed_at, edition, status, threshold_version)
            VALUES (:run_id, :trade_date, :observed_at, :edition, 'RUNNING', :version)
        """), {"run_id": run_id, "trade_date": trade_date, "observed_at": observed_at,
               "edition": edition, "version": policy_version})
        self.connection.commit()
        return run_id

    def load_history(self, chain_codes: Sequence[str], limit: int = 3) -> dict[str, tuple[SelectedChain, ...]]:
        latest = self.load_latest_result()
        output = {code: [] for code in chain_codes}
        if latest is not None:
            for chain in latest.chains:
                if chain.chain_code in output and limit > 0:
                    output[chain.chain_code].append(chain)
        return {key: tuple(value) for key, value in output.items()}

    def save_success(self, result: RotationRunResult) -> None:
        try:
            self.connection.execute(text("""
                INSERT INTO sector_rotation_runs
                    (run_id, trade_date, observed_at, edition, status, threshold_version,
                     warning_json, result_json)
                VALUES (:run_id, :trade_date, :observed_at, :edition, 'SUCCESS', :version,
                        :warnings, :result)
                ON DUPLICATE KEY UPDATE status='SUCCESS', warning_json=VALUES(warning_json),
                    result_json=VALUES(result_json), error_code=NULL, error_message=NULL
            """), {"run_id": result.run_id, "trade_date": result.trade_date,
                   "observed_at": result.observed_at, "edition": result.edition,
                   "version": result.policy_version, "warnings": _json_dump(result.warnings),
                   "result": _json_dump(asdict(result))})
            for chain in result.chains:
                self.connection.execute(text("""
                    INSERT INTO sector_rotation_snapshots
                        (run_id, chain_code, chain_name, parent_code, observed_at,
                         threshold_version, state, bucket, data_complete, total_score,
                         strength_score, breadth_score, amount_score, persistence_score,
                         structure_score, overheat_penalty, reasons_json, raw_json)
                    VALUES (:run_id,:chain_code,:chain_name,:parent_code,:observed_at,
                            :version,:state,:bucket,:complete,:total,:strength,:breadth,
                            :amount,:persistence,:structure,:penalty,:reasons,:raw)
                """), {"run_id": result.run_id, "chain_code": chain.chain_code,
                       "chain_name": chain.chain_name, "parent_code": chain.parent_code,
                       "observed_at": result.observed_at, "version": result.policy_version,
                       "state": chain.state.value if chain.state else None,
                       "bucket": chain.bucket.value, "complete": chain.metrics.data_complete,
                       "total": chain.score.total, "strength": chain.score.strength_score,
                       "breadth": chain.score.breadth_score, "amount": chain.score.amount_score,
                       "persistence": chain.score.persistence_score,
                       "structure": chain.score.structure_score,
                       "penalty": chain.score.overheat_penalty,
                       "reasons": _json_dump(chain.score.reasons + chain.state_reasons),
                       "raw": _json_dump(asdict(chain))})
            for candidate in result.candidates:
                levels = candidate.levels
                self.connection.execute(text("""
                    INSERT INTO sector_rotation_candidates
                        (run_id, chain_code, ts_code, stock_name, observed_at, role, pool_rank,
                         formal_eligible, held, watch_price, trigger_price, no_chase_price,
                         invalidation_price, reasons_json, rejection_json, raw_json)
                    VALUES (:run_id,:chain_code,:code,:name,:observed_at,:role,:rank,:formal,
                            :held,:watch,:trigger,:no_chase,:invalidation,:reasons,:rejections,:raw)
                """), {"run_id": result.run_id, "chain_code": candidate.chain_code,
                       "code": candidate.code, "name": candidate.name,
                       "observed_at": result.observed_at, "role": candidate.role.value,
                       "rank": candidate.pool_rank, "formal": candidate.formal_eligible,
                       "held": candidate.held,
                       "watch": levels.watch_price if levels else None,
                       "trigger": levels.trigger_price if levels else None,
                       "no_chase": levels.no_chase_price if levels else None,
                       "invalidation": levels.invalidation_price if levels else None,
                       "reasons": _json_dump(candidate.reasons),
                       "rejections": _json_dump(candidate.rejection_reasons),
                       "raw": _json_dump(asdict(candidate))})
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def save_failure(self, run_id: str, code: str, message: str) -> None:
        self.connection.execute(text("""
            UPDATE sector_rotation_runs SET status='FAILED', error_code=:code,
                error_message=:message WHERE run_id=:run_id
        """), {"run_id": run_id, "code": code, "message": message})
        self.connection.commit()

    def load_latest_result(self) -> RotationRunResult | None:
        row = self.connection.execute(text("""
            SELECT result_json FROM sector_rotation_runs
            WHERE status='SUCCESS' ORDER BY observed_at DESC LIMIT 1
        """)).fetchone()
        if row is None or not row.result_json:
            return None
        return _decode_result(json.loads(row.result_json))


def _decode_result(raw: dict[str, Any]) -> RotationRunResult:
    chains = []
    for item in raw["chains"]:
        metrics = ChainMetrics(**{
            **item["metrics"],
            **{key: Decimal(str(item["metrics"][key])) for key in (
                "return_percentile", "rank_improvement", "breadth_ratio", "above_ma5_ratio",
                "above_ma20_ratio", "amount_ratio", "advancing_amount_ratio", "leader_concentration")},
        })
        score = ChainScore(**{
            **item["score"],
            **{key: Decimal(str(item["score"][key])) for key in (
                "total", "strength_score", "breadth_score", "amount_score",
                "persistence_score", "structure_score", "overheat_penalty")},
            "reasons": tuple(item["score"]["reasons"]),
        })
        chains.append(SelectedChain(
            item["chain_code"], item["chain_name"], item["parent_code"],
            tuple(item["raw_sector_codes"]), tuple(item["raw_sector_names"]), item["best_rank"],
            Decimal(str(item["raw_change_pct"])), metrics, score,
            RotationState(item["state"]) if item["state"] else None,
            RotationState(item["previous_state"]) if item["previous_state"] else None,
            tuple(item["state_reasons"]), tuple(item["coexistence_codes"]),
            tuple(item["member_codes"]), RotationBucket(item["bucket"]),
        ))
    candidates = []
    for item in raw["candidates"]:
        levels = item["levels"]
        typed_levels = PriceLevels(**{key: Decimal(str(value)) for key, value in levels.items()}) if levels else None
        candidates.append(RotationCandidate(
            item["chain_code"], item["code"], item["name"], CandidateRole(item["role"]),
            item["pool_rank"], item["formal_eligible"], item["held"], item["metrics"],
            typed_levels, tuple(item["reasons"]), tuple(item["rejection_reasons"]),
        ))
    return RotationRunResult(
        raw["run_id"], datetime.fromisoformat(raw["observed_at"]), date.fromisoformat(raw["trade_date"]),
        raw["edition"], raw["policy_version"], tuple(chains), tuple(candidates),
        tuple(raw["warnings"]), Path(raw["report_path"]) if raw.get("report_path") else None,
    )
