from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from scripts.tools.jywg_portfolio_sync import BrokerAccount, BrokerPosition
from scripts.tools.portfolio_db import get_engine
from stock_ai.advisor_memory.position_sync import sync_broker_facts_with_memory


@pytest.fixture()
def engine():
    value = get_engine()
    if value is None:
        pytest.skip("MySQL is not configured")
    return value


def test_advisor_ledger_tables_exist(engine) -> None:
    with engine.connect() as conn:
        tables = {
            str(row[0])
            for row in conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() AND table_name IN "
                    "('advisor_decision_cycles', 'advisor_decision_events', "
                    "'portfolio_position_events')"
                )
            )
        }

    assert tables == {
        "advisor_decision_cycles",
        "advisor_decision_events",
        "portfolio_position_events",
    }


def test_decision_events_reject_updates(engine) -> None:
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            cycle_id = conn.execute(
                text(
                    """
                    INSERT INTO advisor_decision_cycles
                      (ts_code, name, started_trade_date, review_trade_date,
                       expiry_trade_date, initial_action, current_action, status, source)
                    VALUES
                      ('600000', '测试股份', :started, :review, :expiry,
                       '持有观察', '持有观察', 'ACTIVE', 'test')
                    """
                ),
                {
                    "started": date(2026, 8, 10),
                    "review": date(2026, 8, 12),
                    "expiry": date(2026, 8, 14),
                },
            ).lastrowid
            event_id = conn.execute(
                text(
                    """
                    INSERT INTO advisor_decision_events
                      (cycle_id, event_type, new_action, effective_trade_date,
                       source, event_fingerprint)
                    VALUES
                      (:cycle_id, 'CYCLE_OPENED', '持有观察', :effective, 'test',
                       'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
                    """
                ),
                {"cycle_id": cycle_id, "effective": date(2026, 8, 10)},
            ).lastrowid

            with pytest.raises(DatabaseError, match="append-only"):
                conn.execute(
                    text(
                        "UPDATE advisor_decision_events SET new_action = '清仓' "
                        "WHERE event_id = :event_id"
                    ),
                    {"event_id": event_id},
                )
        finally:
            transaction.rollback()


def test_position_events_reject_deletes(engine) -> None:
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            event_id = conn.execute(
                text(
                    """
                    INSERT INTO portfolio_position_events
                      (ts_code, name, event_type, shares_before, shares_after,
                       shares_delta, plan_compliance, source, broker_captured_at,
                       event_fingerprint)
                    VALUES
                      ('600000', '测试股份', 'CLOSED', 500, 0, -500, 'UNKNOWN',
                       'test', '2026-08-13 05:00:00.000000',
                       'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb')
                    """
                )
            ).lastrowid

            with pytest.raises(DatabaseError, match="append-only"):
                conn.execute(
                    text(
                        "DELETE FROM portfolio_position_events "
                        "WHERE position_event_id = :event_id"
                    ),
                    {"event_id": event_id},
                )
        finally:
            transaction.rollback()


def _broker_position(
    *, shares: int, captured_at, code: str = "999993", cost: str = "6.80"
) -> BrokerPosition:
    from decimal import Decimal

    return BrokerPosition(
        code=code,
        name="测试股份",
        asset_type="stock",
        shares=shares,
        available_shares=shares,
        cost_price=Decimal(cost) if shares else Decimal("0"),
        current_price=Decimal("7.01"),
        market_value=Decimal("3505.00") if shares else Decimal("0"),
        position_pnl=None,
        position_pnl_pct=None,
        daily_pnl=None,
        daily_pnl_pct=None,
        status="",
        action="",
        broker_captured_at=captured_at,
    )


def _broker_account(*, captured_at) -> BrokerAccount:
    from decimal import Decimal

    return BrokerAccount(
        total_assets=Decimal("100000"),
        available_cash=Decimal("100000"),
        cash_balance=Decimal("100000"),
        withdrawable_cash=Decimal("100000"),
        frozen_cash=Decimal("0"),
        market_value=Decimal("0"),
        position_ratio=Decimal("0"),
        holding_pnl=Decimal("0"),
        daily_pnl=Decimal("0"),
        broker_captured_at=captured_at,
        masked_account_identifier="",
    )


def test_broker_close_is_atomic_inactive_and_idempotent(engine) -> None:
    from datetime import datetime, timezone

    captured_at = datetime(2026, 8, 13, 5, 0, tzinfo=timezone.utc)
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            conn.execute(
                text(
                    """
                    INSERT INTO portfolio_positions
                      (ts_code, name, asset_type, shares, cost_price, source, is_active)
                    VALUES ('999993', '测试股份', 'stock', 500, 6.80, 'test', 1)
                    ON DUPLICATE KEY UPDATE shares=500, cost_price=6.80,
                      source='test', is_active=1
                    """
                )
            )
            active_rows = [
                (str(row[0]).zfill(6), int(row[1]), str(row[2]))
                for row in conn.execute(
                    text(
                        "SELECT ts_code, shares, cost_price FROM portfolio_positions "
                        "WHERE is_active=1 AND ts_code <> '999993'"
                    )
                )
            ]
            complete_capture = [
                _broker_position(shares=shares, cost=cost, captured_at=captured_at, code=code)
                for code, shares, cost in active_rows
            ] + [_broker_position(shares=0, captured_at=captured_at)]

            first = sync_broker_facts_with_memory(
                complete_capture,
                _broker_account(captured_at=captured_at),
                source="test",
                connection=conn,
            )
            second = sync_broker_facts_with_memory(
                complete_capture,
                _broker_account(captured_at=captured_at),
                source="test",
                connection=conn,
            )
            projection = conn.execute(
                text(
                    "SELECT shares, is_active FROM portfolio_positions "
                    "WHERE ts_code='999993'"
                )
            ).mappings().one()
            event_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM portfolio_position_events "
                    "WHERE ts_code='999993' AND source='test' AND event_type='CLOSED'"
                )
            ).scalar_one()

            assert first["position_events"] == 1
            assert second["position_events"] == 0
            assert projection == {"shares": 0, "is_active": 0}
            assert event_count == 1
        finally:
            transaction.rollback()
