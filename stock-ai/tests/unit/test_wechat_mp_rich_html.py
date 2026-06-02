"""公众号富文本 HTML 标注。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import text_to_html
from scripts.tools.wechat_mp_rich_html import (
    format_line_rich_html,
    strip_journal_title_lines,
)


def test_section_bold() -> None:
    assert "<strong>" in format_line_rich_html("一、观察名单")


def test_strip_journal_title() -> None:
    raw = "研究员札记 | 6月2日 周一\n\n一、盘面一览"
    assert "研究员札记" not in strip_journal_title_lines(raw)
    assert "一、盘面一览" in strip_journal_title_lines(raw)


def test_sentiment_and_pct() -> None:
    assert "#c0392b" in format_line_rich_html("[利好] 央行降准")
    assert "#1a7f37" in format_line_rich_html("创业板指 -0.80%")


def test_top5_rank_and_metric() -> None:
    rank = format_line_rich_html("1. 京东方A（000725）（已持仓）")
    assert "<strong>" in rank
    metric = format_line_rich_html("· 情绪阶段：退潮")
    assert "<strong>情绪阶段</strong>" in metric


def test_stock_score_line() -> None:
    html = format_line_rich_html("京东方A（69分）：暂不操作")
    assert "<strong>京东方A</strong>" in html
    assert "69分" in html


def test_text_to_html_integrates_rich() -> None:
    body = "一、盘面一览\n\n上证指数 +1.25%\n\n[利空] 海外波动加剧"
    html = text_to_html(body)
    assert "<blockquote" in html
    assert "#22d3ee" in html
    assert "font-weight: 700" in html
    assert "span style=" in html


def test_blockquote_section_title_gt() -> None:
    body = "> 股票这块\n\n收盘后入库。"
    html = text_to_html(body)
    assert "<blockquote" in html
    assert "股票这块" in html
    assert "收盘后入库" in html


def test_blockquote_cn_section_inline_block() -> None:
    body = "二、个股拆解\n1. 京东方A（000725）\n地位：观察"
    html = text_to_html(body)
    assert "二、个股拆解" in html
    assert "#0f172a" in html
    assert "京东方A" in html
