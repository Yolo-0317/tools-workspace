"""公众号文章评分。"""

from __future__ import annotations

import json
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


def _user_hotspot_article(tmp_path: Path, *, short: bool = False) -> Path:
    paragraphs = [
        "9月22日，北京商报走访发现部分月饼礼盒已经打折。消费者看到价格变动，最想弄清楚的是礼盒降价究竟说明了什么，不能只凭一个价签判断整个市场。",
        "一家门店里，原价119元的礼盒折后卖79元，另一款从208元降到138元。同一位店员也说，百元左右的礼盒和散装月饼仍有人买。",
        "对买来自己吃的人来说，口味、分量和能否吃完往往比盒子更重要。送礼的人则要考虑体面和携带方便，两种用途原本就不是同一笔账。",
        "但礼盒不会因为有人买散装就完全失去价值。它承载了节日往来，只是有些消费者不愿意为超出需要的包装和分量付钱。",
        "商家在节前备货时，要估计团购和散客各会买多少。团购一旦减少，单靠零散购买未必能按原价消化原本准备的礼盒。",
        "节令商品还有时间压力。中秋一过，月饼仍然能吃，礼盒作为节礼的用途却会迅速减弱，店家便可能提前调整价格。",
        "与此同时，深圳一家会员店的部分款式在9月23日的页面上显示售罄。页面显示无货，不等于所有门店线下也无货，更不能推算全国销量。",
        "有人买得少，有人买得快，这些报道并不互相推翻。它们说的是不同渠道、不同款式和不同用途，市场不会只剩下涨价或降价一种声音。",
        "打折前的标价也是商家设定的。看到六折时，消费者不妨回头看看同类月饼平时卖多少钱，而不是把标价当成这盒月饼必然值那么多的证据。",
        "对于要送人的人，包装可能仍然重要，但收礼者的口味和人数也重要。一盒看上去气派的月饼，如果最后大半留在桌上，贵与便宜就不能只按购买时算。",
        "买给自己吃则更简单。散装月饼能让人少量选择不同口味，也不用为装饰付钱。喜欢礼盒的人仍可以购买，重要的是知道自己为哪一部分付了钱。",
        "某个渠道卖完不能证明全部月饼都畅销，某个门店打折也不能证明全部月饼都滞销。把销售地点、日期和具体款式放回报道里，这件事才不至于只剩一个夸张结论。",
        "对商家而言，少生产礼盒、调整包装和提前促销都可能是应对方式。但这些是从现有销售现象推出来的可能选择，不能冒充已经发生的行业统一行动。",
        "买之前倒可以先想清楚，月饼最后是谁吃、要吃几块、愿意为包装多付多少。折扣越醒目，越要看看自己原本是否需要这一整盒。",
        "一盒月饼降价了，省下的是标价和售价之间的差额；若家里根本吃不完，付款仍是一笔支出。你会因为折扣买下原本不打算买的礼盒吗？",
    ]
    body = "\n\n".join(paragraphs[:4] if short else paragraphs)
    path = tmp_path / "article.json"
    path.write_text(
        json.dumps({
            "title": "月饼礼盒提前打折，是月饼卖不动了吗？",
            "digest": "部分礼盒降价与个别款式售罄同时出现。",
            "body": body,
            "topic": "月饼礼盒提前打折",
            "original_thesis": "礼盒降价反映节令备货与购买用途的变化，不能直接证明所有月饼都卖不动了。",
            "research_urls": [
                "https://www.bbtnews.com.cn/story/1",
                "https://www.sznews.com/news/2",
                "https://www.thepaper.cn/newsDetail_forward_3",
            ],
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_user_hotspot_cli_uses_dedicated_precheck_not_automated_scoring(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from scripts.tools.wechat_mp_eval import main

    path = _user_hotspot_article(tmp_path)
    monkeypatch.setattr(sys, "argv", ["wechat_mp_eval", "--user-hotspot-article", str(path)])

    assert main() == 0
    output = capsys.readouterr().out
    assert "用户主动热点预检" in output
    assert "仍须人工审稿" in output
    assert "分块标题" not in output
    assert "2000" not in output
    assert "可进草稿箱" not in output


def test_user_hotspot_cli_rejects_body_below_850_chars(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from scripts.tools.wechat_mp_eval import main

    path = _user_hotspot_article(tmp_path, short=True)
    monkeypatch.setattr(sys, "argv", ["wechat_mp_eval", "--user-hotspot-article", str(path)])

    assert main() == 1
    assert "text_too_short" in capsys.readouterr().out
