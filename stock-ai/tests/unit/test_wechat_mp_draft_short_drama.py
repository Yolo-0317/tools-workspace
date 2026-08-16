"""公众号长文推稿的短剧写入前后门禁。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.tools import wechat_mp_draft as draft


def test_main_blocks_plain_product_before_cover_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["wechat_mp_draft", "--kind", "market"])
    monkeypatch.setattr(draft, "mp_configured", lambda: True)
    monkeypatch.setattr(
        draft,
        "_build_for_kind",
        lambda *args, **kwargs: {
            "title": "测试长文",
            "digest": "测试摘要",
            "body_text": "正文",
            "content": '<mp-common-cpsad data-pid="101_1"></mp-common-cpsad>',
        },
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_public.check_public_compliance",
        lambda *args, **kwargs: [],
    )
    cover_calls: list[str] = []

    def fake_cover(*, kind: str, cover_kind: str):
        cover_calls.append(kind)
        return cover_kind, "thumb", None

    monkeypatch.setattr(draft, "_resolve_cover_kind", lambda kind: kind)
    monkeypatch.setattr(draft, "_pick_cover_for_kind", fake_cover)
    monkeypatch.setattr(draft, "get_material_image_meta", lambda _: ({}, None))
    monkeypatch.setattr(
        draft,
        "upsert_draft_article",
        lambda *args, **kwargs: ("media", "created", None),
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_prune_drafts.prune_obsolete_drafts",
        lambda **kwargs: 0,
    )

    exit_code = draft.main()

    assert exit_code == 1
    assert cover_calls == []


def test_main_verifies_saved_short_drama_before_recording_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["wechat_mp_draft", "--kind", "market"])
    monkeypatch.setenv("WECHAT_MP_SHORT_DRAMA", "1")
    monkeypatch.setattr(draft, "mp_configured", lambda: True)
    article = {
        "title": "测试长文",
        "digest": "测试摘要",
        "body_text": "正文",
        "content": '<mp-common-cpsad data-adtype="short-play"></mp-common-cpsad>',
        "short_drama": {
            "drama_id": "123",
            "drama_name": "报销风波",
            "era": "现代",
            "theme": "职场",
            "media_count": 60,
            "rate_bp": 6000,
            "plan_id": "plan-123",
        },
    }
    monkeypatch.setattr(draft, "_build_for_kind", lambda *args, **kwargs: article)
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_public.check_public_compliance",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(draft, "_resolve_cover_kind", lambda kind: kind)
    monkeypatch.setattr(
        draft,
        "_pick_cover_for_kind",
        lambda **kwargs: ("market", "thumb", None),
    )
    monkeypatch.setattr(draft, "get_material_image_meta", lambda _: ({}, None))
    monkeypatch.setattr(
        draft,
        "upsert_draft_article",
        lambda *args, **kwargs: ("media-123", "created", None),
    )
    events: list[tuple[str, str]] = []
    monkeypatch.setattr(
        draft,
        "verify_saved_short_drama",
        lambda **kwargs: events.append(("verified", kwargs["expected_drama_id"])),
    )
    monkeypatch.setattr(
        draft,
        "record_drama_usage",
        lambda drama, **kwargs: events.append(("recorded", drama["drama_id"])),
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_prune_drafts.prune_obsolete_drafts",
        lambda **kwargs: 0,
    )

    exit_code = draft.main()

    assert exit_code == 0
    assert events == [("verified", "123"), ("recorded", "123")]
