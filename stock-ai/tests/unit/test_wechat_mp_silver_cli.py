from __future__ import annotations

import sys

import pytest

from scripts.tools import wechat_mp_content as content_mod
from scripts.tools import wechat_mp_draft as draft_cli
from scripts.tools import wechat_mp_draft_batch as batch_mod
from scripts.tools import wechat_mp_silver_article as silver_article_mod
from scripts.tools import wechat_mp_tv_cover as tv_cover_mod
from scripts.tools.wechat_mp_masthead import slogan_for_kind
from scripts.tools.wechat_mp_monetization import vertical_hints_for_kind
from scripts.tools.wechat_mp_public import information_notice_for_kind
from scripts.tools.wechat_mp_seo import DIGEST_SEO_CORE, recommended_hashtags
from scripts.tools.wechat_mp_short_drama import LONGFORM_KINDS
from scripts.tools.wechat_mp_traffic_checklist import run_traffic_checklist
from scripts.tools.wechat_mp_codex_silver import load_codex_silver_draft_data


def _valid_silver_draft():
    urls = [
        "https://community.example/a",
        "https://media.example/b",
        "https://research.example/c",
    ]
    return load_codex_silver_draft_data(
        {
            "title": "退休后，把一天安排得松一点",
            "digest": "从生活场景谈退休后的节奏。",
            "body": "退休后的生活安排，需要兼顾自己的节奏、家人的边界和每天的小目标。" * 75,
            "topic": "退休后的日常安排",
            "lane": "relation",
            "research_urls": urls,
            "original_thesis": "退休后的充实感不来自把日程塞满，而来自稳定节奏和可以持续的小目标。",
            "reader_problem": "怎样把退休后的日子重新安排好？",
            "facts": [{"claim": "生活节奏需要调整", "source_url": urls[0]}],
            "practical_steps": ["先固定每天的一件小事"],
            "cautions": ["个体情况不同"],
            "rejected_claims": [],
            "slot_key": "silver",
        }
    )


def test_silver_is_manual_only() -> None:
    assert "silver" in content_mod.DRAFT_KINDS
    assert "silver" not in content_mod.DAILY_DRAFT_KINDS
    assert all(
        "silver" not in tuple(config.get("kinds") or ())
        for config in batch_mod.SCHEDULE_BATCHES.values()
    )
    assert "silver" in LONGFORM_KINDS


def test_silver_presentation_maps_and_checklist() -> None:
    assert slogan_for_kind("silver") == "退休不是退场，把日子重新安排好"
    assert DIGEST_SEO_CORE["silver"] == ("退休生活", "中年生活")
    assert recommended_hashtags("silver")[:2] == ["退休生活", "中年生活"]
    assert {"夫妻", "睡眠", "养老金", "防骗"}.issubset(
        set(vertical_hints_for_kind("silver"))
    )
    assert "不替代医生诊断" in information_notice_for_kind("silver")

    body = (
        "早晨六点半醒来，退休后的时间忽然全归自己，反而不知道先做什么。\n\n"
        "> 先把一天放慢\n\n"
        + "退休生活需要稳定节奏，也需要给夫妻和子女留下边界。" * 35
        + "\n\n> 从一件小事开始\n\n"
        + "睡眠、饮食和运动不必一次全部改变，先从可以坚持的习惯开始。" * 30
        + "\n\n> 给变化留出时间\n\n"
        + "每个人的家庭安排不同，适合自己的节奏才有机会长期保持。" * 28
        + "\n\n你刚退休时最想先调整哪件小事？欢迎留言说说。"
    )
    report = run_traffic_checklist(
        title="退休后，把一天安排得松一点",
        digest="退休生活与中年生活：重新安排每天的节奏。",
        body=body,
        kind="silver",
    )
    by_id = {item.id: item for item in report.items}
    assert by_id["silver_natural_title"].passed
    assert by_id["sections"].passed
    assert by_id["read_length"].passed


def test_silver_flags_only_accept_single_silver() -> None:
    draft_cli._validate_topic_kinds(["silver"], "退休后怎样安排一天")
    draft_cli._validate_silver_lane_kinds(["silver"], "relation")
    with pytest.raises(ValueError, match="--silver-lane"):
        draft_cli._validate_silver_lane_kinds(["hot_business"], "relation")
    with pytest.raises(ValueError, match="--topic"):
        draft_cli._validate_topic_kinds(["hotspot"], "一个题目")


def test_silver_uses_independent_slot_and_forwards_lane(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_build_article(kind: str, **kwargs: object) -> dict[str, str]:
        captured.update(kwargs)
        return {"title": "标题", "digest": "摘要", "body_text": "正文", "content": "正文"}

    monkeypatch.setattr(draft_cli, "build_article", fake_build_article)
    draft_cli._build_for_kind(
        "silver",
        edition=None,
        market_title=None,
        variant=None,
        silver_lane="health",
        topic_hint="睡眠习惯",
        codex_draft=None,
        upload_figures=False,
    )

    assert draft_cli._resolve_draft_slot_key("silver", _valid_silver_draft()) == "silver"
    assert captured["silver_lane"] == "health"
    assert captured["upload_figures"] is False


def test_silver_uses_verified_discussion_cover(monkeypatch) -> None:
    topic = {
        "trend_title": "冒充公检法安全账户诈骗",
        "title_zh": "冒充公检法安全账户诈骗",
        "cover_slug": "冒充公检法安全账户诈骗",
    }
    monkeypatch.setattr(
        silver_article_mod,
        "get_last_built_silver_topic",
        lambda: topic,
    )
    monkeypatch.setattr(
        tv_cover_mod,
        "pick_discussion_draft_thumb",
        lambda value: ("thumb-silver", None) if value == topic else (None, {"errcode": -1}),
    )
    monkeypatch.setattr(
        draft_cli,
        "pick_thumb_for_draft_kind",
        lambda _kind: ("generic-thumb", None),
    )

    result = draft_cli._pick_cover_for_kind(
        kind="silver",
        cover_kind="hot_business",
    )

    assert result == ("discussion", "thumb-silver", None)


def test_manual_silver_dry_run_prints_report_without_upload(monkeypatch, capsys) -> None:
    draft_calls: list[object] = []

    def fake_build(kind: str, **kwargs: object) -> dict[str, object]:
        return {
            "title": "退休后，把一天安排得松一点",
            "digest": "退休生活与中年生活：重新安排日常节奏。",
            "body_text": "退休生活从每天的具体场景开始。" * 120,
            "content": "退休生活从每天的具体场景开始。" * 120,
            "silver_report": {
                "lane": "relation",
                "topic": "退休后的日常安排",
                "source_domains": 3,
                "fact_count": 2,
                "authority_source_count": 0,
            },
            "short_drama_skipped": {"reason": "没有合适的安全短剧"},
        }

    monkeypatch.setattr(draft_cli, "build_article", fake_build)
    monkeypatch.setattr(draft_cli, "assert_longform_promotion_safe", lambda *_, **__: None)
    monkeypatch.setattr(
        draft_cli, "upsert_draft_article", lambda *args, **kwargs: draft_calls.append((args, kwargs))
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["wechat_mp_draft", "--kind", "silver", "--silver-lane", "relation", "--dry-run"],
    )

    assert draft_cli.main() == 0
    output = capsys.readouterr().out
    assert "方向: relation" in output
    assert "来源域: 3" in output
    assert "事实条数: 2" in output
    assert "短剧推广: 已跳过" in output
    assert draft_calls == []
