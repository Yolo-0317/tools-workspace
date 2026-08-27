from __future__ import annotations

from pathlib import Path

import pytest

from scripts.tools import wechat_mp_content as content
from scripts.tools import wechat_mp_literary_cache as cache
from scripts.tools.wechat_mp_literary import (
    LiteraryDraft,
    build_literary_article,
    load_literary_draft_data,
)


def _payload() -> dict:
    body = (
        "司马迁站在未写完的竹简前，他需要决定的不是是否受辱，而是这部书还能不能写完。"
        * 42
    )
    body += "\n\n[[hl:真正留下来的，不是一次忍耐，而是一部仍能被后来人检验的历史。]]"
    return {
        "title": "司马迁真正难的，不只是活下来",
        "digest": "从《史记》的写作选择，看一个人如何处理评价与目标。",
        "body": body,
        "topic": "典籍里的中国 史记",
        "research_urls": [
            "https://www.chnmuseum.cn/a",
            "https://tv.cctv.com/b",
            "https://www.nlc.cn/c",
        ],
        "original_thesis": "司马迁真正重要的选择，是让写作目标压过同时代人对个人尊严的评价。",
        "slot_key": "literary",
        "topic_slug": "dianji-shiji",
    }


def test_literary_draft_validates_manual_independent_kind() -> None:
    draft = load_literary_draft_data(_payload())

    assert isinstance(draft, LiteraryDraft)
    assert draft.slot_key == "literary"
    assert "literary" in content.DRAFT_KINDS
    assert "literary" not in content.DAILY_DRAFT_KINDS


def test_literary_draft_rejects_source_domain_reuse() -> None:
    payload = _payload()
    payload["research_urls"] = [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]

    with pytest.raises(ValueError, match="3 个不同来源域"):
        load_literary_draft_data(payload)


def test_build_literary_article_renders_highlight_without_raw_marker() -> None:
    article = build_literary_article(
        load_literary_draft_data(_payload()),
        upload_figures=False,
    )

    assert article["title"] == "司马迁真正难的，不只是活下来"
    assert "[[hl:" not in article["content"]
    assert "真正留下来的" in article["content"]
    assert 'style="color:#1a5276;font-weight:700;"' in article["content"]
    assert article["slot_key"] == "literary"


def test_literary_next_slot_is_preserved() -> None:
    payload = _payload()
    payload["slot_key"] = "literary_next"

    draft = load_literary_draft_data(payload)
    article = build_literary_article(draft, upload_figures=False)

    assert draft.slot_key == "literary_next"
    assert article["slot_key"] == "literary_next"


def test_literary_queue_slot_is_preserved() -> None:
    payload = _payload()
    payload["slot_key"] = "literary_queue"

    draft = load_literary_draft_data(payload)
    article = build_literary_article(draft, upload_figures=False)

    assert draft.slot_key == "literary_queue"
    assert article["slot_key"] == "literary_queue"


def test_literary_queue_2_slot_is_preserved() -> None:
    payload = _payload()
    payload["slot_key"] = "literary_queue_2"

    draft = load_literary_draft_data(payload)
    article = build_literary_article(draft, upload_figures=False)

    assert draft.slot_key == "literary_queue_2"
    assert article["slot_key"] == "literary_queue_2"


def test_literary_queue_3_slot_is_preserved() -> None:
    payload = _payload()
    payload["slot_key"] = "literary_queue_3"

    draft = load_literary_draft_data(payload)
    article = build_literary_article(draft, upload_figures=False)

    assert draft.slot_key == "literary_queue_3"
    assert article["slot_key"] == "literary_queue_3"


def test_literary_cache_is_separate_from_tv_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "literary")
    draft = load_literary_draft_data(_payload())

    path = cache.save_literary_body_cache(draft)
    loaded = cache.load_literary_body_cache("dianji-shiji")

    assert path.parent == tmp_path / "literary"
    assert loaded is not None
    assert loaded["slot_key"] == "literary"
    assert "body_core" in loaded
