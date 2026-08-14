from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.gates import (
    anti_chase_gate,
    base_gate,
    classify_market,
    sector_gate,
)
from stock_ai.buy_point_selection.models import (
    BuyPointBar,
    MarketSnapshot,
    SectorSnapshot,
    SelectionPolicy,
)
from stock_ai.buy_point_selection.reference_data import RiskFlag


POLICY = SelectionPolicy()


def _bars(*, count: int = 60, amount: str = "120000", latest_pct: str = "1") -> tuple[BuyPointBar, ...]:
    start = date(2026, 5, 1)
    values = []
    for index in range(count):
        close = Decimal("10") + Decimal(index) / Decimal("100")
        values.append(
            BuyPointBar(
                trade_date=start + timedelta(days=index),
                open=close - Decimal("0.02"),
                high=close + Decimal("0.10"),
                low=close - Decimal("0.10"),
                close=close,
                pct_chg=Decimal(latest_pct if index == count - 1 else "0.5"),
                amount_qian=Decimal(amount),
            )
        )
    return tuple(values)


def test_market_states_follow_frozen_thresholds() -> None:
    """Catches soft scoring accidentally replacing the hard market permission state."""
    assert classify_market(MarketSnapshot(2, 52.0, 0.95, True)).status == "ALLOW"
    assert classify_market(MarketSnapshot(1, 39.0, 0.90, True)).status == "FREEZE"
    assert classify_market(MarketSnapshot(2, 48.0, 0.85, True)).status == "LIMITED"
    assert classify_market(MarketSnapshot(3, 70.0, 1.20, False)).status == "FREEZE"


@pytest.mark.parametrize(
    ("signal", "three_day", "five_day", "ma5_dist", "ma20_dist", "reason"),
    [
        (5.01, 3.0, 5.0, 2.0, 4.0, "SIGNAL_DAY_OVERHEATED"),
        (4.0, 8.01, 5.0, 2.0, 4.0, "RETURN_3D_OVERHEATED"),
        (4.0, 3.0, 12.01, 2.0, 4.0, "RETURN_5D_OVERHEATED"),
        (4.0, 3.0, 5.0, 5.01, 4.0, "MA5_DISTANCE_OVERHEATED"),
        (4.0, 3.0, 5.0, 2.0, 12.01, "MA20_DISTANCE_OVERHEATED"),
    ],
)
def test_anti_chase_rejects_each_overheat_boundary(
    signal, three_day, five_day, ma5_dist, ma20_dist, reason
) -> None:
    """Catches a single overheat condition being diluted by unrelated strengths."""
    decision = anti_chase_gate(signal, three_day, five_day, ma5_dist, ma20_dist, POLICY)
    assert not decision.passed
    assert reason in decision.reasons


def test_base_gate_rejects_non_main_board_holding_risk_and_low_liquidity() -> None:
    """Catches excluded securities entering setup detection through a partial gate."""
    assert "NON_MAIN_BOARD" in base_gate("300001", _bars(), set(), {}, POLICY).reasons
    assert "EXISTING_HOLDING" in base_gate("600001", _bars(), {"600001"}, {}, POLICY).reasons
    risk = {
        "600001": (
            RiskFlag("600001", "ST", "VETO", date(2026, 1, 1), None, "test"),
        )
    }
    assert "POINT_IN_TIME_RISK_VETO" in base_gate("600001", _bars(), set(), risk, POLICY).reasons
    assert "LIQUIDITY_TOO_LOW" in base_gate("600001", _bars(amount="99999"), set(), {}, POLICY).reasons


def test_base_gate_accepts_clean_main_board_symbol() -> None:
    """Catches an inverted hard gate that rejects the valid baseline case."""
    assert base_gate("600001", _bars(), set(), {}, POLICY).passed


def test_sector_requires_point_in_time_breadth_and_turnover() -> None:
    """Catches a single-stock move or incomplete membership being called sector resonance."""
    good = SectorSnapshot("801010.SI", "农林牧渔", 0.72, 6, 2, 0.55, 0.85, True)
    assert sector_gate(good).passed
    assert not sector_gate(replace(good, membership_complete=False)).passed
    assert not sector_gate(replace(good, strengthening_member_count=1)).passed
