from __future__ import annotations

from dataclasses import fields, replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.models import (
    BuyPointBar,
    DetectedSetup,
    MarketSnapshot,
    SelectionPolicy,
    SetupType,
)
from stock_ai.buy_point_selection.reference_data import (
    ReferenceCoverage,
    RiskFlag,
    SectorMembership,
)
from stock_ai.buy_point_selection.threshold_shadow_research import (
    ThresholdProfile,
    ThresholdShadowSetup,
    build_threshold_profiles,
    generate_threshold_shadow_setups,
    profile_matrix_hash,
    replay_threshold_shadows,
)


SIGNAL_DATE = date(2026, 8, 3)


def _single_width_failure_platform() -> tuple[BuyPointBar, ...]:
    bars = []
    for index in range(60):
        close = Decimal("10.40") + Decimal(index) * Decimal("0.01")
        high = close + Decimal("0.04")
        low = close - Decimal("0.04")
        amount = Decimal("200000")
        if index == 30:
            low = Decimal("10.00")
        if index == 45:
            high = Decimal("11.30")
        if index >= 50:
            high = close + Decimal("0.02")
            low = close - Decimal("0.02")
        if index >= 55:
            amount = Decimal("120000")
        bars.append(
            BuyPointBar(
                SIGNAL_DATE - timedelta(days=59 - index),
                close,
                high,
                low,
                close,
                Decimal("0.10"),
                amount,
            )
        )
    return tuple(bars)


def _flat_history() -> tuple[BuyPointBar, ...]:
    return tuple(
        BuyPointBar(
            SIGNAL_DATE - timedelta(days=59 - index),
            Decimal("10.00"),
            Decimal("10.10"),
            Decimal("9.90"),
            Decimal("10.00"),
            Decimal("0"),
            Decimal("200000"),
        )
        for index in range(60)
    )


def _literal_setup_generator(
    code: str,
    signal_date: date,
    bars: tuple[BuyPointBar, ...],
    profiles: tuple[ThresholdProfile, ...],
    formal_policy: SelectionPolicy,
) -> tuple[ThresholdShadowSetup, ...]:
    del bars, formal_policy
    setup = DetectedSetup(
        code,
        SetupType.PRE_BREAKOUT,
        signal_date,
        signal_date - timedelta(days=20),
        Decimal("10.10"),
        Decimal("9.90"),
        Decimal("0.80"),
        ("SHADOW_FIXTURE",),
        {},
    )
    return (
        ThresholdShadowSetup(
            code,
            signal_date,
            profiles[0],
            setup,
            Decimal("0.05"),
        ),
    )


def _nonzero_setup_generator(
    code: str,
    signal_date: date,
    bars: tuple[BuyPointBar, ...],
    profiles: tuple[ThresholdProfile, ...],
    formal_policy: SelectionPolicy,
) -> tuple[ThresholdShadowSetup, ...]:
    row = _literal_setup_generator(
        code, signal_date, bars, profiles, formal_policy
    )[0]
    return (replace(row, executable_shares=100),)


def _wide_risk_setup_generator(
    code: str,
    signal_date: date,
    bars: tuple[BuyPointBar, ...],
    profiles: tuple[ThresholdProfile, ...],
    formal_policy: SelectionPolicy,
) -> tuple[ThresholdShadowSetup, ...]:
    row = _literal_setup_generator(
        code, signal_date, bars, profiles, formal_policy
    )[0]
    return (replace(row, setup=replace(row.setup, structure_low=Decimal("8"))),)


def _run_literal_replay(
    *,
    bars: tuple[BuyPointBar, ...] | None = None,
    market: MarketSnapshot | None = None,
    coverage: ReferenceCoverage | None = None,
    memberships: tuple[SectorMembership, ...] | None = None,
    holdings: frozenset[str] = frozenset(),
    risk_flags: tuple[RiskFlag, ...] = (),
    setup_generator=_literal_setup_generator,
):
    profile = build_threshold_profiles()[0]
    return replay_threshold_shadows(
        signal_dates=(SIGNAL_DATE,),
        trading_dates=tuple(
            SIGNAL_DATE + timedelta(days=index) for index in range(3)
        ),
        bars_by_code={"600001": bars or _flat_history()},
        memberships=(
            memberships
            if memberships is not None
            else (
                SectorMembership(
                    "600001", "S1", "测试行业", SIGNAL_DATE, None, "fixture"
                ),
            )
        ),
        risk_flags=risk_flags,
        coverage_by_date={
            SIGNAL_DATE: coverage
            or ReferenceCoverage(SIGNAL_DATE, True, True, True)
        },
        market_snapshots={
            SIGNAL_DATE: market or MarketSnapshot(3, 60.0, 1.1, True)
        },
        holding_codes_by_date={SIGNAL_DATE: holdings},
        profiles=(profile,),
        formal_policy=SelectionPolicy(
            sector_return_percentile_min=0,
            sector_liquid_members_min=1,
            sector_strengthening_members_min=0,
            sector_breadth_min=0,
            sector_amount_ratio_min=0,
        ),
        setup_generator=setup_generator,
    )


def test_profile_matrix_has_48_unique_single_field_relaxations() -> None:
    """Catches a missing ladder rung or a profile mutating multiple gates."""
    profiles = build_threshold_profiles()

    assert len(profiles) == 48
    assert len({value.profile_id for value in profiles}) == 48
    profile = next(
        value
        for value in profiles
        if value.policy_field == "platform_width_max"
        and value.relaxation_rate == Decimal("0.10")
    )
    assert profile == ThresholdProfile(
        profile_id="PRE_BREAKOUT:platform_width_max:UPPER:0.10",
        setup_type=SetupType.PRE_BREAKOUT,
        policy_field="platform_width_max",
        direction="UPPER",
        relaxation_rate=Decimal("0.10"),
        formal_value=Decimal("0.12"),
        shadow_value=Decimal("0.1320"),
        failure_reason="PLATFORM_WIDTH_WIDE",
        metric_name="platform_width",
    )

    formal = SelectionPolicy()
    shadow = replace(formal, **{profile.policy_field: profile.shadow_value})
    changed = {
        field.name
        for field in fields(SelectionPolicy)
        if getattr(formal, field.name) != getattr(shadow, field.name)
    }
    assert changed == {"platform_width_max"}


def test_lower_bound_profile_relaxes_only_downward() -> None:
    """Catches a lower-bound profile being widened in the wrong direction."""
    profile = next(
        value
        for value in build_threshold_profiles()
        if value.policy_field == "trend_return10_min"
        and value.relaxation_rate == Decimal("0.25")
    )

    assert profile.direction == "LOWER"
    assert profile.formal_value == Decimal("0.05")
    assert profile.shadow_value == Decimal("0.0375")


def test_profile_matrix_hash_is_order_independent_and_content_sensitive() -> None:
    """Catches artifact identity ignoring a changed shadow threshold."""
    profiles = build_threshold_profiles()
    changed = replace(profiles[0], shadow_value=Decimal("0.999"))

    assert profile_matrix_hash(tuple(reversed(profiles))) == profile_matrix_hash(
        profiles
    )
    assert profile_matrix_hash((changed, *profiles[1:])) != profile_matrix_hash(
        profiles
    )


def test_single_width_failure_is_admitted_only_by_width_profile() -> None:
    """Catches an unrelated gate being relaxed or a small width miss being lost."""
    profiles = build_threshold_profiles()
    width = next(
        value
        for value in profiles
        if value.policy_field == "platform_width_max"
        and value.relaxation_rate == Decimal("0.10")
    )
    amount = next(
        value
        for value in profiles
        if value.policy_field == "platform_amount_ratio_max"
        and value.relaxation_rate == Decimal("0.10")
    )

    rows = generate_threshold_shadow_setups(
        "600001",
        SIGNAL_DATE,
        _single_width_failure_platform(),
        (width, amount),
    )

    assert [value.profile.profile_id for value in rows] == [width.profile_id]
    assert rows[0].actual_deviation == Decimal("0.01") / Decimal("0.12")
    assert rows[0].executable_shares == 0


def test_forged_or_structural_profile_is_rejected() -> None:
    """Catches callers bypassing the frozen numeric profile allowlist."""
    forged = replace(
        build_threshold_profiles()[0],
        policy_field="max_signal_gain_pct",
        shadow_value=Decimal("9"),
    )

    with pytest.raises(ValueError, match="unsupported threshold profile"):
        generate_threshold_shadow_setups(
            "600001",
            SIGNAL_DATE,
            _single_width_failure_platform(),
            (forged,),
        )


def test_formal_positive_and_multi_failure_shapes_are_not_incremental() -> None:
    """Catches a formal setup or a two-gate miss entering one-gate shadows."""
    width = next(
        value
        for value in build_threshold_profiles()
        if value.policy_field == "platform_width_max"
        and value.relaxation_rate == Decimal("0.10")
    )
    bars = list(_single_width_failure_platform())
    formal = list(bars)
    formal[45] = replace(formal[45], high=Decimal("11.19"))
    multiple = [
        replace(value, amount_qian=Decimal("200000"))
        if index >= 55
        else value
        for index, value in enumerate(bars)
    ]

    assert generate_threshold_shadow_setups(
        "600001", SIGNAL_DATE, formal, (width,)
    ) == ()
    assert generate_threshold_shadow_setups(
        "600001", SIGNAL_DATE, multiple, (width,)
    ) == ()


def test_future_bar_cannot_change_shadow_setup_generation() -> None:
    """Catches outcome prices leaking into profile admission."""
    profile = next(
        value
        for value in build_threshold_profiles()
        if value.policy_field == "platform_width_max"
        and value.relaxation_rate == Decimal("0.10")
    )
    bars = _single_width_failure_platform()
    future = replace(
        bars[-1],
        trade_date=SIGNAL_DATE + timedelta(days=1),
        high=Decimal("99"),
        close=Decimal("90"),
    )

    assert generate_threshold_shadow_setups(
        "600001", SIGNAL_DATE, (*bars, future), (profile,)
    ) == generate_threshold_shadow_setups(
        "600001", SIGNAL_DATE, bars, (profile,)
    )


def test_shadow_candidate_passes_every_unchanged_gate_with_zero_shares() -> None:
    """Catches shadow setups bypassing gates or becoming executable candidates."""
    profile = build_threshold_profiles()[0]
    trading_dates = tuple(
        SIGNAL_DATE + timedelta(days=index) for index in range(3)
    )

    replay = replay_threshold_shadows(
        signal_dates=(SIGNAL_DATE,),
        trading_dates=trading_dates,
        bars_by_code={"600001": _flat_history()},
        memberships=(
            SectorMembership(
                "600001", "S1", "测试行业", SIGNAL_DATE, None, "fixture"
            ),
        ),
        risk_flags=(),
        coverage_by_date={
            SIGNAL_DATE: ReferenceCoverage(SIGNAL_DATE, True, True, True)
        },
        market_snapshots={
            SIGNAL_DATE: MarketSnapshot(3, 60.0, 1.1, True)
        },
        holding_codes_by_date={SIGNAL_DATE: frozenset()},
        profiles=(profile,),
        formal_policy=SelectionPolicy(
            sector_return_percentile_min=0,
            sector_liquid_members_min=1,
            sector_strengthening_members_min=0,
            sector_breadth_min=0,
            sector_amount_ratio_min=0,
        ),
        setup_generator=_literal_setup_generator,
    )

    candidate = replay.candidates[0]
    assert candidate.profile_id == profile.profile_id
    assert candidate.code == "600001"
    assert candidate.signal_date == SIGNAL_DATE
    assert candidate.executable_shares == 0
    assert candidate.status == "CASE_ANALYSIS_ONLY"
    assert candidate.trade_permission == "NO-TRADE"
    assert candidate.plan.maximum_shares >= 100


def test_replay_rejects_a_generator_that_returns_executable_setup() -> None:
    """Catches an injected or future generator making research executable."""
    profile = build_threshold_profiles()[0]

    with pytest.raises(ValueError, match="shadow setup must be zero-share"):
        replay_threshold_shadows(
            signal_dates=(SIGNAL_DATE,),
            trading_dates=tuple(
                SIGNAL_DATE + timedelta(days=index) for index in range(3)
            ),
            bars_by_code={"600001": _flat_history()},
            memberships=(
                SectorMembership(
                    "600001", "S1", "测试行业", SIGNAL_DATE, None, "fixture"
                ),
            ),
            risk_flags=(),
            coverage_by_date={
                SIGNAL_DATE: ReferenceCoverage(SIGNAL_DATE, True, True, True)
            },
            market_snapshots={
                SIGNAL_DATE: MarketSnapshot(3, 60.0, 1.1, True)
            },
            holding_codes_by_date={SIGNAL_DATE: frozenset()},
            profiles=(profile,),
            formal_policy=SelectionPolicy(
                sector_return_percentile_min=0,
                sector_liquid_members_min=1,
                sector_strengthening_members_min=0,
                sector_breadth_min=0,
                sector_amount_ratio_min=0,
            ),
            setup_generator=_nonzero_setup_generator,
        )


def test_market_freeze_keeps_raw_shape_but_rejects_candidate() -> None:
    """Catches market-hidden setups disappearing or bypassing the freeze."""
    replay = _run_literal_replay(market=MarketSnapshot(1, 30.0, 0.70, True))

    assert len(replay.raw_setups) == 1
    assert replay.candidates == ()
    assert replay.rejections[0].stage == "MARKET"
    assert replay.rejections[0].reasons == ("INDEX_AND_BREADTH_WEAK",)


@pytest.mark.parametrize(
    ("holdings", "risk_flags", "reason"),
    (
        (frozenset({"600001"}), (), "EXISTING_HOLDING"),
        (
            frozenset(),
            (RiskFlag("600001", "ST", "VETO", SIGNAL_DATE, None, "fixture"),),
            "POINT_IN_TIME_RISK_VETO",
        ),
    ),
)
def test_point_in_time_base_failures_stop_profile_generation(
    holdings: frozenset[str],
    risk_flags: tuple[RiskFlag, ...],
    reason: str,
) -> None:
    """Catches holdings or VETO facts being ignored by research replay."""
    replay = _run_literal_replay(holdings=holdings, risk_flags=risk_flags)

    assert replay.raw_setups == ()
    assert replay.candidates == ()
    assert replay.rejections[0].stage == "BASE"
    assert reason in replay.rejections[0].reasons


def test_anti_chase_sector_and_plan_failures_remain_hard() -> None:
    """Catches a relaxed setup weakening any downstream production gate."""
    overheated = list(_flat_history())
    overheated[-1] = replace(overheated[-1], pct_chg=Decimal("6"))

    anti = _run_literal_replay(bars=tuple(overheated))
    sector = _run_literal_replay(memberships=())
    plan = _run_literal_replay(setup_generator=_wide_risk_setup_generator)

    assert anti.candidates == ()
    assert anti.rejections[-1].stage == "ANTI_CHASE"
    assert sector.candidates == ()
    assert sector.rejections[-1].reasons == ("SECTOR_MISSING",)
    assert plan.candidates == ()
    assert plan.rejections[-1].stage == "PRICE_PLAN"
    assert "RISK_DISTANCE_OUT_OF_RANGE" in plan.rejections[-1].reasons


def test_incomplete_coverage_and_future_bars_fail_closed() -> None:
    """Catches incomplete inputs or future bars changing shadow decisions."""
    incomplete = _run_literal_replay(
        coverage=ReferenceCoverage(SIGNAL_DATE, False, True, True)
    )
    bars = _flat_history()
    future = replace(
        bars[-1],
        trade_date=SIGNAL_DATE + timedelta(days=1),
        high=Decimal("99"),
        close=Decimal("90"),
    )

    baseline = _run_literal_replay(bars=bars)
    with_future = _run_literal_replay(bars=(*bars, future))

    assert incomplete.incomplete_dates == (SIGNAL_DATE,)
    assert incomplete.candidates == ()
    assert with_future == baseline
