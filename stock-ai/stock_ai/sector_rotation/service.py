from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from statistics import mean
from typing import Any, Sequence
from uuid import uuid4

from stock_ai.buy_point_selection.models import BuyPointBar

from .models import (
    ChainMetrics, MemberSnapshot, RotationCandidate, RotationPolicy, RotationRunResult,
    RotationState, ScoredChain, SelectedChain,
)
from .normalization import load_chain_rules, merge_sector_rows
from .pricing import calculate_price_levels
from .providers import RotationDataProvider
from .reporting import write_rotation_report
from .repository import RotationRepository
from .scoring import classify_state, score_chain
from .selection import build_observation_pool, promote_formal_candidates, select_core_pool


class RotationSourceError(RuntimeError):
    pass


def _decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value)) if value is not None else Decimal(default)
    except (ValueError, TypeError):
        return Decimal(default)


def _bars(raw: Sequence[dict[str, Any]]) -> tuple[BuyPointBar, ...]:
    output = []
    for value in raw:
        try:
            output.append(BuyPointBar(
                trade_date=date.fromisoformat(str(value["trade_date"])[:10]),
                open=_decimal(value.get("open")), high=_decimal(value.get("high")),
                low=_decimal(value.get("low")), close=_decimal(value.get("close")),
                pct_chg=_decimal(value.get("pct_chg")), amount_qian=_decimal(value.get("amount")),
            ))
        except (KeyError, ValueError):
            continue
    return tuple(sorted(output, key=lambda item: item.trade_date))


def _average(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values)) if values else Decimal("0")


def _member_snapshot(
    raw: dict[str, Any], bars: Sequence[BuyPointBar], held_codes: set[str]
) -> MemberSnapshot:
    code = str(raw.get("code") or "").zfill(6)
    complete = len(bars) >= 20 and _decimal(raw.get("price")) > 0
    closes = [value.close for value in bars]
    amounts = [value.amount_qian for value in bars]
    ma5 = _average(closes[-5:])
    ma10 = _average(closes[-10:])
    ma20 = _average(closes[-20:])
    price = _decimal(raw.get("price"), str(closes[-1] if closes else 0))
    return5 = ((price / closes[-6]) - 1) * 100 if len(closes) >= 6 and closes[-6] else Decimal("0")
    amount_base = _average(amounts[-6:-1]) if len(amounts) >= 6 else Decimal("0")
    amount_ratio = amounts[-1] / amount_base if amounts and amount_base > 0 else Decimal("0")
    true_ranges = [value.high - value.low for value in bars[-14:]]
    atr14 = _average(true_ranges)
    distance = ((price / ma5) - 1) * 100 if ma5 > 0 else Decimal("0")
    name = str(raw.get("name") or code)
    return MemberSnapshot(
        code, name, price, _decimal(raw.get("change_pct")), return5, amount_ratio,
        ma5, ma10, ma20, distance,
        max((value.high for value in bars[-20:]), default=Decimal("0")),
        min((value.low for value in bars[-20:]), default=Decimal("0")),
        atr14, bool(bars and amounts[-1] > 0), "ST" in name.upper() or "退" in name,
        code in held_codes, complete,
    )


def _chain_metrics(
    chain: Any,
    members: Sequence[MemberSnapshot],
    universe_size: int,
    history: Sequence[SelectedChain],
    complete: bool,
) -> ChainMetrics:
    liquid = [value for value in members if value.liquid]
    count = len(liquid)
    positive = [value for value in liquid if value.change_pct > 0]
    total_amount = sum((value.amount_ratio for value in liquid), Decimal("0"))
    advancing_amount = sum((value.amount_ratio for value in positive), Decimal("0"))
    previous_rank = history[0].best_rank if history else chain.best_rank
    rank_improvement = Decimal(max(0, previous_rank - chain.best_rank)) / Decimal(max(1, universe_size))
    return ChainMetrics(
        return_percentile=Decimal(universe_size - chain.best_rank + 1) / Decimal(max(1, universe_size)),
        rank_improvement=rank_improvement,
        breadth_ratio=Decimal(len(positive)) / Decimal(count) if count else Decimal("0"),
        above_ma5_ratio=Decimal(sum(value.price >= value.ma5 for value in liquid)) / Decimal(count) if count else Decimal("0"),
        above_ma20_ratio=Decimal(sum(value.price >= value.ma20 for value in liquid)) / Decimal(count) if count else Decimal("0"),
        strengthening_count=sum(value.change_pct > 0 and value.amount_ratio >= 1 for value in liquid),
        liquid_count=count,
        amount_ratio=_average([value.amount_ratio for value in liquid]),
        advancing_amount_ratio=advancing_amount / total_amount if total_amount > 0 else Decimal("0"),
        persistence_count=sum(value.state in {RotationState.STARTING, RotationState.CONFIRMED} for value in history[:3]),
        leader_concentration=max((value.amount_ratio for value in liquid), default=Decimal("0")) / total_amount if total_amount > 0 else Decimal("1"),
        data_complete=complete and bool(liquid) and all(value.data_complete for value in liquid),
    )


def detect_sector_rotation(
    *,
    provider: RotationDataProvider,
    repository: RotationRepository | None,
    policy: RotationPolicy,
    observed_at: datetime,
    edition: str,
    top_sectors: int,
    stocks_per_sector: int,
    output_path: Path | None = None,
) -> RotationRunResult:
    run_id = repository.start_run(
        observed_at=observed_at, trade_date=observed_at.date(), edition=edition,
        policy_version=policy.version,
    ) if repository else uuid4().hex
    try:
        ranked = provider.fetch_ranked_sectors(max(top_sectors, 60))
        if not ranked:
            raise RotationSourceError("SECTOR_RANKING_UNAVAILABLE")
    except Exception as exc:
        if repository:
            repository.save_failure(run_id, "SECTOR_RANKING_UNAVAILABLE", str(exc))
        if isinstance(exc, RotationSourceError):
            raise
        raise RotationSourceError("SECTOR_RANKING_UNAVAILABLE") from exc

    normalized = merge_sector_rows(ranked, load_chain_rules())
    chain_codes = [value.chain_code for value in normalized]
    history_map = repository.load_history(chain_codes, limit=3) if repository else provider.load_previous_snapshots(chain_codes)
    previous_result = repository.load_latest_result() if repository else None
    bounded = normalized[:60]
    member_groups = provider.fetch_chain_members(bounded)
    raw_by_chain: dict[str, list[dict[str, Any]]] = {}
    for chain in bounded:
        seen: set[str] = set()
        values = []
        for board_code in chain.raw_sector_codes:
            for item in member_groups.get(board_code, []):
                code = str(item.get("code") or "").zfill(6)
                if code not in seen:
                    values.append(item)
                    seen.add(code)
        raw_by_chain[chain.chain_code] = values[:stocks_per_sector]
    codes = sorted({str(item.get("code") or "").zfill(6) for values in raw_by_chain.values() for item in values})
    panel = provider.load_daily_panel(codes, 60)
    held_codes = provider.load_held_codes()
    warning_values = tuple(getattr(provider, "warnings", ()))
    incomplete_boards = {value.split(":", 1)[1] for value in warning_values if value.startswith("CONSTITUENTS_INCOMPLETE:")}
    rules = {value.chain_code: value for value in load_chain_rules()}

    member_snapshots: dict[str, tuple[MemberSnapshot, ...]] = {}
    scored: list[ScoredChain] = []
    for chain in bounded:
        members = tuple(
            _member_snapshot(value, _bars(panel.get(str(value.get("code") or "").zfill(6), [])), held_codes)
            for value in raw_by_chain[chain.chain_code]
        )
        member_snapshots[chain.chain_code] = members
        prior = tuple(history_map.get(chain.chain_code, ()))
        complete = not any(code in incomplete_boards for code in chain.raw_sector_codes)
        metrics = _chain_metrics(chain, members, len(bounded), prior, complete)
        score = score_chain(metrics, policy)
        previous_states = tuple((value.state, value.score) for value in reversed(prior) if value.state)
        state, state_reasons = classify_state(score, metrics, previous_states, policy)
        rule = rules.get(chain.chain_code)
        scored.append(ScoredChain(
            **chain.__dict__, metrics=metrics, score=score, state=state,
            previous_state=prior[0].state if prior else None, state_reasons=state_reasons,
            coexistence_codes=rule.coexistence_codes if rule else (),
            member_codes=tuple(value.code for value in members),
        ))

    selected = select_core_pool(scored, policy)[:top_sectors]
    all_candidates: list[RotationCandidate] = []
    for chain in selected:
        observations = build_observation_pool(chain, member_snapshots[chain.chain_code], policy)
        promoted = promote_formal_candidates(observations, policy) if chain.metrics.data_complete else ()
        promoted_codes = {value.code for value in promoted}
        member_by_code = {value.code: value for value in member_snapshots[chain.chain_code]}
        for candidate in observations:
            is_formal = candidate.code in promoted_codes
            adjusted = replace(candidate, formal_eligible=is_formal)
            if not chain.metrics.data_complete:
                adjusted = replace(
                    adjusted, formal_eligible=False,
                    rejection_reasons=adjusted.rejection_reasons + ("CHAIN_DATA_INCOMPLETE",),
                )
            levels = calculate_price_levels(
                adjusted, member_by_code[adjusted.code],
                _bars(panel.get(adjusted.code, [])), policy,
            ) if adjusted.formal_eligible else None
            all_candidates.append(replace(adjusted, levels=levels))

    result = RotationRunResult(
        run_id, observed_at, observed_at.date(), edition, policy.version, tuple(selected),
        tuple(all_candidates), warning_values, None,
    )
    report_path = write_rotation_report(result, output_path, previous_result)
    result = replace(result, report_path=report_path)
    if repository:
        try:
            repository.save_success(result)
        except Exception as exc:
            repository.save_failure(run_id, "REPOSITORY_WRITE_FAILED", str(exc))
            raise
    return result
