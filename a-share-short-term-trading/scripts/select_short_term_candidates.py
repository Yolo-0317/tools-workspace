#!/usr/bin/env python3
"""Manually run buy-point-first full-universe selection and print an auditable report."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, replace
from datetime import date, datetime, time, timedelta, timezone
import json
from io import StringIO
from pathlib import Path
import sys
from typing import Callable, Protocol

from collections import Counter
from decimal import Decimal
from sqlalchemy import text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
STOCK_AI_ROOT = WORKSPACE_ROOT / "stock-ai"
for path in (PROJECT_ROOT, STOCK_AI_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from short_term_trading.capture import capture_chip
from short_term_trading.buy_point_selection_service import (
    AccountEvidence,
    BuyPointRuntimeReport,
    ChipEvidence,
    MaterializationDependencies,
    MaterializationRequest,
    advance_buy_point_plan_states,
    materialize_buy_point_selection,
    persist_buy_point_runtime,
    render_buy_point_runtime_report,
)
from short_term_trading.evidence import CaptureRecorder
from short_term_trading.market_capture import build_default_market_state_provider
from short_term_trading.repositories import EvidenceRepository, PlanningRepository
from short_term_trading.selection_service import (
    SelectionReport,
    render_selection_report,
)
from short_term_trading.session import TradingCalendar, TradingSession, classify_trading_session
from stock_ai.buy_point_selection.gates import (
    anti_chase_gate,
    base_gate,
    classify_market,
    sector_gate,
)
from stock_ai.buy_point_selection.models import (
    BuyPointBar,
    MarketSnapshot,
    SectorSnapshot,
    SelectionPolicy as BuyPointPolicy,
)
from stock_ai.buy_point_selection.patterns import detect_setups
from stock_ai.buy_point_selection.planning import RiskBudget
from stock_ai.buy_point_selection.reference_data import (
    ReferenceCoverage,
    RiskFlag,
    SQLReferenceRepository,
    SectorMembership,
)
from stock_ai.buy_point_selection.service import (
    BuyPointSelectionResult,
    CandidateEvidence,
    LegacyShadow,
    SelectionInput as BuyPointSelectionInput,
    select_buy_points,
)
from stock_ai.market_codes import is_sh_sz_main_board_code, normalize_code6
from stock_ai.buy_point_selection.validation import (
    load_historical_release,
    policy_hash as buy_point_policy_hash,
)
from short_term_trading.evidence import is_chip_snapshot_for_trade_date
from stock_ai.relative_strength import load_relative_strength_snapshot
from stock_ai.selection_validation import load_promoted_policy
from stock_ai.short_term_selection import SelectionPolicy


LANES = ("combined", "ma5", "five_factor", "bottom_breakout")
VALIDATION_ARTIFACT = STOCK_AI_ROOT / "config" / "short_term_selection_validation.json"
BUY_POINT_VALIDATION_ARTIFACT = (
    STOCK_AI_ROOT / "config" / "buy_point_selection_validation.json"
)


class CliInputError(RuntimeError):
    """Expected safe failure whose message may be printed to the user."""


def resolve_runtime_policy(
    engine: object,
    analysis_date: date,
    *,
    artifact_path: Path = VALIDATION_ARTIFACT,
) -> tuple[SelectionPolicy, dict[str, float] | None]:
    policy = load_promoted_policy(
        artifact_path,
        expected_data_end=analysis_date,
    )
    if not policy.strict:
        return policy, None
    snapshot = load_relative_strength_snapshot(engine, analysis_date)
    if snapshot.current_trade_date != analysis_date or not snapshot.is_usable:
        raise CliInputError(
            f"2.1 全市场相对强度覆盖率不足 95%（当前 {snapshot.coverage_ratio:.2%}），已停止选股"
        )
    return policy, dict(snapshot.percentiles)


class SelectionCliRuntime(Protocol):
    calendar: TradingCalendar

    def run_lanes(self, strategies: tuple[str, ...]) -> int: ...

    def latest_daily_trade_date(self) -> date | None: ...

    def refresh_reference_data(self, start: date, end: date) -> int: ...

    def execute(
        self, *, context: object, analysis_date: date, trading_date: date
    ) -> object: ...


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="手动运行短线自动选股（不会自动下单）")
    parser.add_argument("--output", choices=("text", "json"), default="text")
    parser.add_argument("--at", help="带时区 ISO 时间，仅用于复现")
    parser.add_argument(
        "--skip-lanes",
        action="store_true",
        help="仅在人工重试/测试时复用已落库的旧策略影子结果",
    )
    parser.add_argument(
        "--refresh-reference-data",
        action="store_true",
        help="显式刷新点时行业、ST 与重大公告参考数据",
    )
    return parser


def _row_value(row: object, name: str):
    if isinstance(row, dict):
        return row[name]
    return getattr(row, name)


def load_main_board_panel(
    engine: object,
    analysis_date: date,
    *,
    lookback_calendar_days: int = 180,
) -> dict[str, tuple[BuyPointBar, ...]]:
    """Load the complete bounded main-board panel in one SQL query."""
    start_date = analysis_date - timedelta(days=lookback_calendar_days)
    statement = """
        SELECT ts_code, trade_date, open, high, low, close, pct_chg, amount
        FROM stock_daily
        WHERE trade_date BETWEEN :start_date AND :analysis_date
        ORDER BY ts_code, trade_date
    """
    with engine.connect() as connection:
        rows = connection.execute(
            text(statement),
            {"start_date": start_date, "analysis_date": analysis_date},
        ).mappings()
        loaded = list(rows)
    grouped: dict[str, dict[date, BuyPointBar]] = {}
    for row in loaded:
        code = normalize_code6(str(_row_value(row, "ts_code")))
        if not is_sh_sz_main_board_code(code):
            continue
        trade_date = _row_value(row, "trade_date")
        if not isinstance(trade_date, date):
            trade_date = date.fromisoformat(str(trade_date)[:10])
        values = (
            _row_value(row, "open"),
            _row_value(row, "high"),
            _row_value(row, "low"),
            _row_value(row, "close"),
            _row_value(row, "amount"),
        )
        if any(value is None for value in values):
            continue
        grouped.setdefault(code, {})[trade_date] = BuyPointBar(
            trade_date=trade_date,
            open=Decimal(str(values[0])),
            high=Decimal(str(values[1])),
            low=Decimal(str(values[2])),
            close=Decimal(str(values[3])),
            pct_chg=Decimal(str(_row_value(row, "pct_chg") or 0)),
            amount_qian=Decimal(str(values[4])),
        )
    return {
        code: tuple(value for _, value in sorted(by_date.items()))[-120:]
        for code, by_date in grouped.items()
    }


def _average(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def _sector_snapshots(
    panel: dict[str, tuple[BuyPointBar, ...]],
    memberships: dict[str, SectorMembership],
    policy: BuyPointPolicy,
) -> dict[str, SectorSnapshot]:
    grouped: dict[str, list[tuple[str, tuple[BuyPointBar, ...]]]] = {}
    names: dict[str, str] = {}
    for code, membership in memberships.items():
        bars = panel.get(code, ())
        if len(bars) < 20:
            continue
        grouped.setdefault(membership.sector_code, []).append((code, bars))
        names[membership.sector_code] = membership.sector_name
    returns = {
        sector: _average([bars[-1].close / bars[-6].close - Decimal("1") for _, bars in members])
        for sector, members in grouped.items()
        if members and all(len(bars) >= 10 for _, bars in members)
    }
    ordered_returns = sorted(returns.values())
    snapshots: dict[str, SectorSnapshot] = {}
    for sector, members in grouped.items():
        if sector not in returns:
            continue
        liquid = [
            (code, bars)
            for code, bars in members
            if _average([value.amount_qian for value in bars[-5:]])
            >= policy.min_average_amount5_qian
        ]
        strengthening = sum(
            bars[-1].close >= _average([value.close for value in bars[-20:]])
            and bars[-1].pct_chg > 0
            for _, bars in liquid
        )
        advancing = sum(bars[-1].pct_chg > 0 for _, bars in liquid)
        recent_amount = sum(
            (value.amount_qian for _, bars in liquid for value in bars[-5:]), Decimal("0")
        )
        prior_amount = sum(
            (value.amount_qian for _, bars in liquid for value in bars[-10:-5]), Decimal("0")
        )
        rank = ordered_returns.index(returns[sector]) + 1
        snapshots[sector] = SectorSnapshot(
            sector_code=sector,
            sector_name=names[sector],
            return_percentile=rank / len(ordered_returns),
            liquid_member_count=len(liquid),
            strengthening_member_count=strengthening,
            breadth_ratio=advancing / len(liquid) if liquid else 0.0,
            amount_ratio=float(recent_amount / prior_amount) if prior_amount > 0 else 0.0,
            membership_complete=True,
        )
    return snapshots


def _cumulative_return_pct(bars: tuple[BuyPointBar, ...], sessions: int) -> Decimal:
    return (bars[-1].close / bars[-sessions - 1].close - Decimal("1")) * Decimal("100")


def market_snapshot_from_view(value: object, analysis_date: date) -> MarketSnapshot:
    indexes = getattr(value, "indexes_above_ma20", None)
    breadth = getattr(value, "breadth_pct", None)
    amount_ratio = getattr(value, "amount_ratio", None)
    complete = (
        getattr(value, "trading_date", None) == analysis_date
        and indexes is not None
        and breadth is not None
        and amount_ratio is not None
        and bool(getattr(value, "evidence_refs", ()))
    )
    return MarketSnapshot(
        indexes_above_ma20=int(indexes or 0),
        breadth_pct=float(breadth or 0),
        amount_ratio=float(amount_ratio or 0),
        complete=complete,
    )


def scan_buy_point_universe(
    *,
    panel: dict[str, tuple[BuyPointBar, ...]],
    analysis_date: date,
    holding_codes: set[str],
    risk_flags_by_code: dict[str, tuple[RiskFlag, ...]],
    memberships: dict[str, SectorMembership],
    coverage: ReferenceCoverage,
    market_snapshot: MarketSnapshot,
    risk_budget: RiskBudget,
    account_fresh: bool,
    existing_structure_ids: frozenset[str],
    legacy_shadow: tuple[LegacyShadow, ...],
    policy: BuyPointPolicy | None = None,
) -> BuyPointSelectionResult:
    resolved = policy or BuyPointPolicy()
    sector_values = _sector_snapshots(panel, memberships, resolved)
    candidates: list[CandidateEvidence] = []
    prefilter_rejections: Counter[str] = Counter()
    for code, bars in sorted(panel.items()):
        if not bars or bars[-1].trade_date != analysis_date:
            prefilter_rejections["LATEST_BAR_MISSING"] += 1
            continue
        base = base_gate(code, bars, holding_codes, risk_flags_by_code, resolved)
        if not base.passed:
            prefilter_rejections.update(base.reasons)
            continue
        setups = detect_setups(code, bars, resolved)
        if not setups:
            prefilter_rejections["NO_BUY_POINT_SETUP"] += 1
            continue
        setup = max(setups, key=lambda value: (value.quality, value.setup_type.value))
        ma5 = _average([value.close for value in bars[-5:]])
        ma20 = _average([value.close for value in bars[-20:]])
        anti = anti_chase_gate(
            bars[-1].pct_chg,
            _cumulative_return_pct(bars, 3),
            _cumulative_return_pct(bars, 5),
            (bars[-1].close / ma5 - Decimal("1")) * Decimal("100"),
            (bars[-1].close / ma20 - Decimal("1")) * Decimal("100"),
            resolved,
        )
        if not anti.passed:
            prefilter_rejections.update(anti.reasons)
            continue
        membership = memberships.get(code)
        missing: list[str] = []
        gate_reasons: tuple[str, ...] = ()
        percentile: Decimal | None = None
        sector_code: str | None = None
        if not coverage.sector_complete or membership is None:
            missing.append("SECTOR")
        else:
            sector_code = membership.sector_code
            sector_value = sector_values.get(sector_code)
            if sector_value is None:
                missing.append("SECTOR")
            else:
                decision = sector_gate(sector_value, resolved)
                gate_reasons = decision.reasons
                percentile = Decimal(str(sector_value.return_percentile))
        candidates.append(
            CandidateEvidence(
                code=code,
                name=code,
                setup=setup,
                bars=bars,
                sector_code=sector_code,
                sector_percentile=percentile,
                average_amount5_qian=_average([value.amount_qian for value in bars[-5:]]),
                gate_reasons=gate_reasons,
                missing_fields=tuple(missing),
            )
        )
    market = classify_market(market_snapshot)
    result = select_buy_points(
        BuyPointSelectionInput(
            market_status=market.status,
            candidates=tuple(candidates),
            legacy_shadow=legacy_shadow,
            risk_budget=risk_budget,
            existing_structure_ids=existing_structure_ids,
            risk_coverage_complete=coverage.st_complete and coverage.announcement_complete,
            account_fresh=account_fresh,
            policy=resolved,
        )
    )
    combined = Counter(result.rejection_counts)
    combined.update(prefilter_rejections)
    return BuyPointSelectionResult(
        qualified=result.qualified,
        observe=result.observe,
        shadow=result.shadow,
        rejection_counts=dict(sorted(combined.items())),
    )


def _resolve_dates(now: datetime, calendar: TradingCalendar) -> tuple[object, date, date]:
    context = classify_trading_session(now, calendar)
    if not context.calendar_confirmed:
        raise CliInputError("交易日历无法确认，已停止选股")
    today = context.local_now.date()
    if context.session is TradingSession.NON_TRADING_DAY:
        analysis_date = calendar.latest_on_or_before(today)
        trading_date = calendar.next_on_or_after(today)
    elif context.session is TradingSession.POST_MARKET:
        analysis_date = today
        trading_date = calendar.next_on_or_after(today + timedelta(days=1))
    else:
        analysis_date = calendar.latest_on_or_before(today - timedelta(days=1))
        trading_date = today
    if analysis_date is None or trading_date is None:
        raise CliInputError("无法确定完整日线日期或下一交易日")
    return replace(
        context,
        diagnosis_trade_date=analysis_date,
        next_trade_date=trading_date,
    ), analysis_date, trading_date


class DefaultRuntime:
    def __init__(self) -> None:
        from dotenv import load_dotenv
        from scripts.tools import portfolio_db
        from short_term_trading.diagnosis_runtime import StockAiTradingCalendar

        load_dotenv(STOCK_AI_ROOT / ".env", override=False)
        self.calendar = StockAiTradingCalendar()
        self._portfolio_db = portfolio_db
        self._engine = portfolio_db.get_engine()
        if self._engine is None:
            raise CliInputError("MySQL 配置不可用")
        self._evidence = EvidenceRepository(self._engine)
        self._planning = PlanningRepository(self._engine)

    def run_lanes(self, strategies: tuple[str, ...]) -> int:
        if strategies != LANES:
            raise CliInputError("短线选股必须运行完整四轨")
        from scripts.selection.run_parallel_selection import main as run_parallel

        return run_parallel()

    def latest_daily_trade_date(self) -> date | None:
        return self._portfolio_db.latest_stock_daily_trade_date(engine=self._engine)

    def refresh_reference_data(self, start: date, end: date) -> int:
        from scripts.sync.sync_buy_point_reference_data import main as sync_references

        return sync_references(
            ["--start", start.isoformat(), "--end", end.isoformat()]
        )

    def execute(
        self, *, context: object, analysis_date: date, trading_date: date
    ) -> BuyPointRuntimeReport:
        from scripts.tools.portfolio_db import (
            load_account,
            load_holding_codes,
            load_selection_daily_results,
            mysql_url,
        )
        policy = BuyPointPolicy()
        panel = load_main_board_panel(self._engine, analysis_date)
        if not panel:
            raise CliInputError("主板全市场日线面板为空")
        references = SQLReferenceRepository(self._engine)
        coverage = references.coverage(analysis_date)
        memberships = references.membership_on(analysis_date)
        risk_flags = references.risk_flags_on(analysis_date)

        legacy_rows: list[LegacyShadow] = []
        seen_legacy: set[tuple[str, str]] = set()
        for lane in LANES:
            lane_date, rows = load_selection_daily_results(
                analysis_date, strategy=lane, engine=self._engine
            )
            if lane_date != analysis_date:
                continue
            for row in rows:
                code = normalize_code6(str(row.get("代码") or row.get("code") or ""))
                identity = (code, lane)
                if identity in seen_legacy:
                    continue
                seen_legacy.add(identity)
                legacy_rows.append(
                    LegacyShadow(
                        code=code,
                        name=str(row.get("名称") or row.get("name") or code),
                        source=f"legacy-{lane}",
                        reasons=("RESEARCH_ONLY",),
                    )
                )

        account = load_account(engine=self._engine)
        account_fresh = bool(
            account is not None
            and account.snapshot_date is not None
            and account.snapshot_date >= analysis_date
            and account.available_cash is not None
        )
        cash = Decimal(str(account.available_cash or 0)) if account else Decimal("0")
        market_value = Decimal(str(account.market_value or 0)) if account else Decimal("0")
        risk_budget = RiskBudget(
            loss_budget=min(Decimal("500"), cash * Decimal("0.01")),
            ticket_limit=min(Decimal("4000"), cash),
            remaining_exposure=max(Decimal("0"), Decimal("40000") - market_value),
        )
        market_state = build_default_market_state_provider(mysql_url()).get_state(context)
        market_snapshot = market_snapshot_from_view(market_state, analysis_date)

        prepared = self._planning.load_prepared_buy_point_plans(policy.rule_version)
        resolved_market_status = getattr(
            market_state.status, "value", str(market_state.status)
        )
        state_events = advance_buy_point_plan_states(
            prepared,
            panel,
            resolved_market_status,
            risk_flags,
        )
        for event in state_events:
            self._planning.append_plan_event(event)
        existing = self._planning.load_buy_point_structure_ids(policy.rule_version)
        result = scan_buy_point_universe(
            panel=panel,
            analysis_date=analysis_date,
            holding_codes=load_holding_codes(engine=self._engine),
            risk_flags_by_code=risk_flags,
            memberships=memberships,
            coverage=coverage,
            market_snapshot=market_snapshot,
            risk_budget=risk_budget,
            account_fresh=account_fresh,
            existing_structure_ids=existing,
            legacy_shadow=tuple(legacy_rows),
            policy=policy,
        )

        chips: dict[str, ChipEvidence] = {}
        evidence_refs: dict[str, tuple[str, ...]] = {}
        recorder = CaptureRecorder(self._evidence)
        for item in result.qualified:
            snapshot = self._evidence.get_latest_valid_snapshot(item.code, "chip")
            if not is_chip_snapshot_for_trade_date(snapshot, analysis_date):
                try:
                    capture_chip(item.code, recorder)
                except Exception:
                    snapshot = None
                else:
                    snapshot = self._evidence.get_latest_valid_snapshot(item.code, "chip")
            if is_chip_snapshot_for_trade_date(snapshot, analysis_date):
                chips[item.code] = ChipEvidence(
                    item.code,
                    analysis_date,
                    Decimal(str(snapshot.data["cost_90_high"])),
                )
                evidence_refs[item.code] = (str(snapshot.snapshot_id),)

        sector_exposure: dict[str, Decimal] = {}
        for holding_code in load_holding_codes(engine=self._engine):
            membership = memberships.get(holding_code)
            if membership is not None:
                sector_exposure[membership.sector_code] = Decimal("1")
        account_evidence = None
        if account is not None and account.snapshot_date is not None:
            account_evidence = AccountEvidence(
                captured_at=datetime.combine(
                    account.snapshot_date, time(7, 0), tzinfo=timezone.utc
                ),
                available_cash=cash,
                total_exposure=market_value,
                sector_exposure=sector_exposure,
            )
        historical_release = load_historical_release(
            BUY_POINT_VALIDATION_ARTIFACT,
            expected_rule_version=policy.rule_version,
            expected_policy_hash=buy_point_policy_hash(policy),
        )
        dependencies = MaterializationDependencies(
            chips_by_code=chips,
            account=account_evidence,
            historical_release=historical_release,
            forward_gate=self._planning.forward_gate_summary(policy.rule_version),
            evidence_refs_by_code=evidence_refs,
        )
        request = MaterializationRequest(
            analysis_date=analysis_date,
            trading_date=trading_date,
            as_of=getattr(context, "now_utc"),
            market_status=resolved_market_status,
            request_live=True,
            rule_version=policy.rule_version,
        )
        report = materialize_buy_point_selection(result, dependencies, request)
        persist_buy_point_runtime(
            report,
            result,
            dependencies,
            request,
            self._planning,
            resolved_count=len(state_events),
            duplicate_count=int(result.rejection_counts.get("EXISTING_STRUCTURE", 0)),
        )
        return report


def default_runtime(_: argparse.Namespace) -> SelectionCliRuntime:
    return DefaultRuntime()


def _report_dict(report: object) -> dict[str, object]:
    payload = asdict(report)
    payload["analysis_date"] = report.analysis_date.isoformat()
    payload["trading_date"] = report.trading_date.isoformat()
    for key in ("items", "formal", "observe", "shadow"):
        for item in payload.get(key, []):
            plan = item.get("plan")
            if plan is not None and hasattr(plan, "model_dump"):
                item["plan"] = plan.model_dump(mode="json")
    return payload


def main(
    argv: list[str] | None = None,
    *,
    runtime_factory: Callable[[argparse.Namespace], SelectionCliRuntime] | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    now = datetime.now(timezone.utc)
    if args.at:
        try:
            now = datetime.fromisoformat(args.at)
        except ValueError:
            print("短线自动选股失败：--at 必须是合法 ISO 时间")
            return 2
        if now.tzinfo is None or now.utcoffset() is None:
            print("短线自动选股失败：--at 必须包含时区")
            return 2
    try:
        runtime = (runtime_factory or default_runtime)(args)
        if not args.skip_lanes:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                runtime.run_lanes(LANES)
        context, analysis_date, trading_date = _resolve_dates(now, runtime.calendar)
        if args.refresh_reference_data:
            refresh = getattr(runtime, "refresh_reference_data", None)
            if not callable(refresh):
                raise CliInputError("运行时不支持点时参考数据刷新")
            if refresh(analysis_date - timedelta(days=180), analysis_date) != 0:
                raise CliInputError("点时参考数据刷新失败")
        latest = runtime.latest_daily_trade_date()
        if context.session is TradingSession.POST_MARKET and latest != analysis_date:
            raise CliInputError("当日日线尚未完整入库，未生成交易价位")
        if latest is None or latest < analysis_date:
            raise CliInputError("完整日线尚未入库，未生成交易价位")
        report = runtime.execute(
            context=context,
            analysis_date=analysis_date,
            trading_date=trading_date,
        )
    except CliInputError as exc:
        print(f"短线自动选股失败：{exc}")
        return 2
    except Exception:
        print("短线自动选股失败：数据或配置不可用，未生成交易价位")
        return 2

    if args.output == "json":
        print(json.dumps(_report_dict(report), ensure_ascii=False, indent=2))
    else:
        if isinstance(report, BuyPointRuntimeReport):
            print(render_buy_point_runtime_report(report))
        else:
            print(render_selection_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
