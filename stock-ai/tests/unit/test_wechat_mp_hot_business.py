from __future__ import annotations

import pytest

from scripts.tools import wechat_mp_hot_business as mod
from scripts.tools.wechat_mp_hot_business import (
    HotBusinessAssessment,
    pick_hot_business_topic,
)
from scripts.tools.wechat_mp_hotspot_article import HotspotTopic


def _topic(title: str, score: float = 800.0) -> HotspotTopic:
    return HotspotTopic(
        item={"title": title, "summary": title, "attention_score": score},
        bucket="other",
        score=score,
        section_title=title,
    )


def _researched(item: dict[str, object]) -> dict[str, object]:
    out = dict(item)
    out["web_research"] = [
        {"url": "https://brand.example/a", "title": "官方", "source": "品牌"},
        {"url": "https://media.example/b", "title": "媒体", "source": "媒体"},
        {"url": "https://industry.example/c", "title": "行业", "source": "行业"},
    ]
    return out


def _assessment(
    index: int, *, heat: int, business: int, verifiability: int, relevance: int
) -> HotBusinessAssessment:
    return HotBusinessAssessment(
        index=index,
        heat=heat,
        business_space=business,
        verifiability=verifiability,
        reader_relevance=relevance,
        reason="测试评分",
    )


def test_pick_hot_business_topic_uses_highest_qualified_score(monkeypatch) -> None:
    candidates = [_topic("品牌涨价"), _topic("明星恋情")]
    monkeypatch.setattr(mod, "pick_hotspot_candidates", lambda items=None: candidates)
    monkeypatch.setattr(mod, "attach_hotspot_research", _researched)
    monkeypatch.setattr(
        mod,
        "_request_assessments",
        lambda rows: [
            _assessment(0, heat=35, business=28, verifiability=20, relevance=9),
            _assessment(1, heat=40, business=4, verifiability=10, relevance=4),
        ],
    )

    picked = pick_hot_business_topic()

    assert picked.topic.item["title"] == "品牌涨价"
    assert picked.assessment is not None
    assert picked.assessment.total == 92


def test_no_candidate_at_70_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(mod, "pick_hotspot_candidates", lambda items=None: [_topic("普通话题")])
    monkeypatch.setattr(mod, "attach_hotspot_research", _researched)
    monkeypatch.setattr(
        mod,
        "_request_assessments",
        lambda rows: [
            _assessment(0, heat=30, business=10, verifiability=10, relevance=5)
        ],
    )

    with pytest.raises(RuntimeError, match="没有达到 70 分"):
        pick_hot_business_topic()


def test_manual_topic_skips_scoring_but_keeps_research_gate(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "_request_assessments",
        lambda rows: (_ for _ in ()).throw(AssertionError("不应自动评分")),
    )
    monkeypatch.setattr(mod, "attach_hotspot_research", _researched)

    picked = pick_hot_business_topic(topic_hint="某平台会员涨价")

    assert picked.topic.item["title"] == "某平台会员涨价"
    assert len(picked.research_urls) == 3
    assert picked.assessment is None


def test_manual_topic_still_requires_three_domains(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "attach_hotspot_research",
        lambda item: {**item, "web_research": [{"url": "https://one.example/a"}]},
    )

    with pytest.raises(RuntimeError, match="3 个不同来源域"):
        pick_hot_business_topic(topic_hint="某平台会员涨价")
