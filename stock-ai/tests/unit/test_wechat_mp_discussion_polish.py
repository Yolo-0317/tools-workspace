from scripts.tools.wechat_mp_discussion_polish import reflow_discussion_layout
from scripts.tools.wechat_mp_client import text_to_html
from scripts.tools.wechat_mp_rich_html import opening_lede_paragraph_style


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


def test_discussion_html_scroll_and_lede() -> None:
    body = "北京石景山法院审结了一起纠纷案。\n\n母亲要求继承87个账号。\n\n[[hl:账号里的钱能取出来吗？]]"
    html = text_to_html(body, upload_figures=False, article_kind="discussion")
    assert opening_lede_paragraph_style() in html
    assert "margin:0 0 14px" in html
    assert "账号里的钱能取出来吗？" in html
    assert "#eef6fc" in html
