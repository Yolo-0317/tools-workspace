from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from short_term_trading.diagnosis import TradePlanDraft
from short_term_trading.evidence import EvidenceSnapshot
from short_term_trading.intraday import IntradayRiskGate, verify_intraday_plan


NOW = datetime(2026, 8, 10, 2, 0, tzinfo=timezone.utc)


def _snapshot(kind: str, data: dict, offset_seconds: int = 0) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        snapshot_id=f"{kind}-{offset_seconds}",
        code="600000",
        kind=kind,
        as_of=NOW + timedelta(seconds=offset_seconds),
        source="fixture",
        parser_version="v1",
        data=data,
        raw_evidence_ref=f"fixture:{kind}",
    )


def _plan() -> TradePlanDraft:
    return TradePlanDraft(
        code="600000",
        status="WAIT_ENTRY",
        reason="fixture",
        as_of=NOW.isoformat(),
        trigger_price=10.0,
        entry_ceiling=10.3,
        invalidation_price=9.8,
        first_reduce_price=10.4,
        pullback_low=9.9,
        pullback_high=10.1,
        maximum_shares=300,
        indicators={},
        evidence_refs={},
    )


def _quote(price: float = 10.1) -> EvidenceSnapshot:
    return _snapshot(
        "quote",
        {"price": price, "change_pct": 1.0, "amount": 100.0, "turnover": 2.0, "volume_ratio": 1.8, "vwap": 10.0, "trigger_held_3m": True},
    )


def _order_books() -> list[EvidenceSnapshot]:
    values = {**{f"bid_{index}": 120 for index in range(1, 6)}, **{f"ask_{index}": 80 for index in range(1, 6)}}
    return [_snapshot("order_book", values, offset) for offset in (-120, -60, 0)]


def _risk() -> IntradayRiskGate:
    return IntradayRiskGate("ALLOW", True, 200)


def test_all_intraday_gates_allow_buy() -> None:
    decision = verify_intraday_plan(
        _plan(),
        quote=_quote(),
        fund_flow=_snapshot("fund_flow", {"main_net_inflow": 10.0}),
        sector=_snapshot("sector", {"theme_name": "测试", "change_pct": 2.0, "advancing_ratio": 70.0, "leader_code": "600001"}),
        chip=_snapshot("chip", {"cost_90_low": 9.6, "cost_90_high": 10.0, "profit_ratio": 60.0, "concentration": 30.0}),
        order_books=_order_books(),
        risk_gate=_risk(),
        now=NOW,
    )

    assert decision.status == "BUY_ALLOWED"
    assert decision.maximum_shares == 200
    assert decision.failed_gates == []


def test_missing_order_book_rejects_trade() -> None:
    decision = verify_intraday_plan(
        _plan(),
        quote=_quote(),
        fund_flow=_snapshot("fund_flow", {"main_net_inflow": 10.0}),
        sector=_snapshot("sector", {"theme_name": "测试", "change_pct": 2.0, "advancing_ratio": 70.0, "leader_code": "600001"}),
        chip=_snapshot("chip", {"cost_90_low": 9.6, "cost_90_high": 10.0, "profit_ratio": 60.0, "concentration": 30.0}),
        order_books=[],
        risk_gate=_risk(),
        now=NOW,
    )

    assert decision.status == "NO_TRADE"
    assert "order_book" in decision.failed_gates


def test_holding_below_invalidation_exits_before_new_entry_gates() -> None:
    decision = verify_intraday_plan(
        _plan(),
        quote=_quote(9.7),
        fund_flow=None,
        sector=None,
        chip=None,
        order_books=[],
        risk_gate=_risk(),
        now=NOW,
        is_holding=True,
    )

    assert decision.status == "EXIT"


def test_market_freeze_does_not_block_a_holding_hard_exit() -> None:
    decision = verify_intraday_plan(
        _plan(),
        quote=_quote(9.7),
        fund_flow=None,
        sector=None,
        chip=None,
        order_books=[],
        risk_gate=IntradayRiskGate("FREEZE", False, 0, "大盘情绪冻结"),
        now=NOW,
        is_holding=True,
    )

    assert decision.status == "EXIT"
    assert decision.reason == "现价跌破硬失效价"
