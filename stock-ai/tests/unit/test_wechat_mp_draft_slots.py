from __future__ import annotations

from scripts.tools import wechat_mp_draft_slots as slots
from scripts.tools import wechat_mp_product as product


def test_managed_slots_include_literary_next() -> None:
    assert "literary_next" in slots.managed_slot_keys()


def test_managed_slots_include_literary_queue() -> None:
    assert "literary_queue" in slots.managed_slot_keys()


def test_managed_slots_include_literary_queue_2() -> None:
    assert "literary_queue_2" in slots.managed_slot_keys()


def test_managed_slots_include_literary_queue_3() -> None:
    assert "literary_queue_3" in slots.managed_slot_keys()


def test_literary_upsert_does_not_delete_tv_review_slot(monkeypatch) -> None:
    deleted: list[str] = []
    saved: list[tuple[str, str]] = []
    monkeypatch.setattr(
        slots,
        "get_slot_media_id",
        lambda key: {"literary": "literary-old", "tv_review": "tv-old"}.get(key),
    )
    monkeypatch.setattr(slots, "draft_delete", lambda media_id: deleted.append(media_id))
    monkeypatch.setattr(slots, "draft_add", lambda articles: ("literary-new", None))
    monkeypatch.setattr(
        slots,
        "set_slot_media_id",
        lambda key, media_id, **kwargs: saved.append((key, media_id)),
    )
    monkeypatch.setattr(slots, "attach_cover_crop_fields", lambda *args, **kwargs: None)
    monkeypatch.setattr(product, "draft_article_payload", lambda article: dict(article))

    media_id, action, error = slots.upsert_draft_article(
        "literary",
        {"title": "文学稿", "content": "<p>正文</p>"},
        thumb_media_id="thumb",
        slot_key="literary",
    )

    assert (media_id, action, error) == ("literary-new", "recreated", None)
    assert deleted == ["literary-old"]
    assert saved == [("literary", "literary-new")]
