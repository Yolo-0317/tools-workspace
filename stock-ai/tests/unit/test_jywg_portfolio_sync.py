from datetime import timezone
from decimal import Decimal

import pytest

from scripts.tools.jywg_portfolio_sync import jywg_payload_to_broker_facts, jywg_payload_to_card


def payload() -> dict:
    return {
        "source": "jywg.18.cn-opencli",
        "fetched_at": "2026-08-10T08:15:30+00:00",
        "user": "测试用户(1234)",
        "account": {
            "总资产": "100,000.00",
            "可用资金": "30,000.00",
            "资金余额": "31,000.00",
            "可取资金": "29,000.00",
            "冻结资金": "1,000.00",
            "证券市值": "70,000.00",
            "持仓盈亏": "2,500.00",
            "当日盈亏": "350.00",
        },
        "positions": [
            {
                "code": "600000",
                "name": "浦发银行",
                "qty": "500",
                "available": "200",
                "cost": "6.80",
                "price": "7.01",
                "market_value": "3,505.00",
                "pnl": "105.00",
                "pnl_pct": "3.09%",
                "day_pnl": "33.00",
                "day_pnl_pct": "0.95%",
            }
        ],
    }


def test_broker_fact_conversion_preserves_every_position_and_account_field() -> None:
    positions, account = jywg_payload_to_broker_facts(payload())
    position = positions[0]

    assert position.shares == 500
    assert position.available_shares == 200
    assert position.cost_price == Decimal("6.80")
    assert position.current_price == Decimal("7.01")
    assert position.market_value == Decimal("3505.00")
    assert position.position_pnl == Decimal("105.00")
    assert position.position_pnl_pct == Decimal("3.09")
    assert position.daily_pnl == Decimal("33.00")
    assert position.daily_pnl_pct == Decimal("0.95")
    assert position.broker_captured_at.tzinfo is timezone.utc

    assert account.cash_balance == Decimal("31000.00")
    assert account.withdrawable_cash == Decimal("29000.00")
    assert account.frozen_cash == Decimal("1000.00")
    assert account.daily_pnl == Decimal("350.00")
    assert account.masked_account_identifier == "12****34"
    assert "1234" not in account.masked_account_identifier


def test_existing_card_conversion_keeps_total_quantity_not_available_quantity() -> None:
    positions, account = jywg_payload_to_card(payload())

    assert positions[0].shares == 500
    assert positions[0].price == 7.01
    assert account.total_assets == 100000.0


def test_broker_fact_conversion_rejects_missing_capture_time() -> None:
    value = payload()
    value.pop("fetched_at")

    with pytest.raises(ValueError, match="fetched_at"):
        jywg_payload_to_broker_facts(value)
