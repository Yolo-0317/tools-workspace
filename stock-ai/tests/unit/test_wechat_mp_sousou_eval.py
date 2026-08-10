"""搜一搜 eval 规则。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_eval import evaluate_article
from scripts.tools.wechat_mp_sousou_eval import (
    check_hotspot_selection_leak,
    check_title_opening_aligned,
    check_title_sousou_complete,
)


def test_title_sousou_rejects_dangling_return():
    ok, notes = check_title_sousou_complete('热点深评｜"戴高乐"号航母从中东返…对A股怎么看？')
    assert not ok
    assert any("半句话" in n for n in notes)


def test_title_sousou_accepts_complete_hook():
    ok, _ = check_title_sousou_complete('热点深评｜戴高乐号航母返港对A股怎么看？')
    assert ok


def test_hotspot_reader_meta_rejected():
    from scripts.tools.wechat_mp_sousou_eval import check_hotspot_reader_meta

    ok, notes = check_hotspot_reader_meta(
        "本篇不复盘快讯清单，只围绕霍尔木兹这一单一变量，沿事件递进阅读；下文先交代选题逻辑。"
    )
    assert not ok
    assert notes


def test_hotspot_selection_leak_in_why_section():
    body = "\n".join(
        [
            "7月10日收盘，深写戴高乐返港。",
            "",
            "> 为啥盯这条",
            "在候选五条中，相较「霍尔木兹」故选返港。",
            "",
            "> 航母返港",
            "先说事实：法国宣布返航。",
        ]
    )
    ok, notes = check_hotspot_selection_leak(body)
    assert not ok


def test_eval_penalizes_bad_hotspot_title():
    body = "\n".join(
        [
            "7月30日收盘，戴高乐号航母返港牵动军工链。",
            "",
            "> 热搜在吵什么",
            "返港牵动军工与航运预期，可用板块强弱验证。",
            "",
            "> 航母返港",
            "法国航母返港，军工链盘中一度冲高。",
            "讨论降温，资金更看竞价能不能站稳。",
            "短线映射有限，别被标题带着追。",
            "",
            "> 短线怎么验",
            "短线更值得盯竞价承接。",
        ]
        + ["补充盘面观察。" * 30]
    )
    bad = evaluate_article(
        title='热点深评｜戴高乐号从中东返…对A股怎么看？',
        digest="摘要",
        body=body,
        kind="hotspot",
    )
    good = evaluate_article(
        title="热点深评｜戴高乐号航母返港对A股怎么看？",
        digest="摘要",
        body=body,
        kind="hotspot",
    )
    assert good.total_score > bad.total_score


def test_title_opening_aligned():
    ok, _ = check_title_opening_aligned(
        "热点深评｜戴高乐号航母返港对A股怎么看？",
        "7月10日收盘，戴高乐号航母返港牵动军工与油运预期。",
        kind="hotspot",
    )
    assert ok


def test_sanitize_reader_data_gap_meta_sentence():
    from scripts.tools.wechat_mp_public import (
        check_reader_data_gap_meta,
        sanitize_reader_data_gap,
    )

    raw = (
        "盘面怎么反应：能源、油运、黄金等地缘敏感板块在7月10日交易时段的"
        "样本个股涨跌与换手数据未获取。"
    )
    ok, _ = check_reader_data_gap_meta(raw)
    assert not ok
    out = sanitize_reader_data_gap(raw, kind="hotspot")
    assert "未获取" not in out
    assert "分化" in out or "放量" in out
