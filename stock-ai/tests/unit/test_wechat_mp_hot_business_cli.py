from __future__ import annotations

import sys

import pytest

from scripts.tools import wechat_mp_content as content_mod
from scripts.tools import wechat_mp_draft as draft_cli
from scripts.tools import wechat_mp_draft_batch as batch_mod
from scripts.tools import wechat_mp_hotspot_article as hotspot_mod
from scripts.tools import wechat_mp_tv_cover as cover_mod
from scripts.tools.wechat_mp_codex_hot_business import (
    load_codex_hot_business_draft_data,
)


def _valid_business_draft():
    return load_codex_hot_business_draft_data(
        {
            "title": "某品牌涨价，成本由谁承担？",
            "digest": "从渠道和成本解释这次涨价。",
            "body": "正文" * 1000,
            "topic": "某品牌涨价",
            "research_urls": [
                "https://brand.example/a",
                "https://media.example/b",
                "https://industry.example/c",
            ],
            "original_thesis": "这次涨价的关键不是标价变化，而是渠道成本重新分配。",
            "business_question": "这次涨价的成本由谁承担？",
            "facts": [
                {
                    "claim": "品牌公告调整价格",
                    "source_url": "https://brand.example/a",
                }
            ],
            "inferences": ["渠道利润可能重新分配"],
            "rejected_claims": [],
            "slot_key": "hot_business",
        }
    )


def test_hot_business_is_manual_only() -> None:
    assert "hot_business" in content_mod.DRAFT_KINDS
    assert "hot_business" not in content_mod.DAILY_DRAFT_KINDS
    assert all(
        "hot_business" not in tuple(config.get("kinds") or ())
        for config in batch_mod.SCHEDULE_BATCHES.values()
    )


def test_topic_flag_only_accepts_single_hot_business() -> None:
    draft_cli._validate_topic_kinds(["hot_business"], "品牌涨价")
    with pytest.raises(ValueError, match="--topic"):
        draft_cli._validate_topic_kinds(["hotspot"], "品牌涨价")


def test_hot_business_uses_independent_slot() -> None:
    assert (
        draft_cli._resolve_draft_slot_key("hot_business", _valid_business_draft())
        == "hot_business"
    )


def test_hot_business_dry_run_disables_figure_upload(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_build_article(kind: str, **kwargs: object) -> dict[str, str]:
        captured.update(kwargs)
        return {"title": "标题", "digest": "摘要", "body_text": "正文", "content": "正文"}

    monkeypatch.setattr(draft_cli, "build_article", fake_build_article)
    draft_cli._build_for_kind(
        "hot_business",
        edition=None,
        market_title=None,
        variant=None,
        topic_hint="品牌涨价",
        codex_draft=None,
        upload_figures=False,
    )
    assert captured["upload_figures"] is False
    assert captured["topic_hint"] == "品牌涨价"


def test_hot_business_cover_reuses_discussion_cover(monkeypatch) -> None:
    topic = {"title_zh": "品牌涨价", "cover_slug": "brand-price"}
    monkeypatch.setattr(hotspot_mod, "get_last_built_hotspot_topic", lambda: topic)
    monkeypatch.setattr(hotspot_mod, "hotspot_social_layout_enabled", lambda: True)
    monkeypatch.setattr(
        cover_mod, "pick_discussion_draft_thumb", lambda _: ("thumb", None)
    )

    cover_kind, thumb, error = draft_cli._pick_cover_for_kind(
        kind="hot_business", cover_kind="hotspot"
    )

    assert (cover_kind, thumb, error) == ("discussion", "thumb", None)


def test_manual_hot_business_dry_run_prints_quality_report_without_upload(
    monkeypatch, capsys
) -> None:
    build_calls: list[dict[str, object]] = []
    wechat_draft_calls: list[object] = []

    def fake_build(kind: str, **kwargs: object) -> dict[str, object]:
        build_calls.append({"kind": kind, **kwargs})
        return {
            "title": "某平台会员涨价，成本由谁承担？",
            "digest": "热点商业与商业观察：从渠道和成本解释会员涨价。",
            "body_text": "某平台在8月宣布会员价格调整。" * 80,
            "content": "某平台在8月宣布会员价格调整。" * 80,
            "hot_business_report": {
                "candidate_score": None,
                "source_domains": 3,
                "fact_count": 4,
                "inference_count": 2,
            },
            "short_drama_skipped": {
                "reason": "没有通过题材安全门禁的短剧",
            },
        }

    monkeypatch.setattr(draft_cli, "build_article", fake_build)
    monkeypatch.setattr(draft_cli, "assert_longform_promotion_safe", lambda *_, **__: None)
    monkeypatch.setattr(
        draft_cli,
        "upsert_draft_article",
        lambda *args, **kwargs: wechat_draft_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "wechat_mp_draft",
            "--kind",
            "hot_business",
            "--topic",
            "某平台会员涨价",
            "--dry-run",
        ],
    )

    assert draft_cli.main() == 0
    output = capsys.readouterr().out
    assert output.count("=== hot_business ===") == 1
    assert "候选评分" in output
    assert "来源域: 3" in output
    assert "短剧推广: 已跳过" in output
    assert "没有通过题材安全门禁的短剧" in output
    assert build_calls[0]["upload_figures"] is False
    assert wechat_draft_calls == []
