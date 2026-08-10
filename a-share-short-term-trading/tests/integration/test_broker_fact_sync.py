from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

import pytest
from sqlalchemy import text


pytestmark = pytest.mark.skipif(
    os.getenv("STT_MYSQL_INTEGRATION") != "1",
    reason="set STT_MYSQL_INTEGRATION=1 to use the configured household MySQL",
)


def test_broker_facts_round_trip_and_alert_rules_are_untouched() -> None:
    migration_scripts = Path(__file__).resolve().parents[2] / "scripts"
    sys.path.insert(0, str(migration_scripts))
    from apply_migrations import create_root_engine
    from scripts.tools.jywg_portfolio_sync import BrokerAccount, BrokerPosition
    from scripts.tools.portfolio_db import sync_broker_positions_and_account

    engine = create_root_engine()
    connection = engine.connect()
    transaction = connection.begin()
    captured_at = datetime(2026, 8, 10, 8, 15, tzinfo=timezone.utc)
    positions = [
        BrokerPosition(
            code=code,
            name=f"测试{code}",
            asset_type="stock",
            shares=500,
            available_shares=200,
            cost_price=Decimal("6.80"),
            current_price=Decimal("7.01"),
            market_value=Decimal("3505.00"),
            position_pnl=Decimal("105.00"),
            position_pnl_pct=Decimal("3.09"),
            daily_pnl=Decimal("33.00"),
            daily_pnl_pct=Decimal("0.95"),
            status="盈利",
            action="",
            broker_captured_at=captured_at,
        )
        for code in ("999991", "999992")
    ]
    account = BrokerAccount(
        total_assets=Decimal("100000.00"),
        available_cash=Decimal("30000.00"),
        cash_balance=Decimal("31000.00"),
        withdrawable_cash=Decimal("29000.00"),
        frozen_cash=Decimal("1000.00"),
        market_value=Decimal("70000.00"),
        position_ratio=Decimal("0.70"),
        holding_pnl=Decimal("2500.00"),
        daily_pnl=Decimal("350.00"),
        broker_captured_at=captured_at,
        masked_account_identifier="12******90",
    )
    try:
        alert_before = connection.execute(text("SELECT COUNT(*) FROM alert_rules")).scalar_one()
        stats = sync_broker_positions_and_account(
            positions, account, source="jywg", connection=connection
        )
        rows = connection.execute(
            text(
                """
                SELECT ts_code, shares, available_shares, current_price, market_value,
                       position_pnl, position_pnl_pct, daily_pnl, daily_pnl_pct,
                       broker_captured_at, source, is_active
                FROM portfolio_positions WHERE ts_code IN ('999991', '999992')
                ORDER BY ts_code
                """
            )
        ).mappings().all()
        stored_account = connection.execute(
            text(
                """
                SELECT cash_balance, withdrawable_cash, frozen_cash, daily_pnl, broker_captured_at
                FROM portfolio_account WHERE id = 1
                """
            )
        ).mappings().one()

        assert stats == {"positions": 2, "account": 1, "rules": 0}
        assert len(rows) == 2
        assert rows[0]["available_shares"] == 200
        assert rows[0]["current_price"] == Decimal("7.0100")
        assert rows[0]["daily_pnl"] == Decimal("33.0000")
        assert rows[0]["source"] == "jywg"
        assert rows[0]["is_active"] == 1
        assert stored_account["cash_balance"] == Decimal("31000.0000")
        assert stored_account["daily_pnl"] == Decimal("350.0000")
        assert connection.execute(text("SELECT COUNT(*) FROM alert_rules")).scalar_one() == alert_before

        active_other = connection.execute(
            text(
                "SELECT COUNT(*) FROM portfolio_positions "
                "WHERE ts_code NOT IN ('999991', '999992') AND is_active = 1"
            )
        ).scalar_one()
        assert active_other == 0
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()
