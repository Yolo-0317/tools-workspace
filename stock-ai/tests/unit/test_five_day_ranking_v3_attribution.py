from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal, localcontext
import hashlib
import json

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3 import (
    build_five_day_ranking_v3_train_review,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_attribution import (
    MIN_MARKET_MEDIAN_MEMBERS,
    AttributedReturn,
    AttributionAuditTotals,
    MarketClosePanel,
    MarketCoverageIncomplete,
    RankedAttributedReturn,
    attribute_interval,
    attribution_verdict,
    build_five_day_ranking_v3_attribution_review,
    canonical_decimal_mean,
    diagnose_rank_one,
    exact_decimal_sum,
    fifth_subsequent_train_date,
    matched_index_id,
    simple_return,
    spearman_correlation,
    summarize_attributed_returns,
    wilson_interval,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_report import (
    FiveDayRankingV3TrainArtifact,
    five_day_ranking_v3_train_payload,
)

from five_day_ranking_v3_fixtures import (
    make_v3_observation,
    make_v3_plan,
    make_v3_research_review,
    weekday_dates,
)


START = date(2026, 7, 1)
END = date(2026, 7, 8)
PARENT_RESEARCH_IDENTITY = "a" * 64


def test_public_wilson_helper_keeps_exact_extreme_endpoints() -> None:
    assert wilson_interval(0, 2)[0] == Decimal("0")
    assert wilson_interval(3, 3)[1] == Decimal("1")


def test_public_spearman_helper_is_general_and_keeps_tie_semantics() -> None:
    assert spearman_correlation(
        (Decimal("1"), Decimal("2"), Decimal("3")),
        (Decimal("1"), Decimal("2"), Decimal("3")),
    ) == Decimal("1")
    assert spearman_correlation(
        (Decimal("1"), Decimal("2"), Decimal("2")),
        (Decimal("1"), Decimal("2"), Decimal("3")),
    ) == Decimal("0.8660254037844386467637231705")


@pytest.mark.parametrize(
    ("successes", "total"),
    ((-1, 2), (3, 2), (0, 0)),
)
def test_public_wilson_helper_rejects_invalid_counts(
    successes: int,
    total: int,
) -> None:
    with pytest.raises(ValueError, match="Wilson counts"):
        wilson_interval(successes, total)


def test_public_spearman_helper_rejects_misaligned_values() -> None:
    with pytest.raises(ValueError, match="same non-zero length"):
        spearman_correlation(
            (Decimal("1"), Decimal("2")),
            (Decimal("1"),),
        )


def test_exact_decimal_sum_ignores_ambient_precision() -> None:
    with localcontext() as context:
        context.prec = 6
        value = exact_decimal_sum(
            (
                Decimal("123456789.123456789"),
                Decimal("-123456788.123456788"),
            )
        )

    assert value == Decimal("1.000000001")


def test_canonical_decimal_mean_uses_local_precision_28() -> None:
    with localcontext() as context:
        context.prec = 4
        value = canonical_decimal_mean(Decimal("1"), 3)

    assert value == Decimal("0.3333333333333333333333333333")


def test_attribution_summary_even_median_ignores_ambient_precision() -> None:
    with localcontext() as context:
        context.prec = 4
        value = summarize_attributed_returns(
            (
                _attributed("0.1234567890123456789012345678", "0", "0"),
                _attributed("0.9876543210987654321098765432", "0", "0"),
            ),
            eligible_rows=2,
            excluded_missing_coverage=0,
        )

    assert value.median_return == Decimal(
        "0.5555555550555555555055555555"
    )


def _attributed(
    raw: str,
    matched_index: str,
    market_median: str,
) -> AttributedReturn:
    raw_value = Decimal(raw)
    index_value = Decimal(matched_index)
    median_value = Decimal(market_median)
    return AttributedReturn(
        raw_return=raw_value,
        matched_index_return=index_value,
        market_median_return=median_value,
        index_excess=raw_value - index_value,
        market_median_excess=raw_value - median_value,
        market_members=1000,
    )


def _ranked(
    signal_date: date,
    rank: int,
    *,
    raw: str,
    index_excess: str | None = None,
    market_excess: str | None = None,
) -> RankedAttributedReturn:
    raw_value = Decimal(raw)
    index_excess_value = Decimal(
        raw if index_excess is None else index_excess
    )
    market_excess_value = Decimal(
        raw if market_excess is None else market_excess
    )
    return RankedAttributedReturn(
        signal_date=signal_date,
        rank=rank,
        value=AttributedReturn(
            raw_return=raw_value,
            matched_index_return=raw_value - index_excess_value,
            market_median_return=raw_value - market_excess_value,
            index_excess=index_excess_value,
            market_median_excess=market_excess_value,
            market_members=1000,
        ),
    )


def _market_panel(
    *,
    stock_start: str = "10",
    stock_end: str = "11",
    index_start: str = "100",
    index_end: str = "102",
    median_start: str = "10",
    median_end: str = "10.50",
    market_members: int = MIN_MARKET_MEDIAN_MEMBERS,
) -> MarketClosePanel:
    stock_closes = {
        (
            f"600{member:03d}"
            if member < 1000
            else f"601{member - 1000:03d}"
        ): {
            START: Decimal(median_start),
            END: Decimal(median_end),
        }
        for member in range(market_members)
    }
    stock_closes["600001"] = {
        START: Decimal(stock_start),
        END: Decimal(stock_end),
    }
    return MarketClosePanel(
        train_dates=(START, END),
        stock_closes=stock_closes,
        index_closes={
            "sh.000001": {
                START: Decimal(index_start),
                END: Decimal(index_end),
            },
        },
    )


def _artifact_from_research(research) -> FiveDayRankingV3TrainArtifact:
    review = build_five_day_ranking_v3_train_review(
        research,
        parent_research_identity=PARENT_RESEARCH_IDENTITY,
    )
    payload = five_day_ranking_v3_train_payload(review)
    return FiveDayRankingV3TrainArtifact(
        artifact_identity=str(payload["artifact_identity"]),
        parent_research_identity=review.parent_research_identity,
        parent_input_fingerprint=review.parent_input_fingerprint,
        split=review.split,
        policy_set_hash=review.policy_set_hash,
        winner_policy_id=review.winner_policy_id,
        winner_policy_hash=review.winner_policy_hash,
        winner_train_samples=review.winner_train_samples,
        validation_eligible=review.validation_eligible,
        validation_evidence_windows=review.validation_evidence_windows,
        validation_feature_model=review.validation_feature_model,
        payload=payload,
    )


def _rehash_artifact(
    artifact: FiveDayRankingV3TrainArtifact,
    payload: dict[str, object],
) -> FiveDayRankingV3TrainArtifact:
    content = {
        key: value
        for key, value in payload.items()
        if key != "artifact_identity"
    }
    identity = hashlib.sha256(
        json.dumps(
            content,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    payload["artifact_identity"] = identity
    return replace(
        artifact,
        artifact_identity=identity,
        payload=payload,
    )


def _completed_training_fixture():
    sessions = weekday_dates(630)
    calibration = tuple(
        make_v3_observation(
            make_v3_plan(
                sessions[index],
                code=f"{600000 + index:06d}",
            ),
            net_return=Decimal("0.01"),
            resolution_date=sessions[index + 1],
        )
        for index in range(60)
    )
    evaluation = make_v3_observation(
        make_v3_plan(sessions[252], code="600999"),
        net_return=Decimal("0.04"),
        resolution_date=sessions[257],
    )
    assert evaluation.trade.entry_price is not None
    assert evaluation.trade.exit is not None
    evaluation = replace(
        evaluation,
        trade=replace(
            evaluation.trade,
            exit=replace(
                evaluation.trade.exit,
                price=evaluation.trade.entry_price * Decimal("1.05"),
            ),
        ),
    )
    research = make_v3_research_review((*calibration, evaluation))
    return _artifact_from_research(research), research, evaluation


def _bounded_market_panel(
    train_dates: tuple[date, ...],
    endpoint_dates: tuple[date, ...],
    *,
    target_code: str = "600999",
    target_closes: dict[date, Decimal] | None = None,
    missing_index_dates: frozenset[date] = frozenset(),
) -> MarketClosePanel:
    dates = tuple(sorted(set(endpoint_dates)))
    stock_closes = {
        f"600{member:03d}": {
            endpoint: Decimal("10") for endpoint in dates
        }
        for member in range(1000)
    }
    if target_closes is not None:
        stock_closes[target_code] = {
            **stock_closes.get(target_code, {}),
            **target_closes,
        }
    index_closes = {
        index_id: {
            endpoint: Decimal("100")
            for endpoint in dates
            if endpoint not in missing_index_dates
        }
        for index_id in ("sh.000001", "sz.399001", "sh.000688")
    }
    return MarketClosePanel(
        train_dates=train_dates,
        stock_closes=stock_closes,
        index_closes=index_closes,
    )


def _complete_fixture_with_panel():
    artifact, research, evaluation = _completed_training_fixture()
    signal_date = evaluation.plan.candidate.signal_date
    entry_date = evaluation.trade.entry_date
    assert entry_date is not None
    assert evaluation.trade.exit is not None
    exit_date = evaluation.trade.exit.actual_exit_date
    panel = _bounded_market_panel(
        artifact.split.train,
        (signal_date, entry_date, exit_date),
        target_closes={
            signal_date: Decimal("10"),
            exit_date: Decimal("10.50"),
        },
    )
    return artifact, research, evaluation, panel


@pytest.mark.parametrize(
    ("code", "expected"),
    (
        ("600001", "sh.000001"),
        ("601001.SH", "sh.000001"),
        ("603001", "sh.000001"),
        ("605001", "sh.000001"),
        ("000001", "sz.399001"),
        ("001001.SZ", "sz.399001"),
        ("002001", "sz.399001"),
        ("003001", "sz.399001"),
        ("688001", "sh.000688"),
    ),
)
def test_v3_attribution_maps_supported_boards_to_indexes(
    code: str,
    expected: str,
) -> None:
    assert matched_index_id(code) == expected


@pytest.mark.parametrize("code", ("300001", "830001", "900001", "fund"))
def test_v3_attribution_rejects_unsupported_boards(code: str) -> None:
    with pytest.raises(ValueError, match="unsupported attribution board"):
        matched_index_id(code)


def test_fixed_five_date_never_crosses_train_boundary() -> None:
    dates = weekday_dates(7, start=START)

    assert fifth_subsequent_train_date(dates[0], dates) == dates[5]
    assert fifth_subsequent_train_date(dates[2], dates) is None


@pytest.mark.parametrize(
    "dates",
    (
        (START, START),
        (END, START),
    ),
)
def test_fixed_five_date_rejects_non_increasing_train_calendar(
    dates: tuple[date, ...],
) -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        fifth_subsequent_train_date(START, dates)


def test_fixed_five_date_rejects_signal_outside_train_calendar() -> None:
    dates = weekday_dates(7, start=START)

    with pytest.raises(ValueError, match="signal date is not in train calendar"):
        fifth_subsequent_train_date(date(2026, 6, 30), dates)


def test_simple_return_is_exact_decimal() -> None:
    assert simple_return(Decimal("7.5"), Decimal("8.25")) == Decimal("0.1")


@pytest.mark.parametrize(
    ("start", "end"),
    (
        (Decimal("0"), Decimal("1")),
        (Decimal("1"), Decimal("-1")),
        (Decimal("NaN"), Decimal("1")),
        (Decimal("1"), Decimal("Infinity")),
    ),
)
def test_simple_return_rejects_non_positive_or_non_finite_endpoints(
    start: Decimal,
    end: Decimal,
) -> None:
    with pytest.raises(ValueError, match="finite positive close"):
        simple_return(start, end)


def test_interval_attribution_uses_dual_benchmarks_and_decimal() -> None:
    value = attribute_interval("600001", START, END, _market_panel())

    assert value.raw_return == Decimal("0.1")
    assert value.matched_index_return == Decimal("0.02")
    assert value.market_median_return == Decimal("0.05")
    assert value.index_excess == Decimal("0.08")
    assert value.market_median_excess == Decimal("0.05")
    assert value.market_members == 1000


def test_interval_attribution_accepts_same_day_with_zero_benchmarks() -> None:
    panel = _market_panel()

    value = attribute_interval("600001", START, START, panel)

    assert value.raw_return == Decimal("0")
    assert value.matched_index_return == Decimal("0")
    assert value.market_median_return == Decimal("0")
    assert value.index_excess == Decimal("0")
    assert value.market_median_excess == Decimal("0")
    assert value.market_members == 1000


def test_interval_attribution_rejects_reversed_dates() -> None:
    panel = _market_panel()

    with pytest.raises(ValueError, match="interval endpoints must be train dates"):
        attribute_interval("600001", END, START, panel)


def test_interval_attribution_uses_even_cross_sectional_return_median() -> None:
    panel = _market_panel(market_members=1000)
    stock_closes = dict(panel.stock_closes)
    stock_closes["600998"] = {START: Decimal("10"), END: Decimal("10.40")}
    stock_closes["600999"] = {START: Decimal("10"), END: Decimal("10.60")}

    value = attribute_interval(
        "600001",
        START,
        END,
        MarketClosePanel(panel.train_dates, stock_closes, panel.index_closes),
    )

    assert value.market_median_return == Decimal("0.05")


def test_interval_attribution_uses_odd_cross_sectional_return_median() -> None:
    panel = _market_panel(market_members=1001)
    stock_closes = dict(panel.stock_closes)
    member_codes = tuple(sorted(stock_closes))
    for member_code in member_codes[:500]:
        stock_closes[member_code] = {
            START: Decimal("10"),
            END: Decimal("10.40"),
        }
    stock_closes[member_codes[500]] = {
        START: Decimal("10"),
        END: Decimal("10.50"),
    }
    for member_code in member_codes[501:]:
        stock_closes[member_code] = {
            START: Decimal("10"),
            END: Decimal("10.60"),
        }

    value = attribute_interval(
        "600001",
        START,
        END,
        MarketClosePanel(panel.train_dates, stock_closes, panel.index_closes),
    )

    assert value.market_median_return == Decimal("0.05")
    assert value.market_members == 1001


def test_interval_attribution_excludes_non_main_board_from_market_median() -> None:
    panel = _market_panel()
    stock_closes = dict(panel.stock_closes)
    stock_closes["300001"] = {START: Decimal("1"), END: Decimal("100")}

    value = attribute_interval(
        "600001",
        START,
        END,
        MarketClosePanel(panel.train_dates, stock_closes, panel.index_closes),
    )

    assert value.market_median_return == Decimal("0.05")
    assert value.market_members == 1000


def test_interval_attribution_rejects_interval_outside_train_calendar() -> None:
    panel = _market_panel()

    with pytest.raises(ValueError, match="interval endpoints must be train dates"):
        attribute_interval("600001", START, date(2026, 7, 9), panel)


def test_interval_attribution_fails_closed_when_index_endpoint_is_missing() -> None:
    panel = _market_panel()
    incomplete = MarketClosePanel(
        panel.train_dates,
        panel.stock_closes,
        {"sh.000001": {START: Decimal("100")}},
    )

    with pytest.raises(MarketCoverageIncomplete) as raised:
        attribute_interval("600001", START, END, incomplete)

    assert raised.value.reason == "INDEX_ENDPOINT_MISSING"


def test_interval_attribution_requires_one_thousand_market_members() -> None:
    panel = _market_panel(market_members=999)

    with pytest.raises(MarketCoverageIncomplete) as raised:
        attribute_interval("600001", START, END, panel)

    assert raised.value.reason == "MARKET_MEMBERS_BELOW_1000"


def test_attribution_summary_reports_hand_derived_aggregate_metrics() -> None:
    rows = (
        _attributed("-0.02", "-0.03", "-0.04"),
        _attributed("0.04", "-0.01", "0.00"),
        _attributed("0.01", "0.00", "0.01"),
    )

    value = summarize_attributed_returns(
        rows,
        eligible_rows=4,
        excluded_missing_coverage=1,
    )

    assert value.eligible_rows == 4
    assert value.completed_rows == 3
    assert value.excluded_rows == 1
    assert value.excluded_missing_coverage == 1
    assert value.mean_return == Decimal("0.01")
    assert value.median_return == Decimal("0.01")
    assert value.positive_ratio == Decimal("2") / Decimal("3")
    assert value.positive_wilson_interval == (
        Decimal("0.2076596008020477361408035871"),
        Decimal("0.9385080552796037749310168249"),
    )
    assert value.mean_matched_index_return == (
        Decimal("-0.04") / Decimal("3")
    )
    assert value.median_matched_index_return == Decimal("-0.01")
    assert value.mean_market_median_return == Decimal("-0.01")
    assert value.median_market_median_return == Decimal("0")
    assert value.mean_index_excess == Decimal("0.07") / Decimal("3")
    assert value.median_index_excess == Decimal("0.01")
    assert value.mean_market_median_excess == Decimal("0.02")
    assert value.median_market_median_excess == Decimal("0.02")
    assert value.mean_gross_return is None
    assert value.mean_after_cost_drag is None
    assert value.verdict == "INCONCLUSIVE"


@pytest.mark.parametrize(
    ("raw_returns", "expected_ratio", "endpoint", "expected_endpoint"),
    (
        (("-0.03", "-0.02"), Decimal("0"), 0, Decimal("0")),
        (
            ("0.01", "0.02", "0.03"),
            Decimal("1"),
            1,
            Decimal("1"),
        ),
    ),
)
def test_wilson_extreme_endpoint_is_exact_under_low_ambient_precision(
    raw_returns: tuple[str, ...],
    expected_ratio: Decimal,
    endpoint: int,
    expected_endpoint: Decimal,
) -> None:
    with localcontext() as context:
        context.prec = 4
        value = summarize_attributed_returns(
            tuple(_attributed(raw, "0", "0") for raw in raw_returns),
            eligible_rows=len(raw_returns),
            excluded_missing_coverage=0,
        )

    assert value.positive_ratio == expected_ratio
    assert value.positive_wilson_interval is not None
    assert value.positive_wilson_interval[endpoint] == expected_endpoint
    assert value.positive_wilson_interval[0] <= expected_ratio
    assert value.positive_wilson_interval[1] >= expected_ratio


def test_attribution_summary_reports_gross_return_and_after_cost_drag() -> None:
    value = summarize_attributed_returns(
        (
            _attributed("0.04", "0.01", "0.02"),
            _attributed("-0.02", "-0.01", "-0.03"),
        ),
        eligible_rows=2,
        excluded_missing_coverage=0,
        gross_returns=(Decimal("0.05"), Decimal("-0.01")),
    )

    assert value.mean_gross_return == Decimal("0.02")
    assert value.mean_after_cost_drag == Decimal("0.01")


def test_attribution_summary_derives_recurring_means_from_exact_audit_totals() -> None:
    raw_returns = (
        Decimal("0.0135792468135792468135792468"),
        Decimal("-0.0246801357924680135792468013"),
        Decimal("0.0379135792468013579246801357"),
    )
    gross_returns = (
        Decimal("0.0148138147037027036025915924"),
        Decimal("-0.0234455679023445567902344557"),
        Decimal("0.0391481471369248147136924813"),
    )
    value = summarize_attributed_returns(
        tuple(_attributed(str(raw), "0", "0") for raw in raw_returns),
        eligible_rows=3,
        excluded_missing_coverage=0,
        gross_returns=gross_returns,
    )

    assert value.audit_totals == AttributionAuditTotals(
        positive_rows=2,
        raw_return_sum=Decimal("0.0268126902679125911590125812"),
        matched_index_return_sum=Decimal("0"),
        market_median_return_sum=Decimal("0"),
        gross_return_sum=Decimal("0.0305163939382829615260496180"),
    )
    assert value.mean_return == Decimal("0.008937563422637530386337527067")
    assert value.mean_gross_return == Decimal("0.01017213131276098717534987267")
    assert value.mean_after_cost_drag == Decimal(
        "0.0012345678901234567890123456"
    )


def test_empty_attribution_summary_uses_none_instead_of_fabricated_zero() -> None:
    value = summarize_attributed_returns(
        (),
        eligible_rows=2,
        excluded_missing_coverage=2,
    )

    assert value.completed_rows == 0
    assert value.excluded_rows == 2
    assert value.audit_totals == AttributionAuditTotals(
        positive_rows=0,
        raw_return_sum=Decimal("0"),
        matched_index_return_sum=Decimal("0"),
        market_median_return_sum=Decimal("0"),
        gross_return_sum=None,
    )
    assert value.mean_return is None
    assert value.median_return is None
    assert value.positive_ratio is None
    assert value.positive_wilson_interval is None
    assert value.mean_index_excess is None
    assert value.mean_market_median_excess is None
    assert value.verdict == "INCONCLUSIVE"


def test_empty_actual_attribution_summary_keeps_zero_gross_audit_total() -> None:
    value = summarize_attributed_returns(
        (),
        eligible_rows=0,
        excluded_missing_coverage=0,
        gross_returns=(),
    )

    assert value.audit_totals.gross_return_sum == Decimal("0")
    assert value.mean_gross_return is None
    assert value.mean_after_cost_drag is None


@pytest.mark.parametrize(
    ("eligible_rows", "missing_coverage", "gross_returns", "message"),
    (
        (0, 0, None, "completed rows cannot exceed eligible rows"),
        (1, 1, None, "missing coverage cannot exceed excluded rows"),
        (-1, 0, None, "counts must be non-negative"),
        (1, 0, (), "gross returns must align with completed rows"),
    ),
)
def test_attribution_summary_rejects_inconsistent_counts_or_gross_rows(
    eligible_rows: int,
    missing_coverage: int,
    gross_returns: tuple[Decimal, ...] | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        summarize_attributed_returns(
            (_attributed("0.01", "0", "0"),),
            eligible_rows=eligible_rows,
            excluded_missing_coverage=missing_coverage,
            gross_returns=gross_returns,
        )


def test_attribution_summary_rejects_non_finite_values() -> None:
    row = AttributedReturn(
        raw_return=Decimal("NaN"),
        matched_index_return=Decimal("0"),
        market_median_return=Decimal("0"),
        index_excess=Decimal("0"),
        market_median_excess=Decimal("0"),
        market_members=1000,
    )

    with pytest.raises(ValueError, match="finite attribution values"):
        summarize_attributed_returns(
            (row,),
            eligible_rows=1,
            excluded_missing_coverage=0,
        )


def test_attribution_summary_rejects_non_finite_gross_return() -> None:
    with pytest.raises(ValueError, match="finite attribution values"):
        summarize_attributed_returns(
            (_attributed("0.01", "0", "0"),),
            eligible_rows=1,
            excluded_missing_coverage=0,
            gross_returns=(Decimal("NaN"),),
        )


@pytest.mark.parametrize(
    ("raw", "index_excess", "median_excess", "expected"),
    (
        ("-0.01", "0.002", "0.001", "MARKET_DRAG"),
        ("-0.01", "0", "-0.001", "STRATEGY_DRAG"),
        ("-0.01", "0.001", "0", "MIXED"),
        ("-0.01", "0", "0", "STRATEGY_DRAG"),
        ("0", "-0.001", "-0.001", "INCONCLUSIVE"),
        ("0.01", "0.001", "0.001", "INCONCLUSIVE"),
    ),
)
def test_attribution_verdict_uses_frozen_sign_truth_table(
    raw: str,
    index_excess: str,
    median_excess: str,
    expected: str,
) -> None:
    assert attribution_verdict(
        completed_rows=30,
        mean_return=Decimal(raw),
        mean_index_excess=Decimal(index_excess),
        mean_market_median_excess=Decimal(median_excess),
    ) == expected


def test_attribution_verdict_requires_thirty_completed_rows() -> None:
    assert attribution_verdict(
        completed_rows=29,
        mean_return=Decimal("-0.01"),
        mean_index_excess=Decimal("0.002"),
        mean_market_median_excess=Decimal("0.001"),
    ) == "INCONCLUSIVE"


def test_rank_one_diagnosis_pairs_lower_ranks_within_each_date() -> None:
    dates = weekday_dates(2, start=START)
    rows = (
        _ranked(dates[0], 1, raw="0.10"),
        _ranked(dates[0], 2, raw="0.09"),
        _ranked(dates[1], 1, raw="0.00"),
        _ranked(dates[1], 2, raw="-0.10"),
        _ranked(dates[1], 3, raw="-0.10"),
    )

    value = diagnose_rank_one(rows)

    assert value.pairs.paired_dates == 2
    assert value.pairs.mean_raw_difference == Decimal("0.055")
    assert value.pairs.median_raw_difference == Decimal("0.055")
    assert value.pairs.mean_index_excess_difference == Decimal("0.055")
    assert value.pairs.mean_market_excess_difference == Decimal("0.055")
    assert value.pairs.rank_one_win_ratio == Decimal("1")
    assert value.pairs.verdict == "RANKER_INCONCLUSIVE"


def _paired_rank_rows(
    count: int,
    *,
    rank_one_index_excess: str = "-0.01",
    rank_one_market_excess: str = "-0.02",
) -> tuple[RankedAttributedReturn, ...]:
    dates = weekday_dates(count, start=START)
    return tuple(
        row
        for signal_date in dates
        for row in (
            _ranked(
                signal_date,
                1,
                raw="-0.02",
                index_excess=rank_one_index_excess,
                market_excess=rank_one_market_excess,
            ),
            _ranked(
                signal_date,
                2,
                raw="-0.01",
                index_excess="0",
                market_excess="0",
            ),
        )
    )


def test_rank_one_diagnosis_requires_fifteen_paired_dates() -> None:
    value = diagnose_rank_one(_paired_rank_rows(14))

    assert value.pairs.paired_dates == 14
    assert value.pairs.verdict == "RANKER_INCONCLUSIVE"


def test_rank_one_diagnosis_labels_non_positive_dual_excess_as_inverted() -> None:
    value = diagnose_rank_one(_paired_rank_rows(15))

    assert value.pairs.paired_dates == 15
    assert value.pairs.mean_index_excess_difference == Decimal("-0.01")
    assert value.pairs.mean_market_excess_difference == Decimal("-0.02")
    assert value.pairs.verdict == "RANKER_INVERTED"


@pytest.mark.parametrize(
    ("index_excess", "market_excess", "expected"),
    (
        ("0.01", "0.02", "RANKER_HEALTHY"),
        ("0.01", "0", "RANKER_MIXED"),
    ),
)
def test_rank_one_diagnosis_distinguishes_healthy_and_mixed_signs(
    index_excess: str,
    market_excess: str,
    expected: str,
) -> None:
    value = diagnose_rank_one(
        _paired_rank_rows(
            15,
            rank_one_index_excess=index_excess,
            rank_one_market_excess=market_excess,
        )
    )

    assert value.pairs.verdict == expected


def test_rank_correlation_uses_negative_ordinal_rank() -> None:
    rows = tuple(
        _ranked(
            START,
            rank,
            raw=str(Decimal("0.06") - Decimal(rank) / Decimal("100")),
        )
        for rank in range(1, 6)
    )

    value = diagnose_rank_one(rows)

    assert value.correlations.eligible_dates == 1
    assert value.correlations.completed_dates == 1
    assert value.correlations.mean_raw_correlation == Decimal("1")
    assert value.correlations.median_raw_correlation == Decimal("1")
    assert value.correlations.mean_index_excess_correlation == Decimal("1")
    assert value.correlations.mean_market_excess_correlation == Decimal("1")


def test_rank_correlation_assigns_average_ranks_to_tied_returns() -> None:
    rows = tuple(
        _ranked(START, rank, raw=raw)
        for rank, raw in enumerate(
            ("0.05", "0.04", "0.04", "0.02", "0.01"),
            start=1,
        )
    )

    value = diagnose_rank_one(rows)

    assert value.correlations.mean_raw_correlation == Decimal(
        "0.9746794344808963906838413200"
    )


def test_rank_correlation_excludes_cross_sections_smaller_than_five() -> None:
    rows = tuple(
        _ranked(START, rank, raw=str(Decimal(rank) / Decimal("100")))
        for rank in range(1, 5)
    )

    value = diagnose_rank_one(rows)

    assert value.correlations.eligible_dates == 0
    assert value.correlations.completed_dates == 0
    assert value.correlations.mean_raw_correlation is None


def test_rank_correlation_counts_but_excludes_constant_return_section() -> None:
    rows = tuple(
        _ranked(START, rank, raw="0.01")
        for rank in range(1, 6)
    )

    value = diagnose_rank_one(rows)

    assert value.correlations.eligible_dates == 1
    assert value.correlations.completed_dates == 0
    assert value.correlations.mean_raw_correlation is None


@pytest.mark.parametrize(
    "rows",
    (
        (
            _ranked(START, 1, raw="0.01"),
            _ranked(START, 1, raw="0.02"),
        ),
        (_ranked(START, 0, raw="0.01"),),
    ),
)
def test_rank_one_diagnosis_rejects_invalid_ordinal_ranks(
    rows: tuple[RankedAttributedReturn, ...],
) -> None:
    with pytest.raises(ValueError, match="positive and unique within date"):
        diagnose_rank_one(rows)


def test_attribution_builder_rejects_parent_identity_before_market_access() -> None:
    artifact, research, _, panel = _complete_fixture_with_panel()

    with pytest.raises(ValueError, match="parent research identity mismatch"):
        build_five_day_ranking_v3_attribution_review(
            artifact,
            research,
            parent_research_identity="b" * 64,
            market_panel=panel,
        )


def test_attribution_builder_rejects_parent_input_fingerprint_mismatch() -> None:
    artifact, research, _, panel = _complete_fixture_with_panel()

    with pytest.raises(ValueError, match="parent input fingerprint mismatch"):
        build_five_day_ranking_v3_attribution_review(
            artifact,
            replace(research, input_fingerprint="0" * 64),
            parent_research_identity=PARENT_RESEARCH_IDENTITY,
            market_panel=panel,
        )


@pytest.mark.parametrize(
    "unsafe_research",
    (
        {"point_in_time_complete": False},
        {"test_outcomes_read": True},
    ),
)
def test_attribution_builder_rejects_unsafe_parent_research(
    unsafe_research: dict[str, object],
) -> None:
    artifact, research, _, panel = _complete_fixture_with_panel()

    with pytest.raises(ValueError, match="parent research safety mismatch"):
        build_five_day_ranking_v3_attribution_review(
            artifact,
            replace(research, **unsafe_research),
            parent_research_identity=PARENT_RESEARCH_IDENTITY,
            market_panel=panel,
        )


def test_attribution_builder_requires_exact_train_market_calendar() -> None:
    artifact, research, _, panel = _complete_fixture_with_panel()
    wrong_panel = MarketClosePanel(
        panel.train_dates[:-1],
        panel.stock_closes,
        panel.index_closes,
    )

    with pytest.raises(ValueError, match="market panel train calendar mismatch"):
        build_five_day_ranking_v3_attribution_review(
            artifact,
            research,
            parent_research_identity=PARENT_RESEARCH_IDENTITY,
            market_panel=wrong_panel,
        )


@pytest.mark.parametrize(
    ("flag", "value"),
    (
        ("validation_outcomes_read", True),
        ("test_outcomes_read", True),
        ("promotion_eligible", True),
        ("trade_permission", "TRADE"),
    ),
)
def test_attribution_builder_rejects_unsafe_train_artifact_flags(
    flag: str,
    value: object,
) -> None:
    artifact, research, _, panel = _complete_fixture_with_panel()
    payload = dict(artifact.payload)
    payload[flag] = value
    unsafe = _rehash_artifact(artifact, payload)

    with pytest.raises(ValueError, match="train artifact safety mismatch"):
        build_five_day_ranking_v3_attribution_review(
            unsafe,
            research,
            parent_research_identity=PARENT_RESEARCH_IDENTITY,
            market_panel=panel,
        )


def test_attribution_builder_rejects_cross_train_ranked_key() -> None:
    artifact, research, _, panel = _complete_fixture_with_panel()
    payload = dict(artifact.payload)
    variants = [dict(value) for value in payload["variants"]]
    first = variants[0]
    segment = dict(first["segment"])
    ranked = [dict(value) for value in segment["ranked_plan_keys"]]
    assert ranked
    ranked[0]["signal_date"] = artifact.split.validation[0].isoformat()
    segment["ranked_plan_keys"] = ranked
    first["segment"] = segment
    variants[0] = first
    payload["variants"] = variants
    cross_train = _rehash_artifact(artifact, payload)

    with pytest.raises(ValueError, match="plan key is outside train split"):
        build_five_day_ranking_v3_attribution_review(
            cross_train,
            research,
            parent_research_identity=PARENT_RESEARCH_IDENTITY,
            market_panel=panel,
        )


def test_attribution_builder_rejects_missing_or_duplicate_plan_mapping() -> None:
    artifact, research, evaluation, panel = _complete_fixture_with_panel()
    missing_research = replace(
        research,
        observations=tuple(
            value
            for value in research.observations
            if value is not evaluation
        ),
    )

    with pytest.raises(ValueError, match="plan key has no parent observation"):
        build_five_day_ranking_v3_attribution_review(
            artifact,
            missing_research,
            parent_research_identity=PARENT_RESEARCH_IDENTITY,
            market_panel=panel,
        )

    duplicate_research = replace(
        research,
        observations=(*research.observations, evaluation),
    )
    with pytest.raises(ValueError, match="duplicate parent observation key"):
        build_five_day_ranking_v3_attribution_review(
            artifact,
            duplicate_research,
            parent_research_identity=PARENT_RESEARCH_IDENTITY,
            market_panel=panel,
        )


def test_attribution_builder_excludes_last_five_train_sessions() -> None:
    sessions = weekday_dates(630)
    calibration = tuple(
        make_v3_observation(
            make_v3_plan(
                sessions[index],
                code=f"{600000 + index:06d}",
            ),
            resolution_date=sessions[index + 1],
        )
        for index in range(60)
    )
    late = make_v3_observation(
        make_v3_plan(sessions[377], code="699999"),
        resolution_date=sessions[378],
    )
    research = make_v3_research_review((*calibration, late))
    artifact = _artifact_from_research(research)
    panel = MarketClosePanel(artifact.split.train, {}, {})

    review = build_five_day_ranking_v3_attribution_review(
        artifact,
        research,
        parent_research_identity=PARENT_RESEARCH_IDENTITY,
        market_panel=panel,
    )
    variant = next(
        value
        for value in review.variants
        if value.fold_id == "train-fold-2"
        and value.policy_id == "EDGE-K30"
        and value.selection_mode == "FORMAL"
    )

    assert variant.funnel_counts["FIXED_FIVE_WITHOUT_TRAIN_HORIZON"] == 1
    assert sum(
        value.eligible_rows
        for value in variant.fixed_five_by_rank_band.values()
    ) == 1
    assert sum(
        value.completed_rows
        for value in variant.fixed_five_by_rank_band.values()
    ) == 0
    assert review.coverage.attempted_intervals == 0
    assert review.status == "COMPLETE"


def test_attribution_builder_creates_all_variants_and_actual_cost_drag() -> None:
    artifact, research, _, panel = _complete_fixture_with_panel()

    review = build_five_day_ranking_v3_attribution_review(
        artifact,
        research,
        parent_research_identity=PARENT_RESEARCH_IDENTITY,
        market_panel=panel,
    )
    first = review.variants[0]

    assert len(review.variants) == 72
    assert first.fold_id == "train-fold-1"
    assert first.policy_id == "EDGE-K30"
    assert first.selection_mode == "TOP_1"
    assert first.actual.completed_rows == 1
    assert first.actual.mean_return == Decimal("0.04")
    assert first.actual.mean_gross_return == Decimal("0.05")
    assert first.actual.mean_after_cost_drag == Decimal("0.01")
    assert sum(
        value.eligible_rows for value in first.actual_by_status.values()
    ) == first.actual.eligible_rows
    assert sum(
        value.completed_rows for value in first.actual_by_status.values()
    ) == first.actual.completed_rows
    assert sum(
        value.eligible_rows
        for value in first.fixed_five_by_rank_band.values()
    ) == first.funnel_counts["FIXED_FIVE_RANKED_ELIGIBLE"]
    assert review.train_only is True
    assert review.validation_outcomes_read is False
    assert review.test_outcomes_read is False
    assert review.promotion_eligible is False
    assert review.trade_permission == "NO-TRADE"
    assert review.status == "COMPLETE"


def test_attribution_builder_keeps_same_day_actual_trade() -> None:
    _, research, evaluation = _completed_training_fixture()
    entry_date = evaluation.trade.entry_date
    assert entry_date is not None
    assert evaluation.trade.exit is not None
    same_day = replace(
        evaluation,
        resolution_date=entry_date,
        trade=replace(
            evaluation.trade,
            exit=replace(
                evaluation.trade.exit,
                planned_exit_date=entry_date,
                actual_exit_date=entry_date,
            ),
        ),
    )
    same_day_research = replace(
        research,
        observations=tuple(
            same_day if value is evaluation else value
            for value in research.observations
        ),
    )
    artifact = _artifact_from_research(same_day_research)
    signal_date = same_day.plan.candidate.signal_date
    panel = _bounded_market_panel(
        artifact.split.train,
        (signal_date, entry_date),
        target_closes={
            signal_date: Decimal("10"),
            entry_date: Decimal("10.5"),
        },
    )

    review = build_five_day_ranking_v3_attribution_review(
        artifact,
        same_day_research,
        parent_research_identity=PARENT_RESEARCH_IDENTITY,
        market_panel=panel,
    )

    actual = review.variants[0].actual
    assert actual.completed_rows == 1
    assert actual.mean_return == Decimal("0.04")
    assert actual.mean_matched_index_return == Decimal("0")
    assert actual.mean_market_median_return == Decimal("0")
    assert actual.mean_index_excess == Decimal("0.04")
    assert actual.mean_market_median_excess == Decimal("0.04")
    assert review.status == "COMPLETE"


def test_attribution_builder_fails_closed_on_index_coverage_gap() -> None:
    artifact, research, evaluation, panel = _complete_fixture_with_panel()
    assert evaluation.trade.exit is not None
    missing_date = evaluation.trade.exit.actual_exit_date
    incomplete_panel = _bounded_market_panel(
        panel.train_dates,
        tuple(panel.index_closes["sh.000001"]),
        target_closes=dict(panel.stock_closes["600999"]),
        missing_index_dates=frozenset((missing_date,)),
    )

    review = build_five_day_ranking_v3_attribution_review(
        artifact,
        research,
        parent_research_identity=PARENT_RESEARCH_IDENTITY,
        market_panel=incomplete_panel,
    )

    assert review.status == "MARKET_DATA_INCOMPLETE"
    assert review.coverage.index_endpoint_missing_intervals > 0
    assert review.coverage.market_members_below_threshold_intervals == 0
    assert missing_date in review.coverage.missing_endpoint_dates
    assert review.coverage.attempted_intervals == (
        review.coverage.completed_intervals
        + review.coverage.index_endpoint_missing_intervals
        + review.coverage.market_members_below_threshold_intervals
    )
    assert all(
        variant.actual.verdict == "INCONCLUSIVE"
        and variant.rank_pairs.verdict == "RANKER_INCONCLUSIVE"
        and all(
            value.verdict == "INCONCLUSIVE"
            for value in variant.fixed_five_by_rank_band.values()
        )
        for variant in review.variants
    )


def test_attribution_builder_fails_closed_below_market_member_boundary() -> None:
    artifact, research, _, panel = _complete_fixture_with_panel()
    stock_closes = dict(panel.stock_closes)
    del stock_closes["600000"]

    review = build_five_day_ranking_v3_attribution_review(
        artifact,
        research,
        parent_research_identity=PARENT_RESEARCH_IDENTITY,
        market_panel=MarketClosePanel(
            panel.train_dates,
            stock_closes,
            panel.index_closes,
        ),
    )

    assert review.status == "MARKET_DATA_INCOMPLETE"
    assert review.coverage.index_endpoint_missing_intervals == 0
    assert review.coverage.market_members_below_threshold_intervals > 0
    assert review.coverage.attempted_intervals == (
        review.coverage.completed_intervals
        + review.coverage.market_members_below_threshold_intervals
    )


def test_attribution_builder_excludes_missing_fixed_five_stock_endpoint() -> None:
    artifact, research, evaluation, panel = _complete_fixture_with_panel()
    assert evaluation.trade.exit is not None
    end = evaluation.trade.exit.actual_exit_date
    stock_closes = {
        code: dict(values) for code, values in panel.stock_closes.items()
    }
    del stock_closes["600999"][end]
    stock_closes["601998"] = dict(stock_closes["600000"])

    review = build_five_day_ranking_v3_attribution_review(
        artifact,
        research,
        parent_research_identity=PARENT_RESEARCH_IDENTITY,
        market_panel=MarketClosePanel(
            panel.train_dates,
            stock_closes,
            panel.index_closes,
        ),
    )
    first = review.variants[0]

    assert first.actual.completed_rows == 1
    assert first.funnel_counts["FIXED_FIVE_STOCK_ENDPOINT_MISSING"] == 1
    assert sum(
        value.eligible_rows
        for value in first.fixed_five_by_rank_band.values()
    ) == 1
    assert sum(
        value.completed_rows
        for value in first.fixed_five_by_rank_band.values()
    ) == 0
    assert review.coverage.index_endpoint_missing_intervals == 0
    assert review.coverage.market_members_below_threshold_intervals == 0
    assert review.status == "COMPLETE"


def test_any_coverage_gap_forces_other_sufficient_verdicts_inconclusive() -> None:
    artifact, research, _, _ = _complete_fixture_with_panel()
    sessions = artifact.split.train
    added = tuple(
        make_v3_observation(
            make_v3_plan(
                sessions[252 + offset],
                code=f"{601000 + offset:06d}",
            ),
            net_return=Decimal("-0.01"),
            resolution_date=sessions[257 + offset],
        )
        for offset in range(31)
    )
    research = replace(
        research,
        observations=(*research.observations, *added),
    )
    payload = dict(artifact.payload)
    variants = [dict(value) for value in payload["variants"]]
    first = variants[0]
    segment = dict(first["segment"])
    segment["ranked_plan_keys"] = [
        {
            "signal_date": value.plan.candidate.signal_date.isoformat(),
            "code": value.plan.candidate.code,
            "structure_id": value.plan.structure_id,
            "profile_id": value.plan.profile.profile_id,
            "rank": 1,
            "selected": True,
        }
        for value in added
    ]
    first["segment"] = segment
    variants[0] = first
    payload["variants"] = variants
    artifact = _rehash_artifact(artifact, payload)

    endpoint_dates = tuple(sessions[index] for index in range(252, 288))
    base_closes = {
        endpoint: Decimal(1000 - 10 * offset)
        for offset, endpoint in enumerate(endpoint_dates)
    }
    stock_closes = {
        f"600{member:03d}": dict(base_closes)
        for member in range(1000)
    }
    for offset, value in enumerate(added):
        stock_closes[value.plan.candidate.code] = {
            sessions[252 + offset]: Decimal("10"),
            sessions[257 + offset]: Decimal("9.90"),
        }
    missing_date = sessions[287]
    index_closes = {
        "sh.000001": {
            endpoint: close
            for endpoint, close in base_closes.items()
            if endpoint != missing_date
        },
    }

    review = build_five_day_ranking_v3_attribution_review(
        artifact,
        research,
        parent_research_identity=PARENT_RESEARCH_IDENTITY,
        market_panel=MarketClosePanel(
            sessions,
            stock_closes,
            index_closes,
        ),
    )

    assert review.status == "MARKET_DATA_INCOMPLETE"
    assert review.coverage.index_endpoint_missing_intervals == 1
    assert review.variants[0].fixed_five_by_rank_band[
        "RANK_1"
    ].completed_rows == 30
    assert review.variants[0].fixed_five_by_rank_band[
        "RANK_1"
    ].verdict == "INCONCLUSIVE"


def test_market_data_fingerprint_is_order_independent_and_content_bound() -> None:
    artifact, research, _, panel = _complete_fixture_with_panel()
    first = build_five_day_ranking_v3_attribution_review(
        artifact,
        research,
        parent_research_identity=PARENT_RESEARCH_IDENTITY,
        market_panel=panel,
    )
    reordered = MarketClosePanel(
        panel.train_dates,
        dict(reversed(tuple(panel.stock_closes.items()))),
        dict(reversed(tuple(panel.index_closes.items()))),
    )
    second = build_five_day_ranking_v3_attribution_review(
        artifact,
        research,
        parent_research_identity=PARENT_RESEARCH_IDENTITY,
        market_panel=reordered,
    )
    changed_stock_closes = {
        code: dict(values) for code, values in panel.stock_closes.items()
    }
    changed_date = next(iter(changed_stock_closes["600000"]))
    changed_stock_closes["600000"][changed_date] = Decimal("11")
    changed = build_five_day_ranking_v3_attribution_review(
        artifact,
        research,
        parent_research_identity=PARENT_RESEARCH_IDENTITY,
        market_panel=MarketClosePanel(
            panel.train_dates,
            changed_stock_closes,
            panel.index_closes,
        ),
    )

    assert len(first.market_data_fingerprint) == 64
    assert first.market_data_fingerprint == second.market_data_fingerprint
    assert first.market_data_fingerprint != changed.market_data_fingerprint
