"""holdings_card_parser — P5 金额「≤125 元」勿误解析为股价。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.holdings_card_parser import parse_holdings_alert_rules

CARD = Path(__file__).resolve().parents[2] / "investment-agent" / "持仓执行卡.md"


def test_waneng_no_price_below_125_from_loss_cap():
    text = CARD.read_text(encoding="utf-8")
    rules = parse_holdings_alert_rules(text)
    waneng_below = [
        r
        for r in rules
        if r["code"] == "000543" and r["type"] == "price_below"
    ]
    prices = {r["price"] for r in waneng_below}
    assert 125.0 not in prices
    assert 9.2 in prices

