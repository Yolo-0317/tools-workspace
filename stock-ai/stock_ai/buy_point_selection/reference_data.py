"""Point-in-time sector and risk reference facts for buy-point selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from typing import Callable, Iterable, Literal, Mapping, Protocol, Sequence
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection, Engine


RiskSeverity = Literal["OBSERVE", "VETO"]


@dataclass(frozen=True)
class SectorMembership:
    code: str
    sector_code: str
    sector_name: str
    valid_from: date
    valid_to: date | None
    source: str


@dataclass(frozen=True)
class RiskFlag:
    code: str
    flag_type: str
    severity: RiskSeverity
    effective_from: date
    effective_to: date | None
    source: str
    evidence_ref: str = ""


@dataclass(frozen=True)
class ReferenceCoverage:
    analysis_date: date
    sector_complete: bool
    st_complete: bool
    announcement_complete: bool

    @property
    def complete(self) -> bool:
        return self.sector_complete and self.st_complete and self.announcement_complete


@dataclass(frozen=True)
class ReferenceSyncRun:
    run_id: str
    dataset: Literal["sector", "st", "announcement"]
    start_date: date
    end_date: date
    status: Literal["COMPLETE", "FAILED"]
    row_count: int
    error_code: str | None
    captured_at: datetime
    provider: str = "TUSHARE"
    expected_count: int | None = None
    coverage_ratio: Decimal | None = None
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ReferenceCheckpoint:
    provider: str
    dataset: str
    partition_key: str
    cursor_value: str | None
    status: Literal["RUNNING", "COMPLETE", "FAILED"]
    error_code: str | None
    details: Mapping[str, object]
    updated_at: datetime


class ReferenceRepository(Protocol):
    def upsert_sector_memberships(
        self, rows: Sequence[SectorMembership], captured_at: datetime
    ) -> int: ...

    def upsert_risk_flags(self, rows: Sequence[RiskFlag], captured_at: datetime) -> int: ...

    def save_sync_run(self, run: ReferenceSyncRun) -> None: ...

    def save_checkpoint(self, checkpoint: ReferenceCheckpoint) -> None: ...

    def save_checkpoints(self, checkpoints: Sequence[ReferenceCheckpoint]) -> None: ...

    def load_checkpoint(
        self, provider: str, dataset: str, partition_key: str
    ) -> ReferenceCheckpoint | None: ...

    def load_checkpoints(
        self, provider: str, dataset: str, partition_keys: Sequence[str]
    ) -> Mapping[str, ReferenceCheckpoint]: ...

    def memberships_between(
        self, start: date, end: date
    ) -> tuple[SectorMembership, ...]: ...


class SQLReferenceRepository:
    """MySQL adapter; all reads preserve the requested analysis date."""

    def __init__(self, database: Engine | Connection) -> None:
        self._database = database

    def _begin(self):
        begin = getattr(self._database, "begin", None)
        if isinstance(self._database, Engine) and callable(begin):
            return begin()
        return _BorrowedConnection(self._database)

    def upsert_sector_memberships(
        self, rows: Sequence[SectorMembership], captured_at: datetime
    ) -> int:
        statement = text(
            "INSERT INTO buy_point_sector_memberships "
            "(code, sector_code, sector_name, valid_from, valid_to, source, captured_at) "
            "VALUES (:code, :sector_code, :sector_name, :valid_from, :valid_to, :source, :captured_at) "
            "ON DUPLICATE KEY UPDATE sector_name=VALUES(sector_name), "
            "valid_to=VALUES(valid_to), source=VALUES(source), captured_at=VALUES(captured_at)"
        )
        payload = [
            {
                "code": row.code,
                "sector_code": row.sector_code,
                "sector_name": row.sector_name,
                "valid_from": row.valid_from,
                "valid_to": row.valid_to,
                "source": row.source,
                "captured_at": captured_at,
            }
            for row in rows
        ]
        if payload:
            with self._begin() as connection:
                connection.execute(statement, payload)
        return len(payload)

    def upsert_risk_flags(self, rows: Sequence[RiskFlag], captured_at: datetime) -> int:
        statement = text(
            "INSERT INTO buy_point_risk_flags "
            "(flag_id, code, flag_type, severity, effective_from, effective_to, "
            "source, evidence_ref, captured_at) VALUES "
            "(:flag_id, :code, :flag_type, :severity, :effective_from, :effective_to, "
            ":source, :evidence_ref, :captured_at) "
            "ON DUPLICATE KEY UPDATE severity=VALUES(severity), "
            "effective_to=VALUES(effective_to), evidence_ref=VALUES(evidence_ref), "
            "captured_at=VALUES(captured_at)"
        )
        payload = []
        for row in rows:
            identity = json.dumps(
                [row.code, row.flag_type, row.effective_from.isoformat(), row.source],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            payload.append(
                {
                    "flag_id": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                    "code": row.code,
                    "flag_type": row.flag_type,
                    "severity": row.severity,
                    "effective_from": row.effective_from,
                    "effective_to": row.effective_to,
                    "source": row.source,
                    "evidence_ref": row.evidence_ref,
                    "captured_at": captured_at,
                }
            )
        if payload:
            with self._begin() as connection:
                connection.execute(statement, payload)
        return len(payload)

    def save_sync_run(self, run: ReferenceSyncRun) -> None:
        statement = text(
            "INSERT INTO buy_point_reference_sync_runs "
            "(run_id, dataset, provider, start_date, end_date, status, row_count, "
            "expected_count, coverage_ratio, error_code, details_json, captured_at) "
            "VALUES (:run_id, :dataset, :provider, :start_date, :end_date, :status, "
            ":row_count, :expected_count, :coverage_ratio, :error_code, :details_json, "
            ":captured_at) ON DUPLICATE KEY UPDATE "
            "status=VALUES(status), row_count=VALUES(row_count), "
            "provider=VALUES(provider), expected_count=VALUES(expected_count), "
            "coverage_ratio=VALUES(coverage_ratio), error_code=VALUES(error_code), "
            "details_json=VALUES(details_json), captured_at=VALUES(captured_at)"
        )
        values = dict(run.__dict__)
        values.pop("details")
        values["details_json"] = json.dumps(
            dict(run.details), ensure_ascii=False, separators=(",", ":"), default=str
        )
        with self._begin() as connection:
            connection.execute(statement, values)

    def save_checkpoint(self, checkpoint: ReferenceCheckpoint) -> None:
        self.save_checkpoints((checkpoint,))

    def save_checkpoints(self, checkpoints: Sequence[ReferenceCheckpoint]) -> None:
        statement = text(
            "INSERT INTO buy_point_reference_checkpoints "
            "(provider, dataset, partition_key, cursor_value, status, error_code, "
            "details_json, updated_at) VALUES (:provider, :dataset, :partition_key, "
            ":cursor_value, :status, :error_code, :details_json, :updated_at) "
            "ON DUPLICATE KEY UPDATE cursor_value=VALUES(cursor_value), "
            "status=VALUES(status), error_code=VALUES(error_code), "
            "details_json=VALUES(details_json), updated_at=VALUES(updated_at)"
        )
        values = []
        for checkpoint in checkpoints:
            row = dict(checkpoint.__dict__)
            row.pop("details")
            row["details_json"] = json.dumps(
                dict(checkpoint.details),
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
            values.append(row)
        if not values:
            return
        with self._begin() as connection:
            connection.execute(statement, values)

    def load_checkpoint(
        self, provider: str, dataset: str, partition_key: str
    ) -> ReferenceCheckpoint | None:
        statement = text(
            "SELECT provider, dataset, partition_key, cursor_value, status, error_code, "
            "details_json, updated_at FROM buy_point_reference_checkpoints "
            "WHERE provider=:provider AND dataset=:dataset AND partition_key=:partition_key"
        )
        rows = self._read(
            statement,
            {
                "provider": provider,
                "dataset": dataset,
                "partition_key": partition_key,
            },
        )
        if not rows:
            return None
        return self._checkpoint_from_row(rows[0])

    def load_checkpoints(
        self, provider: str, dataset: str, partition_keys: Sequence[str]
    ) -> Mapping[str, ReferenceCheckpoint]:
        keys = tuple(dict.fromkeys(partition_keys))
        if not keys:
            return {}
        statement = text(
            "SELECT provider, dataset, partition_key, cursor_value, status, error_code, "
            "details_json, updated_at FROM buy_point_reference_checkpoints "
            "WHERE provider=:provider AND dataset=:dataset "
            "AND partition_key IN :partition_keys"
        ).bindparams(bindparam("partition_keys", expanding=True))
        rows = self._read(
            statement,
            {"provider": provider, "dataset": dataset, "partition_keys": keys},
        )
        checkpoints = tuple(self._checkpoint_from_row(row) for row in rows)
        return {row.partition_key: row for row in checkpoints}

    @staticmethod
    def _checkpoint_from_row(row: Mapping[str, object]) -> ReferenceCheckpoint:
        raw_details = row["details_json"]
        details = (
            json.loads(raw_details)
            if isinstance(raw_details, str)
            else dict(raw_details or {})
        )
        return ReferenceCheckpoint(
            provider=str(row["provider"]),
            dataset=str(row["dataset"]),
            partition_key=str(row["partition_key"]),
            cursor_value=(
                None if row["cursor_value"] is None else str(row["cursor_value"])
            ),
            status=str(row["status"]),
            error_code=(None if row["error_code"] is None else str(row["error_code"])),
            details=details,
            updated_at=row["updated_at"],
        )

    def memberships_between(
        self, start: date, end: date
    ) -> tuple[SectorMembership, ...]:
        statement = text(
            "SELECT code, sector_code, sector_name, valid_from, valid_to, source "
            "FROM buy_point_sector_memberships WHERE valid_from <= :end "
            "AND (valid_to IS NULL OR valid_to >= :start) "
            "ORDER BY code, valid_from, sector_code"
        )
        rows = self._read(statement, {"start": start, "end": end})
        return tuple(
            SectorMembership(
                code=str(row["code"]),
                sector_code=str(row["sector_code"]),
                sector_name=str(row["sector_name"]),
                valid_from=row["valid_from"],
                valid_to=row["valid_to"],
                source=str(row["source"]),
            )
            for row in rows
        )

    def membership_on(self, analysis_date: date) -> dict[str, SectorMembership]:
        statement = text(
            "SELECT code, sector_code, sector_name, valid_from, valid_to, source "
            "FROM buy_point_sector_memberships WHERE valid_from <= :analysis_date "
            "AND (valid_to IS NULL OR valid_to >= :analysis_date)"
        )
        rows = self._read(statement, {"analysis_date": analysis_date})
        return membership_on(
            (
                SectorMembership(
                    str(row["code"]),
                    str(row["sector_code"]),
                    str(row["sector_name"]),
                    row["valid_from"],
                    row["valid_to"],
                    str(row["source"]),
                )
                for row in rows
            ),
            analysis_date,
        )

    def risk_flags_on(self, analysis_date: date) -> dict[str, tuple[RiskFlag, ...]]:
        statement = text(
            "SELECT code, flag_type, severity, effective_from, effective_to, source, evidence_ref "
            "FROM buy_point_risk_flags WHERE effective_from <= :analysis_date "
            "AND (effective_to IS NULL OR effective_to >= :analysis_date)"
        )
        rows = self._read(statement, {"analysis_date": analysis_date})
        return risk_flags_on(
            (
                RiskFlag(
                    str(row["code"]),
                    str(row["flag_type"]),
                    str(row["severity"]),
                    row["effective_from"],
                    row["effective_to"],
                    str(row["source"]),
                    str(row["evidence_ref"] or ""),
                )
                for row in rows
            ),
            analysis_date,
        )

    def coverage(self, analysis_date: date) -> ReferenceCoverage:
        statement = text(
            "SELECT dataset FROM buy_point_reference_sync_runs "
            "WHERE status='COMPLETE' AND start_date <= :analysis_date "
            "AND end_date >= :analysis_date GROUP BY dataset"
        )
        datasets = {
            str(row["dataset"])
            for row in self._read(statement, {"analysis_date": analysis_date})
        }
        return ReferenceCoverage(
            analysis_date,
            sector_complete="sector" in datasets,
            st_complete="st" in datasets,
            announcement_complete="announcement" in datasets,
        )

    def _read(self, statement, parameters: Mapping[str, object]):
        if isinstance(self._database, Engine):
            with self._database.connect() as connection:
                return list(connection.execute(statement, parameters).mappings())
        return list(self._database.execute(statement, parameters).mappings())


class _BorrowedConnection:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def __enter__(self) -> Connection:
        return self._connection

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def _code6(value: object) -> str:
    raw = str(value or "").split(".")[0]
    if not raw.isdigit():
        raise ValueError("stock code must be numeric")
    return raw.zfill(6)


def _date8(value: object) -> date:
    raw = str(value or "").strip().replace("-", "")
    if len(raw) != 8 or not raw.isdigit():
        raise ValueError("date must be YYYYMMDD")
    return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))


def _optional_date8(value: object) -> date | None:
    raw = str(value or "").strip()
    return None if not raw or raw.lower() == "nan" else _date8(raw)


def _active(start: date, end: date | None, on: date) -> bool:
    return start <= on and (end is None or on <= end)


def membership_on(
    rows: Iterable[SectorMembership], analysis_date: date
) -> dict[str, SectorMembership]:
    resolved: dict[str, SectorMembership] = {}
    for row in rows:
        if not _active(row.valid_from, row.valid_to, analysis_date):
            continue
        current = resolved.get(row.code)
        if current is not None and current.sector_code != row.sector_code:
            raise ValueError(f"overlapping sector memberships for {row.code}")
        resolved[row.code] = row
    return resolved


def risk_flags_on(
    rows: Iterable[RiskFlag], analysis_date: date
) -> dict[str, tuple[RiskFlag, ...]]:
    grouped: dict[str, list[RiskFlag]] = {}
    for row in rows:
        if _active(row.effective_from, row.effective_to, analysis_date):
            grouped.setdefault(row.code, []).append(row)
    return {
        code: tuple(sorted(values, key=lambda item: (item.flag_type, item.source)))
        for code, values in sorted(grouped.items())
    }


def normalize_sector_memberships(
    rows: Iterable[Mapping[str, object]],
    *,
    previous_trade_date: Callable[[date], date | None],
) -> tuple[SectorMembership, ...]:
    normalized: list[SectorMembership] = []
    for row in rows:
        raw_out = _optional_date8(row.get("out_date"))
        valid_to = previous_trade_date(raw_out) if raw_out is not None else None
        if raw_out is not None and valid_to is None:
            raise ValueError(f"cannot resolve trading day before {raw_out.isoformat()}")
        normalized.append(
            SectorMembership(
                code=_code6(row.get("ts_code")),
                sector_code=str(row.get("l1_code") or "").strip(),
                sector_name=str(row.get("l1_name") or "").strip(),
                valid_from=_date8(row.get("in_date")),
                valid_to=valid_to,
                source="tushare-index-member-all",
            )
        )
    if any(not row.sector_code or not row.sector_name for row in normalized):
        raise ValueError("sector code and name are required")
    return tuple(
        sorted(normalized, key=lambda item: (item.code, item.valid_from, item.sector_code))
    )


def classify_announcement_title(title: str) -> tuple[str, RiskSeverity] | None:
    veto_tokens = (
        ("立案调查", "REGULATORY_INVESTIGATION"),
        ("终止上市", "DELISTING"),
        ("退市风险警示", "DELISTING_RISK"),
        ("重大违法", "MAJOR_VIOLATION"),
        ("债务逾期", "DEBT_DEFAULT"),
    )
    normalized = str(title or "").strip()
    for token, flag_type in veto_tokens:
        if token in normalized:
            return flag_type, "VETO"
    return None


def normalize_st_flags(rows: Iterable[Mapping[str, object]]) -> tuple[RiskFlag, ...]:
    normalized: list[RiskFlag] = []
    for row in rows:
        trade_date = _date8(row.get("trade_date"))
        code = _code6(row.get("ts_code"))
        normalized.append(
            RiskFlag(
                code=code,
                flag_type="ST",
                severity="VETO",
                effective_from=trade_date,
                effective_to=trade_date,
                source="tushare-stock-st",
                evidence_ref=f"stock_st:{code}:{trade_date.isoformat()}",
            )
        )
    return tuple(sorted(normalized, key=lambda item: (item.effective_from, item.code)))


def normalize_announcement_flags(
    rows: Iterable[Mapping[str, object]],
) -> tuple[RiskFlag, ...]:
    normalized: list[RiskFlag] = []
    for row in rows:
        classified = classify_announcement_title(str(row.get("title") or ""))
        if classified is None:
            continue
        flag_type, severity = classified
        normalized.append(
            RiskFlag(
                code=_code6(row.get("ts_code")),
                flag_type=flag_type,
                severity=severity,
                effective_from=_date8(row.get("ann_date")),
                effective_to=None,
                source="tushare-anns-d",
                evidence_ref=str(row.get("url") or "").strip(),
            )
        )
    return tuple(
        sorted(normalized, key=lambda item: (item.effective_from, item.code, item.flag_type))
    )


def _records(value: object) -> list[Mapping[str, object]]:
    if value is None:
        return []
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        records = to_dict("records")
        return [dict(row) for row in records]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        return [dict(row) for row in value]
    raise TypeError("provider result must be a DataFrame or iterable of mappings")


def _sync_run(
    dataset: Literal["sector", "st", "announcement"],
    start: date,
    end: date,
    status: Literal["COMPLETE", "FAILED"],
    row_count: int,
    captured_at: datetime,
    error_code: str | None = None,
) -> ReferenceSyncRun:
    identity = f"buy-point-reference:{dataset}:{start}:{end}:{status}:{error_code or ''}"
    return ReferenceSyncRun(
        run_id=str(uuid5(NAMESPACE_URL, identity)),
        dataset=dataset,
        start_date=start,
        end_date=end,
        status=status,
        row_count=row_count,
        error_code=error_code,
        captured_at=captured_at,
    )


def _provider_error_code(exc: Exception) -> str:
    message = str(exc)
    if "没有接口(" in message and "访问权限" in message:
        return "TUSHARE_PERMISSION_DENIED"
    return type(exc).__name__


def sync_reference_data(
    pro: object,
    repository: ReferenceRepository,
    trade_dates: Sequence[date],
    *,
    captured_at: datetime,
) -> tuple[ReferenceSyncRun, ...]:
    ordered = tuple(trade_dates)
    if not ordered or any(current <= previous for previous, current in zip(ordered, ordered[1:])):
        raise ValueError("trade_dates must be non-empty and strictly increasing")
    start, end = ordered[0], ordered[-1]
    runs: list[ReferenceSyncRun] = []

    def previous_trade_date(value: date) -> date | None:
        return max((item for item in ordered if item < value), default=None)

    try:
        classifications = _records(pro.index_classify(level="L1", src="SW2021"))
        raw_members: list[Mapping[str, object]] = []
        for row in classifications:
            sector_code = str(row.get("index_code") or row.get("l1_code") or "").strip()
            if not sector_code:
                raise ValueError("index_classify row has no index code")
            raw_members.extend(
                _records(pro.index_member_all(l1_code=sector_code, is_new="N"))
            )
        raw_members = [
            row
            for row in raw_members
            if _date8(row.get("in_date")) <= end
            and (
                _optional_date8(row.get("out_date")) is None
                or _optional_date8(row.get("out_date")) > start
            )
        ]
        memberships = normalize_sector_memberships(
            raw_members, previous_trade_date=previous_trade_date
        )
        count = repository.upsert_sector_memberships(memberships, captured_at)
        run = _sync_run("sector", start, end, "COMPLETE", count, captured_at)
    except Exception as exc:  # noqa: BLE001 - provider failures become auditable coverage
        run = _sync_run(
            "sector", start, end, "FAILED", 0, captured_at, _provider_error_code(exc)
        )
    repository.save_sync_run(run)
    runs.append(run)

    try:
        raw_st = [
            row
            for trade_date in ordered
            for row in _records(pro.stock_st(trade_date=trade_date.strftime("%Y%m%d")))
        ]
        flags = normalize_st_flags(raw_st)
        count = repository.upsert_risk_flags(flags, captured_at)
        run = _sync_run("st", start, end, "COMPLETE", count, captured_at)
    except Exception as exc:  # noqa: BLE001
        run = _sync_run(
            "st", start, end, "FAILED", 0, captured_at, _provider_error_code(exc)
        )
    repository.save_sync_run(run)
    runs.append(run)

    try:
        raw_announcements = [
            row
            for trade_date in ordered
            for row in _records(pro.anns_d(ann_date=trade_date.strftime("%Y%m%d")))
        ]
        flags = normalize_announcement_flags(raw_announcements)
        count = repository.upsert_risk_flags(flags, captured_at)
        run = _sync_run("announcement", start, end, "COMPLETE", count, captured_at)
    except Exception as exc:  # noqa: BLE001
        run = _sync_run(
            "announcement",
            start,
            end,
            "FAILED",
            0,
            captured_at,
            _provider_error_code(exc),
        )
    repository.save_sync_run(run)
    runs.append(run)
    return tuple(runs)
