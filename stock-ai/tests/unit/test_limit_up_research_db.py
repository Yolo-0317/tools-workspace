from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from scripts.tools.portfolio_db import (
    finish_limit_up_research_run,
    load_limit_up_pool,
    load_limit_up_research_bundle,
    save_limit_up_research_bundle,
    start_limit_up_research_run,
)
from stock_ai.limit_up_research.models import ForwardLabel, PoolFact, SelectionAttribution


class _Result:
    lastrowid = 41


class _Connection:
    def __init__(self):
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params))
        return _Result()


class _Context:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, tb):
        return False


class _Engine:
    def __init__(self):
        self.connection = _Connection()
        self.begin_count = 0

    def begin(self):
        self.begin_count += 1
        return _Context(self.connection)


class _ReadRow:
    def __init__(self, **values):
        self._mapping = values


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class _ReadConnection:
    def __init__(self):
        self.calls = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append((sql, params))
        if "FROM limit_up_research_runs" in sql:
            return _Rows([_ReadRow(run_id=9, trade_date=date(2026, 8, 13), status="SUCCEEDED")])
        if "FROM limit_up_research_pool" in sql:
            return _Rows([_ReadRow(
                trade_date=date(2026, 8, 13), pool_kind="LIMIT_UP", ts_code="601991",
                missing_fields_json='["last_seal_time"]', raw_json='{"c":"601991"}',
            )])
        if "FROM limit_up_selection_attribution" in sql:
            return _Rows([_ReadRow(
                trade_date=date(2026, 8, 13), selection_date=date(2026, 8, 12),
                ts_code="601991", reason_codes_json='["SELECTED"]', evidence_json="{}",
            )])
        if "FROM limit_up_forward_labels" in sql:
            return _Rows([_ReadRow(
                signal_date=date(2026, 8, 13), ts_code="601991", horizon="T1",
                missing_fields_json="[]",
            )])
        raise AssertionError(sql)


class _ReadEngine:
    def __init__(self):
        self.connection = _ReadConnection()

    def connect(self):
        return _Context(self.connection)


def test_run_audit_uses_separate_short_transactions() -> None:
    engine = _Engine()

    run_id = start_limit_up_research_run(
        date(2026, 8, 13), source="eastmoney-opencli-topic-pool", engine=engine
    )
    finish_limit_up_research_run(run_id, status="FAILED", error="network", engine=engine)

    assert run_id == 41
    assert engine.begin_count == 2
    assert "INSERT INTO limit_up_research_runs" in engine.connection.calls[0][0]
    assert engine.connection.calls[1][1]["status"] == "FAILED"


def test_bundle_uses_one_transaction_for_all_three_upsert_groups() -> None:
    engine = _Engine()
    td = date(2026, 8, 13)
    fact = PoolFact(td, "LIMIT_UP", "601991", "大唐发电", 10.02, 81200.0, 2,
                    "电力行业", None, None, 1, None, (), {"c": "601991"})
    attribution = SelectionAttribution(td, "601991", "combined", True, 1, 78.0,
                                       "强势关注", "SELECTED", None, (), {}, "combined-current")
    label = ForwardLabel(td, "601991", "T1", date(2026, 8, 14), 10.0, 11.0,
                         10.0, 12.0, -2.0, True, 2, True, ())

    counts = save_limit_up_research_bundle(
        41, td, (fact,), (attribution,), (label,), engine=engine
    )

    assert engine.begin_count == 1
    assert counts == {"pool": 1, "attributions": 1, "labels": 1}
    sql = "\n".join(call[0] for call in engine.connection.calls)
    assert "limit_up_research_pool" in sql
    assert "limit_up_selection_attribution" in sql
    assert "limit_up_forward_labels" in sql


def test_bundle_rejects_invalid_rows_before_opening_transaction() -> None:
    engine = _Engine()
    td = date(2026, 8, 13)
    fact = PoolFact(td, "LIMIT_UP", "601991", "大唐发电", 10.02, 81200.0, 2,
                    "电力行业", None, None, 1, None, (), {"c": "601991"})
    attribution = SelectionAttribution(td, "601991", "combined", True, 1, 78.0,
                                       "强势关注", "SELECTED", None, (), {}, "combined-current")
    label = ForwardLabel(td, "601991", "T1", date(2026, 8, 14), 10.0, 11.0,
                         10.0, 12.0, -2.0, True, 2, True, ())

    with pytest.raises(ValueError, match="six-digit"):
        save_limit_up_research_bundle(
            41, td, (replace(fact, code="bad"),), (attribution,), (label,), engine=engine
        )

    assert engine.begin_count == 0


def test_finish_rejects_unknown_status_before_database_access() -> None:
    engine = _Engine()

    with pytest.raises(ValueError, match="SUCCEEDED or FAILED"):
        finish_limit_up_research_run(1, status="STARTED", engine=engine)

    assert engine.begin_count == 0


def test_read_interfaces_decode_json_and_return_a_complete_bundle() -> None:
    engine = _ReadEngine()

    pool = load_limit_up_pool(date(2026, 8, 13), pool_kind="LIMIT_UP", engine=engine)
    bundle = load_limit_up_research_bundle(date(2026, 8, 13), engine=engine)

    assert pool[0]["raw_json"] == {"c": "601991"}
    assert pool[0]["missing_fields_json"] == ["last_seal_time"]
    assert engine.connection.calls[0][1] == {"d": "2026-08-13", "kind": "LIMIT_UP"}
    assert bundle["run"]["run_id"] == 9
    assert bundle["pool"][0]["ts_code"] == "601991"
    assert bundle["attributions"][0]["selection_date"] == "2026-08-12"
    assert bundle["labels"][0]["horizon"] == "T1"
