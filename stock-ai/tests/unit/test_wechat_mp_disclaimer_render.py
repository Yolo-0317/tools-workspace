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
    assert merged.count("本文为作者个人投资日记") == 1
    assert "font-size:15px" in html
    assert "text-align:center" in html
    assert "#c0392b" in html
    assert html.index("盘面速览") < html.rindex("不构成投资建议")


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
