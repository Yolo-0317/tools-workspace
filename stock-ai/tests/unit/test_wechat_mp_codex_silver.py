from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.tools.wechat_mp_codex_silver import (
    SILVER_SLOT_KEY,
    CodexSilverDraft,
    SilverFact,
    load_codex_silver_draft,
    load_codex_silver_draft_data,
    validate_silver_draft,
)


def _body() -> str:
    return "退休后的生活安排，需要兼顾自己的节奏、家人的边界和每天的小目标。" * 75


def _payload(*, lane: str = "relation") -> dict[str, object]:
    urls = [
        "https://community.example/a",
        "https://media.example/b",
        "https://research.example/c",
    ]
    return {
        "title": "退休后，夫妻相处最怕把关心变成管束",
        "digest": "从三个生活场景谈退休后的边界感。",
        "body": _body(),
        "topic": "退休后的夫妻边界",
        "lane": lane,
        "research_urls": urls,
        "original_thesis": "退休后的家庭矛盾往往不是感情变差，而是全天相处后生活边界需要重新协商。",
        "reader_problem": "退休后夫妻全天相处，怎样减少摩擦？",
        "facts": [{"claim": "退休会改变家庭成员的时间分配", "source_url": urls[0]}],
        "practical_steps": ["先约定各自独处的时间", "每周安排一次共同活动"],
        "cautions": ["个体情况不同，不把建议当成统一答案"],
        "rejected_claims": ["退休夫妻都会感情变差"],
        "slot_key": "silver",
    }


def _draft() -> CodexSilverDraft:
    return load_codex_silver_draft_data(_payload())


def test_silver_draft_exposes_discussion_topic() -> None:
    draft = replace(_draft(), topic="冒充公检法安全账户诈骗")

    topic = draft.as_discussion_topic()

    assert topic == {
        "trend_title": "冒充公检法安全账户诈骗",
        "title_zh": "冒充公检法安全账户诈骗",
        "cover_slug": "冒充公检法安全账户诈骗",
        "from_trend": False,
        "research_urls": list(draft.research_urls),
    }


def test_load_silver_draft_requires_structured_evidence(tmp_path: Path) -> None:
    source = tmp_path / "silver.json"
    source.write_text(json.dumps(_payload(), ensure_ascii=False), encoding="utf-8")

    draft = load_codex_silver_draft(source)

    assert draft.lane == "relation"
    assert draft.slot_key == SILVER_SLOT_KEY
    assert draft.facts == (
        SilverFact("退休会改变家庭成员的时间分配", "https://community.example/a"),
    )


def test_rejects_unknown_lane() -> None:
    data = _payload()
    data["lane"] = "travel"

    with pytest.raises(ValueError, match="lane"):
        load_codex_silver_draft_data(data)


@pytest.mark.parametrize("body", ["太短" * 100, "太长" * 1500])
def test_requires_body_between_1600_and_2600_non_whitespace_chars(body: str) -> None:
    with pytest.raises(ValueError, match="1600.*2600"):
        validate_silver_draft(replace(_draft(), body=body))


def test_requires_three_distinct_source_domains() -> None:
    data = _payload()
    data["research_urls"] = [
        "https://same.example/a",
        "https://same.example/b",
        "https://other.example/c",
    ]
    data["facts"] = [{"claim": "可核验事实", "source_url": "https://same.example/a"}]

    with pytest.raises(ValueError, match="3 个不同来源域"):
        load_codex_silver_draft_data(data)


def test_rejects_fact_url_outside_research_urls() -> None:
    broken = replace(
        _draft(), facts=(SilverFact("未经映射的说法", "https://other.example/x"),)
    )

    with pytest.raises(ValueError, match="facts.*research_urls"):
        validate_silver_draft(broken)


def test_rejects_rejected_claim_reintroduced_into_public_copy() -> None:
    draft = _draft()
    broken = replace(draft, body=draft.body + "退休夫妻都会感情变差")

    with pytest.raises(ValueError, match="rejected_claims"):
        validate_silver_draft(broken)


@pytest.mark.parametrize(
    "title", ["银发栏目：相处之道", "五十岁以后｜重新安排生活", "人生下半场｜学会独处"]
)
def test_rejects_fixed_column_prefixes(title: str) -> None:
    with pytest.raises(ValueError, match="固定栏目名"):
        validate_silver_draft(replace(_draft(), title=title))


def test_health_lane_requires_authoritative_health_source() -> None:
    data = _payload(lane="health")

    with pytest.raises(ValueError, match="权威健康来源"):
        load_codex_silver_draft_data(data)


def test_health_lane_accepts_authority_but_rejects_treatment_advice() -> None:
    data = _payload(lane="health")
    data["research_urls"] = [
        "https://www.nhc.gov.cn/a",
        "https://hospital.example/b",
        "https://media.example/c",
    ]
    data["facts"] = [{"claim": "健康生活方式资料", "source_url": "https://www.nhc.gov.cn/a"}]
    draft = load_codex_silver_draft_data(data)

    with pytest.raises(ValueError, match="诊断、用药或治疗建议"):
        validate_silver_draft(replace(draft, body=draft.body + "建议服用某种保健品。"))


def test_money_lane_requires_authority_and_rejects_return_promises() -> None:
    data = _payload(lane="money")
    with pytest.raises(ValueError, match="权威政务或监管来源"):
        load_codex_silver_draft_data(data)

    data["research_urls"] = [
        "https://www.mps.gov.cn/a",
        "https://bank.example/b",
        "https://media.example/c",
    ]
    data["facts"] = [{"claim": "公开反诈提醒", "source_url": "https://www.mps.gov.cn/a"}]
    draft = load_codex_silver_draft_data(data)

    with pytest.raises(ValueError, match="收益承诺或产品推荐"):
        validate_silver_draft(replace(draft, digest="这款理财保证收益，适合退休家庭。"))
