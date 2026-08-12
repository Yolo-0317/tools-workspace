from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.news_impact import (
    NewsEvent,
    ProbabilityPaths,
    StockContext,
    analyze_stock_news_impact,
    deduplicate_events,
    filter_fresh_events,
)
from stock_ai.news_impact.mappings import iter_event_mapped_stocks


NOW = datetime(2026, 8, 12, 9, 0, tzinfo=timezone(timedelta(hours=8)))


def event(**changes):
    values = {
        "event_id": "coreweave-q2",
        "title": "CoreWeave上调资本开支",
        "summary": "AI云厂商提高数据中心资本开支",
        "published_at": NOW - timedelta(hours=2),
        "observed_at": NOW,
        "source_url": "https://example.com/official",
        "source_name": "公司官网",
        "source_tier": "official",
        "market": "US",
        "country": "US",
        "subjects": ("CoreWeave",),
        "event_type": "capex",
        "direction": "positive",
        "confirmation_state": "official",
        "scope": "overseas",
        "evidence": "资本开支提高",
    }
    values.update(changes)
    return NewsEvent(**values)


def test_overseas_event_expires_after_24_hours():
    stale = event(published_at=NOW - timedelta(hours=25))
    assert filter_fresh_events([stale], now=NOW) == []


def test_policy_and_a_share_events_use_distinct_freshness_windows():
    policy = event(event_id="policy", scope="policy", published_at=NOW - timedelta(days=2))
    announcement = event(event_id="notice", scope="a_share", published_at=NOW - timedelta(days=6))
    assert filter_fresh_events([policy, announcement], now=NOW) == [policy, announcement]


def test_duplicate_reprints_keep_highest_quality_source():
    media = event(source_tier="media", source_name="媒体")
    official = event(source_tier="official")
    assert deduplicate_events([media, official]) == [official]


def test_ai_cloud_demand_maps_to_lotus_without_claiming_direct_supply():
    stock = StockContext("600186", "莲花控股", "食品", ("算力租赁",))
    result = analyze_stock_news_impact(
        stock,
        [event()],
        ProbabilityPaths(35, 45, 20),
        now=NOW,
        existing_holding=True,
    )
    assert result.score == 2.4
    assert result.impacts[0].transmission_type == "demand_validation"
    assert result.impacts[0].relevance == "medium"
    assert "直接供应" not in result.impacts[0].mapping_evidence


def test_fixed_stock_mapping_works_when_batch_fundamental_lacks_concepts():
    stock = StockContext("600186", "莲花控股")
    result = analyze_stock_news_impact(
        stock, [event()], ProbabilityPaths(35, 45, 20), now=NOW, existing_holding=True
    )
    assert result.score == 2.4


def test_event_mapped_stocks_are_code_name_pairs_without_duplicates():
    stocks = iter_event_mapped_stocks(event())

    lotus = next(item for item in stocks if item.code == "600186")
    assert lotus.name == "莲花控股"
    assert lotus.theme == "ai_cloud"
    assert "算力租赁" in lotus.sectors
    assert len({item.code for item in stocks}) == len(stocks)


def test_sector_only_mapping_does_not_invent_stock_candidates():
    memory_event = event(
        event_id="memory",
        title="SK海力士HBM需求增长",
        summary="存储芯片需求改善",
        subjects=("SK海力士",),
    )

    assert iter_event_mapped_stocks(memory_event) == ()


def test_rumor_does_not_change_score_or_probabilities():
    stock = StockContext("600186", "莲花控股", "食品", ("算力租赁",))
    result = analyze_stock_news_impact(
        stock,
        [event(source_tier="rumor", confirmation_state="unverified")],
        ProbabilityPaths(35, 45, 20),
        now=NOW,
        existing_holding=True,
    )
    assert result.score == 0
    assert result.probability.final == ProbabilityPaths(35, 45, 20)


def test_positive_score_adjusts_paths_and_preserves_total():
    stock = StockContext("600186", "莲花控股", "食品", ("算力租赁",))
    events = [event(event_id=f"event-{idx}", subjects=(subject,)) for idx, subject in enumerate(("CoreWeave", "Nebius", "Supermicro"))]
    result = analyze_stock_news_impact(stock, events, ProbabilityPaths(35, 45, 20), now=NOW, existing_holding=True)
    assert result.impacts[0].transmission_type == "peer_validation"
    assert result.impacts[0].base_score == 5
    assert result.probability.final.strong > 35
    assert sum(result.probability.final.as_tuple()) == 100


def test_policy_link_uses_macro_base_score_two():
    policy = event(
        event_id="policy-ai",
        title="发布AI数据中心产业政策",
        summary="支持算力基础设施建设",
        subjects=(),
        event_type="policy",
        scope="policy",
    )
    result = analyze_stock_news_impact(
        StockContext("600186", "莲花控股"), [policy], ProbabilityPaths(35, 45, 20),
        now=NOW, existing_holding=True,
    )
    assert result.impacts[0].transmission_type == "macro_policy"
    assert result.impacts[0].base_score == 2


def test_verified_material_negative_vetoes_new_risk_but_not_protective_exit():
    bad = event(
        event_id="regulatory",
        title="公司被立案调查",
        summary="监管机构正式立案调查",
        market="CN",
        country="CN",
        subjects=("莲花控股",),
        event_type="investigation",
        direction="negative",
        scope="a_share",
    )
    stock = StockContext("600186", "莲花控股", "食品", ("算力租赁",))
    new_risk = analyze_stock_news_impact(stock, [bad], ProbabilityPaths(20, 50, 30), now=NOW, existing_holding=False)
    holding = analyze_stock_news_impact(stock, [bad], ProbabilityPaths(20, 50, 30), now=NOW, existing_holding=True)
    assert new_risk.veto.new_risk_forbidden is True
    assert holding.veto.protective_exit_allowed is True


def test_no_events_disclose_overseas_coverage_gap_without_probability_change():
    result = analyze_stock_news_impact(
        StockContext("003816", "中国广核", "电力", ("核电",)),
        [],
        ProbabilityPaths(25, 50, 25),
        now=NOW,
        existing_holding=True,
    )
    assert "overseas_company" in result.missing_scopes
    assert result.probability.final == ProbabilityPaths(25, 50, 25)
