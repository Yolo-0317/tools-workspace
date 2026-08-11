from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from short_term_trading.daily_sync import DailyBar
from short_term_trading.diagnosis import RiskProfile
from short_term_trading.evidence import EvidenceSnapshot
from short_term_trading.market_regime import MarketStateView
from short_term_trading.selection_service import (
    SelectionDependencies,
    SelectionRequest,
    materialize_short_term_selection,
    render_selection_report,
)
from stock_ai.short_term_selection import CandidateSignal, RejectedSignal, SelectionResult


UTC = timezone.utc
ANALYSIS_DATE = date(2026, 8, 10)
NOW = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)


def _bars(code: str) -> list[DailyBar]:
    result: list[DailyBar] = []
    start = ANALYSIS_DATE - timedelta(days=29)
    for index in range(30):
        close = 9.0 + index * 0.05
        result.append(
            DailyBar(
                ts_code=code,
                exch_code="SH" if code.startswith("6") else "SZ",
                trade_date=start + timedelta(days=index),
                open=close - 0.03,
                high=close + 0.10,
                low=close - 0.10,
                close=close,
                pre_close=None,
                change_amount=0.05,
                pct_chg=0.5,
                vol=1000,
                amount=200_000,
            )
        )
    return result


def _signal(code: str = "600000", candidate_type: str = "BREAKOUT") -> CandidateSignal:
    return CandidateSignal(
        code=code,
        name=f"测试{code}",
        sector="测试行业",
        candidate_type=candidate_type,
        setup_score=82.5,
        liquidity_score=0.8,
        trend_score=0.9,
        catalyst_score=0.2,
        source_strategies=("combined", "ma5"),
        reasons=("趋势完整", "量价配合"),
        metrics={"ma5": 10.3, "ma10": 10.1, "ma20": 9.8},
    )


def _selection(*signals: CandidateSignal) -> SelectionResult:
    return SelectionResult(
        analysis_date=ANALYSIS_DATE,
        candidates=signals or (_signal(),),
        rejected=(RejectedSignal("600099", "LIQUIDITY"),),
    )


def _chip(code: str = "600000", source_date: date = ANALYSIS_DATE) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        snapshot_id=f"00000000-0000-4000-8000-{int(code):012d}",
        code=code,
        kind="chip",
        as_of=NOW,
        source="test-chip",
        parser_version="1",
        data={
            "source_trade_date": source_date.isoformat(),
            "cost_90_low": 9.7,
            "cost_90_high": 10.0,
            "average_cost": 9.85,
            "profit_ratio": 60.0,
            "concentration": 30.0,
            "input_bar_count": 30,
            "method": "test",
        },
        raw_evidence_ref=f"test:chip:{code}",
    )


@dataclass
class FakeEvidence:
    chips: dict[str, EvidenceSnapshot | None]
    saved: list[EvidenceSnapshot] = field(default_factory=list)

    def save_snapshot(self, snapshot: EvidenceSnapshot) -> None:
        self.saved.append(snapshot)

    def get_latest_valid_snapshot(self, code: str, kind: str) -> EvidenceSnapshot | None:
        assert kind == "chip"
        return self.chips.get(code)


@dataclass
class FakePlanning:
    saved_candidates: list[object] = field(default_factory=list)
    saved_plans: list[object] = field(default_factory=list)

    def upsert_candidate(self, candidate: object) -> None:
        self.saved_candidates.append(candidate)

    def upsert_plan(self, plan: object) -> None:
        self.saved_plans.append(plan)


def _request(status: str = "ALLOW", approved: bool = True) -> SelectionRequest:
    return SelectionRequest(
        analysis_date=ANALYSIS_DATE,
        trading_date=date(2026, 8, 11),
        now=NOW,
        market_state=MarketStateView(
            status=status,
            trading_date=ANALYSIS_DATE,
            as_of=NOW,
            expires_at=NOW + timedelta(days=1),
            indexes_above_ma20=2,
            breadth_pct=65,
            amount_ratio=1.1,
            strong_sector_count=3,
            reasons=("市场可交易",),
        ),
        risk_profile=RiskProfile(1000, 20_000, 20_000),
        portfolio_approved=approved,
    )


def _dependencies(
    *,
    chips: dict[str, EvidenceSnapshot | None] | None = None,
    failing_code: str | None = None,
    refreshed_chip: EvidenceSnapshot | None = None,
) -> tuple[SelectionDependencies, FakeEvidence, FakePlanning, list[str]]:
    evidence = FakeEvidence(chips or {"600000": _chip()})
    planning = FakePlanning()
    refreshed: list[str] = []

    def load_bars(code: str, analysis_date: date) -> list[DailyBar]:
        if code == failing_code:
            raise RuntimeError("simulated bar failure")
        assert analysis_date == ANALYSIS_DATE
        return _bars(code)

    def refresh_chip(code: str, analysis_date: date) -> None:
        refreshed.append(code)
        if refreshed_chip is not None:
            evidence.chips[code] = refreshed_chip

    return (
        SelectionDependencies(
            evidence_repository=evidence,
            planning_repository=planning,
            load_daily_bars=load_bars,
            refresh_chip=refresh_chip,
        ),
        evidence,
        planning,
        refreshed,
    )


def test_materializer_saves_candidate_and_executable_plan() -> None:
    dependencies, evidence, planning, _ = _dependencies()

    report = materialize_short_term_selection(_selection(), dependencies, _request())

    assert report.items[0].status == "EXECUTABLE"
    assert planning.saved_candidates[-1].candidate_type == "BREAKOUT"
    assert planning.saved_candidates[-1].executable_status == "EXECUTABLE"
    assert planning.saved_plans[0].risk_reward_ratio >= Decimal("1.5")
    assert planning.saved_plans[0].evidence_refs[0] == evidence.saved[0].snapshot_id
    assert evidence.saved[0].raw_evidence_ref == "mysql:stock_daily:600000:2026-08-10"


def test_missing_chip_keeps_observation_but_saves_no_executable_plan() -> None:
    dependencies, _, planning, refreshed = _dependencies(chips={"600000": None})

    report = materialize_short_term_selection(_selection(), dependencies, _request())

    assert report.items[0].status == "OBSERVE"
    assert "筹码" in report.items[0].reason
    assert planning.saved_plans == []
    assert refreshed == ["600000"]


def test_stale_chip_is_refreshed_once_and_reloaded() -> None:
    old_chip = _chip(source_date=date(2026, 8, 9))
    dependencies, _, planning, refreshed = _dependencies(
        chips={"600000": old_chip}, refreshed_chip=_chip()
    )

    report = materialize_short_term_selection(_selection(), dependencies, _request())

    assert report.items[0].status == "EXECUTABLE"
    assert refreshed == ["600000"]
    assert len(planning.saved_plans) == 1


def test_one_symbol_failure_does_not_hide_other_valid_symbols() -> None:
    signals = (_signal("600001"), _signal("000001"))
    dependencies, evidence, _, _ = _dependencies(
        chips={"600001": _chip("600001"), "000001": _chip("000001")},
        failing_code="600001",
    )

    report = materialize_short_term_selection(_selection(*signals), dependencies, _request())

    assert [item.code for item in report.items] == ["000001"]
    assert report.rejection_counts["PLAN_ERROR"] == 1
    assert [snapshot.code for snapshot in evidence.saved] == ["000001"]


def test_limited_keeps_at_most_two_executable_candidates() -> None:
    signals = tuple(_signal(code) for code in ("600000", "600001", "000001"))
    dependencies, _, planning, _ = _dependencies(
        chips={code: _chip(code) for code in ("600000", "600001", "000001")}
    )

    report = materialize_short_term_selection(_selection(*signals), dependencies, _request("LIMITED"))

    assert len([item for item in report.items if item.status == "EXECUTABLE"]) == 2
    assert len(planning.saved_plans) == 3
    assert planning.saved_plans[-1].maximum_shares is None


def test_freeze_persists_zero_share_observation_plan() -> None:
    dependencies, _, planning, _ = _dependencies()

    report = materialize_short_term_selection(_selection(), dependencies, _request("FREEZE", False))

    assert report.items[0].status == "OBSERVE"
    assert planning.saved_plans[0].status.value == "NO_TRADE"
    assert planning.saved_plans[0].maximum_shares == 0


def test_renderer_contains_auditable_plan_and_no_order_disclaimer() -> None:
    dependencies, _, _, _ = _dependencies()
    report = materialize_short_term_selection(_selection(), dependencies, _request())

    rendered = render_selection_report(report)

    assert "分析数据日：2026-08-10" in rendered
    assert "市场状态：ALLOW" in rendered
    assert "突破" in rendered
    assert "触发价" in rendered and "第一减仓价" in rendered
    assert "LIQUIDITY：1" in rendered
    assert rendered.endswith("这是交易计划，不代表已经下单。")
