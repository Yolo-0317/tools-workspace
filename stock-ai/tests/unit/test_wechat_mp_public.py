"""公众号公开稿脱敏。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_prose import humanize_mp_text
from scripts.tools.wechat_mp_public import sanitize_public_mp_text


def test_sanitize_strips_holdings_markers() -> None:
    raw = "1. 平安银行（000001）（已持仓）\n结合持仓：明日减仓\nP0 计划卖出"
    out = sanitize_public_mp_text(raw)
    assert "已持仓" not in out
    assert "结合持仓" not in out
    assert "P0" not in out


def test_humanize_applies_public_sanitize() -> None:
    raw = "📌已持仓 京东方A\n"
    out = humanize_mp_text(raw)
    assert "已持仓" not in out
