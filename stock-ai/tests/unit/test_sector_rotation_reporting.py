from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal

from stock_ai.sector_rotation.models import (
    CandidateRole, ChainMetrics, ChainScore, PriceLevels, RotationBucket,
    RotationCandidate, RotationRunResult, RotationState, SelectedChain,
)
from stock_ai.sector_rotation.reporting import render_rotation_report


def _chain(code: str, bucket: RotationBucket, state: RotationState) -> SelectedChain:
    metrics = ChainMetrics(Decimal("0.8"), Decimal("0.7"), Decimal("0.7"), Decimal("0.7"),
                           Decimal("0.7"), 8, 10, Decimal("1.3"), Decimal("0.7"), 2,
                           Decimal("0.3"), True)
    score = ChainScore(Decimal("76"), Decimal("23"), Decimal("18"), Decimal("15"),
                       Decimal("14"), Decimal("7"), Decimal("1"), ("结构健康",))
    return SelectedChain(code, code, code, ("BK1",), (code,), 1, Decimal("2"), metrics,
                         score, state, RotationState.STARTING, ("状态有效",), (),
                         ("600001",), bucket)


def report_result() -> RotationRunResult:
    chains = (
        _chain("半导体", RotationBucket.STRONG, RotationState.CONFIRMED),
        _chain("铜铝", RotationBucket.STRENGTHENING, RotationState.LATENT),
        _chain("储能", RotationBucket.PULLBACK, RotationState.LATENT),
    )
    candidates = tuple(
        RotationCandidate(
            chain.chain_code, f"60000{index}", f"样本{index}", CandidateRole.LEADER,
            1, True, index == 0, {"change_pct": Decimal("3")},
            PriceLevels(Decimal("10"), Decimal("10.2"), Decimal("10.7"), Decimal("9.5")),
            ("LEADER_STRENGTH",), (),
        )
        for index, chain in enumerate(chains)
    )
    return RotationRunResult(
        "run-1", datetime(2026, 8, 18, 14, 40, tzinfo=timezone.utc), date(2026, 8, 18),
        "intraday", "sector-rotation-1.0.0", chains, candidates,
        ("部分成分股数据延迟",), None,
    )


def previous_result() -> RotationRunResult:
    current = report_result()
    previous_chain = replace(current.chains[0], state=RotationState.STARTING)
    return replace(current, run_id="run-0", chains=(previous_chain, *current.chains[1:]))


def test_report_contains_freshness_six_buckets_ten_stock_pool_and_formal_levels() -> None:
    text = render_rotation_report(report_result(), previous_result())

    assert "数据时间与完整性" in text
    assert "当前最强" in text
    assert "正在增强" in text
    assert "回踩观察" in text
    assert "状态变化" in text
    assert "持仓交集" in text
    assert "观察价" in text and "触发价" in text and "禁追价" in text and "失效位" in text
    assert "禁止追高" in text
    assert "非自动交易" in text
    assert "🚀" not in text


def test_report_explains_a_short_bucket_instead_of_padding_it() -> None:
    result = report_result()
    text = render_rotation_report(replace(result, chains=result.chains[:2]), None)

    assert "本次仅有2个方向通过门槛" in text
