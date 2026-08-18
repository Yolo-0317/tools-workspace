"""公众号品牌头。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_masthead import (
    KIND_SLOGANS,
    masthead_html,
    resolve_banner_path,
    slogan_for_kind,
)


def test_masthead_contains_banner_and_slogan_panel() -> None:
    html = masthead_html("market", upload_images=False, local_preview=True)
    assert resolve_banner_path().name in html
    assert all(ch in html for ch in "牛马也智能")
    assert slogan_for_kind("market") in html
    assert "text-align:center" in html
    assert "border-radius:10px" in html
    assert "#061528" in html
    assert "#00e5ff" in html
    assert "margin:0 0 14px" in html
    assert "line-height:0" in html


def test_masthead_kind_slogans() -> None:
    market = masthead_html("market", upload_images=False, local_preview=True)
    news = masthead_html("news", upload_images=False, local_preview=True)
    assert slogan_for_kind("market") in market
    assert slogan_for_kind("news") in news
    assert slogan_for_kind("market") != slogan_for_kind("news")


def test_masthead_slogan_box_style() -> None:
    html = masthead_html("sector", upload_images=False, local_preview=True)
    assert "#0b2340" in html
    assert "#e8f4fc" in html
    assert "#7dd3fc" in html


def test_all_kinds_have_slogan() -> None:
    for kind in ("market", "news", "sector", "hotspot", "workspace", "temp"):
        assert kind in KIND_SLOGANS
    for kind in ("market", "news", "sector", "workspace", "temp"):
        assert masthead_html(kind, upload_images=False, local_preview=True)


def test_masthead_uses_banner_cache_when_upload_disabled(monkeypatch, tmp_path) -> None:
    from scripts.tools import wechat_mp_masthead as mh

    banner = tmp_path / "banner.png"
    banner.write_bytes(b"test-banner-bytes")
    cache_key = mh.banner_cache_key(banner)
    cache_file = tmp_path / "upload_cache.json"
    cache_file.write_text(
        json.dumps({"urls": {cache_key: "https://mmbiz.qpic.cn/test/banner"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(mh, "DEFAULT_BANNER_PATH", banner)
    monkeypatch.setattr(mh, "UPLOAD_CACHE_PATH", cache_file)
    html = masthead_html("market", upload_images=False, local_preview=False)
    assert "https://mmbiz.qpic.cn/test/banner" in html
    assert "<img " in html
