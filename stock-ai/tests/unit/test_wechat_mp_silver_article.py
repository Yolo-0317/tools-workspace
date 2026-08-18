from __future__ import annotations

import json

import pytest

from scripts.tools import wechat_mp_silver_article as article_mod
from scripts.tools.wechat_mp_codex_silver import load_codex_silver_draft_data
from scripts.tools.wechat_mp_silver_topics import SilverTopic


def _topic(lane: str = "relation") -> SilverTopic:
    return SilverTopic(
        topic_id=f"{lane}-test",
        lane=lane,
        title="退休后的日常安排",
        reader_problem="怎样把退休后的日子重新安排好？",
        search_terms=("退休生活", "日常安排"),
        scene_prompt="从早晨醒来不知道做什么的场景开篇",
        risk_notes=("不制造年龄焦虑",),
    )


def _payload(lane: str = "relation") -> dict[str, object]:
    authority = {
        "relation": "https://community.example/a",
        "health": "https://www.nhc.gov.cn/a",
        "money": "https://www.mps.gov.cn/a",
    }[lane]
    urls = [authority, "https://media.example/b", "https://research.example/c"]
    return {
        "title": "退休后，把一天安排得松一点",
        "digest": "从具体生活场景谈退休后的节奏。",
        "body": "退休后的生活安排，需要兼顾自己的节奏、家人的边界和每天的小目标。" * 75,
        "topic": "退休后的日常安排",
        "lane": lane,
        "research_urls": urls,
        "original_thesis": "退休后的充实感不来自把日程塞满，而来自稳定节奏和可以持续的小目标。",
        "reader_problem": "怎样把退休后的日子重新安排好？",
        "facts": [{"claim": "公开资料中的生活建议", "source_url": authority}],
        "practical_steps": ["先固定每天起床和吃饭的时间"],
        "cautions": ["每个人的身体和家庭情况不同"],
        "rejected_claims": [],
        "slot_key": "silver",
    }


def _research(lane: str) -> list[dict[str, str]]:
    urls = _payload(lane)["research_urls"]
    return [
        {"title": f"资料 {index}", "snippet": "公开资料摘要", "source": "公开来源", "url": url, "published": ""}
        for index, url in enumerate(urls)
    ]


def test_generate_silver_draft_returns_validated_json(monkeypatch) -> None:
    monkeypatch.setattr(article_mod, "resolve_silver_topic", lambda **_: _topic())
    monkeypatch.setattr(article_mod, "research_silver_topic", lambda _: _research("relation"))
    monkeypatch.setattr(
        article_mod,
        "call_wechat_mp_llm",
        lambda *_, **__: json.dumps(_payload(), ensure_ascii=False),
    )

    draft = article_mod.generate_silver_draft()

    assert draft.lane == "relation"
    assert draft.slot_key == "silver"


def test_generate_silver_draft_rejects_malformed_json(monkeypatch) -> None:
    monkeypatch.setattr(article_mod, "resolve_silver_topic", lambda **_: _topic())
    monkeypatch.setattr(article_mod, "research_silver_topic", lambda _: _research("relation"))
    monkeypatch.setattr(article_mod, "call_wechat_mp_llm", lambda *_, **__: "not json")

    with pytest.raises(RuntimeError, match="有效 JSON"):
        article_mod.generate_silver_draft()


def test_silver_prompt_starts_with_account_role_card(monkeypatch) -> None:
    captured: list[str] = []
    monkeypatch.setattr(article_mod, "resolve_silver_topic", lambda **_: _topic())
    monkeypatch.setattr(article_mod, "research_silver_topic", lambda _: _research("relation"))

    def fake_llm(messages, **_kwargs):
        captured.append(messages[-1]["content"])
        return json.dumps(_payload(), ensure_ascii=False)

    monkeypatch.setattr(article_mod, "call_wechat_mp_llm", fake_llm)
    article_mod.generate_silver_draft()

    prompt = captured[0]
    assert "## 账号角色卡（最先遵守）" in prompt
    assert prompt.index("## 账号角色卡（最先遵守）") < prompt.index("方向：")
    assert prompt.index("## 账号角色卡（最先遵守）") < prompt.index("写作要求：")


@pytest.mark.parametrize(
    ("lane", "required_rule"),
    [
        ("health", "不得诊断、解读个人检查结果或推荐药物、保健品和治疗方案"),
        ("money", "不得推荐金融产品、预测收益或提供个性化投资建议"),
    ],
)
def test_lane_prompt_contains_exact_safety_rule(
    lane: str, required_rule: str, monkeypatch
) -> None:
    captured: list[object] = []
    monkeypatch.setattr(article_mod, "resolve_silver_topic", lambda **_: _topic(lane))
    monkeypatch.setattr(article_mod, "research_silver_topic", lambda _: _research(lane))

    def fake_llm(messages, **kwargs):
        captured.extend(messages)
        return json.dumps(_payload(lane), ensure_ascii=False)

    monkeypatch.setattr(article_mod, "call_wechat_mp_llm", fake_llm)

    article_mod.generate_silver_draft(lane=lane)

    assert required_rule in str(captured)


def test_build_silver_article_keeps_natural_title_and_forwards_dry_render(
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []
    draft = load_codex_silver_draft_data(_payload())
    monkeypatch.setattr(article_mod, "generate_silver_draft", lambda **_: draft)

    def fake_shell(**kwargs):
        calls.append(kwargs)
        return {"title": kwargs["title"], "body_text": kwargs["body_text"]}

    monkeypatch.setattr(article_mod, "_article_shell", fake_shell)
    monkeypatch.setattr(article_mod, "attach_publish_hints", lambda article, *_, **__: article)
    monkeypatch.setattr(
        article_mod,
        "_prepare_silver_body_with_figures",
        lambda value: value.body,
    )

    article = article_mod.build_silver_article(upload_figures=False)

    assert article["title"] == "退休后，把一天安排得松一点"
    assert article["slot_key"] == "silver"
    assert article["silver_report"]["lane"] == "relation"
    assert calls[0]["upload_figures"] is False
    assert calls[0]["kind"] == "silver"


def _patch_public_figure_dependencies(monkeypatch, *, marker_count: int) -> None:
    monkeypatch.setattr(
        article_mod,
        "discussion_body_figure_target",
        lambda: 3,
        raising=False,
    )
    monkeypatch.setattr(
        article_mod,
        "prepare_hotspot_topic_images",
        lambda *_, **__: None,
        raising=False,
    )
    monkeypatch.setattr(
        article_mod,
        "inject_discussion_figures",
        lambda body, _topic, **_kwargs: body
        + "\n\n"
        + "\n\n".join(
            f"[[fig:discussion/冒充公检法安全账户诈骗/still-{index:02d}.jpg|cap=图源：公开报道]]"
            for index in range(1, marker_count + 1)
        ),
        raising=False,
    )
    monkeypatch.setattr(
        article_mod,
        "ensure_discussion_cover",
        lambda *_: None,
        raising=False,
    )
    monkeypatch.setattr(
        article_mod,
        "_article_shell",
        lambda **kwargs: {
            "title": kwargs["title"],
            "body_text": kwargs["body_text"],
        },
    )
    monkeypatch.setattr(
        article_mod,
        "attach_publish_hints",
        lambda article, *_, **__: article,
    )


def test_silver_injects_three_verified_discussion_images(monkeypatch) -> None:
    _patch_public_figure_dependencies(monkeypatch, marker_count=3)
    draft = load_codex_silver_draft_data(_payload())
    draft = draft.__class__(
        **{**draft.__dict__, "topic": "冒充公检法安全账户诈骗"}
    )

    article = article_mod.build_silver_article(
        codex_draft=draft,
        upload_figures=False,
    )

    assert article["body_text"].count("[[fig:") == 3
    assert article_mod.get_last_built_silver_topic()["cover_slug"] == (
        "冒充公检法安全账户诈骗"
    )


def test_silver_fails_closed_when_public_images_are_insufficient(monkeypatch) -> None:
    _patch_public_figure_dependencies(monkeypatch, marker_count=2)
    draft = load_codex_silver_draft_data(_payload())

    with pytest.raises(RuntimeError, match="银发正文配图不足 3 张"):
        article_mod.build_silver_article(codex_draft=draft, upload_figures=False)
