"""Codex 成稿 JSON → 公众号热点长图文。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.tools.wechat_mp_codex_hotspot import (
    CodexHotspotDraft,
    load_codex_hotspot_draft,
)


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _valid_hotspot_body() -> str:
    paragraphs = []
    for index in range(1, 7):
        sentence = (
            f"第{index}组公开信息记录于2026年8月10日，相关人员、机构和处理流程都有明确时间线。"
            "报道分别交代了事件发生、回应发布、规则适用和后续核查的先后顺序，"
            "读者可以据此区分已经确认的事实、当事人说法和仍待调查的部分。"
        )
        paragraphs.append(sentence * 4)
    return "\n\n".join(paragraphs)


def test_load_codex_hotspot_draft_reads_valid_json(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path / "draft.json",
        {
            "title": "一件具体事件为什么引发争议？",
            "digest": "这篇文章梳理事件、规则与争议焦点。",
            "body": "第一段正文。\n\n第二段正文。",
            "topic": "具体事件",
            "research_urls": ["https://example.com/report"],
            "original_thesis": "规则真正要解决的，是把本可提前阻止的成本留在开业之前。",
            "slot_key": "hotspot_afternoon",
        },
    )

    draft = load_codex_hotspot_draft(path)

    assert draft.title == "一件具体事件为什么引发争议？"
    assert draft.topic == "具体事件"
    assert draft.research_urls == ("https://example.com/report",)
    assert draft.slot_key == "hotspot_afternoon"
    assert draft.original_thesis == "规则真正要解决的，是把本可提前阻止的成本留在开业之前。"
    assert draft.as_discussion_topic() == {
        "title_zh": "具体事件",
        "trend_title": "具体事件",
        "cover_slug": "具体事件",
        "from_trend": True,
        "research_urls": ["https://example.com/report"],
    }


def test_validate_codex_hotspot_originality_rejects_missing_source_diversity() -> None:
    from scripts.tools.wechat_mp_codex_hotspot import validate_codex_hotspot_originality

    draft = CodexHotspotDraft(
        title="一件具体事件为什么引发争议？",
        digest="这篇文章梳理事件、规则与争议焦点。",
        body=_valid_hotspot_body(),
        topic="具体事件",
        research_urls=("https://example.com/one", "https://example.com/two"),
        original_thesis="真正的问题是成本为何被推给最后一个知道风险的普通人。",
    )

    with pytest.raises(ValueError, match="sources_too_few"):
        validate_codex_hotspot_originality(draft, history_posts=[])


@pytest.mark.parametrize("field", ["title", "digest", "body", "topic"])
def test_load_codex_hotspot_draft_rejects_missing_required_field(
    tmp_path: Path,
    field: str,
) -> None:
    payload = {
        "title": "标题",
        "digest": "摘要",
        "body": "正文",
        "topic": "事件",
    }
    payload.pop(field)
    path = _write_json(tmp_path / "draft.json", payload)

    with pytest.raises(ValueError, match=field):
        load_codex_hotspot_draft(path)


def test_load_codex_hotspot_draft_rejects_non_string_source_url(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path / "draft.json",
        {
            "title": "标题",
            "digest": "摘要",
            "body": "正文",
            "topic": "事件",
            "research_urls": ["https://example.com/report", 42],
        },
    )

    with pytest.raises(ValueError, match="research_urls"):
        load_codex_hotspot_draft(path)


def test_build_hotspot_article_uses_codex_body_without_generator(monkeypatch) -> None:
    from scripts.tools import wechat_mp_content as content_mod
    from scripts.tools import wechat_mp_hotspot_article as hotspot_mod

    draft = CodexHotspotDraft(
        title="具体事件为什么引发争议？",
        digest="这篇文章梳理事件、规则与争议焦点。",
        body=_valid_hotspot_body(),
        topic="具体事件",
        original_thesis="真正的问题是规则执行为何总让普通人承担最后的成本。",
    )

    def fail_if_generated(**_kwargs):
        pytest.fail("Codex 输入不应调用热点生成器")

    monkeypatch.setattr(hotspot_mod, "generate_hotspot_body", fail_if_generated)
    monkeypatch.setattr(hotspot_mod, "hotspot_social_layout_enabled", lambda: False)

    article = content_mod.build_hotspot_article(codex_draft=draft)

    assert article["title"] == draft.title
    assert "第1组公开信息记录于2026年8月10日" in article["body_text"]


def test_build_hotspot_article_uses_verified_images_without_filling_to_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    import types

    news_ai_stub = types.ModuleType("scripts.tools.news_ai_interpret")
    news_ai_stub.sanitize_public_ai_summary = lambda text: text  # type: ignore[attr-defined]
    portfolio_stub = types.ModuleType("scripts.tools.portfolio_db")
    portfolio_stub.load_emotion_cycle_checklist = lambda: {}  # type: ignore[attr-defined]
    news_db_stub = types.ModuleType("scripts.tools.news_db")
    news_db_stub.pick_top_news_by_attention = lambda **_kwargs: []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "scripts.tools.news_ai_interpret", news_ai_stub)
    monkeypatch.setitem(sys.modules, "scripts.tools.portfolio_db", portfolio_stub)
    monkeypatch.setitem(sys.modules, "scripts.tools.news_db", news_db_stub)

    from scripts.tools import wechat_mp_codex_images as images_mod
    from scripts.tools import wechat_mp_content as content_mod
    from scripts.tools import wechat_mp_discussion_figures as figures_mod
    from scripts.tools import wechat_mp_hotspot_article as hotspot_mod

    draft = CodexHotspotDraft(
        title="具体事件为什么引发争议？",
        digest="这篇文章梳理事件、规则与争议焦点。",
        body=_valid_hotspot_body(),
        topic="具体事件",
    )
    monkeypatch.setattr(hotspot_mod, "hotspot_social_layout_enabled", lambda: True)
    monkeypatch.setattr(figures_mod, "INLINE_DISCUSSION_ROOT", tmp_path)
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_seo.attach_publish_hints",
        lambda article, *_args, **_kwargs: article,
    )
    calls: dict[str, object] = {}
    cover_source = tmp_path / "topic" / "douyin-cover.jpg"
    body_source = tmp_path / "topic" / "official-01.jpg"
    body_source.parent.mkdir(parents=True)
    from PIL import Image

    Image.effect_noise((800, 600), 80).convert("RGB").save(body_source)

    def prepare(_topic, *, body_count, image_policy):
        from scripts.tools.wechat_mp_hotspot_image_policy import (
            VerifiedFigure,
            VerifiedHotspotImages,
        )

        calls["image_policy"] = image_policy
        return VerifiedHotspotImages(
            cover_source=cover_source,
            body_figures=(
                VerifiedFigure(
                    path=body_source,
                    rel="discussion/topic/official-01.jpg",
                    caption="图源：官方媒体",
                    page_url="https://example.gov.cn/report",
                    source_name="官方媒体",
                    source_type="official_report",
                ),
            ),
            source_meta={},
        )

    def inject(body, _topic, *, figures):
        calls["figures"] = figures
        return body + "\n\n[[fig:discussion/topic/official-01.jpg|cap=图源：官方媒体]]"

    def cover(_topic, *, source_path, allow_fetch):
        calls["cover_source"] = source_path
        calls["allow_fetch"] = allow_fetch
        return tmp_path / "cover.jpg"

    monkeypatch.setattr(images_mod, "prepare_hotspot_topic_images", prepare)
    monkeypatch.setattr(figures_mod, "inject_discussion_figures", inject)
    monkeypatch.setattr(figures_mod, "ensure_discussion_cover", cover)

    article = content_mod.build_hotspot_article(
        codex_draft=draft,
        upload_figures=False,
    )

    assert article["body_text"].count("[[fig:") == 1
    assert calls == {
        "image_policy": "verified_only",
        "figures": [
            {
                "rel": "discussion/topic/official-01.jpg",
                "cap": "图源：官方媒体",
            }
        ],
        "cover_source": cover_source,
        "allow_fetch": False,
    }


def test_validate_codex_hotspot_body_rejects_short_body() -> None:
    from scripts.tools.wechat_mp_hotspot_article import validate_codex_hotspot_body

    with pytest.raises(ValueError, match="字数"):
        validate_codex_hotspot_body("2026年发生了一件事。", topic="具体事件")


@pytest.mark.parametrize("kinds", [["news"], ["hotspot", "news"]])
def test_validate_codex_draft_kinds_requires_single_hotspot(
    kinds: list[str],
    tmp_path: Path,
) -> None:
    from scripts.tools import wechat_mp_draft as draft_cli

    with pytest.raises(ValueError, match="单篇 hotspot"):
        draft_cli._validate_codex_draft_kinds(kinds, tmp_path / "draft.json")


def test_direct_hotspot_codex_draft_requires_browser_workflow(tmp_path: Path) -> None:
    from scripts.tools import wechat_mp_draft as draft_cli

    with pytest.raises(ValueError, match="wechat_mp_browser_write"):
        draft_cli._validate_codex_draft_kinds(["hotspot"], tmp_path / "draft.json")


def test_resolve_codex_slot_key_prefers_environment(monkeypatch) -> None:
    from scripts.tools import wechat_mp_draft as draft_cli

    draft = CodexHotspotDraft(
        title="标题",
        digest="摘要",
        body="正文",
        topic="事件",
        slot_key="hotspot_afternoon",
    )
    monkeypatch.setenv("WECHAT_MP_HOTSPOT_SLOT_KEY", "hotspot_evening")

    assert draft_cli._resolve_codex_slot_key(draft) == "hotspot_evening"


def test_build_for_kind_forwards_codex_draft_to_hotspot(monkeypatch) -> None:
    from scripts.tools import wechat_mp_draft as draft_cli

    draft = CodexHotspotDraft(
        title="标题",
        digest="摘要",
        body="正文",
        topic="事件",
    )

    def fake_build_article(kind: str, **kwargs):
        return {"kind": kind, "codex_draft": kwargs.get("codex_draft")}

    monkeypatch.setattr(draft_cli, "build_article", fake_build_article)

    result = draft_cli._build_for_kind(
        "hotspot",
        edition="close",
        market_title=None,
        variant=None,
        codex_draft=draft,
    )

    assert result == {"kind": "hotspot", "codex_draft": draft}


def test_pick_cover_for_hotspot_uses_built_event_cover(monkeypatch) -> None:
    from scripts.tools import wechat_mp_draft as draft_cli
    from scripts.tools import wechat_mp_hotspot_article as hotspot_mod
    from scripts.tools import wechat_mp_tv_cover as cover_mod

    topic = {"title_zh": "具体事件", "cover_slug": "具体事件"}
    monkeypatch.setattr(hotspot_mod, "hotspot_social_layout_enabled", lambda: True)
    monkeypatch.setattr(hotspot_mod, "get_last_built_hotspot_topic", lambda: topic)
    monkeypatch.setattr(
        cover_mod,
        "pick_discussion_draft_thumb",
        lambda built_topic: ("event-thumb", None) if built_topic is topic else (None, {}),
    )

    cover_kind, thumb, error = draft_cli._pick_cover_for_kind(
        kind="hotspot",
        cover_kind="sector",
    )

    assert (cover_kind, thumb, error) == ("discussion", "event-thumb", None)


def test_main_invalid_codex_kind_reports_plain_error(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    from scripts.tools import wechat_mp_draft as draft_cli

    monkeypatch.setattr(
        "sys.argv",
        [
            "wechat_mp_draft",
            "--kind",
            "news",
            "--codex-draft",
            str(tmp_path / "draft.json"),
            "--dry-run",
        ],
    )

    assert draft_cli.main() == 1
    error = capsys.readouterr().err
    assert "错误: --codex-draft 仅允许与单篇 hotspot 一起使用" in error
    assert "❌" not in error


def test_main_direct_hotspot_json_reports_browser_workflow_error(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    from scripts.tools import wechat_mp_draft as draft_cli

    path = _write_json(
        tmp_path / "draft.json",
        {
            "title": "标题",
            "digest": "摘要",
            "body": "2026年短正文。",
            "topic": "具体事件",
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "wechat_mp_draft",
            "--kind",
            "hotspot",
            "--codex-draft",
            str(path),
            "--dry-run",
        ],
    )

    assert draft_cli.main() == 1
    error = capsys.readouterr().err
    assert "错误: 用户主动热点必须使用 scripts.tools.wechat_mp_browser_write" in error
    assert "❌" not in error


def test_main_direct_hotspot_json_is_rejected_before_mp_credentials(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    from scripts.tools import wechat_mp_draft as draft_cli

    path = _write_json(
        tmp_path / "draft.json",
        {
            "title": "标题",
            "digest": "摘要",
            "body": "正文",
            "topic": "具体事件",
        },
    )
    monkeypatch.setattr(draft_cli, "mp_configured", lambda: False)
    monkeypatch.setattr(
        "sys.argv",
        [
            "wechat_mp_draft",
            "--kind",
            "hotspot",
            "--codex-draft",
            str(path),
        ],
    )

    assert draft_cli.main() == 1
    error = capsys.readouterr().err
    assert "错误: 用户主动热点必须使用 scripts.tools.wechat_mp_browser_write" in error
    assert "❌" not in error
