"""公众号富文本 HTML 标注。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import split_wechat_body_blocks, text_to_html
from scripts.tools.wechat_mp_rich_html import (
    format_line_rich_html,
    opening_lede_paragraph_style,
    strip_journal_title_lines,
)


def test_market_opening_lede_before_first_section() -> None:
    body = (
        "上证报4097点涨0.56%；跌多涨少，结构未共振。午后看科技能否扩散。\n\n"
        "> 盘面速览\n\n"
        "截至午间收盘，指数温和上行。"
    )
    html = text_to_html(body, upload_figures=False, article_kind="market")
    lede_snip = opening_lede_paragraph_style()
    assert "4097" in html
    assert lede_snip in html
    assert html.index("4097") < html.index("盘面速览")
    assert html.count("font-size:17px;font-weight:700") >= 1


def test_top5_opening_lede_under_first_section_only() -> None:
    body = (
        "> 筛选名单\n\n"
        "今日最强信号：科技主线集中，科创50领涨。\n\n"
        "> 个股拆解\n\n"
        "1. 测试股（000001）"
    )
    html = text_to_html(body, upload_figures=False, article_kind="top5")
    assert opening_lede_paragraph_style() in html
    assert "今日最强信号" in html
    assert html.index("今日最强信号") < html.index("个股拆解")
    # 第二节正文为常规 16px
    assert 'font-size:16px;color:#333333' in html


def test_dragons_opening_lede_under_emotion_section() -> None:
    body = (
        "> 情绪与盘面\n\n"
        "炸板率32%，涨跌比1927:3270，情绪偏分歧。\n\n"
        "> 龙头拆解\n\n"
        "地位：观察。"
    )
    html = text_to_html(body, upload_figures=False, article_kind="dragons")
    assert opening_lede_paragraph_style() in html
    assert "炸板率" in html


def test_no_opening_lede_without_article_kind() -> None:
    body = "开篇一句。\n\n> 盘面速览\n\n正文。"
    html = text_to_html(body, upload_figures=False)
    assert opening_lede_paragraph_style() not in html


def test_section_bold() -> None:
    html = format_line_rich_html("一、观察名单")
    assert "font-weight:700" in html
    assert "#1a5276" in html


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
    assert "一、盘面一览" in html
    assert "text-align:center" in html
    assert "#1a5276" in html
    assert "font-size:17px" in html
    assert "margin:0 0 5px" in html
    assert "span style=" in html


def test_blockquote_section_title_gt() -> None:
    body = "> 股票这块\n\n收盘后入库。"
    html = text_to_html(body)
    assert "股票这块" in html
    assert "收盘后入库" in html
    assert "text-align:center" in html


def test_news_blank_lines_merge_one_paragraph() -> None:
    body = (
        "三、要闻精选\n\n"
        "地缘：\n\n"
        "[中性] 标题一\n"
        "  摘要一行\n\n"
        "[利空] 标题二\n\n"
        "国内：\n\n"
        "[利好] 标题三"
    )
    html = text_to_html(body, upload_figures=False)
    assert "line-height:1.78" in html
    assert html.count("<p style=") >= 3
    assert "标题一" in html and "标题三" in html


def test_news_item_title_larger_font() -> None:
    body = "1. [利好] 测试标题\n  摘要内容\n  AI点评：板块或受益"
    html = text_to_html(body, upload_figures=False)
    assert "font-size:18px" in html
    assert "测试标题" in html
    assert "AI点评" in html


def test_blockquote_cn_section_inline_block() -> None:
    body = "二、个股拆解\n1. 京东方A（000725）\n地位：观察"
    html = text_to_html(body)
    assert "二、个股拆解" in html
    assert "京东方A" in html
    assert "text-align:center" in html


def test_figure_and_section_not_same_block() -> None:
    body = (
        "[[fig:inline-p01.jpg|]]\n\n"
        "> 盘面速览\n\n"
        "上证指数 +1.25%"
    )
    blocks = split_wechat_body_blocks(body)
    assert len(blocks) == 3
    assert blocks[0].strip().startswith("[[fig:")
    assert "> 盘面速览" in blocks[1]
    html = text_to_html(body, upload_figures=False, local_figure_preview=True)
    assert "inline-p01.jpg" in html
    assert "盘面速览" in html
    assert "text-align:center" in html
    assert "[[fig:" not in html
    assert "font-size:12px;color:#999999" not in html
    assert "盘面配图" not in html
    assert "max-height:200px" in html
    assert "object-fit:cover" in html
