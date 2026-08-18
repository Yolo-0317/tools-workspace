"""公众号文章评分。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_eval import (
    BANNED_AI_PHRASES,
    evaluate_article,
    format_report,
)


def test_opening_block_skips_information_notice() -> None:
    from scripts.tools.wechat_mp_eval import _opening_block

    body = (
        "【说明】本文依据公开资料整理一般生活信息。\n\n"
        "7月底，一名家属报警称亲人接到陌生电话后失联，这个场景值得先记住。"
    )

    assert _opening_block(body).startswith("7月底")


def test_section_count_does_not_double_count_plain_and_html() -> None:
    from scripts.tools.wechat_mp_eval import _count_section_heads

    body = "> 第一节\n\n正文。\n\n> 第二节\n\n正文。"
    html = "<blockquote>第一节</blockquote><p>正文。</p><blockquote>第二节</blockquote>"

    assert _count_section_heads(body, html=html) == 2


from scripts.tools.wechat_mp_workspace_article import generate_workspace_overview_body


def test_workspace_body_scores_ok() -> None:
    body = generate_workspace_overview_body()
    rep = evaluate_article(
        title="脚本越写越散？后来全收进了一个仓库",
        digest="工具工作区全景",
        body=body,
        kind="workspace",
    )
    assert not rep.compliance_failures
    assert rep.total_score >= 70
    assert rep.ai_flavor_score <= 45


def test_ai_flavor_high_on_template_text() -> None:
    body = (
        "首先，在当今数字化时代，自动化非常重要。\n\n"
        "其次，值得一提的是，赋能和一站式解决方案助力生态建设。\n\n"
        "最后，综上所述，欢迎留言点赞让我知道。"
    )
    rep = evaluate_article(title="震惊！重磅！", digest="", body=body, kind="test")
    assert rep.ai_flavor_score >= 50
    assert rep.total_score < 60
    assert rep.compliance_failures or rep.verdict != "可进草稿箱"


def test_format_report_contains_verdict() -> None:
    rep = evaluate_article(title="测试标题？", digest="摘要", body="收盘后入库。", kind="x")
    text = format_report(rep)
    assert "【总分】" in text
    assert rep.verdict in text


def test_banned_phrases_non_empty() -> None:
    assert "赋能" in BANNED_AI_PHRASES
