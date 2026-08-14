"""Deterministic allocation into qualified, observe, and legacy-shadow tiers."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_FLOOR
from typing import Mapping, Sequence

from stock_ai.market_codes import normalize_code6

from .models import BuyPointBar, CandidateTier, DetectedSetup, SelectionPolicy
from .planning import PricePlan, RiskBudget, build_price_plan, structure_id


@dataclass(frozen=True)
class CandidateEvidence:
    code: str
    name: str
    setup: DetectedSetup
    bars: tuple[BuyPointBar, ...]
    sector_code: str | None
    sector_percentile: Decimal | None
    average_amount5_qian: Decimal
    gate_reasons: tuple[str, ...]
    missing_fields: tuple[str, ...]


@dataclass(frozen=True)
class LegacyShadow:
    code: str
    name: str
    source: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SelectionItem:
    code: str
    name: str
    tier: CandidateTier
    setup: DetectedSetup
    sector_code: str | None
    sector_percentile: Decimal | None
    average_amount5_qian: Decimal
    plan: PricePlan | None
    missing_fields: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SelectionInput:
    market_status: str
    candidates: tuple[CandidateEvidence, ...]
    legacy_shadow: tuple[LegacyShadow, ...]
    risk_budget: RiskBudget
    existing_structure_ids: frozenset[str]
    risk_coverage_complete: bool
    account_fresh: bool
    policy: SelectionPolicy


@dataclass(frozen=True)
class BuyPointSelectionResult:
    qualified: tuple[SelectionItem, ...]
    observe: tuple[SelectionItem, ...]
    shadow: tuple[LegacyShadow, ...]
    rejection_counts: Mapping[str, int]


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _observe_item(
    value: CandidateEvidence,
    *,
    missing_fields: Sequence[str] = (),
    reasons: Sequence[str] = (),
) -> SelectionItem:
    return SelectionItem(
        code=normalize_code6(value.code),
        name=value.name,
        tier=CandidateTier.OBSERVE,
        setup=value.setup,
        sector_code=value.sector_code,
        sector_percentile=value.sector_percentile,
        average_amount5_qian=value.average_amount5_qian,
        plan=None,
        missing_fields=_unique(missing_fields),
        reasons=_unique(reasons),
    )


def _ranking_key(item: SelectionItem) -> tuple[Decimal | str, ...]:
    if item.plan is None:
        raise ValueError("qualified ranking requires a price plan")
    risk_pct = item.plan.risk_distance / item.plan.trigger_price
    return (
        -item.setup.quality,
        -item.plan.risk_reward_ratio,
        risk_pct,
        -(item.sector_percentile or Decimal("0")),
        -item.average_amount5_qian,
        item.code,
    )


def select_buy_points(value: SelectionInput) -> BuyPointSelectionResult:
    rejection_counts: Counter[str] = Counter()
    observe: list[SelectionItem] = []
    eligible: list[SelectionItem] = []

    for candidate in value.candidates:
        identity = structure_id(candidate.code, candidate.setup, value.policy.rule_version)
        if identity in value.existing_structure_ids:
            rejection_counts["EXISTING_STRUCTURE"] += 1
            continue
        if candidate.gate_reasons:
            rejection_counts.update(candidate.gate_reasons)
            continue

        missing = list(candidate.missing_fields)
        if candidate.sector_code is None and "SECTOR" not in missing:
            missing.append("SECTOR")
        if not value.risk_coverage_complete:
            missing.append("RISK_COVERAGE")
        if not value.account_fresh:
            missing.append("ACCOUNT_FRESHNESS")
        if missing:
            observe.append(_observe_item(candidate, missing_fields=missing, reasons=("DATA_INCOMPLETE",)))
            continue
        if value.market_status == "FREEZE":
            observe.append(_observe_item(candidate, reasons=("MARKET_FREEZE",)))
            continue

        decision = build_price_plan(
            candidate.setup,
            candidate.bars,
            value.risk_budget,
            value.market_status,
            value.policy,
        )
        if decision.plan is None:
            rejection_counts.update(decision.reasons)
            continue
        eligible.append(
            SelectionItem(
                code=normalize_code6(candidate.code),
                name=candidate.name,
                tier=CandidateTier.FORMAL,
                setup=candidate.setup,
                sector_code=candidate.sector_code,
                sector_percentile=candidate.sector_percentile,
                average_amount5_qian=candidate.average_amount5_qian,
                plan=decision.plan,
                missing_fields=(),
                reasons=(),
            )
        )

    limit = {
        "ALLOW": value.policy.max_formal_candidates,
        "LIMITED": value.policy.limited_candidates,
        "FREEZE": 0,
    }.get(value.market_status, 0)
    qualified: list[SelectionItem] = []
    selected_sectors: set[str] = set()
    remaining_exposure = value.risk_budget.remaining_exposure
    for item in sorted(eligible, key=_ranking_key):
        if item.sector_code in selected_sectors:
            rejection_counts["SECTOR_CONCENTRATION"] += 1
            continue
        if len(qualified) >= limit:
            rejection_counts["DAILY_CANDIDATE_LIMIT"] += 1
            continue
        if item.plan is None:
            raise ValueError("eligible row is missing its price plan")
        exposure_lots = (
            remaining_exposure / item.plan.trigger_price / Decimal("100")
        ).to_integral_value(rounding=ROUND_FLOOR)
        exposure_shares = int(exposure_lots * Decimal("100"))
        allocated_shares = min(item.plan.maximum_shares, exposure_shares)
        if allocated_shares < 100:
            rejection_counts["PORTFOLIO_EXPOSURE_EXHAUSTED"] += 1
            continue
        if allocated_shares != item.plan.maximum_shares:
            item = replace(
                item,
                plan=replace(item.plan, maximum_shares=allocated_shares),
            )
        qualified.append(item)
        remaining_exposure -= item.plan.trigger_price * Decimal(allocated_shares)
        if item.sector_code is not None:
            selected_sectors.add(item.sector_code)

    return BuyPointSelectionResult(
        qualified=tuple(qualified),
        observe=tuple(observe),
        shadow=value.legacy_shadow,
        rejection_counts=dict(sorted(rejection_counts.items())),
    )
