"""免责块：去重 + 醒目 HTML + CPS 位置。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_content import DISCLAIMER, render_article_content_html
from scripts.tools.wechat_mp_monetization import strip_inline_disclaimer_blocks
from scripts.tools.wechat_mp_product import cps_injection_index, inject_cpsad_for_kind


def test_strip_inline_llm_disclaimer_paragraph() -> None:
    core = (
        "> 结构判断\n正文。\n"
        "（免责声明：本文仅代表作者研究观点，不构成任何投资建议。市场有风险，投资需谨慎。）"
    )
    out = strip_inline_disclaimer_blocks(core)
    assert "免责声明" not in out
    assert "结构判断" in out


def test_strip_trailing_llm_disclaimer() -> None:
    core = "> 结构判断\n以上仅为市场观察，不构成投资建议。"
    out = strip_inline_disclaimer_blocks(core)
    assert "不构成投资" not in out


def test_single_disclaimer_in_rendered_html() -> None:
    body = (
        "> 盘面速览\n\n指数涨0.2%。\n\n"
        "以上仅为市场观察，不构成投资建议。\n\n"
        f"{DISCLAIMER}"
    )
    html, merged = render_article_content_html(body, kind="market", upload_figures=False)
    assert merged.count("不构成投资建议") == 1
    assert merged.count("本文为作者个人复盘笔记") == 1 or merged.count("市场信息整理与复盘笔记") == 1
    assert html.index("盘面速览") < html.rindex("不构成投资建议")


def test_hotspot_uses_commentary_notice_not_finance() -> None:
    from scripts.tools.wechat_mp_public import (
        COMMENTARY_INFORMATION_NOTICE,
        INFORMATION_NOTICE,
        information_notice_for_kind,
    )

    assert information_notice_for_kind("hotspot") == COMMENTARY_INFORMATION_NOTICE
    assert INFORMATION_NOTICE not in information_notice_for_kind("hotspot")
    assert information_notice_for_kind("news") == INFORMATION_NOTICE


def test_hotspot_render_commentary_notice_and_disclaimer() -> None:
    from scripts.tools.wechat_mp_content import COMMENTARY_DISCLAIMER
    from scripts.tools.wechat_mp_public import COMMENTARY_INFORMATION_NOTICE

    body = "张三是笔试第一名。第二名花钱劝他弃考。"
    html, merged = render_article_content_html(body, kind="hotspot", upload_figures=False)
    assert COMMENTARY_INFORMATION_NOTICE in merged
    assert "非证券投资咨询" not in merged
    assert "公开市场数据整理" not in merged
    assert COMMENTARY_DISCLAIMER in merged
    assert COMMENTARY_INFORMATION_NOTICE in html or "公开报道" in html


def test_tv_review_keeps_spoiler_warning_before_commentary_notice() -> None:
    from scripts.tools.wechat_mp_public import COMMENTARY_INFORMATION_NOTICE

    body = "剧透预警：下文涉及《奥德赛》完整剧情与结局。\n\n正文第一段。"
    html, merged = render_article_content_html(body, kind="tv_review", upload_figures=False)

    assert merged.startswith("剧透预警：下文涉及《奥德赛》完整剧情与结局。")
    assert merged.index("剧透预警") < merged.index(COMMENTARY_INFORMATION_NOTICE)
    assert html.index("剧透预警") < html.index("公开报道")


def test_information_notice_not_duplicated_on_re_render() -> None:
    from scripts.tools.wechat_mp_public import INFORMATION_NOTICE

    body = "> 要闻精选\n\n第一条快讯摘要。"
    _, merged_once = render_article_content_html(body, kind="news", upload_figures=False)
    assert merged_once.count("【说明】") == 1
    assert INFORMATION_NOTICE in merged_once

    _, merged_twice = render_article_content_html(merged_once, kind="news", upload_figures=False)
    assert merged_twice.count("【说明】") == 1
    assert merged_twice.count(INFORMATION_NOTICE) == 1


def test_silver_information_notice_not_duplicated_on_re_render() -> None:
    from scripts.tools.wechat_mp_public import SILVER_INFORMATION_NOTICE

    body = "> 家庭先约好一句话\n\n接到陌生办案电话，先挂断，再联系家人。"
    _, merged_once = render_article_content_html(
        body,
        kind="silver",
        engagement_kind="discussion",
        upload_figures=False,
    )
    _, merged_twice = render_article_content_html(
        merged_once,
        kind="silver",
        engagement_kind="discussion",
        upload_figures=False,
    )

    assert merged_twice.count("【说明】") == 1
    assert merged_twice.count(SILVER_INFORMATION_NOTICE) == 1


def test_silver_discussion_render_keeps_scan_friendly_subheadings() -> None:
    body = (
        "> 骗子先切断你的求证渠道\n\n"
        "陌生人要求躲开家人接电话，先不要照做。\n\n"
        "> 家庭要先恢复联系\n\n"
        "挂断电话，再拨打自己保存的官方号码核实。"
    )

    _, merged = render_article_content_html(
        body,
        kind="silver",
        engagement_kind="discussion",
        upload_figures=False,
    )

    assert "> 骗子先切断你的求证渠道" in merged
    assert "> 家庭要先恢复联系" in merged


def test_cps_at_two_thirds_not_opening() -> None:
    parts = [f'<p id="p{i}">段{i}</p>' for i in range(6)]
    body = "".join(parts)
    html = body + f'<p style="background-color:#fff5f5">{DISCLAIMER}</p>'
    pos = cps_injection_index(html)
    assert pos == body.index("</p>", int(len(body) * 2 / 3) - 1) or pos >= int(
        len(body) * 2 / 3
    )
    out = inject_cpsad_for_kind(html, "101_999", kind="market")
    cps = out.index("mp-common-cpsad")
    assert out.index("p3") < cps < out.index("p4")
    assert cps < out.index("#fff5f5")


def test_article_shell_attaches_short_drama_after_cta_rerender(monkeypatch) -> None:
    from scripts.tools.wechat_mp_content import _article_shell

    def fake_cta(article, *, kind):
        out = dict(article)
        out["body_text"] = out["body_text"].replace(
            DISCLAIMER,
            f"CTA最终段\n\n{DISCLAIMER}",
        )
        return out

    def fake_short_drama(article, *, kind):
        assert "CTA最终段" in article["content"]
        out = dict(article)
        out["content"] += '<mp-common-cpsad data-adtype="short-play"></mp-common-cpsad>'
        return out

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_stock_ai_cta.attach_stock_ai_cta",
        fake_cta,
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_short_drama.attach_short_drama",
        fake_short_drama,
    )

    article = _article_shell(
        title="测试",
        digest="测试摘要",
        body_text="正文第一段。",
        upload_figures=False,
        kind="market",
    )

    assert article["content"].endswith("</mp-common-cpsad>")
