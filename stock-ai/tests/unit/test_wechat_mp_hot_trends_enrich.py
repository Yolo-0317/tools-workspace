"""热搜选题 enrichment 与 hotspot 长文模板。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_hotspot_article import (
    HotspotTopic,
    HOTSPOT_MIN_BODY_CHARS,
    _hotspot_body_usable,
    _template_hotspot_body,
)
from scripts.tools.wechat_mp_prose import strip_hotspot_subheadings


def test_template_hotspot_body_long_pure_paragraphs():
    topic = HotspotTopic(
        item={
            "title": "A股存储芯片概念震荡回升",
            "summary": "weibo第3、baidu第5热议存储芯片链。",
            "market_context": "科创50: 1023.45 (+12.3, +1.22%)",
        },
        bucket="tech",
        score=1.0,
        section_title="存储芯片概念回升",
    )
    from scripts.tools.wechat_mp_hotspot_article import _attach_hotspot_research

    topic = HotspotTopic(
        item=_attach_hotspot_research(topic.item),
        bucket=topic.bucket,
        score=topic.score,
        section_title=topic.section_title,
    )
    body = _template_hotspot_body([topic], trade_label="7月30日收盘")
    assert len(body) >= HOTSPOT_MIN_BODY_CHARS
    assert _hotspot_body_usable(body, bucket="tech")
    assert "> " not in body
    assert "##" not in body
    assert "为啥盯这条" not in body


def test_strip_hotspot_subheadings():
    raw = "> 热搜在吵什么\n\n正文第一段。\n\n> 盘面怎么定价\n\n正文第二段。"
    out = strip_hotspot_subheadings(raw)
    assert "> " not in out
    assert "正文第一段" in out
    assert "正文第二段" in out


def test_strip_hotspot_meta_commentary():
    from scripts.tools.wechat_mp_prose import strip_hotspot_meta_commentary

    raw = "7月30日收盘，热搜在聊「市值前十」。公开报道里有一条值得先记住：建行工行创新高。"
    out = strip_hotspot_meta_commentary(raw)
    assert "公开报道" not in out
    assert "值得先记住" not in out
    assert "热搜在聊" not in out
    assert "建行工行" in out


def test_strip_hotspot_meta_commentary_removes_read_hook_closing():
    from scripts.tools.wechat_mp_prose import strip_hotspot_meta_commentary

    raw = (
        "建行、工行收盘创新高。"
        "若「市值前十」次日承接走弱，舆情里喊得最响的方向，往往最先在龙头竞价上露馅——"
        "这是对「网上怎么说」的硬验证，而不是复述评论。"
    )
    out = strip_hotspot_meta_commentary(raw)
    assert "硬验证" not in out
    assert "复述评论" not in out
    assert "露馅" not in out
    assert "建行、工行收盘创新高" in out


def test_finalize_hotspot_body_no_closing_suspense():
    from scripts.tools.wechat_mp_hotspot_polish import finalize_hotspot_body

    body = "7月30日收盘，市值前十红了九家。建行、工行盘中创新高。"
    out = finalize_hotspot_body(body, trade_label="7月30日", primary_theme="市值前十")
    assert "硬验证" not in out
    assert "复述评论" not in out
    assert "露馅" not in out
    assert out.strip().endswith("创新高。")


def test_reflow_hotspot_layout_splits_long_para():
    from scripts.tools.wechat_mp_hotspot_polish import reflow_hotspot_layout

    long_para = "。".join([("这是一段偏长的行情描述" * 3) + f"涨{i}%" for i in range(10)])
    out = reflow_hotspot_layout(long_para + "。", max_chars=100)
    assert out.count("\n\n") >= 2
    assert all(len(p) <= 180 for p in out.split("\n\n"))


def test_hotspot_body_usable_rejects_subheadings():
    text = "> 小节\n\n" + ("半导体链映射清晰，指数跌多涨少。" * 40)
    assert not _hotspot_body_usable(text, bucket="tech")
