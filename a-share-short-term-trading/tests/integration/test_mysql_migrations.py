from __future__ import annotations

import os
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text


pytestmark = pytest.mark.skipif(
    os.getenv("STT_MYSQL_INTEGRATION") != "1",
    reason="set STT_MYSQL_INTEGRATION=1 to use the configured household MySQL",
)

PROJECT = Path(__file__).resolve().parents[2]


def test_migrations_are_repeatable_and_support_rollback_only_dml() -> None:
    sys.path.insert(0, str(PROJECT / "scripts"))
    from apply_migrations import apply_migrations, create_root_engine

    engine = create_root_engine()
    apply_migrations(engine)
    apply_migrations(engine)

    tables = set(inspect(engine).get_table_names())
    expected = {
        "stt_schema_versions",
        "stt_watchlist",
        "stt_market_states",
        "stt_candidates",
        "stt_evidence_snapshots",
        "stt_capture_attempts",
        "stt_source_health",
        "stt_daily_sync_runs",
        "stt_trade_plans",
        "stt_risk_decisions",
        "stt_decision_snapshots",
        "stt_intraday_decisions",
        "stt_outcome_observations",
        "stt_trade_journal",
        "stt_plan_evaluations",
    }
    assert expected <= tables

    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM stt_schema_versions WHERE version = '1.1'")
        ).scalar_one() == 1
        connection.commit()

        transaction = connection.begin()
        watch_id = str(uuid4())
        connection.execute(
            text(
                """
                INSERT INTO stt_watchlist
                    (watch_id, code, trading_date, status, source, created_at, updated_at)
                VALUES
                    (:watch_id, '600000', '2026-08-10', 'ACTIVE', 'integration', UTC_TIMESTAMP(6), UTC_TIMESTAMP(6))
                """
            ),
            {"watch_id": watch_id},
        )
        assert connection.execute(
            text("SELECT COUNT(*) FROM stt_watchlist WHERE watch_id = :watch_id"),
            {"watch_id": watch_id},
        ).scalar_one() == 1
        transaction.rollback()

        assert connection.execute(
            text("SELECT COUNT(*) FROM stt_watchlist WHERE watch_id = :watch_id"),
            {"watch_id": watch_id},
        ).scalar_one() == 0
