"""简选小电版式：正文 #话题、免责高亮。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_commerce_draft import build_commerce_article
from scripts.tools.wechat_mp_rich_html import commerce_hashtag_html, disclaimer_html
from scripts.tools.wechat_mp_seo import insert_hashtags_after_intro


def test_commerce_disclaimer_centered_highlight() -> None:
    html = disclaimer_html("本文为个人体验与信息整理，部分链接含推广合作。", kind="commerce")
    assert "text-align:center" in html
    assert "#fffaf5" in html
    assert "#c0392b" not in html


def test_commerce_hashtag_html_centered() -> None:
    html = commerce_hashtag_html(["租房好物", "小家电"])
    assert "#租房好物" in html
    assert "text-align:center" in html


def test_insert_hashtags_after_intro() -> None:
    body = "开篇一段。\n\n> 窄台面为什么先谈收纳\n\n正文。"
    out = insert_hashtags_after_intro(body, ["租房好物", "小家电"])
    assert out.index("开篇") < out.index("#租房好物") < out.index("窄台面")


def test_build_commerce_hashtags_in_body_and_styled_disclaimer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT", "0")
    monkeypatch.setenv("WECHAT_MP_MONETIZE", "0")
    monkeypatch.setenv("WECHAT_MP_COMMERCE_MASTHEAD", "0")
    monkeypatch.setenv("WECHAT_MP_COMMERCE_SEO", "1")
    art = build_commerce_article(
        title="合租单间厨房小电怎么选",
        digest="对照。（文内有合作推广）",
        body_md="> 窄台面为什么先谈收纳\n\n先腾切菜位。",
        vertical="home",
        slot="guide",
    )
    html = str(art.get("content") or "")
    body = str(art.get("body_text") or "")
    assert "#租房好物" in body or "#小家电" in body
    assert "#租房好物" in html
    assert "#fffaf5" in html
    assert "本文为个人体验" in html
