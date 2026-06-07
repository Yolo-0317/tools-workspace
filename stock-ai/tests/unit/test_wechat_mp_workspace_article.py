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
    assert "text-align:center" in art["content"]
    assert "个人工程笔记" in art["body_text"]
    assert "不构成投资建议" not in art["body_text"]


def test_english_buddy_workspace_variant() -> None:
    from scripts.tools.wechat_mp_english_buddy_article import (
        generate_english_buddy_article_body,
    )

    body = generate_english_buddy_article_body()
    assert "在家里的 Mac" in body
    assert "> 整体长什么样" in body
    assert "同一 git" not in body
    assert "FastAPI + Vue" not in body
    assert "> 和会员 App 差在哪" in body
    assert "> 课文从哪来" in body
    assert "> 发音三色怎么评" in body
    assert "收盘自动化" not in body
    assert "SideStore" not in body
    assert "Home Hub" not in body
    assert "17:30" not in body
    assert "MySQL" not in body
    assert len(body) >= 1800
    assert "tools-workspace" not in body
    assert "stock-ai" not in body
    assert "yueyue" not in body
    assert "不是教培产品" not in body
    assert "ENGLISH_BUDDY" not in body
    assert "WHISPER_WORKERS" not in body
    assert "start_call" not in body
    assert "[[fig:english-buddy-home.jpg|max-h=480;fit=contain]]" in body
    assert "[[fig:english-buddy-readalong.jpg|max-h=520;fit=contain]]" in body
    assert "```" in body
    for phrase in _AI_PHRASES:
        assert phrase not in body

    art = build_workspace_article(variant="english_buddy")
    assert "会员" in art["title"]
    assert "收盘自动化" not in art["body_text"]
    assert "max-height:480px" in art["content"]
    assert "max-height:520px" in art["content"]
    assert "object-fit:contain" in art["content"]
    assert "Whisper" in art["body_text"] or "whisper" in art["body_text"].lower()
    assert "<pre" in art["content"]
    assert art["recommended_hashtags"] == [
        "本地AI",
        "家庭自动化",
        "给娃省事",
        "英语跟读",
        "亲子英语",
    ]
