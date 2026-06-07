"""阅读原文 content_source_url 开关。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_content import _source_url, content_source_url_enabled
from scripts.tools.wechat_mp_product import draft_article_payload


def test_source_url_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("WECHAT_MP_READ_SOURCE_URL", raising=False)
    monkeypatch.setenv("WECHAT_MP_SOURCE_URL", "https://hub.yoloworld.site:8883/news")
    assert not content_source_url_enabled()
    assert _source_url() == ""


def test_source_url_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_MP_READ_SOURCE_URL", "1")
    monkeypatch.setenv("WECHAT_MP_SOURCE_URL", "https://hub.yoloworld.site:8883/news")
    assert content_source_url_enabled()
    assert _source_url().startswith("https://")


def test_draft_payload_strips_source_url_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_MP_READ_SOURCE_URL", "0")
    item = draft_article_payload(
        {
            "title": "t",
            "content": "<p>x</p>",
            "content_source_url": "https://hub.yoloworld.site:8883/news",
        }
    )
    assert "content_source_url" not in item
