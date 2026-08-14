from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from short_term_trading.buy_point_selection_service import (
    AccountEvidence,
    ChipEvidence,
    MaterializationDependencies,
    MaterializationRequest,
    advance_buy_point_plan_states,
    materialize_buy_point_selection,
    persist_buy_point_runtime,
    render_buy_point_runtime_report,
)
from short_term_trading.contracts import TradePlanV3
from short_term_trading.repositories.planning import ForwardGateSummary
from stock_ai.buy_point_selection.models import (
    BuyPointBar,
    CandidateTier,
    DetectedSetup,
    SelectionPolicy,
    SetupType,
)
from stock_ai.buy_point_selection.planning import PricePlan
from stock_ai.buy_point_selection.service import (
    BuyPointSelectionResult,
    LegacyShadow,
    SelectionItem,
)
from stock_ai.buy_point_selection.validation import HistoricalRelease


ANALYSIS_DATE = date(2026, 8, 10)
TRADING_DATE = date(2026, 8, 11)
AS_OF = datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc)
EVIDENCE_ID = "60000000-0000-4000-8000-000000000001"
POLICY = SelectionPolicy()


def _setup() -> DetectedSetup:
    return DetectedSetup(
        code="600001",
        setup_type=SetupType.PRE_BREAKOUT,
        analysis_date=ANALYSIS_DATE,
        structure_start=date(2026, 7, 10),
        structure_high=Decimal("10.00"),
        structure_low=Decimal("9.77"),
        quality=Decimal("0.85"),
        reasons=("CONTRACTING_PLATFORM_NEAR_TOP",),
        metrics={},
    )


def _price_plan() -> PricePlan:
    return PricePlan(
        structure_id="0123456789abcdef0123456789abcdef",
        code="600001",
        setup_type=SetupType.PRE_BREAKOUT,
        signal_date=ANALYSIS_DATE,
        signal_close=Decimal("9.95"),
        trigger_price=Decimal("10.01"),
        invalidation_price=Decimal("9.71"),
        target_2r=Decimal("10.61"),
        risk_distance=Decimal("0.30"),
        risk_reward_ratio=Decimal("2"),
        maximum_shares=300,
        valid_through_trade_date=date(2026, 8, 12),
    )


def _result() -> BuyPointSelectionResult:
    item = SelectionItem(
        code="600001",
        name="虚构股份",
        tier=CandidateTier.FORMAL,
        setup=_setup(),
        sector_code="S1",
        sector_percentile=Decimal("0.80"),
        average_amount5_qian=Decimal("150000"),
        plan=_price_plan(),
        missing_fields=(),
        reasons=(),
    )
    return BuyPointSelectionResult(
        qualified=(item,),
        observe=(),
        shadow=(LegacyShadow("600099", "旧影子", "legacy-three-up", ("RESEARCH_ONLY",)),),
        rejection_counts={},
    )


def _account(**changes) -> AccountEvidence:
    values = {
        "captured_at": AS_OF,
        "available_cash": Decimal("10000"),
        "total_exposure": Decimal("10000"),
        "sector_exposure": {},
    }
    values.update(changes)
    return AccountEvidence(**values)


def _deps(
    *,
    chip: ChipEvidence | None = None,
    account: AccountEvidence | None = None,
    historical_live: bool = True,
    forward_live: bool = True,
) -> MaterializationDependencies:
    resolved_chip = chip if chip is not None else ChipEvidence("600001", ANALYSIS_DATE, Decimal("10.80"))
    return MaterializationDependencies(
        chips_by_code={"600001": resolved_chip} if resolved_chip is not None else {},
        account=account or _account(),
        historical_release=HistoricalRelease(
            historical_live,
            POLICY.rule_version,
            "policy-hash",
            () if historical_live else ("HISTORICAL_PROMOTION_FAILED",),
        ),
        forward_gate=ForwardGateSummary(20, 20, 0, forward_live),
        evidence_refs_by_code={"600001": (EVIDENCE_ID,)},
    )


def _request(*, live: bool = True, market_status: str = "ALLOW") -> MaterializationRequest:
    return MaterializationRequest(
        analysis_date=ANALYSIS_DATE,
        trading_date=TRADING_DATE,
        as_of=AS_OF,
        market_status=market_status,
        request_live=live,
        rule_version=POLICY.rule_version,
    )


def test_missing_chip_downgrades_formal_to_observe_without_share_count() -> None:
    """Catches missing dated chip evidence silently retaining executable size."""
    deps = _deps()
    deps = MaterializationDependencies(
        chips_by_code={},
        account=deps.account,
        historical_release=deps.historical_release,
        forward_gate=deps.forward_gate,
        evidence_refs_by_code=deps.evidence_refs_by_code,
    )
    report = materialize_buy_point_selection(_result(), deps, _request())
    assert report.formal == ()
    assert report.observe[0].missing_fields == ("CHIP",)
    assert report.observe[0].maximum_shares is None
    assert "最大股数" not in render_buy_point_runtime_report(report).split("准备中观察", 1)[1]


def test_unpromoted_release_keeps_every_new_plan_shadow_only() -> None:
    """Catches historical or forward failure being bypassed by a strong current setup."""
    report = materialize_buy_point_selection(
        _result(), _deps(historical_live=False), _request(live=True)
    )
    assert report.release_mode == "SHADOW"
    assert report.formal == ()
    assert report.shadow[0].maximum_shares == 0
    assert all("最大股数" not in line for line in render_buy_point_runtime_report(report).splitlines()[1:])


def test_cost_overhang_before_two_r_downgrades_candidate() -> None:
    """Catches a chip resistance ceiling invalidating the promised 2R space."""
    chip = ChipEvidence("600001", ANALYSIS_DATE, Decimal("10.40"))
    report = materialize_buy_point_selection(_result(), _deps(chip=chip), _request())
    assert report.formal == ()
    assert report.observe[0].reason_code == "CHIP_RESISTANCE_BEFORE_2R"


def test_stale_account_cash_sector_and_freeze_each_remove_formal_permission() -> None:
    """Catches runtime account or market facts being treated as soft scores."""
    cases = (
        (_deps(account=_account(captured_at=AS_OF - timedelta(days=1))), _request(), "ACCOUNT_STALE"),
        (_deps(account=_account(available_cash=Decimal("1000"))), _request(), "INSUFFICIENT_CASH"),
        (_deps(account=_account(sector_exposure={"S1": Decimal("100")})), _request(), "SECTOR_EXPOSURE"),
        (_deps(), _request(market_status="FREEZE"), "MARKET_FREEZE"),
    )
    for dependencies, request, reason in cases:
        report = materialize_buy_point_selection(_result(), dependencies, request)
        assert report.formal == ()
        assert report.observe[0].reason_code == reason


def _bar(day: int, *, high: str, low: str, close: str = "9.90") -> BuyPointBar:
    return BuyPointBar(
        trade_date=date(2026, 8, day),
        open=Decimal("9.90"),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        pct_chg=Decimal("0"),
        amount_qian=Decimal("150000"),
    )


def _prepared_plan() -> TradePlanV3:
    return TradePlanV3(
        plan_id="60000000-0000-4000-8000-000000000002",
        candidate_id="60000000-0000-4000-8000-000000000003",
        analysis_date=ANALYSIS_DATE,
        trading_date=TRADING_DATE,
        code="600001",
        structure_id="0123456789abcdef0123456789abcdef",
        selection_tier="FORMAL",
        plan_state="PREPARED",
        signal_close=Decimal("9.95"),
        trigger_price=Decimal("10.01"),
        invalidation_price=Decimal("9.71"),
        target_2r=Decimal("10.61"),
        risk_distance=Decimal("0.30"),
        risk_reward_ratio=Decimal("2"),
        maximum_shares=300,
        market_status="ALLOW",
        valid_through_trade_date=date(2026, 8, 12),
        valid_session_count=2,
        rule_version=POLICY.rule_version,
        evidence_refs=(EVIDENCE_ID,),
        as_of=AS_OF,
        source="buy-point-selection",
        data_status="VALID",
    )


def test_previous_prepared_plan_expires_after_second_untriggered_session() -> None:
    """Catches stale prepared plans remaining actionable beyond their trigger window."""
    bars = (_bar(11, high="10.00", low="9.80"), _bar(12, high="10.00", low="9.80"))
    events = advance_buy_point_plan_states((_prepared_plan(),), {"600001": bars}, "ALLOW", {})
    assert events[0].new_state == "EXPIRED"


def test_structure_break_before_entry_invalidates_plan() -> None:
    """Catches a broken structure being left prepared merely because trigger was absent."""
    bars = (_bar(11, high="9.95", low="9.60"),)
    events = advance_buy_point_plan_states((_prepared_plan(),), {"600001": bars}, "ALLOW", {})
    assert events[0].new_state == "INVALIDATED"


def test_touching_trigger_changes_condition_state_but_does_not_claim_broker_open() -> None:
    """Catches a simulated trigger being mislabeled as a confirmed position opening."""
    bars = (_bar(11, high="10.05", low="9.80", close="10.02"),)
    events = advance_buy_point_plan_states((_prepared_plan(),), {"600001": bars}, "ALLOW", {})
    assert events[0].new_state == "TRIGGERED"
    assert events[0].reason_code == "PRICE_TRIGGER_SIMULATED"


def test_materialized_daily_run_is_handed_to_one_atomic_repository_call() -> None:
    """Catches report success diverging from the append-only daily ledger."""
    report = materialize_buy_point_selection(_result(), _deps(), _request())

    class Repository:
        def __init__(self):
            self.calls = []

        def save_buy_point_run(self, rows, forward_run):
            self.calls.append((rows, forward_run))

    repository = Repository()
    persist_buy_point_runtime(
        report,
        _result(),
        _deps(),
        _request(),
        repository,
        resolved_count=2,
        duplicate_count=1,
    )
    assert len(repository.calls) == 1
    rows, forward = repository.calls[0]
    assert len(rows) == 1
    assert rows[0][0].selection_tier == "FORMAL"
    assert rows[0][1].plan_state == "PREPARED"
    assert rows[0][2].new_state == "PREPARED"
    assert forward.formal_count == 1
    assert forward.shadow_count == 1
    assert forward.resolved_count == 2
