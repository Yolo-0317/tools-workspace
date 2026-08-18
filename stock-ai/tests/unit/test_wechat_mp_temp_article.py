"""临时稿槽 temp：变体注册与 build_article。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_content import DAILY_DRAFT_KINDS, DRAFT_KINDS, build_temp_article
from scripts.tools.wechat_mp_temp_article import (
    generate_temp_article_body,
    list_temp_variants,
    resolve_temp_variant,
)


def test_draft_kinds_include_temp_not_in_daily() -> None:
    assert "temp" in DRAFT_KINDS
    assert "temp" not in DAILY_DRAFT_KINDS
    assert DAILY_DRAFT_KINDS == ("hotspot", "sector", "news", "workspace")


def test_lark_cli_variant_registered() -> None:
    assert "lark_cli" in list_temp_variants()
    assert resolve_temp_variant("lark_cli") == "lark_cli"


def test_world_cup_variant_registered() -> None:
    assert "world_cup" in list_temp_variants()
    assert resolve_temp_variant("world_cup") == "world_cup"


def test_lark_cli_body_has_sections_and_no_git_brand() -> None:
    body = generate_temp_article_body(variant="lark_cli")
    assert "> 为什么值得多一层" in body
    assert "tools-workspace" not in body
    assert "lark-cli" in body


def test_build_temp_article_shell() -> None:
    art = build_temp_article(variant="lark_cli")
    assert art["title"]
    assert art["digest"]
    assert "content" in art
    assert len(art["title"]) <= 32


def test_temp_uses_engineering_disclaimer_not_investment() -> None:
    from scripts.tools.wechat_mp_content import TECH_DISCLAIMER, disclaimer_for_kind

    assert disclaimer_for_kind("temp") == TECH_DISCLAIMER
    art = build_temp_article(variant="lark_cli")
    assert "个人工程笔记" in art["body_text"]
    assert "不构成投资建议" not in art["body_text"]
    assert "市场有风险" not in art["body_text"]
