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
    check_public_compliance,
    sanitize_public_mp_text,
    strip_investment_advice,
)


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
    body = "复盘而已。\n\n本文为作者个人投资日记，不构成投资建议。市场有风险。"
    assert check_public_compliance(body) == []


def test_humanize_applies_public_sanitize() -> None:
    raw = "📌已持仓 京东方A\n"
    out = humanize_mp_text(raw)
    assert "已持仓" not in out
