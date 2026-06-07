"""技术稿：禁止 Agent/槽位运维话术出现在成稿与品牌头。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_content import build_temp_article
from scripts.tools.wechat_mp_masthead import KIND_SLOGANS, masthead_html
from scripts.tools.wechat_mp_public import sanitize_tech_mp_meta

_BANNED = ("临稿栏", "不碰日更", "日更五槽", "给 Agent 用", "链接给用户")


def test_temp_masthead_slogan_is_reader_facing() -> None:
    assert "临稿" not in KIND_SLOGANS["temp"]
    assert "五槽" not in KIND_SLOGANS["temp"]
    html = masthead_html("temp", upload_images=False)
    for word in _BANNED:
        assert word not in html


def test_lark_cli_article_no_agent_ops_wording() -> None:
    art = build_temp_article(variant="lark_cli")
    blob = art["body_text"] + art["content"]
    for word in _BANNED:
        assert word not in blob
    assert "在 Cursor 里怎么配" in art["body_text"]


def test_sanitize_tech_mp_meta_strips_ops_line() -> None:
    raw = "给 Agent 用：后台跑命令，把链接给用户点完。\n\n正常段落。"
    out = sanitize_tech_mp_meta(raw)
    assert "给 Agent 用" not in out
    assert "链接给用户" not in out
    assert "正常段落" in out
