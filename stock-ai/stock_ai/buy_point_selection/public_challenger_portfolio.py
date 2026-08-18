"""Shared eligibility and capacity rules for the public challenger tracks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

from stock_ai.market_codes import normalize_code6

from .gates import base_gate
from .models import BuyPointBar, SelectionPolicy
from .public_challenger_signals import (
    CONTRARIAN_TRACK,
    EXECUTION_TRACK,
    RESIDUAL_TRACK,
    ChallengerSignal,
)
from .reference_data import (
    ReferenceCoverage,
    RiskFlag,
    SectorMembership,
    membership_on,
)


@dataclass(frozen=True)
class ChallengerCandidateDecision:
    signal: ChallengerSignal
    research_eligible: bool
    execution_eligible: bool
    trade_permission: str
    executable_shares: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ChallengerDailySelection:
    signal_date: date
    track_id: str
    all_eligible: tuple[ChallengerCandidateDecision, ...]
    selected: tuple[ChallengerCandidateDecision, ...]
    funnel_counts: Mapping[str, int]


def _code6(value: str) -> str:
    normalized = normalize_code6(value)
    if len(normalized) == 6 and normalized.isdigit():
        return normalized
    digits = "".join(character for character in str(value) if character.isdigit())
    return digits[:6] if len(digits) >= 6 else normalized


def _active_veto(
    code: str,
    signal_date: date,
    flags: Sequence[RiskFlag],
) -> bool:
    normalized = _code6(code)
    return any(
        _code6(row.code) == normalized
        and row.severity == "VETO"
        and row.effective_from <= signal_date
        and (row.effective_to is None or signal_date <= row.effective_to)
        for row in flags
    )


def eligible_universe_on(
    signal_date: date,
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    memberships: Sequence[SectorMembership],
    held_codes: frozenset[str],
) -> tuple[str, ...]:
    active_memberships = {
        _code6(code): row
        for code, row in membership_on(memberships, signal_date).items()
    }
    normalized_holdings = {
        _code6(code) for code in held_codes
    }
    policy = SelectionPolicy()
    eligible: list[str] = []
    for raw_code, values in bars_by_code.items():
        code = _code6(raw_code)
        bounded = tuple(
            sorted(
                (
                    value
                    for value in values
                    if value.trade_date <= signal_date
                ),
                key=lambda value: value.trade_date,
            )
        )
        if (
            not bounded
            or bounded[-1].trade_date != signal_date
            or code not in active_memberships
        ):
            continue
        decision = base_gate(
            code,
            bounded,
            normalized_holdings,
            {},
            policy,
        )
        if decision.passed:
            eligible.append(code)
    return tuple(sorted(set(eligible)))


def qualify_track_signals(
    *,
    signals: Sequence[ChallengerSignal],
    coverage: ReferenceCoverage,
    risk_flags: Sequence[RiskFlag],
    held_codes: frozenset[str],
) -> Mapping[str, ChallengerCandidateDecision]:
    resolved = tuple(signals)
    if not resolved:
        return {}
    signal_dates = {row.signal_date for row in resolved}
    codes = {_code6(row.code) for row in resolved}
    tracks = {row.track_id for row in resolved}
    supported_tracks = {
        CONTRARIAN_TRACK,
        RESIDUAL_TRACK,
        EXECUTION_TRACK,
    }
    if len(signal_dates) != 1 or len(codes) != 1:
        raise ValueError("TRACK_SIGNAL_IDENTITY_MISMATCH")
    if len(tracks) != len(resolved) or not tracks <= supported_tracks:
        raise ValueError("TRACK_SIGNAL_SET_INVALID")
    signal_date = resolved[0].signal_date
    if coverage.analysis_date != signal_date:
        raise ValueError("REFERENCE_COVERAGE_DATE_MISMATCH")
    code = _code6(resolved[0].code)
    normalized_holdings = {
        _code6(value) for value in held_codes
    }
    common_reasons: list[str] = []
    if code in normalized_holdings:
        common_reasons.append("EXISTING_HOLDING")
    if not coverage.sector_complete:
        common_reasons.append("SECTOR_DATA_MISSING")
    if not coverage.st_complete:
        common_reasons.append("SECURITY_STATUS_MISSING")
    result: dict[str, ChallengerCandidateDecision] = {}
    for signal in resolved:
        reasons = list(common_reasons)
        if not signal.in_candidate_pool:
            reasons.append("NOT_IN_CANDIDATE_POOL")
        research_eligible = not reasons
        execution_eligible = False
        if signal.track_id == EXECUTION_TRACK and research_eligible:
            if not coverage.announcement_complete:
                reasons.append("RISK_DATA_MISSING")
            if _active_veto(code, signal_date, risk_flags):
                reasons.append("POINT_IN_TIME_RISK_VETO")
            execution_eligible = not reasons
        result[signal.track_id] = ChallengerCandidateDecision(
            signal=signal,
            research_eligible=research_eligible,
            execution_eligible=execution_eligible,
            trade_permission="NO-TRADE",
            executable_shares=0,
            reasons=tuple(reasons),
        )
    return dict(sorted(result.items()))


def select_capacity_matched(
    decisions: Sequence[ChallengerCandidateDecision],
    market_status: str,
) -> ChallengerDailySelection:
    resolved = tuple(decisions)
    if not resolved:
        raise ValueError("CAPACITY_DECISIONS_EMPTY")
    if market_status not in {"ALLOW", "LIMITED", "FREEZE"}:
        raise ValueError("MARKET_STATUS_INVALID")
    signal_dates = {row.signal.signal_date for row in resolved}
    tracks = {row.signal.track_id for row in resolved}
    if len(signal_dates) != 1 or len(tracks) != 1:
        raise ValueError("CAPACITY_DECISION_IDENTITY_MISMATCH")
    if any(
        row.trade_permission != "NO-TRADE" or row.executable_shares != 0
        for row in resolved
    ):
        raise ValueError("CHALLENGER_TRADE_PERMISSION_INVALID")
    track_id = resolved[0].signal.track_id

    def ranking_key(
        row: ChallengerCandidateDecision,
    ) -> tuple[Decimal, str]:
        signal = row.signal
        score = (
            signal.residual_5d
            if signal.residual_5d is not None
            else signal.formation_return
        )
        return score, signal.code

    all_eligible = tuple(
        sorted(
            (row for row in resolved if row.research_eligible),
            key=ranking_key,
        )
    )
    selectable = tuple(
        row
        for row in all_eligible
        if track_id != EXECUTION_TRACK or row.execution_eligible
    )
    funnel_counts: dict[str, int] = {}
    for row in resolved:
        for reason in set(row.reasons):
            funnel_counts[reason] = funnel_counts.get(reason, 0) + 1
    if market_status == "FREEZE":
        if selectable:
            funnel_counts["MARKET_FREEZE"] = len(selectable)
        selected: tuple[ChallengerCandidateDecision, ...] = ()
    else:
        capacity = 3 if market_status == "ALLOW" else 1
        chosen: list[ChallengerCandidateDecision] = []
        sectors: set[str] = set()
        for row in selectable:
            if row.signal.sector_code in sectors:
                funnel_counts["SECTOR_CAPACITY"] = (
                    funnel_counts.get("SECTOR_CAPACITY", 0) + 1
                )
                continue
            if len(chosen) >= capacity:
                funnel_counts["MARKET_CAPACITY"] = (
                    funnel_counts.get("MARKET_CAPACITY", 0) + 1
                )
                continue
            chosen.append(row)
            sectors.add(row.signal.sector_code)
        selected = tuple(chosen)
    return ChallengerDailySelection(
        signal_date=resolved[0].signal.signal_date,
        track_id=track_id,
        all_eligible=all_eligible,
        selected=selected,
        funnel_counts=dict(sorted(funnel_counts.items())),
    )
