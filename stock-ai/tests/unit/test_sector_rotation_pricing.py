from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.models import BuyPointBar
from stock_ai.sector_rotation.models import (
    CandidateRole,
    MemberSnapshot,
    RotationCandidate,
    RotationPolicy,
)
from stock_ai.sector_rotation.pricing import calculate_price_levels


def candidate(role: CandidateRole) -> RotationCandidate:
    return RotationCandidate(
        "semiconductors", "600001", "示例", role, 1, True, False, {}, None, (), ()
    )


def member() -> MemberSnapshot:
    return MemberSnapshot(
        "600001", "示例", Decimal("10"), Decimal("2"), Decimal("6"),
        Decimal("1.3"), Decimal("9.80"), Decimal("9.70"), Decimal("9.50"),
        Decimal("2.04"), Decimal("10.20"), Decimal("9.20"), Decimal("0.30"),
        True, False, False, True,
    )


def bars60() -> tuple[BuyPointBar, ...]:
    start = date(2026, 6, 1)
    bars = []
    for index in range(60):
        bars.append(
            BuyPointBar(
                start + timedelta(days=index), Decimal("9.75"), Decimal("10.10"),
                Decimal("9.40"), Decimal("9.85"), Decimal("0.5"), Decimal("200000"),
            )
        )
    bars[-10] = BuyPointBar(
        bars[-10].trade_date, Decimal("9.80"), Decimal("10.20"), Decimal("9.20"),
        Decimal("9.90"), Decimal("1"), Decimal("220000"),
    )
    return tuple(bars)


@pytest.mark.parametrize(
    "role", [CandidateRole.LEADER, CandidateRole.CATCH_UP, CandidateRole.PULLBACK]
)
def test_price_levels_are_ordered_for_each_formal_role(role: CandidateRole) -> None:
    levels = calculate_price_levels(candidate(role), member(), bars60(), RotationPolicy())

    assert levels is not None
    assert levels.invalidation_price < levels.watch_price <= levels.trigger_price < levels.no_chase_price


def test_incomplete_structure_downgrades_instead_of_guessing_prices() -> None:
    assert calculate_price_levels(
        candidate(CandidateRole.CATCH_UP), member(), bars60()[:10], RotationPolicy()
    ) is None
