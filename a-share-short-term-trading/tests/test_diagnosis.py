from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from short_term_trading.daily_sync import DailyBar
from short_term_trading.diagnosis import RiskProfile, build_eod_trade_plan
from short_term_trading.evidence import EvidenceSnapshot


NOW = datetime(2026, 8, 9, 8, 0, tzinfo=timezone.utc)


def _bars() -> list[DailyBar]:
    result: list[DailyBar] = []
    for index in range(30):
        close = 10.0 + index * 0.03
        result.append(
            DailyBar(
                ts_code="600000",
                exch_code="SH",
                trade_date=date(2026, 6, 29) + timedelta(days=index),
                open=close - 0.02,
                high=close + 0.10,
                low=close - 0.10,
                close=close,
                pre_close=None,
                change_amount=0.03,
                pct_chg=0.3,
                vol=1000,
                amount=100.0,
            )
        )
    return result


def _chip() -> EvidenceSnapshot:
    return EvidenceSnapshot(
        snapshot_id="chip-1",
        code="600000",
        kind="chip",
        as_of=NOW - timedelta(hours=1),
        source="eastmoney-opencli",
        parser_version="chip-v1",
        data={"cost_90_low": 10.4, "cost_90_high": 10.5, "profit_ratio": 50.0, "concentration": 20.0},
        raw_evidence_ref="fixture:chip-600000",
    )


def test_complete_eod_inputs_create_wait_entry_plan() -> None:
    plan = build_eod_trade_plan(
        "600000",
        _bars(),
        _chip(),
        profile=RiskProfile(per_trade_loss_budget=500, ticket_limit=4000, remaining_exposure=4000),
        now=NOW,
    )

    assert plan.status == "WAIT_ENTRY"
    assert plan.trigger_price is not None
    assert plan.entry_ceiling is not None
    assert plan.invalidation_price is not None
    assert plan.first_reduce_price is not None
    assert plan.trigger_price < plan.entry_ceiling
    assert plan.invalidation_price < plan.trigger_price < plan.first_reduce_price
    assert plan.maximum_shares >= 100
    assert plan.maximum_shares % 100 == 0


def test_missing_chip_snapshot_is_no_trade() -> None:
    plan = build_eod_trade_plan("600000", _bars(), None, now=NOW)

    assert plan.status == "NO_TRADE"
    assert plan.maximum_shares == 0
    assert "筹码" in plan.reason


def test_stale_chip_snapshot_is_no_trade() -> None:
    stale = EvidenceSnapshot(
        snapshot_id="chip-old",
        code="600000",
        kind="chip",
        as_of=NOW - timedelta(days=2),
        source="eastmoney-opencli",
        parser_version="chip-v1",
        data={"cost_90_low": 10.4, "cost_90_high": 10.5, "profit_ratio": 50.0, "concentration": 20.0},
        raw_evidence_ref="fixture:chip-old",
    )
    plan = build_eod_trade_plan("600000", _bars(), stale, now=NOW)

    assert plan.status == "NO_TRADE"
    assert "过期" in plan.reason
