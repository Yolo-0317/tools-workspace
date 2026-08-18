from __future__ import annotations

import json

import pytest

from scripts.tools import wechat_mp_hot_business_article as article_mod
from scripts.tools import wechat_mp_hotspot_body_cache as cache_mod
from scripts.tools.wechat_mp_codex_hot_business import (
    CodexHotBusinessDraft,
    load_codex_hot_business_draft_data,
)
from scripts.tools.wechat_mp_hot_business import (
    HotBusinessAssessment,
    SelectedHotBusinessTopic,
)
from scripts.tools.wechat_mp_hotspot_article import HotspotTopic


def _valid_payload() -> dict[str, object]:
    urls = [
        "https://brand.example/a",
        "https://media.example/b",
        "https://industry.example/c",
    ]
    return {
        "title": "某品牌涨价，成本由谁承担？",
        "digest": "从渠道和成本解释这次涨价。",
        "body": "正文" * 1000,
        "topic": "某品牌涨价",
        "research_urls": urls,
        "original_thesis": "这次涨价的关键不是标价变化，而是渠道成本重新分配。",
        "business_question": "这次涨价的成本由谁承担？",
        "facts": [{"claim": "品牌公告调整价格", "source_url": urls[0]}],
        "inferences": ["渠道利润可能重新分配"],
        "rejected_claims": [],
        "slot_key": "hot_business",
    }


def _valid_draft() -> CodexHotBusinessDraft:
    return load_codex_hot_business_draft_data(_valid_payload())


def _selected_topic() -> SelectedHotBusinessTopic:
    urls = tuple(_valid_payload()["research_urls"])
    item = {
        "title": "某品牌涨价",
        "web_research": [
            {"url": url, "title": url, "snippet": "公开资料"} for url in urls
        ],
    }
    return SelectedHotBusinessTopic(
        topic=HotspotTopic(
            item=item,
            bucket="other",
            score=800.0,
            section_title="某品牌涨价",
        ),
        assessment=HotBusinessAssessment(0, 35, 28, 20, 9, "商业问题明确"),
        research_urls=urls,
    )


def test_generate_hot_business_draft_returns_validated_json(monkeypatch) -> None:
    monkeypatch.setattr(article_mod, "pick_hot_business_topic", lambda **_: _selected_topic())
    monkeypatch.setattr(
        article_mod,
        "call_wechat_mp_llm",
        lambda *_, **__: json.dumps(_valid_payload(), ensure_ascii=False),
    )

    draft = article_mod.generate_hot_business_draft()

    assert draft.slot_key == "hot_business"
    assert draft.business_question == "这次涨价的成本由谁承担？"


def test_generate_hot_business_prompt_contains_completion_rules(monkeypatch) -> None:
    captured: list[str] = []
    monkeypatch.setattr(article_mod, "pick_hot_business_topic", lambda **_: _selected_topic())

    def fake_llm(messages, **_kwargs):
        captured.append(messages[-1]["content"])
        return json.dumps(_valid_payload(), ensure_ascii=False)

    monkeypatch.setattr(article_mod, "call_wechat_mp_llm", fake_llm)
    article_mod.generate_hot_business_draft()

    prompt = captured[0]
    assert "前 80 字" in prompt
    assert "前 300 字" in prompt
    assert "每 300 至 500 字" in prompt
    assert "至少两个可转述" in prompt
    assert "## 账号角色卡（最先遵守）" in prompt
    assert prompt.index("## 账号角色卡（最先遵守）") < prompt.index("热点：")
    assert prompt.index("## 账号角色卡（最先遵守）") < prompt.index("文章必须围绕")


def test_generate_hot_business_draft_rejects_malformed_json(monkeypatch) -> None:
    monkeypatch.setattr(article_mod, "pick_hot_business_topic", lambda **_: _selected_topic())
    monkeypatch.setattr(article_mod, "call_wechat_mp_llm", lambda *_, **__: "not json")

    with pytest.raises(RuntimeError, match="有效 JSON"):
        article_mod.generate_hot_business_draft()


def test_hot_business_cache_does_not_write_hotspot_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cache_mod, "HOTSPOT_CACHE_DIR", tmp_path / "hotspot")
    monkeypatch.setattr(cache_mod, "HOT_BUSINESS_CACHE_DIR", tmp_path / "hot-business")
    cache_mod.save_hotspot_body_cache(
        {"title_zh": "某品牌涨价", "cover_slug": "brand-price"},
        body_core="正文",
        title="标题",
        digest="摘要",
        slot_key="hot_business",
        cache_kind="hot_business",
    )

    assert list((tmp_path / "hot-business").glob("*.json"))
    assert not (tmp_path / "hotspot").exists()


def test_build_hot_business_article_uses_shared_hot_business_render(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_builder(**kwargs):
        calls.append(kwargs)
        return {"title": "标题"}

    monkeypatch.setattr(article_mod, "generate_hot_business_draft", lambda **_: _valid_draft())
    monkeypatch.setattr(article_mod, "build_hotspot_article", fake_builder)

    article = article_mod.build_hot_business_article(upload_figures=False)

    assert calls[0]["article_kind"] == "hot_business"
    assert calls[0]["upload_figures"] is False
    assert article["slot_key"] == "hot_business"
    assert article["hot_business_report"]["source_domains"] == 3
