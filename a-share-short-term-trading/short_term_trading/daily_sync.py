"""Critical-symbol daily-bar synchronization with auditable OpenCLI fallback."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
import json
import os
from pathlib import Path
import sys
from typing import Callable, Protocol
from uuid import uuid4


MAX_CRITICAL_CODES = 8
DEFAULT_LOOKBACK_BARS = 120
DEFAULT_REPAIR_DAYS = 3


@dataclass(frozen=True)
class DailyBar:
    ts_code: str
    exch_code: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    pre_close: float | None
    change_amount: float | None
    pct_chg: float | None
    vol: int
    amount: float


class DailyBarRepository(Protocol):
    def get_recent_bars(self, code: str, limit: int) -> list[DailyBar]: ...

    def upsert_daily_bars(self, bars: list[DailyBar]) -> int: ...

    def record_sync_run(self, payload: dict[str, object]) -> None: ...


KlineFetcher = Callable[[list[str], int], dict[str, list[list[str]]]]


def normalize_code(value: str) -> str:
    code = str(value).split(".")[0].strip().zfill(6)
    if len(code) != 6 or not code.isdigit():
        raise ValueError(f"invalid A-share code: {value}")
    return code


def exchange_for(code: str) -> str:
    return "SH" if code.startswith(("6", "9")) else "SZ"


def default_target_date(now: datetime | None = None) -> date:
    current = now or datetime.now()
    target = current.date()
    if current.time() < time(16, 0):
        target -= timedelta(days=1)
    while target.weekday() >= 5:
        target -= timedelta(days=1)
    return target


def parse_eastmoney_kline(code: str, row: list[str]) -> DailyBar:
    if len(row) < 10:
        raise ValueError(f"{code}: incomplete kline row")
    trade_date = date.fromisoformat(row[0])
    amount_yuan = float(row[6])
    return DailyBar(
        ts_code=code,
        exch_code=exchange_for(code),
        trade_date=trade_date,
        open=float(row[1]),
        close=float(row[2]),
        high=float(row[3]),
        low=float(row[4]),
        pre_close=None,
        change_amount=float(row[9]),
        pct_chg=float(row[8]),
        vol=int(float(row[5])),
        amount=amount_yuan / 1000,
    )


def bar_is_complete(bar: DailyBar) -> bool:
    return (
        bar.open > 0
        and bar.high > 0
        and bar.low > 0
        and bar.close > 0
        and bar.high >= max(bar.open, bar.close, bar.low)
        and bar.low <= min(bar.open, bar.close, bar.high)
        and bar.vol >= 0
        and bar.amount >= 0
    )


def _is_ready(bars: list[DailyBar], target: date, repair_days: int) -> bool:
    ordered = sorted(bars, key=lambda item: item.trade_date, reverse=True)
    if not ordered or ordered[0].trade_date != target:
        return False
    return len(ordered) >= repair_days and all(bar_is_complete(bar) for bar in ordered[:repair_days])


def default_opencli_fetcher(codes: list[str], limit: int) -> dict[str, list[list[str]]]:
    workspace_root = Path(__file__).resolve().parents[2]
    stock_ai_root = Path(os.getenv("STOCK_AI_ROOT", workspace_root / "stock-ai"))
    if not stock_ai_root.exists():
        raise RuntimeError("STOCK_AI_ROOT is unavailable for the OpenCLI adapter")
    sys.path.insert(0, str(stock_ai_root))
    from scripts.tools.fetch_eastmoney_quotes import fetch_kline_rows_batch_opencli

    return fetch_kline_rows_batch_opencli(codes, limit=limit, close_browser=True, reset_browser=True)


def synchronize_critical_daily_bars(
    repository: DailyBarRepository,
    codes: list[str],
    *,
    target_date: date | None = None,
    lookback_bars: int = DEFAULT_LOOKBACK_BARS,
    repair_days: int = DEFAULT_REPAIR_DAYS,
    fetcher: KlineFetcher = default_opencli_fetcher,
    dry_run: bool = False,
    now: datetime | None = None,
) -> dict[str, object]:
    requested = list(dict.fromkeys(normalize_code(code) for code in codes))
    if not requested:
        raise ValueError("critical scope requires at least one code")
    if len(requested) > MAX_CRITICAL_CODES:
        raise ValueError(f"critical scope accepts at most {MAX_CRITICAL_CODES} codes")
    if lookback_bars < 60:
        raise ValueError("lookback_bars must be at least 60")
    if repair_days < 1:
        raise ValueError("repair_days must be positive")

    run_id = str(uuid4())
    started_at = datetime.now().isoformat(timespec="seconds")
    target = target_date or default_target_date(now)
    ready_codes: list[str] = []
    stale_codes: list[str] = []
    missing_dates: dict[str, list[str]] = {}
    evidence_refs: dict[str, str] = {}

    for code in requested:
        existing = repository.get_recent_bars(code, repair_days)
        if _is_ready(existing, target, repair_days):
            ready_codes.append(code)
        else:
            stale_codes.append(code)
            missing_dates[code] = [target.isoformat()]

    upserted_rows = 0
    failure_reasons: dict[str, str] = {}
    if stale_codes and not dry_run:
        raw_rows = fetcher(stale_codes, lookback_bars)
        for code in stale_codes:
            try:
                parsed = [parse_eastmoney_kline(code, row) for row in raw_rows.get(code, [])]
                parsed = [bar for bar in parsed if bar_is_complete(bar)]
                latest = max((bar.trade_date for bar in parsed), default=None)
                if latest != target:
                    failure_reasons[code] = f"latest source date is {latest}, expected {target}"
                    continue
                upserted_rows += repository.upsert_daily_bars(parsed)
                refreshed = repository.get_recent_bars(code, repair_days)
                if _is_ready(refreshed, target, repair_days):
                    ready_codes.append(code)
                    evidence_refs[code] = f"eastmoney-opencli:kline:{code}:{target.isoformat()}"
                    missing_dates.pop(code, None)
                else:
                    failure_reasons[code] = "post-upsert validation failed"
            except Exception as exc:  # noqa: BLE001
                failure_reasons[code] = str(exc)

    failed_codes = [code for code in requested if code not in ready_codes]
    status = "READY" if not stale_codes else "UPDATED"
    if dry_run and stale_codes:
        status = "PARTIAL"
    elif failed_codes:
        status = "PARTIAL" if ready_codes else "FAILED"
    finished_at = datetime.now().isoformat(timespec="seconds")
    result: dict[str, object] = {
        "run_id": run_id,
        "scope": "critical",
        "target_trade_date": target.isoformat(),
        "source_policy": "mysql_then_opencli",
        "status": status,
        "requested_codes": requested,
        "ready_codes": sorted(ready_codes),
        "failed_codes": failed_codes,
        "coverage_ratio": len(ready_codes) / len(requested),
        "missing_dates": missing_dates,
        "upserted_rows": upserted_rows,
        "started_at": started_at,
        "finished_at": finished_at,
        "evidence_refs": evidence_refs,
        "failure_reasons": failure_reasons,
    }
    if not dry_run:
        repository.record_sync_run(result)
    return result


class SqlAlchemyDailyBarRepository:
    """MySQL implementation. SQLAlchemy is imported only for runtime use."""

    def __init__(self, mysql_url: str):
        from sqlalchemy import create_engine

        self._engine = create_engine(mysql_url)

    def get_recent_bars(self, code: str, limit: int) -> list[DailyBar]:
        from sqlalchemy import text

        query = text(
            "SELECT ts_code, exch_code, trade_date, open, high, low, close, pre_close, "
            "change_amount, pct_chg, vol, amount FROM stock_daily "
            "WHERE ts_code = :code ORDER BY trade_date DESC LIMIT :limit"
        )
        with self._engine.connect() as connection:
            rows = connection.execute(query, {"code": code, "limit": limit}).mappings()
            bars: list[DailyBar] = []
            for row in rows:
                values = dict(row)
                for field in ("open", "high", "low", "close", "pre_close", "change_amount", "pct_chg", "amount"):
                    if values[field] is not None:
                        values[field] = float(values[field])
                values["vol"] = int(values["vol"] or 0)
                bars.append(DailyBar(**values))
            return bars

    def upsert_daily_bars(self, bars: list[DailyBar]) -> int:
        if not bars:
            return 0
        from sqlalchemy import text

        statement = text(
            "INSERT INTO stock_daily (ts_code, exch_code, trade_date, open, high, low, close, "
            "pre_close, change_amount, pct_chg, vol, amount) VALUES "
            "(:ts_code, :exch_code, :trade_date, :open, :high, :low, :close, :pre_close, "
            ":change_amount, :pct_chg, :vol, :amount) ON DUPLICATE KEY UPDATE "
            "exch_code=VALUES(exch_code), open=VALUES(open), high=VALUES(high), low=VALUES(low), "
            "close=VALUES(close), pre_close=VALUES(pre_close), change_amount=VALUES(change_amount), "
            "pct_chg=VALUES(pct_chg), vol=VALUES(vol), amount=VALUES(amount), update_time=CURRENT_TIMESTAMP"
        )
        payload = [asdict(bar) for bar in bars]
        with self._engine.begin() as connection:
            connection.execute(statement, payload)
        return len(payload)

    def record_sync_run(self, payload: dict[str, object]) -> None:
        from sqlalchemy import text

        statement = text(
            "INSERT INTO stt_daily_sync_runs (run_id, scope, target_trade_date, source_policy, status, "
            "requested_codes, ready_codes, failed_codes, coverage_ratio, upserted_rows, started_at, finished_at, "
            "evidence_refs, failure_reasons) VALUES "
            "(:run_id, :scope, :target_trade_date, :source_policy, :status, :requested_codes, :ready_codes, "
            ":failed_codes, :coverage_ratio, :upserted_rows, :started_at, :finished_at, :evidence_refs, :failure_reasons)"
        )
        values = dict(payload)
        for key in ("requested_codes", "ready_codes", "failed_codes", "evidence_refs", "failure_reasons"):
            values[key] = json.dumps(values[key], ensure_ascii=False)
        with self._engine.begin() as connection:
            connection.execute(statement, values)
