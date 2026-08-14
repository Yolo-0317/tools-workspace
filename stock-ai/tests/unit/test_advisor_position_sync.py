from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import json

from scripts.tools.jywg_portfolio_sync import BrokerPosition
from stock_ai.advisor_memory.position_sync import (
    PositionProjection,
    diff_position_facts,
    sync_broker_facts_with_memory,
)


CAPTURED = datetime(2026, 8, 13, 5, 0, tzinfo=timezone.utc)


def broker_position(
    *,
    shares: int,
    cost: str = "6.80",
    code: str = "600000",
) -> BrokerPosition:
    return BrokerPosition(
        code=code,
        name="测试股份",
        asset_type="stock",
        shares=shares,
        available_shares=shares,
        cost_price=Decimal(cost),
        current_price=Decimal("7.01"),
        market_value=Decimal("0") if shares == 0 else Decimal("3505.00"),
        position_pnl=None,
        position_pnl_pct=None,
        daily_pnl=None,
        daily_pnl_pct=None,
        status="",
        action="",
        broker_captured_at=CAPTURED,
    )


def projection(*, shares: int, cost: str = "6.80") -> PositionProjection:
    return PositionProjection(
        code="600000",
        name="测试股份",
        shares=shares,
        cost_price=Decimal(cost),
        broker_captured_at=datetime(2026, 8, 12, 7, 0),
    )


def test_positive_to_zero_creates_close_event_without_inventing_execution_price() -> None:
    events = diff_position_facts(
        {"600000": projection(shares=500)},
        [broker_position(shares=0, cost="0")],
        source="jywg",
    )

    assert len(events) == 1
    event = events[0]
    assert event.event_type == "CLOSED"
    assert (event.shares_before, event.shares_after, event.shares_delta) == (500, 0, -500)
    assert event.execution_price is None
    assert event.realized_pnl is None
    assert event.plan_compliance == "UNKNOWN"


def test_share_increase_and_reduction_have_distinct_event_types() -> None:
    added = diff_position_facts(
        {"600000": projection(shares=500)},
        [broker_position(shares=700)],
        source="jywg",
    )
    reduced = diff_position_facts(
        {"600000": projection(shares=500)},
        [broker_position(shares=200)],
        source="jywg",
    )

    assert added[0].event_type == "ADDED"
    assert added[0].shares_delta == 200
    assert reduced[0].event_type == "REDUCED"
    assert reduced[0].shares_delta == -300


def test_new_positive_position_creates_open_event() -> None:
    events = diff_position_facts({}, [broker_position(shares=500)], source="jywg")

    assert events[0].event_type == "OPENED"
    assert events[0].shares_before == 0


def test_unchanged_shares_with_changed_cost_creates_cost_adjustment() -> None:
    events = diff_position_facts(
        {"600000": projection(shares=500, cost="6.80")},
        [broker_position(shares=500, cost="6.75")],
        source="jywg",
    )

    assert events[0].event_type == "COST_ADJUSTED"
    assert events[0].shares_delta == 0


def test_unchanged_position_creates_no_event() -> None:
    events = diff_position_facts(
        {"600000": projection(shares=500, cost="6.80")},
        [broker_position(shares=500, cost="6.80")],
        source="jywg",
    )

    assert events == ()


def test_missing_incoming_row_closes_previous_active_position() -> None:
    events = diff_position_facts(
        {"600000": projection(shares=500)},
        [],
        source="jywg",
        captured_at=CAPTURED,
    )

    assert events[0].event_type == "CLOSED"
    assert events[0].shares_after == 0


class _Result:
    def __init__(self, *, rows=None, row=None, rowcount=1, lastrowid=42):
        self._rows = rows or []
        self._row = row
        self.rowcount = rowcount
        self.lastrowid = lastrowid

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._row

    def scalar(self):
        return None


class _Connection:
    def __init__(self, triggered_plan):
        self.triggered_plan = triggered_plan
        self.calls = []

    def execute(self, statement, parameters=None):
        sql = str(statement)
        values = parameters or {}
        self.calls.append((sql, values))
        if "FROM portfolio_positions" in sql:
            return _Result(rows=[])
        if "FROM advisor_decision_cycles" in sql:
            return _Result(row=None)
        if "FROM stt_trade_plans" in sql:
            return _Result(row=self.triggered_plan)
        return _Result()


def _triggered_plan_row():
    return {
        "plan_id": "70000000-0000-4000-8000-000000000001",
        "code": "600000",
        "structure_id": "0123456789abcdef0123456789abcdef",
        "trigger_price": Decimal("10.01"),
        "invalidation_price": Decimal("9.71"),
        "target_2r": Decimal("10.61"),
        "risk_distance": Decimal("0.30"),
        "maximum_shares": 300,
        "valid_through_trade_date": CAPTURED.date(),
        "rule_version": "buy-point-selection-3.0.0",
    }


def test_broker_open_links_triggered_plan_to_new_decision_cycle(monkeypatch) -> None:
    """Catches a simulated trigger opening memory before a broker-confirmed position exists."""
    connection = _Connection(_triggered_plan_row())
    trading_days = tuple(CAPTURED.date().fromordinal(CAPTURED.date().toordinal() + index) for index in range(5))
    monkeypatch.setattr(
        "stock_ai.advisor_memory.position_sync._confirmed_cycle_dates",
        lambda start: trading_days,
        raising=False,
    )
    monkeypatch.setattr(
        "scripts.tools.portfolio_db.sync_broker_positions_and_account",
        lambda *args, **kwargs: {},
    )
    account = SimpleNamespace(broker_captured_at=CAPTURED)

    stats = sync_broker_facts_with_memory(
        [broker_position(shares=500)],
        account,
        connection=connection,
    )

    cycle_calls = [call for call in connection.calls if "INSERT INTO advisor_decision_cycles" in call[0]]
    assert len(cycle_calls) == 1
    cycle_values = cycle_calls[0][1]
    assert cycle_values["selection_source"] == "buy_point_v3"
    assert cycle_values["selection_plan_id"] == _triggered_plan_row()["plan_id"]
    assert json.loads(cycle_values["trigger_plan"])["trigger_price"] == "10.01"
    position_calls = [call for call in connection.calls if "INSERT IGNORE INTO portfolio_position_events" in call[0]]
    assert position_calls[0][1]["cycle_id"] == 42
    assert stats["position_events"] == 1


def test_open_without_confirmed_triggered_plan_keeps_position_event_unlinked(monkeypatch) -> None:
    """Catches an unmatched broker position inventing a selection plan or decision cycle."""
    connection = _Connection(None)
    monkeypatch.setattr(
        "scripts.tools.portfolio_db.sync_broker_positions_and_account",
        lambda *args, **kwargs: {},
    )
    account = SimpleNamespace(broker_captured_at=CAPTURED)
    sync_broker_facts_with_memory(
        [broker_position(shares=500)],
        account,
        connection=connection,
    )
    assert not any("INSERT INTO advisor_decision_cycles" in call[0] for call in connection.calls)
    position_calls = [call for call in connection.calls if "INSERT IGNORE INTO portfolio_position_events" in call[0]]
    assert position_calls[0][1]["cycle_id"] is None
