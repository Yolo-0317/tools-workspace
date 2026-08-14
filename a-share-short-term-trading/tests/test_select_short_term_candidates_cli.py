from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from short_term_trading.selection_service import SelectionReport
from short_term_trading.buy_point_selection_service import (
    BuyPointRuntimeItem,
    BuyPointRuntimeReport,
)
from stock_ai.buy_point_selection.models import CandidateTier, SetupType
from stock_ai.short_term_selection import BASELINE_POLICY, STRICT_B


SCRIPT = Path(__file__).parents[1] / "scripts" / "select_short_term_candidates.py"
SPEC = importlib.util.spec_from_file_location("select_short_term_candidates", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeCalendar:
    def status(self, value: date) -> bool | None:
        return True

    def latest_on_or_before(self, value: date) -> date | None:
        return date(2026, 8, 7)

    def next_on_or_after(self, value: date) -> date | None:
        return date(2026, 8, 11)


class FakeRuntime:
    def __init__(self, latest_daily: date = date(2026, 8, 10), lane_result: int = 0) -> None:
        self.calendar = FakeCalendar()
        self.latest_daily = latest_daily
        self.lane_calls: list[tuple[str, ...]] = []
        self.analysis_date: date | None = None
        self.refresh_calls: list[tuple[date, date]] = []
        self.lane_result = lane_result

    def run_lanes(self, strategies: tuple[str, ...]) -> int:
        self.lane_calls.append(strategies)
        return self.lane_result

    def latest_daily_trade_date(self) -> date | None:
        return self.latest_daily

    def refresh_reference_data(self, start: date, end: date) -> int:
        self.refresh_calls.append((start, end))
        return 0

    def execute(self, *, context, analysis_date: date, trading_date: date) -> SelectionReport:
        self.analysis_date = analysis_date
        return SelectionReport(
            analysis_date=analysis_date,
            trading_date=trading_date,
            market_status="ALLOW",
            market_reasons=("测试",),
            items=(),
            rejection_counts={},
        )


def test_intraday_uses_previous_completed_trade_date() -> None:
    runtime = FakeRuntime()

    result = MODULE.main(
        ["--at", "2026-08-10T10:00:00+08:00", "--skip-lanes"],
        runtime_factory=lambda args: runtime,
    )

    assert result == 0
    assert runtime.analysis_date == date(2026, 8, 7)


def test_post_market_stale_daily_data_fails_without_prices(capsys) -> None:
    runtime = FakeRuntime(latest_daily=date(2026, 8, 7))

    result = MODULE.main(
        ["--at", "2026-08-10T16:00:00+08:00", "--skip-lanes"],
        runtime_factory=lambda args: runtime,
    )

    output = capsys.readouterr().out
    assert result == 2
    assert "当日日线尚未完整入库" in output
    assert "触发价" not in output
    assert runtime.analysis_date is None


def test_default_manual_run_executes_all_four_lanes() -> None:
    runtime = FakeRuntime()

    result = MODULE.main(
        ["--at", "2026-08-10T10:00:00+08:00"],
        runtime_factory=lambda args: runtime,
    )

    assert result == 0
    assert runtime.lane_calls == [
        ("combined", "ma5", "five_factor", "bottom_breakout")
    ]


def test_legacy_lane_failure_cannot_block_the_new_full_universe_selector() -> None:
    runtime = FakeRuntime(lane_result=1)
    result = MODULE.main(
        ["--at", "2026-08-10T10:00:00+08:00"],
        runtime_factory=lambda args: runtime,
    )
    assert result == 0
    assert runtime.analysis_date == date(2026, 8, 7)


def test_reference_refresh_is_explicit_and_uses_the_bounded_analysis_window() -> None:
    runtime = FakeRuntime()
    result = MODULE.main(
        [
            "--at",
            "2026-08-10T10:00:00+08:00",
            "--skip-lanes",
            "--refresh-reference-data",
        ],
        runtime_factory=lambda args: runtime,
    )
    assert result == 0
    assert runtime.refresh_calls == [(date(2026, 2, 8), date(2026, 8, 7))]


def test_json_output_serializes_new_tiers_and_setup_types(capsys) -> None:
    class Runtime(FakeRuntime):
        def execute(self, *, context, analysis_date: date, trading_date: date):
            self.analysis_date = analysis_date
            item = BuyPointRuntimeItem(
                code="600001",
                name="虚构股份",
                tier=CandidateTier.SHADOW,
                setup_type=SetupType.PRE_BREAKOUT,
                reason_code="FORWARD_GATE_NOT_READY",
                missing_fields=(),
                plan=None,
                maximum_shares=0,
            )
            return BuyPointRuntimeReport(
                analysis_date,
                trading_date,
                "buy-point-selection-3.0.0",
                "SHADOW",
                (),
                (),
                (item,),
                {},
            )

    runtime = Runtime()
    assert MODULE.main(
        ["--at", "2026-08-10T10:00:00+08:00", "--skip-lanes", "--output", "json"],
        runtime_factory=lambda args: runtime,
    ) == 0
    import json

    payload = json.loads(capsys.readouterr().out)
    assert payload["shadow"][0]["tier"] == "SHADOW"
    assert payload["shadow"][0]["setup_type"] == "PRE_BREAKOUT"


def test_unknown_calendar_fails_closed(capsys) -> None:
    runtime = FakeRuntime()
    runtime.calendar.status = lambda value: None

    result = MODULE.main(
        ["--at", "2026-08-10T10:00:00+08:00", "--skip-lanes"],
        runtime_factory=lambda args: runtime,
    )

    assert result == 2
    assert "交易日历无法确认" in capsys.readouterr().out


def test_empty_lane_is_persisted_as_a_completed_bucket(monkeypatch) -> None:
    from scripts.tools import portfolio_db, selection_strategy_bridge

    calls: list[tuple[date, list[dict[str, object]], str]] = []
    monkeypatch.setattr(
        portfolio_db,
        "save_selection_daily_results",
        lambda trade_date, rows, *, strategy: calls.append(
            (trade_date, rows, strategy)
        ) or 0,
    )

    result = selection_strategy_bridge.persist_strategy_rows(
        date(2026, 8, 11), [], "bottom_breakout"
    )

    assert result == 0
    assert calls == [(date(2026, 8, 11), [], "bottom_breakout")]


def test_baseline_policy_does_not_load_a_relative_strength_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "load_promoted_policy", lambda *args, **kwargs: BASELINE_POLICY)
    monkeypatch.setattr(
        MODULE,
        "load_relative_strength_snapshot",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("relative strength should not be loaded for 2.0")
        ),
    )

    policy, percentiles = MODULE.resolve_runtime_policy(object(), date(2026, 8, 10))

    assert policy == BASELINE_POLICY
    assert percentiles is None


def test_promoted_policy_requires_95_percent_cross_section_coverage(monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "load_promoted_policy", lambda *args, **kwargs: STRICT_B)
    monkeypatch.setattr(
        MODULE,
        "load_relative_strength_snapshot",
        lambda *args, **kwargs: SimpleNamespace(
            current_trade_date=date(2026, 8, 10),
            coverage_ratio=0.949,
            is_usable=False,
            percentiles={},
        ),
    )

    with pytest.raises(MODULE.CliInputError, match="覆盖率"):
        MODULE.resolve_runtime_policy(object(), date(2026, 8, 10))


def test_promoted_policy_returns_the_full_market_percentiles(monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "load_promoted_policy", lambda *args, **kwargs: STRICT_B)
    monkeypatch.setattr(
        MODULE,
        "load_relative_strength_snapshot",
        lambda *args, **kwargs: SimpleNamespace(
            current_trade_date=date(2026, 8, 10),
            coverage_ratio=0.98,
            is_usable=True,
            percentiles={"600001": 0.91},
        ),
    )

    policy, percentiles = MODULE.resolve_runtime_policy(object(), date(2026, 8, 10))

    assert policy == STRICT_B
    assert percentiles == {"600001": 0.91}
