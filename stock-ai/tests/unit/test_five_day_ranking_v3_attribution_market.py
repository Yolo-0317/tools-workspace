from __future__ import annotations

from datetime import date
from decimal import Decimal
import os
from types import SimpleNamespace

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3_attribution_market import (
    configured_read_only_engine,
    load_mysql_stock_closes,
    load_required_benchmark_closes,
    load_stock_closes,
    required_index_ids,
)
from stock_ai.buy_point_selection.reference_sources import IndexBar


class _FakeMappings:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def all(self) -> list[dict[str, object]]:
        return self._rows


class _FakeResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> _FakeMappings:
        return _FakeMappings(self._rows)


class _FakeConnection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self.statement = ""
        self.parameters: dict[str, object] = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, statement, parameters):
        self.statement = " ".join(str(statement).split())
        self.parameters = dict(parameters)
        return _FakeResult(self._rows)


class _FakeEngine:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.connection = _FakeConnection(rows)
        self.disposed = False

    def connect(self) -> _FakeConnection:
        return self.connection

    def dispose(self) -> None:
        self.disposed = True


def test_stock_loader_uses_literal_bounds_and_filters_invalid_rows() -> None:
    start = date(2024, 1, 2)
    end = date(2024, 1, 5)
    engine = _FakeEngine(
        [
            {"ts_code": "600001.SH", "trade_date": start, "close": "10.2"},
            {"ts_code": "000001.SZ", "trade_date": end, "close": "9.8"},
            {"ts_code": "300001.SZ", "trade_date": end, "close": "12"},
            {"ts_code": "600002.SH", "trade_date": end, "close": "NaN"},
            {"ts_code": "600003.SH", "trade_date": end, "close": "0"},
            {
                "ts_code": "600004.SH",
                "trade_date": date(2024, 1, 8),
                "close": "11",
            },
        ]
    )

    loaded = load_stock_closes(engine, start, end)

    assert engine.connection.statement == (
        "SELECT ts_code, trade_date, close FROM stock_daily "
        "WHERE trade_date BETWEEN :start AND :end "
        "ORDER BY ts_code, trade_date"
    )
    assert engine.connection.parameters == {"start": start, "end": end}
    assert loaded == {
        "000001": {end: Decimal("9.8")},
        "600001": {start: Decimal("10.2")},
    }


def test_configured_engine_keeps_pre_ping_and_rewrites_only_docker_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setenv(
        "MYSQL_URL",
        "mysql+pymysql://reader:secret@host.docker.internal:3306/stock",
    )

    def engine_factory(url: str, **kwargs):
        seen.update(url=url, kwargs=kwargs)
        return "engine"

    result = configured_read_only_engine(
        engine_factory=engine_factory,
        env_loader=lambda *_args, **_kwargs: None,
    )

    assert result == "engine"
    assert seen == {
        "url": "mysql+pymysql://reader:secret@127.0.0.1:3306/stock",
        "kwargs": {"pool_pre_ping": True},
    }
    assert os.environ["MYSQL_URL"].endswith(
        "host.docker.internal:3306/stock"
    )


def test_mysql_loader_always_disposes_engine() -> None:
    start = date(2024, 1, 2)
    end = date(2024, 1, 5)
    engine = _FakeEngine([])

    assert load_mysql_stock_closes(
        start,
        end,
        engine_loader=lambda: engine,
    ) == {}
    assert engine.disposed is True


def test_required_indexes_follow_only_mapped_train_plan_boards() -> None:
    payload = {
        "variants": [
            {
                "segment": {
                    "admitted_trade_keys": [{"code": "600001.SH"}],
                    "ranked_plan_keys": [
                        {"code": "000001.SZ"},
                        {"code": "688001.SH"},
                    ],
                }
            }
        ]
    }

    assert required_index_ids(SimpleNamespace(payload=payload)) == (
        "sh.000001",
        "sz.399001",
        "sh.000688",
    )


def test_benchmark_loader_normalizes_dates_and_returns_requested_order() -> None:
    start = date(2024, 1, 2)
    end = date(2024, 1, 5)
    calls: list[tuple[date, date]] = []

    def raw_loader(received_start: date, received_end: date):
        calls.append((received_start, received_end))
        return {
            code: (
                IndexBar(code, start, Decimal("10"), Decimal("0")),
                IndexBar(code, end, Decimal("11"), Decimal("10")),
            )
            for code in ("sh.000001", "sz.399001", "sh.000688")
        }

    loaded = load_required_benchmark_closes(
        ("sh.000001", "sz.399001"),
        start,
        end,
        benchmark_loader=raw_loader,
    )

    assert calls == [(start, end)]
    assert tuple(loaded) == ("sh.000001", "sz.399001")
    assert loaded["sh.000001"] == {
        start: Decimal("10"),
        end: Decimal("11"),
    }
