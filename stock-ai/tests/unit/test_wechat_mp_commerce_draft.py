"""带货公众号草稿构建。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_commerce_draft import (
    COMMERCE_DISCLAIMER,
    _LEGACY_BODY_DISCLOSURE,
    build_commerce_article,
    commerce_auto_publish_enabled,
    sanitize_commerce_mp_text,
)
from scripts.tools.wechat_mp_product import inject_cpsad_before_disclaimer


def test_disclosure_only_in_digest_not_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT", "0")
    monkeypatch.setenv("WECHAT_MP_MONETIZE", "0")
    art = build_commerce_article(
        title="小厨房台面不够用？收纳顺序可以参考",
        digest="窄台面先理顺调料和线缆。",
        body_md="窄台面为什么先谈收纳\n\n先腾切菜位。",
        vertical="home",
    )
    body = str(art.get("body_text") or "")
    digest = str(art.get("digest") or "")
    assert _LEGACY_BODY_DISCLOSURE not in body
    assert "合作推广" in digest
    assert COMMERCE_DISCLAIMER.split("。")[0] in body


def test_build_commerce_article_has_disclaimer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT", "0")
    monkeypatch.setenv("WECHAT_MP_MONETIZE", "0")
    art = build_commerce_article(
        title="宿舍桌面三件套？键鼠屏这样搭",
        digest="含推广链接的数码清单。",
        body_md="> 为什么现在值得看\n\n租房桌面只有 80cm。",
        vertical="tech",
    )
    body = str(art.get("body_text") or "")
    assert COMMERCE_DISCLAIMER.split("。")[0] in body
    assert "推广" in str(art.get("digest") or "") or "推广" in body


def test_sanitize_commerce_drops_hype_line() -> None:
    raw = "全网最低价的神器\n\n正常段落。"
    out = sanitize_commerce_mp_text(raw)
    assert "全网最低" not in out
    assert "正常段落" in out


def test_inject_cpsad_before_commerce_disclaimer() -> None:
    html = f'<p style="text-align:center">小结</p><p>正文</p><p>{COMMERCE_DISCLAIMER}</p>'
    out = inject_cpsad_before_disclaimer(html, "101_12345")
    assert "mp-common-cpsad" in out
    assert out.index("mp-common-cpsad") < out.index("本文为个人体验")


def test_build_commerce_cps_not_inside_disclaimer_paragraph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT", "1")
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT_AUTO_PICK", "0")
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT_ID", "10170176108918")
    monkeypatch.setenv("WECHAT_MP_MONETIZE", "0")
    monkeypatch.setenv("WECHAT_MP_COMMERCE_MASTHEAD", "0")
    art = build_commerce_article(
        title="测试标题？好物清单",
        digest="含推广合作说明。",
        body_md="> 小结\n\n按需购买。",
        vertical="home",
    )
    html = str(art.get("content") or "")
    if "mp-common-cpsad" not in html:
        return
    disc_idx = html.find("本文为个人体验")
    cps_idx = html.find("mp-common-cpsad")
    assert cps_idx < disc_idx
    assert "**" not in html


def test_commerce_auto_publish_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WECHAT_MP_COMMERCE_AUTO_PUBLISH", raising=False)
    assert commerce_auto_publish_enabled() is False
    monkeypatch.setenv("WECHAT_MP_COMMERCE_AUTO_PUBLISH", "1")
    assert commerce_auto_publish_enabled() is True
    assert commerce_auto_publish_enabled(cli_publish=False) is False
    assert commerce_auto_publish_enabled(cli_publish=True) is True


def test_attach_footer_product_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT", "1")
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT_AUTO_PICK", "0")
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT_ID", "")
    monkeypatch.setenv("WECHAT_MP_MONETIZE", "0")
    monkeypatch.delenv("WECHAT_MP_DAIHUO_UIN", raising=False)
    art = build_commerce_article(
        title="测试标题？好物清单",
        digest="含推广合作说明。",
        body_md="> 小结\n\n按需购买。",
        vertical="tech",
    )
    # 无 uin / 无 product_id 时不强制 CPS
    assert art.get("title")
