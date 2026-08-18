"""单剧推广稿的公开来源研究与剧情事实台账。"""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.tools import wechat_mp_short_drama as short_drama
from scripts.tools import wechat_mp_short_drama_research as research_mod


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def drama() -> short_drama.ShortDrama:
    return short_drama.ShortDrama(
        drama_id="1713873",
        drama_name="修好铁疙瘩转身踏青云",
        src_appid="wx-source",
        play_appid="wx-play",
        cover_url="https://example.test/cover.jpg",
        era="现代",
        theme="职场",
        description="下岗技师李建军进入工厂，用维修技术解决机床难题。",
        status=1,
        plan_id="plan-1713873",
        rate_bp=6000,
        hot_degree=21052623,
        media_count=60,
        offline_timestamp=1797992049,
        preview_path="plugin-private://player/pages/playlet?dramaId=1713873",
        preview_sn="preview",
        exp_url="https://daihuo.qq.com/cps_drama_expo?drama_id=1713873",
        click_url="",
        trace_id="trace",
        fetched_at=NOW.isoformat(),
    )


def valid_sources() -> tuple[research_mod.DramaSource, ...]:
    return (
        research_mod.DramaSource(
            source_id="platform",
            url="https://daihuo.qq.com/cps_drama_expo?drama_id=1713873",
            title="平台剧目资料",
            source_name="微信短剧推广平台",
            source_type="platform",
            official=True,
            excerpt="下岗技师李建军进入工厂，用维修技术解决机床难题。",
        ),
        research_mod.DramaSource(
            source_id="source-1",
            url="https://news.example.test/drama-1713873",
            title="短剧剧情介绍",
            source_name="测试媒体",
            source_type="report",
            official=False,
            excerpt="李建军下岗后进入工厂，靠维修机床证明自己的技术。",
        ),
    )


def valid_facts() -> tuple[research_mod.DramaFact, ...]:
    source_ids = ("platform", "source-1")
    return (
        research_mod.DramaFact("character-1", "character", "主角名叫李建军。", source_ids),
        research_mod.DramaFact("relationship-1", "relationship", "李建军进入一家工厂工作。", source_ids),
        research_mod.DramaFact("conflict-1", "conflict", "工厂机床故障成为他的技术考验。", source_ids),
        research_mod.DramaFact("reversal-1", "reversal", "他的维修能力改变了同事对他的判断。", source_ids),
    )


def valid_research() -> research_mod.DramaResearch:
    return research_mod.DramaResearch(
        drama_id="1713873",
        drama_name="修好铁疙瘩转身踏青云",
        sources=valid_sources(),
        facts=valid_facts(),
        rejected_claims=("李建军最终获得某项国家奖项",),
    )


def test_validate_drama_research_requires_two_sources_for_every_public_fact() -> None:
    item = valid_research()
    bad_fact = replace(item.facts[2], source_ids=("platform",))

    with pytest.raises(ValueError, match="至少需要两个来源"):
        research_mod.validate_drama_research(
            replace(item, facts=(*item.facts[:2], bad_fact, item.facts[3]))
        )


def test_validate_drama_research_requires_platform_and_independent_source() -> None:
    item = valid_research()
    extra_source = replace(
        item.sources[1],
        source_id="source-2",
        url="https://other.example.test/drama-1713873",
    )
    bad_fact = replace(item.facts[2], source_ids=("source-1", "source-2"))

    with pytest.raises(ValueError, match="平台来源和独立来源"):
        research_mod.validate_drama_research(
            replace(
                item,
                sources=(*item.sources, extra_source),
                facts=(*item.facts[:2], bad_fact, item.facts[3]),
            )
        )


def test_validate_drama_research_rejects_unknown_source_id() -> None:
    item = valid_research()
    bad_fact = replace(item.facts[0], source_ids=("platform", "missing"))

    with pytest.raises(ValueError, match="未登记来源"):
        research_mod.validate_drama_research(
            replace(item, facts=(bad_fact, *item.facts[1:]))
        )


def test_validate_drama_research_requires_all_core_fact_types() -> None:
    item = valid_research()

    with pytest.raises(ValueError, match="缺少人物、关系、冲突或反转"):
        research_mod.validate_drama_research(replace(item, facts=item.facts[:-1]))


def test_platform_source_is_built_from_current_promotion_pool() -> None:
    source = research_mod.platform_source_for_drama(drama())

    assert source.source_id == "platform"
    assert source.official is True
    assert source.url == drama().exp_url
