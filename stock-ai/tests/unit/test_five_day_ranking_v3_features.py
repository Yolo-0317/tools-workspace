from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3_features import (
    V3_FEATURE_NAMES,
    V3FeatureEffect,
    V3FeatureModel,
    build_v3_feature_model,
    derive_v3_plan_features,
    score_v3_feature_adjustment,
)

from five_day_ranking_v3_fixtures import (
    make_v3_observation,
    make_v3_plan,
    weekday_dates,
)


START = date(2023, 1, 2)
PROFILE_ID = "BREAKOUT_TRIGGER__STRUCTURE_ATR"
SETUP_TYPE = "TREND_PULLBACK"


def _feature_model(
    *,
    full_delta: str,
    recent_delta: str,
    full_samples: int = 30,
    recent_samples: int = 15,
    feature_name: str = "setup_quality",
    bin_name: str = "Q1",
) -> V3FeatureModel:
    return V3FeatureModel(
        data_end=START - timedelta(days=1),
        boundaries={name: () for name in V3_FEATURE_NAMES},
        effects={
            (PROFILE_ID, SETUP_TYPE, feature_name, bin_name): V3FeatureEffect(
                full_samples=full_samples,
                recent_samples=recent_samples,
                full_delta=Decimal(full_delta),
                recent_delta=Decimal(recent_delta),
            )
        },
    )


def _seven_positive_feature_model(*, delta: str) -> V3FeatureModel:
    return V3FeatureModel(
        data_end=START - timedelta(days=1),
        boundaries={name: () for name in V3_FEATURE_NAMES},
        effects={
            (PROFILE_ID, SETUP_TYPE, name, "Q1"): V3FeatureEffect(
                full_samples=100,
                recent_samples=100,
                full_delta=Decimal(delta),
                recent_delta=Decimal(delta),
            )
            for name in V3_FEATURE_NAMES
        },
    )


def test_v3_common_features_use_only_signal_plan_values() -> None:
    plan = make_v3_plan(
        date(2025, 1, 10),
        profile_id="PULLBACK_RECLAIM__FIXED_3_PERCENT",
        structure_start=date(2025, 1, 2),
        structure_high=Decimal("11"),
        structure_low=Decimal("9"),
        signal_close=Decimal("10"),
        breakout_trigger=Decimal("10.20"),
        structure_stop=Decimal("9.70"),
        resistance_effective_r=None,
    )

    value = derive_v3_plan_features(
        plan,
        trading_dates=weekday_dates(20, start=date(2024, 12, 23)),
    )

    assert value.setup_quality == Decimal("0.60")
    assert value.structure_duration == 7
    assert value.structure_width == Decimal("2") / Decimal("9")
    assert value.trigger_gap == Decimal("0.02")
    assert value.risk_distance == Decimal("0.03")
    assert value.resistance_effective_r is None
    assert value.log_average_amount5.is_finite()


def test_v3_feature_derivation_rejects_unresolved_profile_stop() -> None:
    plan = make_v3_plan(
        START,
        structure_stop=Decimal("1"),
    )

    with pytest.raises(ValueError, match="profile stop"):
        derive_v3_plan_features(
            plan,
            trading_dates=weekday_dates(20, start=START - timedelta(days=15)),
        )


def test_v3_model_freezes_full_quintiles_and_excludes_future_resolution() -> None:
    dates = weekday_dates(140)
    signal_indexes = (1, 2, 3, 4, 5, 100, 101, 102, 103, 104)
    observations = tuple(
        make_v3_observation(
            make_v3_plan(
                dates[signal_indexes[index]],
                code=f"6000{index:02d}",
                setup_quality=Decimal(index + 1) / Decimal("10"),
            ),
            net_return=Decimal(index + 1) / Decimal("100"),
            net_pnl=Decimal(index + 1) * Decimal("100"),
        )
        for index in range(10)
    )
    future = make_v3_observation(
        make_v3_plan(
            dates[110],
            code="600099",
            setup_quality=Decimal("0.99"),
        ),
        net_return=Decimal("1"),
        net_pnl=Decimal("10000"),
        resolution_date=dates[-1] + timedelta(days=1),
    )

    model = build_v3_feature_model(
        (*observations, future),
        full_dates=dates,
        recent_dates=dates[-126:],
    )

    assert model.boundaries["setup_quality"] == (
        Decimal("0.2"),
        Decimal("0.4"),
        Decimal("0.6"),
        Decimal("0.8"),
    )
    q1 = model.effects[(PROFILE_ID, SETUP_TYPE, "setup_quality", "Q1")]
    assert q1.full_samples == 2
    assert q1.recent_samples == 0
    assert q1.full_delta == Decimal("-0.04")
    assert q1.recent_delta == Decimal("0")
    q4 = model.effects[(PROFILE_ID, SETUP_TYPE, "setup_quality", "Q4")]
    assert q4.recent_samples == 2
    assert q4.recent_delta == Decimal("-0.005")
    assert sum(
        effect.full_samples
        for key, effect in model.effects.items()
        if key[:3] == (PROFILE_ID, SETUP_TYPE, "setup_quality")
    ) == 10


def test_v3_missing_resistance_uses_separate_effect_bin() -> None:
    model = _feature_model(
        full_delta="0.02",
        recent_delta="0.02",
        feature_name="resistance_effective_r",
        bin_name="MISSING",
    )

    scored = score_v3_feature_adjustment(
        make_v3_plan(START, resistance_effective_r=None),
        model,
        shrinkage_k=30,
    )

    assert scored.effects["resistance_effective_r"] == Decimal("0.001")


def test_v3_feature_effect_requires_full_recent_sign_agreement() -> None:
    model = _feature_model(full_delta="0.02", recent_delta="-0.01")

    scored = score_v3_feature_adjustment(
        make_v3_plan(START),
        model,
        shrinkage_k=30,
    )

    assert scored.total == Decimal("0")


@pytest.mark.parametrize(
    ("full_samples", "recent_samples"),
    ((29, 100), (100, 14)),
)
def test_v3_feature_effect_requires_both_sample_minimums(
    full_samples: int,
    recent_samples: int,
) -> None:
    model = _feature_model(
        full_delta="0.02",
        recent_delta="0.02",
        full_samples=full_samples,
        recent_samples=recent_samples,
    )

    scored = score_v3_feature_adjustment(
        make_v3_plan(START),
        model,
        shrinkage_k=30,
    )

    assert scored.total == Decimal("0")


def test_v3_feature_caps_apply_per_feature_and_in_total() -> None:
    model = _seven_positive_feature_model(delta="0.02")

    scored = score_v3_feature_adjustment(
        make_v3_plan(START),
        model,
        shrinkage_k=30,
    )

    assert all(
        abs(value) <= Decimal("0.001")
        for value in scored.effects.values()
    )
    assert scored.total == Decimal("0.003")
