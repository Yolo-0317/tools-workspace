from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.news_impact import NewsEvent, ProbabilityPaths, StockContext, analyze_stock_news_impact
from stock_ai.news_impact.formatting import format_stock_impact_card
from stock_ai.news_impact.providers import normalize_news_record


TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 8, 12, 9, 0, tzinfo=TZ)


def test_news_record_normalization_marks_premarket_overseas_event():
    event = normalize_news_record(
        {
            "href": "https://example.com/coreweave",
            "title": "美股盘前CoreWeave涨超15%",
            "summary": "公司上调资本开支",
            "published_at": NOW.replace(tzinfo=None),
            "source": "eastmoney",
        },
        observed_at=NOW,
    )
    assert event is not None
    assert event.scope == "overseas"
    assert event.confirmation_state == "premarket"
    assert event.subjects == ("CoreWeave",)


def test_unparseable_record_is_not_used_as_positive_event():
    event = normalize_news_record(
        {"href": "x", "title": "算力利好", "summary": "", "published_at": None, "source": "转载"},
        observed_at=NOW,
    )
    assert event is None


def test_standard_cache_row_is_not_reparsed_as_generic_macro_news():
    event = normalize_news_record(
        {
            "href": "https://example.com#news-impact-evt",
            "title": "CoreWeave财报",
            "summary": "NEWS_IMPACT_JSON:{}",
            "published_at": NOW.replace(tzinfo=None),
            "source": "news-impact-json",
        },
        observed_at=NOW,
    )
    assert event is None


def test_stock_card_shows_probability_audit_and_coverage_gap_without_emoji():
    result = analyze_stock_news_impact(
        StockContext("600186", "莲花控股", "食品", ("算力租赁",)),
        [],
        ProbabilityPaths(35, 45, 20),
        now=NOW,
        existing_holding=True,
    )
    card = format_stock_impact_card(result)
    assert "基础概率：强35% / 中45% / 弱20%" in card
    assert "最终概率：强35% / 中45% / 弱20%" in card
    assert "海外公司新闻覆盖不足" in card
    assert "🚀" not in card


def test_stock_card_limits_visible_events_to_three():
    events = []
    for index, subject in enumerate(("CoreWeave", "Nebius", "Supermicro", "CoreWeave")):
        events.append(
            NewsEvent(
                event_id=f"event-{index}",
                title=f"{subject}算力需求增长{index}",
                summary="AI云资本开支增长",
                published_at=NOW - timedelta(hours=1),
                observed_at=NOW,
                source_url=f"https://example.com/{index}",
                source_name="公司官网",
                source_tier="official",
                market="US",
                country="US",
                subjects=(subject,),
                event_type="capex",
                direction="positive",
                confirmation_state="official",
                scope="overseas",
            )
        )
    result = analyze_stock_news_impact(
        StockContext("600186", "莲花控股", "食品", ("算力租赁",)),
        events,
        ProbabilityPaths(35, 45, 20),
        now=NOW,
        existing_holding=True,
    )
    card = format_stock_impact_card(result)
    assert card.count("来源：公司官网") == 3
    assert "另有1条相关消息已合并" in card
    assert "medium相关" not in card
    assert "中等相关" in card
    assert "有效期：24小时" in card
    assert "失效条件：" in card
