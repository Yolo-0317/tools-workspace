from __future__ import annotations

import importlib.util
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from stock_ai.buy_point_selection.execution import ExecutionCosts
from stock_ai.buy_point_selection.historical_replay import (
    HistoricalPlan,
    ReplayBundle,
    replay_historical_plans,
)
from stock_ai.buy_point_selection.models import BuyPointBar, SetupType
from stock_ai.buy_point_selection.planning import PricePlan
from stock_ai.buy_point_selection.reference_data import ReferenceCoverage


SCRIPT = (
    Path(__file__).parents[2]
    / "scripts"
    / "analysis"
    / "generate_buy_point_observations.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "generate_buy_point_observations", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bundle() -> ReplayBundle:
    start = date(2023, 12, 26)
    dates = tuple(start + timedelta(days=index) for index in range(630))
    signal = dates[0]
    first = dates[1]
    second = dates[2]
    plan = PricePlan(
        structure_id="structure-1",
        code="600001",
        setup_type=SetupType.PRE_BREAKOUT,
        signal_date=signal,
        signal_close=Decimal("10.00"),
        trigger_price=Decimal("10.10"),
        invalidation_price=Decimal("9.80"),
        target_2r=Decimal("10.70"),
        risk_distance=Decimal("0.30"),
        risk_reward_ratio=Decimal("2"),
        maximum_shares=100,
        valid_through_trade_date=second,
    )
    bars = (
        BuyPointBar(
            trade_date=first,
            open=Decimal("10.10"),
            high=Decimal("10.20"),
            low=Decimal("9.90"),
            close=Decimal("10.10"),
            pct_chg=Decimal("0"),
            amount_qian=Decimal("200000"),
        ),
        BuyPointBar(
            trade_date=second,
            open=Decimal("10.20"),
            high=Decimal("10.80"),
            low=Decimal("10.00"),
            close=Decimal("10.70"),
            pct_chg=Decimal("0"),
            amount_qian=Decimal("200000"),
        ),
    )
    replay = replay_historical_plans(
        (
            HistoricalPlan(
                signal,
                "600001",
                "S1",
                "ALLOW",
                True,
                plan,
            ),
        ),
        {"600001": bars},
        {signal: ReferenceCoverage(signal, True, True, True)},
        costs=ExecutionCosts(
            commission_rate=Decimal("0"),
            minimum_commission=Decimal("0"),
            slippage_rate=Decimal("0"),
            sell_tax_rate=Decimal("0"),
        ),
    )
    return ReplayBundle(
        trading_dates=dates,
        replay=replay,
        rule_version="buy-point-selection-3.1.0",
        policy_hash="policy-hash",
        rejection_counts={},
    )


def test_cli_writes_deterministic_observation_bundle(tmp_path) -> None:
    """Catches partial output or non-auditable observations being treated as complete."""
    module = _load_module()

    result = module.main(
        [
            "--start",
            "2023-12-26",
            "--end",
            "2026-08-04",
            "--out",
            str(tmp_path),
        ],
        generate=lambda start, end: _bundle(),
    )

    assert result == 0
    dates = json.loads((tmp_path / "trading-dates.json").read_text(encoding="utf-8"))
    observations = json.loads(
        (tmp_path / "outcome-observations.json").read_text(encoding="utf-8")
    )
    integrity = json.loads(
        (tmp_path / "replay-integrity.json").read_text(encoding="utf-8")
    )
    assert len(dates) == 630
    assert observations[0]["signal_date"] == "2023-12-26"
    assert observations[0]["outcome"] == "TARGET_2R_FIRST"
    assert integrity["complete"] is True
    assert integrity["observation_count"] == 1
    assert len(integrity["observations_sha256"]) == 64


def test_cli_returns_failure_for_incomplete_pit_bundle(tmp_path) -> None:
    """Catches an integrity failure receiving a successful shell exit code."""
    module = _load_module()
    complete = _bundle()
    signal = complete.trading_dates[0]
    incomplete_replay = replay_historical_plans(
        complete.replay.opportunities
        and (
            HistoricalPlan(
                signal,
                "600001",
                "S1",
                "ALLOW",
                True,
                complete.replay.opportunities[0].plan,
            ),
        ),
        {"600001": ()},
        {signal: ReferenceCoverage(signal, True, False, True)},
    )
    incomplete = ReplayBundle(
        trading_dates=complete.trading_dates,
        replay=incomplete_replay,
        rule_version=complete.rule_version,
        policy_hash=complete.policy_hash,
        rejection_counts={},
    )

    result = module.main(
        [
            "--start",
            "2023-12-26",
            "--end",
            "2026-08-04",
            "--out",
            str(tmp_path),
        ],
        generate=lambda start, end: incomplete,
    )

    assert result == 2
    integrity = json.loads(
        (tmp_path / "replay-integrity.json").read_text(encoding="utf-8")
    )
    assert integrity["complete"] is False
    assert integrity["missing_st_dates"] == ["2023-12-26"]
