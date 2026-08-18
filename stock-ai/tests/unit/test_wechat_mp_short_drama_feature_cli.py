"""单剧强情节推广稿的手动命令与独立槽位。"""

from __future__ import annotations

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.tools import wechat_mp_content as content_mod
from scripts.tools import wechat_mp_draft as draft_cli
from scripts.tools import wechat_mp_draft_batch as batch_mod
from scripts.tools import wechat_mp_short_drama_feature_article as feature_mod
from scripts.tools import wechat_mp_monetization as monetization
from scripts.tools import wechat_mp_seo as seo


def test_short_drama_feature_is_manual_only() -> None:
    assert "short_drama_feature" in content_mod.DRAFT_KINDS
    assert "short_drama_feature" not in content_mod.DAILY_DRAFT_KINDS
    assert draft_cli._resolve_kinds("all") == list(content_mod.DAILY_DRAFT_KINDS)
    assert all(
        "short_drama_feature" not in tuple(config.get("kinds") or ())
        for config in batch_mod.SCHEDULE_BATCHES.values()
    )


def test_short_drama_feature_uses_independent_slot_and_tv_cover() -> None:
    assert draft_cli._resolve_draft_slot_key("short_drama_feature", None) == "short_drama_feature"
    assert draft_cli._resolve_cover_kind("short_drama_feature") == "tv_review"


def test_short_drama_feature_picks_tv_review_cover(monkeypatch) -> None:
    from scripts.tools import wechat_mp_tv_cover, wechat_mp_tv_topics

    monkeypatch.setattr(
        wechat_mp_tv_topics,
        "pick_tv_topic",
        lambda: (_ for _ in ()).throw(AssertionError("不得使用无关影视话题")),
    )
    monkeypatch.setattr(
        wechat_mp_tv_cover,
        "pick_tv_review_thumb",
        lambda selected: (
            ("thumb-media-id", None)
            if selected == {
                "title_zh": "吹散枕边云照见负心人",
                "platform": "短剧推荐",
                "cover_slug": "short-drama-235776",
            }
            else (None, {"errmsg": "主题错误"})
        ),
    )
    monkeypatch.setattr(
        draft_cli,
        "pick_thumb_for_draft_kind",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("不得按财经封面查找")),
    )

    source, thumb, error = draft_cli._pick_cover_for_kind(
        kind="short_drama_feature",
        cover_kind="tv_review",
        article={
            "short_drama": {
                "drama_id": "235776",
                "drama_name": "吹散枕边云照见负心人",
            }
        },
    )

    assert (source, thumb, error) == ("tv_review", "thumb-media-id", None)


def test_content_routes_short_drama_feature_to_dedicated_builder(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_builder(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"title": "单剧推荐"}

    monkeypatch.setattr(feature_mod, "build_short_drama_feature_article", fake_builder)

    selected_draft = object()
    article = content_mod.build_article(
        "short_drama_feature",
        codex_draft=selected_draft,
        upload_figures=False,
    )

    assert article == {"title": "单剧推荐"}
    assert captured == {"codex_draft": selected_draft, "upload_figures": False}


def test_short_drama_feature_without_codex_draft_only_writes_request(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    request_path = tmp_path / "short_drama_feature_request.json"
    request = {
        "request_type": "short_drama_feature",
        "candidates": [{"drama_id": "1", "drama_name": "候选短剧"}],
    }
    monkeypatch.setattr(draft_cli, "SHORT_DRAMA_REQUEST_PATH", request_path)
    monkeypatch.setattr(feature_mod, "prepare_short_drama_feature_request", lambda: request)
    monkeypatch.setattr(
        draft_cli,
        "build_article",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("不应自动写稿")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["wechat_mp_draft", "--kind", "short_drama_feature", "--dry-run"],
    )

    assert draft_cli.main() == 0
    assert json.loads(request_path.read_text(encoding="utf-8")) == request
    output = capsys.readouterr().out
    assert "已生成 Codex 写稿请求" in output
    assert "候选短剧" in output


def test_short_drama_feature_has_conversion_specific_publish_metadata() -> None:
    digest = seo.enrich_digest("一个下岗技师接下机床难题。", "short_drama_feature")

    assert "短剧推荐" in digest
    assert seo.recommended_hashtags("short_drama_feature") == ["短剧", "短剧推荐", "追剧"]
    assert monetization.vertical_hints_for_kind("short_drama_feature") == (
        "短剧",
        "主角",
        "冲突",
        "反转",
        "继续看",
    )
    assert monetization.recommend_hook_applies_to_kind("short_drama_feature") is False
    body = monetization.append_engagement_hook("剧情停在第一次反转。", kind="short_drama_feature")
    assert "主角" in body
    assert body.endswith("？")


def test_short_drama_feature_dry_run_prints_safe_research_report(
    monkeypatch,
    capsys,
) -> None:
    draft_calls: list[object] = []
    selected_draft = object()

    def fake_build(kind: str, **kwargs: object) -> dict[str, object]:
        assert kind == "short_drama_feature"
        assert kwargs["upload_figures"] is False
        assert kwargs["codex_draft"] is selected_draft
        return {
            "title": "下岗技师进厂第一天，就接下没人敢碰的机床",
            "digest": "一台故障机床，把一个下岗技师逼到必须证明自己的位置。",
            "body_text": "李建军进入工厂。" * 150,
            "content": "李建军进入工厂。" * 150,
            "short_drama": {
                "drama_id": "1713873",
                "drama_name": "修好铁疙瘩转身踏青云",
                "era": "现代",
                "theme": "职场",
                "media_count": 60,
                "rate_bp": 6000,
                "hot_degree": 21052623,
                "score": {
                    "commission": 50.0,
                    "heat": 30.0,
                    "appeal": 10.0,
                    "penalty": 0.0,
                    "final": 90.0,
                },
            },
            "short_drama_feature_report": {
                "attempts": [
                    {
                        "drama_id": "1",
                        "drama_name": "资料不足的剧",
                        "status": "rejected",
                        "reason": "没有独立公开来源",
                    },
                    {
                        "drama_id": "1713873",
                        "drama_name": "修好铁疙瘩转身踏青云",
                        "status": "selected",
                        "reason": "",
                    },
                ],
                "sources": [
                    {
                        "url": "https://daihuo.qq.com/drama/1713873",
                        "source_type": "platform",
                        "official": True,
                    },
                    {
                        "url": "https://news.example.test/1713873",
                        "source_type": "report",
                        "official": False,
                    },
                ],
                "facts": [
                    {"fact_id": "conflict-1", "fact_type": "conflict", "claim": "机床发生故障。"}
                ],
                "body_chars": 1450,
                "fact_gate": "passed",
                "claim_audit": "passed",
            },
        }

    monkeypatch.setattr(draft_cli, "build_article", fake_build)
    monkeypatch.setattr(
        draft_cli,
        "load_codex_short_drama_draft",
        lambda _path: selected_draft,
    )
    monkeypatch.setattr(draft_cli, "assert_longform_promotion_safe", lambda *_a, **_k: None)
    monkeypatch.setattr(
        draft_cli,
        "upsert_draft_article",
        lambda *args, **kwargs: draft_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "wechat_mp_draft",
            "--kind",
            "short_drama_feature",
            "--codex-draft",
            "draft.json",
            "--dry-run",
        ],
    )

    assert draft_cli.main() == 0
    output = capsys.readouterr().out
    assert "=== short_drama_feature ===" in output
    assert "资料不足的剧: 已拒绝 · 没有独立公开来源" in output
    assert "来源: 2（官方 1）" in output
    assert "https://news.example.test/1713873" in output
    assert "剧情事实: 1" in output
    assert "正文去空白字符: 1450" in output
    assert "事实门禁: passed · 审计: passed" in output
    assert "短剧推广: 修好铁疙瘩转身踏青云" in output
    assert "wx_ticket" not in output.lower()
    assert "default_path" not in output.lower()
    assert "cookie" not in output.lower()
    assert "token" not in output.lower()
    assert draft_calls == []
