from decimal import Decimal

from stock_ai.sector_rotation.models import (
    CandidateRole,
    ChainMetrics,
    ChainScore,
    MemberSnapshot,
    RotationBucket,
    RotationPolicy,
    RotationState,
    ScoredChain,
    SelectedChain,
)
from stock_ai.sector_rotation.selection import (
    build_observation_pool,
    promote_formal_candidates,
    select_core_pool,
)


def _metrics(breadth: str = "0.70", persistence: int = 2) -> ChainMetrics:
    return ChainMetrics(
        Decimal("0.80"), Decimal("0.70"), Decimal(breadth), Decimal("0.70"),
        Decimal("0.72"), 8, 10, Decimal("1.30"), Decimal("0.70"), persistence,
        Decimal("0.30"), True,
    )


def _score(total: str) -> ChainScore:
    return ChainScore(Decimal(total), Decimal("20"), Decimal("18"), Decimal("15"),
                      Decimal("12"), Decimal("8"), Decimal("0"), ())


def _chain(index: int, state: RotationState, total: str, parent: str | None = None,
           previous: RotationState | None = None) -> ScoredChain:
    return ScoredChain(
        chain_code=f"chain_{index}", chain_name=f"方向{index}",
        parent_code=parent or f"parent_{index}", raw_sector_codes=(f"BK{index}",),
        raw_sector_names=(f"行业{index}",), best_rank=index,
        raw_change_pct=Decimal("2"), metrics=_metrics(), score=_score(total),
        state=state, previous_state=previous, state_reasons=(),
        coexistence_codes=(), member_codes=(),
    )


def sample_scored_chains() -> tuple[ScoredChain, ...]:
    return (
        _chain(1, RotationState.CONFIRMED, "85"),
        _chain(2, RotationState.STARTING, "80"),
        _chain(3, RotationState.CONFIRMED, "78"),
        _chain(4, RotationState.LATENT, "58"),
        _chain(5, RotationState.LATENT, "54"),
        _chain(6, RotationState.LATENT, "52", previous=RotationState.CONFIRMED),
        _chain(7, RotationState.STARTING, "76", parent="parent_1"),
    )


def test_core_pool_enforces_three_two_one_and_parent_deduplication() -> None:
    selected = select_core_pool(sample_scored_chains(), RotationPolicy())

    assert [value.bucket for value in selected].count(RotationBucket.STRONG) == 3
    assert [value.bucket for value in selected].count(RotationBucket.STRENGTHENING) == 2
    assert [value.bucket for value in selected].count(RotationBucket.PULLBACK) == 1
    assert len({value.parent_code for value in selected}) == len(selected)


def test_short_bucket_is_not_filled_with_a_weak_chain() -> None:
    selected = select_core_pool(
        (_chain(1, RotationState.STARTING, "70"), _chain(2, RotationState.LATENT, "52")),
        RotationPolicy(),
    )

    assert len(selected) == 2


def _selected_chain() -> SelectedChain:
    source = _chain(1, RotationState.CONFIRMED, "82")
    return SelectedChain(**source.__dict__, bucket=RotationBucket.STRONG)


def _member(index: int) -> MemberSnapshot:
    price = Decimal("10") + Decimal(index) / Decimal("10")
    role_slot = index % 4
    change = (Decimal("5"), Decimal("2"), Decimal("0.8"), Decimal("-0.5"))[role_slot]
    return5 = (Decimal("10"), Decimal("6"), Decimal("3"), Decimal("1"))[role_slot]
    amount = (Decimal("1.8"), Decimal("1.3"), Decimal("1.15"), Decimal("0.8"))[role_slot]
    distance = (Decimal("4"), Decimal("3"), Decimal("1.5"), Decimal("0.4"))[role_slot]
    return MemberSnapshot(
        f"600{index:03d}", f"样本{index}", price, change, return5, amount,
        Decimal("10"), Decimal("9.9"), Decimal("9.5"), distance,
        Decimal("11"), Decimal("9"), Decimal("0.3"), True, False, False, True,
    )


def test_observation_pool_keeps_ten_but_only_three_formal_roles() -> None:
    observed = build_observation_pool(_selected_chain(), tuple(_member(i) for i in range(20)), RotationPolicy())
    formal = promote_formal_candidates(observed, RotationPolicy())

    assert len(observed) == 10
    assert len(formal) <= 3
    assert {value.role for value in formal} <= {
        CandidateRole.LEADER, CandidateRole.CATCH_UP, CandidateRole.PULLBACK,
    }


def test_overheated_member_stays_observation_only() -> None:
    hot = _member(0)
    hot = MemberSnapshot(**{**hot.__dict__, "change_pct": Decimal("8")})

    observed = build_observation_pool(_selected_chain(), (hot,), RotationPolicy())

    assert observed[0].formal_eligible is False
    assert "SIGNAL_DAY_OVERHEATED" in observed[0].rejection_reasons
