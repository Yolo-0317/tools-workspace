from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_discussion_polish import reflow_discussion_layout
from scripts.tools.wechat_mp_client import text_to_html
from scripts.tools.wechat_mp_rich_html import opening_lede_paragraph_style


def test_reflow_discussion_keeps_two_sentence_opening_hook() -> None:
    raw = (
        "司马迁，这个名字我们从小在课本上背过无数次。"
        "但你可能没真正想过，这名字背后，是一个怎样顶天立地的灵魂。\n\n"
        "撒贝宁走进那个空间时，也愣了一下。黄帝、秦始皇站在那里。"
    )
    out = reflow_discussion_layout(raw)
    parts = [p for p in out.split("\n\n") if p.strip()]
    assert parts[0].startswith("司马迁，这个名字")
    assert "顶天立地的灵魂" in parts[0]
    assert "撒贝宁走进那个空间时，也愣了一下。" in parts[1]
    html = text_to_html(out, upload_figures=False, article_kind="discussion")
    assert opening_lede_paragraph_style() in html
    assert html.find("顶天立地的灵魂") < html.find("撒贝宁走进")


def test_reflow_discussion_splits_long_paragraph() -> None:
    raw = "第一句很长需要拆开。第二句同样要拆。第三句收尾。"
    out = reflow_discussion_layout(raw)
    parts = [p for p in out.split("\n\n") if p.strip()]
    assert len(parts) == 3


def test_reflow_discussion_keeps_figure_line() -> None:
    raw = "事实一句。\n\n[[fig:still-01|配图]]\n\n结尾一句。"
    out = reflow_discussion_layout(raw)
    assert "[[fig:still-01|配图]]" in out
    assert out.count("\n\n") >= 2


def test_finalize_discussion_body_splits_sentences() -> None:
    from scripts.tools.wechat_mp_discussion_polish import finalize_discussion_body

    raw = "第一句。第二句。第三句。"
    out = finalize_discussion_body(raw)
    assert len([p for p in out.split("\n\n") if p.strip()]) == 3


def test_reflow_discussion_keeps_paren_block_together() -> None:
    raw = (
        "（《典籍里的中国》共22集，会陆续更新每一集的笔记和观察。"
        "不想漏掉的，可以星标一下这个号。）"
    )
    out = reflow_discussion_layout(raw)
    parts = [p for p in out.split("\n\n") if p.strip()]
    assert len(parts) == 1
    assert parts[0].startswith("（") and parts[0].endswith("）")


def test_reflow_discussion_keeps_quoted_period_together() -> None:
    raw = (
        "撒贝宁说：“这列火车时速三百公里。”宋应星转过头，"
        "只说了一句：“这个……比马快多了。”"
    )
    out = reflow_discussion_layout(raw)
    assert "“这列火车时速三百公里。”" in out
    assert not any(p.strip().startswith("”") for p in out.split("\n\n"))


def test_discussion_html_scroll_and_lede() -> None:
    body = "北京石景山法院审结了一起纠纷案。\n\n母亲要求继承87个账号。\n\n[[hl:账号里的钱能取出来吗？]]"
    html = text_to_html(body, upload_figures=False, article_kind="discussion")
    assert opening_lede_paragraph_style() in html
    assert "margin:0 0 14px" in html
    assert "账号里的钱能取出来吗？" in html
    assert "font-weight:700" in html
    assert "border-left:3px" not in html


def test_inline_hl_keeps_sentence_and_bolds_quote() -> None:
    body = "他抬起头，说了一句：「[[hl:天下人衣食富足，我无憾了。]]」"
    html = text_to_html(body, upload_figures=False, article_kind="discussion")
    assert html.count("天下人衣食富足，我无憾了。") == 1
    assert "说了一句：" in html
    assert "font-weight:700" in html
    assert "#1a5276" in html
    assert "border-left:3px" not in html


def test_reflow_keeps_inline_hl_with_period() -> None:
    raw = (
        "三百年后，一个种水稻的人让十四亿人吃饱了饭。"
        "[[hl:功名没记住他，稻子记住了。]]"
    )
    out = reflow_discussion_layout(raw)
    assert "[[hl:功名没记住他，稻子记住了。]]" in out
    assert "[[hl:功名没记住他，稻子记住了。" not in out.replace(
        "[[hl:功名没记住他，稻子记住了。]]", ""
    )
