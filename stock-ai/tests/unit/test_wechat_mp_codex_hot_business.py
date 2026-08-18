from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.tools.wechat_mp_codex_hot_business import (
    CodexHotBusinessDraft,
    HotBusinessFact,
    distinct_source_domain_count,
    load_codex_hot_business_draft,
    load_codex_hot_business_draft_data,
    validate_hot_business_draft,
)


def _payload() -> dict[str, object]:
    urls = [
        "https://brand.example/a",
        "https://media.example/b",
        "https://industry.example/c",
    ]
    return {
        "title": "某品牌降价，成本由谁承担？",
        "digest": "从渠道和供应链解释这次降价。",
        "body": "这是正文内容。" * 400,
        "topic": "某品牌降价",
        "research_urls": urls,
        "original_thesis": "这次降价更像渠道重分配，而不是一次简单的品牌让利行为。",
        "business_question": "降价成本由谁承担？",
        "facts": [{"claim": "官方宣布降价", "source_url": urls[0]}],
        "inferences": ["渠道可能承担一部分成本"],
        "rejected_claims": ["销量已是全国第一"],
        "slot_key": "hot_business",
    }


def _draft() -> CodexHotBusinessDraft:
    return load_codex_hot_business_draft_data(_payload())


def test_load_hot_business_draft_requires_traceable_facts(tmp_path: Path) -> None:
    source = tmp_path / "draft.json"
    source.write_text(json.dumps(_payload(), ensure_ascii=False), encoding="utf-8")

    draft = load_codex_hot_business_draft(source)

    assert draft.facts == (
        HotBusinessFact("官方宣布降价", "https://brand.example/a"),
    )
    assert draft.slot_key == "hot_business"


def test_rejects_fact_url_outside_research_urls() -> None:
    broken = replace(
        _draft(),
        facts=(HotBusinessFact("未经映射的数字", "https://other.example/x"),),
    )

    with pytest.raises(ValueError, match="facts.*research_urls"):
        validate_hot_business_draft(broken)


def test_rejects_rejected_claim_reintroduced_into_body() -> None:
    draft = _draft()
    broken = replace(draft, body=draft.body + "销量已是全国第一")

    with pytest.raises(ValueError, match="rejected_claims"):
        validate_hot_business_draft(broken)


def test_rejects_body_shorter_than_1920_non_whitespace_chars() -> None:
    broken = replace(_draft(), body="短正文 " * 300)

    with pytest.raises(ValueError, match="1920"):
        validate_hot_business_draft(broken)


def test_requires_three_distinct_source_domains() -> None:
    data = _payload()
    data["research_urls"] = [
        "https://same.example/a",
        "https://same.example/b",
        "https://other.example/c",
    ]
    data["facts"] = [
        {"claim": "官方宣布降价", "source_url": "https://same.example/a"}
    ]

    with pytest.raises(ValueError, match="3 个不同来源域"):
        load_codex_hot_business_draft_data(data)


def test_distinct_source_domain_count_normalizes_www() -> None:
    assert distinct_source_domain_count(
        ["https://www.example.com/a", "https://example.com/b", "https://other.com/c"]
    ) == 2
