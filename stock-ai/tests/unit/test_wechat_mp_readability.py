"""公众号正文可读性：段长与序号列表。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.tools.wechat_mp_readability import (
    polish_mobile_readability,
    reflow_inline_numbered_lists,
    split_long_paragraphs,
)


def test_reflow_inline_numbered_one_per_line() -> None:
    raw = "要点如下：1. 锐科激光（300747） 2. 新安股份（002258） 3. 巨化股份（600160）"
    out = reflow_inline_numbered_lists(raw)
    assert "1. 锐科激光" in out
    assert "2. 新安股份" in out
    assert out.count("\n") >= 2


def test_split_long_paragraph_at_period() -> None:
    para = "。".join(["这是测试句"] * 30)
    out = split_long_paragraphs(para, max_chars=80)
    assert out.count("\n\n") >= 1
    for block in out.split("\n\n"):
        if block.strip():
            assert len(block.strip()) <= 120


def test_skip_blockquote_and_figure() -> None:
    raw = "> 筛选名单\n[[fig: inline-p01.jpg]]\n1. A 2. B"
    out = reflow_inline_numbered_lists(raw)
    assert "> 筛选名单" in out
    assert "[[fig:" in out
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    assert any(ln.startswith("1. A") for ln in lines)
    assert any(ln.startswith("2. B") for ln in lines)


def test_split_top5_fields_on_one_line() -> None:
    raw = "逻辑归属：同属主线；量价结构：换手放大；技术位置：均线多头"
    out = reflow_inline_numbered_lists(raw)
    assert "逻辑归属" in out
    assert "量价结构" in out
    assert out.count("\n") >= 2


def test_polish_mobile_readability_combined() -> None:
    raw = "1. 甲 2. 乙。" + "长句。" * 40
    out = polish_mobile_readability(raw, max_chars=60)
    assert "1. 甲" in out
    assert "2. 乙" in out
