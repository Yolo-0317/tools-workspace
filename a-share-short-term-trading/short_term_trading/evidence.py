"""Validated evidence snapshots and capture-attempt audit records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal, Protocol
from uuid import uuid4


SnapshotKind = Literal[
    "market",
    "quote",
    "fund_flow",
    "sector",
    "order_book",
    "chip",
    "daily_technical",
    "event_risk",
    "theme_reference",
]

TTL_SECONDS: dict[str, int] = {
    "quote": 300,
    "order_book": 300,
    "fund_flow": 900,
    "sector": 900,
    "market": 900,
    "chip": 86400,
    "daily_technical": 86400,
    "event_risk": 86400,
    "theme_reference": 604800,
}

REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "quote": ("price", "change_pct", "amount", "turnover", "volume_ratio"),
    "fund_flow": ("main_net_inflow",),
    "sector": ("theme_name", "change_pct", "advancing_ratio", "leader_code"),
    "order_book": tuple([f"bid_{index}" for index in range(1, 6)] + [f"ask_{index}" for index in range(1, 6)]),
    "market": ("breadth", "amount"),
    "chip": (
        "source_trade_date",
        "cost_90_low",
        "cost_90_high",
        "average_cost",
        "profit_ratio",
        "concentration",
        "input_bar_count",
        "method",
    ),
    "daily_technical": ("ma5", "ma10", "ma20", "atr14", "high20", "low10"),
    "event_risk": ("title", "published_at", "url"),
    "theme_reference": ("industry", "concepts"),
}


@dataclass(frozen=True)
class EvidenceSnapshot:
    snapshot_id: str
    code: str | None
    kind: SnapshotKind
    as_of: datetime
    source: str
    parser_version: str
    data: dict[str, Any]
    raw_evidence_ref: str
    data_status: Literal["VALID"] = "VALID"


@dataclass(frozen=True)
class CaptureAttempt:
    attempt_id: str
    code: str | None
    kind: SnapshotKind
    source: str
    started_at: datetime
    finished_at: datetime
    status: Literal["SUCCESS", "PARSE_ERROR", "SOURCE_ERROR"]
    retry_count: int
    field_completeness: float
    parser_version: str
    raw_evidence_ref: str | None
    error_class: str | None
    error_message: str | None


class EvidenceRepository(Protocol):
    def save_snapshot(self, snapshot: EvidenceSnapshot) -> None: ...

    def save_capture_attempt(self, attempt: CaptureAttempt) -> None: ...


def _normalize_code(code: str | None) -> str | None:
    if code is None:
        return None
    normalized = str(code).split(".")[0].strip().zfill(6)
    if len(normalized) != 6 or not normalized.isdigit():
        raise ValueError(f"invalid code: {code}")
    return normalized


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def validate_snapshot(kind: SnapshotKind, code: str | None, data: dict[str, Any]) -> list[str]:
    if kind != "market" and not _normalize_code(code):
        return ["code is required"]
    missing = [field for field in REQUIRED_FIELDS[kind] if data.get(field) is None]
    errors = [f"missing:{field}" for field in missing]
    for name in (
        "price",
        "amount",
        "turnover",
        "volume_ratio",
        "cost_90_low",
        "cost_90_high",
        "average_cost",
        "atr14",
    ):
        value = data.get(name)
        if value is not None and (not isinstance(value, (int, float)) or value < 0):
            errors.append(f"invalid:{name}")
    if data.get("cost_90_low") is not None and data.get("cost_90_high") is not None:
        if data["cost_90_low"] > data["cost_90_high"]:
            errors.append("invalid:cost_range")
    if kind == "chip":
        try:
            date.fromisoformat(str(data.get("source_trade_date")))
        except ValueError:
            errors.append("invalid:source_trade_date")
        for name in ("profit_ratio", "concentration"):
            value = data.get(name)
            if not isinstance(value, (int, float)) or not 0 <= value <= 100:
                errors.append(f"invalid:{name}")
        count = data.get("input_bar_count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 20:
            errors.append("invalid:input_bar_count")
    return errors


def field_completeness(kind: SnapshotKind, data: dict[str, Any]) -> float:
    required = REQUIRED_FIELDS[kind]
    return sum(data.get(field) is not None for field in required) / len(required)


def is_fresh(snapshot: EvidenceSnapshot, now: datetime) -> bool:
    ttl_seconds = TTL_SECONDS[snapshot.kind]
    return _as_utc(snapshot.as_of) + timedelta(seconds=ttl_seconds) >= _as_utc(now)


def is_chip_snapshot_for_trade_date(
    snapshot: EvidenceSnapshot | None,
    expected_trade_date: date,
) -> bool:
    if snapshot is None or snapshot.kind != "chip":
        return False
    if validate_snapshot("chip", snapshot.code, snapshot.data):
        return False
    try:
        source_trade_date = date.fromisoformat(str(snapshot.data["source_trade_date"]))
    except (KeyError, ValueError):
        return False
    return source_trade_date == expected_trade_date


class CaptureRecorder:
    """Writes every capture attempt; only valid payloads become evidence snapshots."""

    def __init__(self, repository: EvidenceRepository) -> None:
        self._repository = repository

    def record_payload(
        self,
        *,
        kind: SnapshotKind,
        code: str | None,
        source: str,
        parser_version: str,
        data: dict[str, Any],
        raw_evidence_ref: str,
        started_at: datetime,
        finished_at: datetime,
        retry_count: int = 0,
    ) -> EvidenceSnapshot | None:
        normalized_code = _normalize_code(code)
        errors = validate_snapshot(kind, normalized_code, data)
        completeness = field_completeness(kind, data)
        status: Literal["SUCCESS", "PARSE_ERROR"] = "SUCCESS" if not errors else "PARSE_ERROR"
        self._repository.save_capture_attempt(
            CaptureAttempt(
                attempt_id=str(uuid4()),
                code=normalized_code,
                kind=kind,
                source=source,
                started_at=_as_utc(started_at),
                finished_at=_as_utc(finished_at),
                status=status,
                retry_count=retry_count,
                field_completeness=completeness,
                parser_version=parser_version,
                raw_evidence_ref=raw_evidence_ref,
                error_class="ValidationError" if errors else None,
                error_message=";".join(errors) if errors else None,
            )
        )
        if errors:
            return None
        snapshot = EvidenceSnapshot(
            snapshot_id=str(uuid4()),
            code=normalized_code,
            kind=kind,
            as_of=_as_utc(finished_at),
            source=source,
            parser_version=parser_version,
            data=data,
            raw_evidence_ref=raw_evidence_ref,
        )
        self._repository.save_snapshot(snapshot)
        return snapshot

    def record_source_error(
        self,
        *,
        kind: SnapshotKind,
        code: str | None,
        source: str,
        parser_version: str,
        started_at: datetime,
        finished_at: datetime,
        error: Exception,
        retry_count: int = 0,
    ) -> None:
        self._repository.save_capture_attempt(
            CaptureAttempt(
                attempt_id=str(uuid4()),
                code=_normalize_code(code),
                kind=kind,
                source=source,
                started_at=_as_utc(started_at),
                finished_at=_as_utc(finished_at),
                status="SOURCE_ERROR",
                retry_count=retry_count,
                field_completeness=0.0,
                parser_version=parser_version,
                raw_evidence_ref=None,
                error_class=type(error).__name__,
                error_message=str(error),
            )
        )


class SqlAlchemyEvidenceRepository:
    """Compatibility adapter backed by the focused repository package."""

    def __init__(self, mysql_url: str):
        from .repositories import EvidenceRepository as Repository
        from .repositories import create_mysql_engine

        self._repository = Repository(create_mysql_engine(mysql_url))

    def save_snapshot(self, snapshot: EvidenceSnapshot) -> None:
        self._repository.save_snapshot(snapshot)

    def save_capture_attempt(self, attempt: CaptureAttempt) -> None:
        self._repository.save_capture_attempt(attempt)

    def get_latest_valid_snapshot(self, code: str, kind: SnapshotKind) -> EvidenceSnapshot | None:
        return self._repository.get_latest_valid_snapshot(code, kind)

    def get_valid_snapshots_since(self, code: str, kind: SnapshotKind, since: datetime) -> list[EvidenceSnapshot]:
        return self._repository.get_valid_snapshots_since(code, kind, since)
