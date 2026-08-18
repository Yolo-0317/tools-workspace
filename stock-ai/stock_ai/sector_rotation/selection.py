from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Sequence

from .models import (
    CandidateRole,
    MemberSnapshot,
    RotationBucket,
    RotationCandidate,
    RotationPolicy,
    RotationState,
    ScoredChain,
    SelectedChain,
)


def _sort_key(chain: ScoredChain) -> tuple[object, ...]:
    state_priority = {
        RotationState.CONFIRMED: 0,
        RotationState.STARTING: 1,
        RotationState.LATENT: 2,
    }
    return (
        state_priority.get(chain.state, 9),
        -chain.score.total,
        -chain.metrics.breadth_ratio,
        -chain.metrics.persistence_count,
        -chain.score.structure_score,
        chain.chain_code,
    )


def _overlap(left: ScoredChain, right: ScoredChain) -> Decimal:
    left_codes, right_codes = set(left.member_codes), set(right.member_codes)
    union = left_codes | right_codes
    if not union:
        return Decimal("0")
    return Decimal(len(left_codes & right_codes)) / Decimal(len(union))


def _can_coexist(
    chain: ScoredChain, selected: Sequence[SelectedChain], policy: RotationPolicy
) -> bool:
    for other in selected:
        if chain.parent_code != other.parent_code:
            continue
        explicitly_allowed = (
            other.chain_code in chain.coexistence_codes
            and chain.chain_code in other.coexistence_codes
        )
        if not explicitly_allowed or _overlap(chain, other) > policy.coexistence_overlap_max:
            return False
    return True


def _append_bucket(
    output: list[SelectedChain],
    candidates: Sequence[ScoredChain],
    bucket: RotationBucket,
    limit: int,
    policy: RotationPolicy,
) -> None:
    used_codes = {value.chain_code for value in output}
    count = 0
    for chain in sorted(candidates, key=_sort_key):
        if count >= limit:
            break
        if chain.chain_code in used_codes or not _can_coexist(chain, output, policy):
            continue
        output.append(SelectedChain(**chain.__dict__, bucket=bucket))
        used_codes.add(chain.chain_code)
        count += 1


def select_core_pool(
    chains: Sequence[ScoredChain], policy: RotationPolicy
) -> tuple[SelectedChain, ...]:
    output: list[SelectedChain] = []
    _append_bucket(
        output,
        [value for value in chains if value.state in {RotationState.STARTING, RotationState.CONFIRMED}],
        RotationBucket.STRONG,
        policy.strongest_count,
        policy,
    )
    _append_bucket(
        output,
        [value for value in chains if value.state is RotationState.LATENT],
        RotationBucket.STRENGTHENING,
        policy.strengthening_count,
        policy,
    )
    _append_bucket(
        output,
        [
            value
            for value in chains
            if value.previous_state is RotationState.CONFIRMED
            and value.state not in {RotationState.FADING, RotationState.OVERHEATED}
            and value.metrics.data_complete
        ],
        RotationBucket.PULLBACK,
        policy.pullback_count,
        policy,
    )
    return tuple(output)


def _role(member: MemberSnapshot, policy: RotationPolicy) -> tuple[CandidateRole, str]:
    if member.change_pct >= Decimal("4") and member.amount_ratio >= Decimal("1.40"):
        return CandidateRole.LEADER, "LEADER_STRENGTH"
    if (
        member.price >= member.ma20
        and abs(member.ma5_distance_pct) <= Decimal("1")
        and member.change_pct <= Decimal("1")
    ):
        return CandidateRole.PULLBACK, "PULLBACK_NEAR_SUPPORT"
    if (
        member.price >= member.ma20
        and Decimal("0") < member.change_pct <= Decimal("1")
        and member.amount_ratio >= Decimal("1")
    ):
        return CandidateRole.FOLLOWER, "FOLLOWER_EXPANSION"
    if (
        member.price >= member.ma20
        and member.amount_ratio >= Decimal("1")
        and member.ma5_distance_pct <= policy.ma5_distance_overheat_pct
    ):
        return CandidateRole.CATCH_UP, "CATCH_UP_NOT_EXTENDED"
    return CandidateRole.FOLLOWER, "FOLLOWER_EXPANSION"


def _member_sort_key(member: MemberSnapshot, role: CandidateRole) -> tuple[object, ...]:
    if role is CandidateRole.PULLBACK:
        return (abs(member.ma5_distance_pct), -member.amount_ratio, member.code)
    return (-member.change_pct, -member.return5_pct, -member.amount_ratio, member.code)


def _rejections(member: MemberSnapshot, role: CandidateRole, policy: RotationPolicy) -> tuple[str, ...]:
    reasons: list[str] = []
    if role is CandidateRole.FOLLOWER:
        reasons.append("ROLE_NOT_FORMAL")
    if member.risk_veto:
        reasons.append("RISK_VETO")
    if not member.data_complete:
        reasons.append("DATA_INCOMPLETE")
    if member.change_pct > policy.signal_day_overheat_pct:
        reasons.append("SIGNAL_DAY_OVERHEATED")
    if member.return5_pct > policy.return5_overheat_pct:
        reasons.append("RETURN5_OVERHEATED")
    if member.ma5_distance_pct > policy.ma5_distance_overheat_pct:
        reasons.append("MA5_DISTANCE_OVERHEATED")
    return tuple(reasons)


def build_observation_pool(
    chain: SelectedChain,
    members: Sequence[MemberSnapshot],
    policy: RotationPolicy,
) -> tuple[RotationCandidate, ...]:
    role_members: dict[CandidateRole, list[tuple[MemberSnapshot, str]]] = {
        role: [] for role in CandidateRole
    }
    for member in members:
        if not member.liquid:
            continue
        role, reason = _role(member, policy)
        role_members[role].append((member, reason))

    quotas = (
        (CandidateRole.LEADER, 2),
        (CandidateRole.FOLLOWER, 3),
        (CandidateRole.CATCH_UP, 3),
        (CandidateRole.PULLBACK, 2),
    )
    selected: list[tuple[MemberSnapshot, CandidateRole, str]] = []
    seen: set[str] = set()
    for role, quota in quotas:
        ordered = sorted(role_members[role], key=lambda value: _member_sort_key(value[0], role))
        for member, reason in ordered:
            if len([value for value in selected if value[1] is role]) >= quota:
                break
            if member.code in seen:
                continue
            selected.append((member, role, reason))
            seen.add(member.code)

    candidates: list[RotationCandidate] = []
    for rank, (member, role, reason) in enumerate(selected[: policy.observation_limit], start=1):
        rejection_reasons = _rejections(member, role, policy)
        candidates.append(
            RotationCandidate(
                chain_code=chain.chain_code,
                code=member.code,
                name=member.name,
                role=role,
                pool_rank=rank,
                formal_eligible=not rejection_reasons,
                held=member.held,
                metrics={
                    "price": member.price,
                    "change_pct": member.change_pct,
                    "return5_pct": member.return5_pct,
                    "amount_ratio": member.amount_ratio,
                    "ma5_distance_pct": member.ma5_distance_pct,
                },
                levels=None,
                reasons=(reason,),
                rejection_reasons=rejection_reasons,
            )
        )
    return tuple(candidates)


def promote_formal_candidates(
    observations: Sequence[RotationCandidate], policy: RotationPolicy
) -> tuple[RotationCandidate, ...]:
    formal: list[RotationCandidate] = []
    for role in (CandidateRole.LEADER, CandidateRole.CATCH_UP, CandidateRole.PULLBACK):
        candidate = next(
            (
                value
                for value in observations
                if value.role is role and value.formal_eligible
            ),
            None,
        )
        if candidate is not None:
            formal.append(replace(candidate, formal_eligible=True))
        if len(formal) >= policy.formal_limit:
            break
    return tuple(formal)
