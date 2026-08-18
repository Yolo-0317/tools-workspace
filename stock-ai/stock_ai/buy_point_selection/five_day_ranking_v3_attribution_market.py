"""Bounded read-only market loading shared by ranking V3 diagnostics."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
from typing import Callable, Mapping, Sequence

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from .five_day_ranking_v3_attribution import matched_index_id
from stock_ai.market_codes import (
    is_sh_sz_main_board_code,
    normalize_code6,
)


ROOT = Path(__file__).resolve().parents[2]
INDEX_ORDER = ("sh.000001", "sz.399001", "sh.000688")


def configured_read_only_engine(
    *,
    engine_factory: Callable[..., object] = create_engine,
    env_loader: Callable[..., object] = load_dotenv,
) -> object:
    """Create the configured pre-ping engine without mutating MYSQL_URL."""

    env_loader(ROOT / ".env", override=False)
    mysql_url = os.environ.get("MYSQL_URL", "").replace(
        "host.docker.internal",
        "127.0.0.1",
    )
    if not mysql_url:
        raise RuntimeError("MYSQL_URL is not configured")
    return engine_factory(mysql_url, pool_pre_ping=True)


def _as_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def load_stock_closes(
    engine: object,
    start: date,
    end: date,
) -> dict[str, dict[date, Decimal]]:
    """Load finite positive main-board closes within literal SQL bounds."""

    statement = text(
        "SELECT ts_code, trade_date, close FROM stock_daily "
        "WHERE trade_date BETWEEN :start AND :end "
        "ORDER BY ts_code, trade_date"
    )
    with engine.connect() as connection:
        rows = connection.execute(
            statement,
            {"start": start, "end": end},
        ).mappings().all()
    closes: dict[str, dict[date, Decimal]] = {}
    for row in rows:
        raw_code = str(row["ts_code"])
        if not is_sh_sz_main_board_code(raw_code):
            continue
        try:
            trade_date = _as_date(row["trade_date"])
            close = Decimal(str(row["close"]))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if (
            not start <= trade_date <= end
            or not close.is_finite()
            or close <= 0
        ):
            continue
        code = normalize_code6(raw_code)
        closes.setdefault(code, {})[trade_date] = close
    return {
        code: dict(sorted(values.items()))
        for code, values in sorted(closes.items())
    }


def load_mysql_stock_closes(
    start: date,
    end: date,
    *,
    engine_loader: Callable[[], object] = configured_read_only_engine,
) -> dict[str, dict[date, Decimal]]:
    """Load bounded closes and always dispose the temporary engine."""

    engine = engine_loader()
    try:
        return load_stock_closes(engine, start, end)
    finally:
        dispose = getattr(engine, "dispose", None)
        if callable(dispose):
            dispose()


def required_index_ids(train_artifact: object) -> tuple[str, ...]:
    """Return only benchmark indexes referenced by train plan registries."""

    payload = train_artifact.payload
    if not isinstance(payload, Mapping):
        raise ValueError("invalid train payload")
    variants = payload.get("variants")
    if not isinstance(variants, list):
        raise ValueError("invalid train payload")
    required: set[str] = set()
    for variant in variants:
        if not isinstance(variant, Mapping):
            raise ValueError("invalid train payload")
        segment = variant.get("segment")
        if not isinstance(segment, Mapping):
            raise ValueError("invalid train payload")
        for field in ("admitted_trade_keys", "ranked_plan_keys"):
            plan_keys = segment.get(field)
            if not isinstance(plan_keys, list):
                raise ValueError("invalid train payload")
            for plan_key in plan_keys:
                if not isinstance(plan_key, Mapping) or "code" not in plan_key:
                    raise ValueError("invalid train payload")
                required.add(matched_index_id(str(plan_key["code"])))
    return tuple(index_id for index_id in INDEX_ORDER if index_id in required)


def load_required_benchmark_closes(
    required_indexes: Sequence[str],
    start: date,
    end: date,
    *,
    benchmark_loader: Callable[
        [date, date], Mapping[str, Sequence[object]]
    ],
) -> dict[str, dict[date, Decimal]]:
    """Normalize the requested benchmark subset at the identical bounds."""

    required = tuple(required_indexes)
    if len(required) != len(set(required)) or any(
        index_id not in INDEX_ORDER for index_id in required
    ):
        raise ValueError("invalid benchmark registry")
    if not required:
        return {}
    loaded = benchmark_loader(start, end)
    result: dict[str, dict[date, Decimal]] = {}
    for index_id in required:
        bars: dict[date, Decimal] = {}
        for bar in loaded.get(index_id, ()):
            try:
                trade_date = _as_date(bar.trade_date)
                close = Decimal(str(bar.close))
            except (AttributeError, InvalidOperation, TypeError, ValueError):
                continue
            if start <= trade_date <= end and close.is_finite() and close > 0:
                bars[trade_date] = close
        result[index_id] = dict(sorted(bars.items()))
    return result
