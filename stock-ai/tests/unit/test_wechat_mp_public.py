"""公众号公开稿脱敏。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_prose import humanize_mp_text
from scripts.tools.wechat_mp_public import (
    audit_recommendation_safety,
    check_public_compliance,
    sanitize_platform_property_risk,
    sanitize_public_mp_text,
    sanitize_public_title,
    strip_investment_advice,
)


def test_sanitize_platform_property_risk() -> None:
    raw = "理财方案+投资操作：明日盯啥？收盘信号出炉，小仓跟。"
    out = sanitize_platform_property_risk(raw)
    assert "理财" not in out or "财经信息" in out
    assert "投资操作" not in out
    assert "明日盯" not in out
    assert "收盘信号" not in out


def test_check_platform_property_risk_in_title() -> None:
    fails = check_public_compliance("复盘正文。", title="情绪高潮怎么玩？明日盯啥")
    assert any("平台风险" in f for f in fails)


def test_check_platform_property_risk_bidu_title() -> None:
    fails = check_public_compliance(
        "正文。",
        title="A股必读？京东方A与亨通光电快讯",
    )
    assert any("诱导性必读" in f or "平台风险" in f for f in fails)


def test_sanitize_public_title_strips_bidu() -> None:
    raw = "A股周末必读？达实智能与天娱数科要闻"
    out = sanitize_public_title(raw, kind="news")
    assert "必读" not in out
    assert audit_recommendation_safety(title=out, body="", digest="") == []


def test_sanitize_public_title_strips_old_winners() -> None:
    from scripts.tools.wechat_mp_public import sanitize_public_title

    cases = [
        ("A股热股10条：洛阳钼业怎么读？", "news"),
        ("情绪高潮怎么玩？中化国际4板还在榜", "dragons"),
        ("A股铅锌+诊断｜洛阳钼业领衔：产业链怎么拆？", "sector"),
        ("A股收盘复盘｜其他化学制品+光学元件怎么读？", "market"),
    ]
    for raw, kind in cases:
        out = sanitize_public_title(raw, kind=kind)
        assert "怎么玩" not in out
        assert "还在榜" not in out
        assert "领衔" not in out
        if kind == "dragons" and "怎么玩" in raw:
            assert "梯队" in out and "结构" in out
        assert audit_recommendation_safety(title=out, body="", digest="") == []


def test_sanitize_strips_holdings_markers() -> None:
    raw = "1. 平安银行（000001）（已持仓）\n结合持仓：明日减仓\nP0 计划卖出"
    out = sanitize_public_mp_text(raw)
    assert "已持仓" not in out
    assert "结合持仓" not in out
    assert "P0" not in out


def test_strip_investment_advice() -> None:
    raw = "建议买入京东方A，观察买入也可低吸试错。\n强烈推荐给各位。"
    out = strip_investment_advice(raw)
    assert "建议买入" not in out
    assert "观察买入" not in out
    assert "强烈推荐" not in out


def test_check_public_compliance_catches_advice() -> None:
    body = "今天建议买入半导体龙头，值得布局。\n\n本文为作者个人投资日记与信息整理，不构成投资建议。"
    fails = check_public_compliance(body, title="测试")
    assert any("买入" in f or "荐" in f or "布局" in f for f in fails)


def test_disclaimer_whitelist() -> None:
    body = "复盘而已。\n\n本文为作者个人复盘笔记，不构成投资建议。市场有风险。"
    assert check_public_compliance(body) == []


def test_humanize_applies_public_sanitize() -> None:
    raw = "📌已持仓 京东方A\n"
    out = humanize_mp_text(raw)
    assert "已持仓" not in out
