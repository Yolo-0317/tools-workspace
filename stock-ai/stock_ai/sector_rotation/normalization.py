from __future__ import annotations

import json
import re
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from .models import ChainRule, NormalizedChain, RawSectorRow

_DEFAULT_RULES_PATH = Path(__file__).with_name("industry_chains.json")
_NAVIGATION_MARKERS = (
    "排行",
    "排名",
    "资金流",
    "涨幅榜",
    "跌幅榜",
    "领涨",
    "更多",
    "首页",
)


def normalize_sector_name(name: str) -> str:
    return re.sub(r"[\s·•/\\（）()\-_]+", "", name).casefold()


def load_chain_rules(path: Path | None = None) -> tuple[ChainRule, ...]:
    payload = json.loads((path or _DEFAULT_RULES_PATH).read_text(encoding="utf-8"))
    rules = tuple(
        ChainRule(
            chain_code=item["chain_code"],
            chain_name=item["chain_name"],
            parent_code=item["parent_code"],
            aliases=tuple(item["aliases"]),
            keywords=tuple(item["keywords"]),
            excludes=tuple(item["excludes"]),
            priority=int(item["priority"]),
            coexistence_codes=tuple(item["coexistence_codes"]),
        )
        for item in payload
    )
    return tuple(sorted(rules, key=lambda value: (-value.priority, value.chain_code)))


def _is_valid_row(row: RawSectorRow) -> bool:
    name = normalize_sector_name(row.sector_name)
    return bool(row.board_code.strip() and name) and not any(
        marker in name for marker in _NAVIGATION_MARKERS
    )


def _matching_rule(name: str, rules: Sequence[ChainRule]) -> ChainRule | None:
    normalized = normalize_sector_name(name)
    eligible = [
        rule
        for rule in rules
        if not any(normalize_sector_name(term) in normalized for term in rule.excludes)
    ]
    alias_matches = [
        rule
        for rule in eligible
        if any(normalize_sector_name(alias) == normalized for alias in rule.aliases)
    ]
    matches = alias_matches or [
        rule
        for rule in eligible
        if any(normalize_sector_name(keyword) in normalized for keyword in rule.keywords)
    ]
    return min(matches, key=lambda value: (-value.priority, value.chain_code), default=None)


def merge_sector_rows(
    rows: Sequence[RawSectorRow], rules: Sequence[ChainRule]
) -> tuple[NormalizedChain, ...]:
    grouped: dict[tuple[str, str, str], list[RawSectorRow]] = defaultdict(list)
    for row in rows:
        if not _is_valid_row(row):
            continue
        rule = _matching_rule(row.sector_name, rules)
        if rule is None:
            key = (f"raw_{row.board_code.strip().lower()}", row.sector_name.strip(), "raw")
        else:
            key = (rule.chain_code, rule.chain_name, rule.parent_code)
        grouped[key].append(row)

    chains: list[NormalizedChain] = []
    for (chain_code, chain_name, parent_code), members in grouped.items():
        ordered = sorted(members, key=lambda value: (value.rank, value.board_code))
        best = ordered[0]
        chains.append(
            NormalizedChain(
                chain_code=chain_code,
                chain_name=chain_name,
                parent_code=parent_code,
                raw_sector_codes=tuple(value.board_code for value in ordered),
                raw_sector_names=tuple(value.sector_name for value in ordered),
                best_rank=best.rank,
                raw_change_pct=Decimal(str(best.change_pct)),
            )
        )
    return tuple(sorted(chains, key=lambda value: (value.best_rank, value.chain_code)))
