"""影视试跑定稿模板 tv_review_v2。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_tv_review_template import (
    load_golden_body_core,
    load_tv_review_template,
    template_prompt_block,
)


def test_load_template() -> None:
    tpl = load_tv_review_template()
    assert tpl["template_id"] == "tv_review_v2"
    assert len(tpl.get("sections") or []) == 5


def test_golden_body_core() -> None:
    body = load_golden_body_core()
    assert "> 连夜刷完10集，半夜却有点发虚" in body
    assert "分集速写" in body
    assert "[[fig:" not in body


def test_prompt_block_mentions_ratings_position() -> None:
    block = template_prompt_block()
    assert "第一节第一段正文之后" in block
    assert "分集速写" in block or "按集" in block or "小标题自拟" in block
