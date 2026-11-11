from dataclasses import replace
from decimal import Decimal

from stock_ai.sector_rotation.models import ChainMetrics, RotationPolicy, RotationState
from stock_ai.sector_rotation.scoring import classify_state, score_chain


def complete_metrics(**overrides: object) -> ChainMetrics:
    values: dict[str, object] = {
        "return_percentile": Decimal("0.82"),
        "rank_improvement": Decimal("0.70"),
        "breadth_ratio": Decimal("0.65"),
        "above_ma5_ratio": Decimal("0.70"),
        "above_ma20_ratio": Decimal("0.72"),
        "strengthening_count": 8,
        "liquid_count": 10,
        "amount_ratio": Decimal("1.30"),
        "advancing_amount_ratio": Decimal("0.68"),
        "persistence_count": 2,
        "leader_concentration": Decimal("0.32"),
        "data_complete": True,
    }
    values.update({key: Decimal(str(value)) if isinstance(value, float) else value for key, value in overrides.items()})
    return ChainMetrics(**values)  # type: ignore[arg-type]


def test_single_leader_spike_cannot_be_called_starting() -> None:
    metrics = complete_metrics(
        return_percentile=0.95,
        breadth_ratio=0.18,
        amount_ratio=1.60,
        leader_concentration=0.86,
    )
    score = score_chain(metrics, RotationPolicy())

    state, reasons = classify_state(score, metrics, (), RotationPolicy())

    assert state is RotationState.OVERHEATED
    assert "LEADER_ONLY" in reasons


def test_two_valid_strong_snapshots_promote_starting_to_confirmed() -> None:
    policy = RotationPolicy()
    metrics = complete_metrics(return_percentile=0.88, breadth_ratio=0.68, amount_ratio=1.35)
    score = score_chain(metrics, policy)

    state, _ = classify_state(
        score,
        metrics,
        ((RotationState.STARTING, score), (RotationState.STARTING, score)),
        policy,
    )

    assert state is RotationState.CONFIRMED


def test_confirmed_chain_with_score_and_breadth_collapse_fades() -> None:
    policy = RotationPolicy()
    previous_score = replace(score_chain(complete_metrics(), policy), total=Decimal("78"))
    metrics = complete_metrics(breadth_ratio=0.32, amount_ratio=0.71)
    score = replace(score_chain(metrics, policy), total=Decimal("55"))

    state, reasons = classify_state(
        score,
        metrics,
        ((RotationState.CONFIRMED, previous_score),),
        policy,
    )

    assert state is RotationState.FADING
    assert "SCORE_DROPPED" in reasons


def test_incomplete_data_cannot_be_starting_or_confirmed() -> None:
    policy = RotationPolicy()
    metrics = replace(complete_metrics(), data_complete=False)
    score = replace(score_chain(metrics, policy), total=Decimal("80"))

    state, reasons = classify_state(score, metrics, (), policy)

    assert state is RotationState.LATENT
    assert "DATA_INCOMPLETE" in reasons
