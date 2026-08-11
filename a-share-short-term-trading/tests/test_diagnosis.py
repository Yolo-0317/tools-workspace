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
        data={
            "source_trade_date": "2026-07-28",
            "cost_90_low": 10.4,
            "cost_90_high": 10.5,
            "average_cost": 10.45,
            "profit_ratio": 50.0,
            "concentration": 20.0,
            "input_bar_count": 210,
            "method": "eastmoney-cyq-v1",
        },
        raw_evidence_ref="fixture:chip-600000",
    )


def _pullback_bars() -> list[DailyBar]:
    closes = [9.0 + index * 0.05 for index in range(20)] + [
        10.10, 10.30, 10.50, 10.80, 11.10, 11.40, 11.20, 11.05, 10.95, 11.00,
    ]
    result: list[DailyBar] = []
    for index, close in enumerate(closes):
        last = index == len(closes) - 1
        result.append(
            DailyBar(
                ts_code="600000",
                exch_code="SH",
                trade_date=date(2026, 6, 29) + timedelta(days=index),
                open=10.90 if last else close - 0.03,
                high=11.12 if last else close + 0.10,
                low=10.80 if last else close - 0.10,
                close=close,
                pre_close=None,
                change_amount=0.05,
                pct_chg=0.5,
                vol=1000,
                amount=100.0,
            )
        )
    return result


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


def test_eod_plan_rejects_a_chip_snapshot_from_the_wrong_trading_date() -> None:
    snapshot = EvidenceSnapshot(
        **{
            **_chip().__dict__,
            "data": {
                **_chip().data,
                "source_trade_date": "2026-08-07",
            },
        }
    )

    plan = build_eod_trade_plan(
        "600000",
        _bars(),
        snapshot,
        now=NOW,
        expected_trade_date=date(2026, 8, 10),
    )

    assert plan.status == "NO_TRADE"
    assert "过期" in plan.reason


def test_eod_plan_accepts_a_wall_clock_old_chip_for_the_expected_trade_date() -> None:
    snapshot = EvidenceSnapshot(
        **{
            **_chip().__dict__,
            "as_of": NOW - timedelta(days=3),
            "data": {
                **_chip().data,
                "source_trade_date": "2026-08-07",
            },
        }
    )

    plan = build_eod_trade_plan(
        "600000",
        _bars(),
        snapshot,
        now=NOW,
        expected_trade_date=date(2026, 8, 7),
    )

    assert plan.status == "WAIT_ENTRY"


def test_breakout_plan_caps_entry_at_one_point_five_percent() -> None:
    volatile = [
        DailyBar(
            **{
                **bar.__dict__,
                "low": bar.close - 0.80,
            }
        )
        for bar in _bars()
    ]

    plan = build_eod_trade_plan(
        "600000",
        volatile,
        _chip(),
        candidate_type="BREAKOUT",
        market_status="ALLOW",
        portfolio_approved=True,
        now=NOW,
    )

    assert plan.status == "WAIT_ENTRY"
    assert plan.entry_ceiling <= round(plan.trigger_price * 1.015 + 0.005, 2)
    assert plan.indicators["prior_high20"] == 10.94


def test_pullback_plan_uses_reversal_high_and_support_invalidation() -> None:
    plan = build_eod_trade_plan(
        "600000",
        _pullback_bars(),
        _chip(),
        candidate_type="PULLBACK",
        market_status="ALLOW",
        portfolio_approved=True,
        now=NOW,
    )

    assert plan.status == "WAIT_ENTRY"
    assert plan.trigger_price == 11.12
    assert plan.invalidation_price < plan.trigger_price
    assert plan.first_reduce_price > plan.entry_ceiling


def test_unapproved_portfolio_keeps_plan_but_does_not_invent_shares() -> None:
    plan = build_eod_trade_plan(
        "600000",
        _bars(),
        _chip(),
        candidate_type="BREAKOUT",
        market_status="ALLOW",
        portfolio_approved=False,
        now=NOW,
    )

    assert plan.status == "WAIT_ENTRY"
    assert plan.maximum_shares is None


def test_market_status_reduces_or_freezes_position_sizing() -> None:
    profile = RiskProfile(
        per_trade_loss_budget=500,
        ticket_limit=4000,
        remaining_exposure=4000,
    )
    allowed = build_eod_trade_plan(
        "600000", _bars(), _chip(), profile=profile, market_status="ALLOW",
        portfolio_approved=True, now=NOW,
    )
    limited = build_eod_trade_plan(
        "600000", _bars(), _chip(), profile=profile, market_status="LIMITED",
        portfolio_approved=True, now=NOW,
    )
    frozen = build_eod_trade_plan(
        "600000", _bars(), _chip(), profile=profile, market_status="FREEZE",
        portfolio_approved=False, now=NOW,
    )

    assert allowed.maximum_shares is not None
    assert limited.maximum_shares is not None
    assert limited.maximum_shares <= allowed.maximum_shares // 2
    assert frozen.status == "WAIT_ENTRY"
    assert frozen.maximum_shares == 0


def test_plan_exposes_final_reward_risk_ratio() -> None:
    plan = build_eod_trade_plan(
        "600000", _bars(), _chip(), portfolio_approved=True, now=NOW
    )

    assert plan.status == "WAIT_ENTRY"
    assert plan.indicators["risk_reward_ratio"] >= 1.5
    assert plan.indicators["atr14"] > 0
