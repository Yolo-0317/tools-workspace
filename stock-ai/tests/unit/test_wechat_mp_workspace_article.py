"""工作区技术分享公众号稿。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_content import DRAFT_KINDS, build_workspace_article
from scripts.tools.wechat_mp_workspace_article import (
    PROJECT_NAME,
    SERIES_TAG,
    generate_workspace_overview_body,
)

from scripts.tools.wechat_mp_eval import BANNED_AI_PHRASES as _AI_PHRASES


def test_draft_kinds_include_workspace() -> None:
    assert "workspace" in DRAFT_KINDS


def test_overview_reads_more_natural() -> None:
    body = generate_workspace_overview_body()
    assert PROJECT_NAME in body
    assert "盘后坞" not in body
    assert "收盘台" not in body
    assert "tools-workspace" not in body
    assert "stock-ai" not in body
    assert "月" not in body.splitlines()[0]
    assert "> 它是什么" in body
    assert "> 公众号草稿" in body
    assert "> 里面分几块" in body
    assert "一、定位" not in body
    assert "我" not in body
    assert "clash" not in body.lower()
    for phrase in _AI_PHRASES:
        assert phrase not in body


def test_build_workspace_article_shell() -> None:
    art = build_workspace_article()
    assert art["title"]
    assert PROJECT_NAME in art["content"] or "git" in art["content"]
    assert "<blockquote" in art["content"]
