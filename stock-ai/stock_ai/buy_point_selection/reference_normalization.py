"""Pure normalization of CNInfo and BaoStock point-in-time facts."""

from __future__ import annotations

from datetime import date, time
from typing import Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

from .reference_data import (
    RiskFlag,
    SectorMembership,
    classify_announcement_title,
)
from .reference_sources import (
    Announcement,
    IndustryCategory,
    IndustryChange,
    SecurityStatus,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")
ANNOUNCEMENT_CUTOFF = time(15, 0)
SW_STANDARD = "申银万国行业分类标准"


def _code6(value: str) -> str:
    raw = str(value or "").strip().split(".")[-1]
    if raw.startswith(("sh", "sz")):
        raw = raw[2:].lstrip(".")
    if not raw.isdigit():
        raise ValueError("stock code must be numeric")
    return raw.zfill(6)


def _level_one(
    category_code: str,
    categories: Mapping[str, IndustryCategory],
    changed_on: date,
) -> IndustryCategory:
    visited: set[str] = set()
    current = categories.get(category_code)
    while current is not None:
        if current.code in visited:
            raise ValueError(f"industry category cycle at {current.code}")
        visited.add(current.code)
        if current.terminated_on is not None and current.terminated_on < changed_on:
            raise ValueError(f"industry category terminated before use: {current.code}")
        if current.level == 1:
            return current
        current = categories.get(current.parent_code)
    raise ValueError(f"cannot resolve level-one industry for {category_code}")


def normalize_cninfo_memberships(
    categories: Sequence[IndustryCategory],
    changes_by_code: Mapping[str, Sequence[IndustryChange]],
    *,
    previous_trade_date: Callable[[date], date | None],
) -> tuple[SectorMembership, ...]:
    by_category = {row.code: row for row in categories}
    if len(by_category) != len(categories):
        raise ValueError("duplicate industry category code")
    normalized: list[SectorMembership] = []
    for raw_code, raw_changes in sorted(changes_by_code.items()):
        code = _code6(raw_code)
        resolved: list[tuple[date, IndustryCategory]] = []
        for change in sorted(raw_changes, key=lambda row: (row.changed_on, row.industry_code)):
            if change.standard != SW_STANDARD:
                continue
            category = _level_one(change.industry_code, by_category, change.changed_on)
            if resolved and resolved[-1][0] == change.changed_on:
                if resolved[-1][1].code != category.code:
                    raise ValueError(f"conflicting same-day industry changes for {code}")
                continue
            if resolved and resolved[-1][1].code == category.code:
                continue
            resolved.append((change.changed_on, category))
        for index, (valid_from, category) in enumerate(resolved):
            valid_to = None
            if index + 1 < len(resolved):
                valid_to = previous_trade_date(resolved[index + 1][0])
                if valid_to is None or valid_to < valid_from:
                    raise ValueError(f"cannot close industry interval for {code}")
            normalized.append(
                SectorMembership(
                    code=code,
                    sector_code=category.code,
                    sector_name=category.name,
                    valid_from=valid_from,
                    valid_to=valid_to,
                    source="CNINFO",
                )
            )
    return tuple(
        sorted(normalized, key=lambda row: (row.code, row.valid_from, row.sector_code))
    )


def _is_st_name(name: str) -> bool:
    normalized = "".join(str(name or "").upper().split())
    return normalized.startswith(("*ST", "ST", "S*ST", "SST"))


def normalize_baostock_risk_flags(
    rows: Sequence[SecurityStatus],
) -> tuple[RiskFlag, ...]:
    normalized: list[RiskFlag] = []
    seen: set[tuple[str, date]] = set()
    for row in rows:
        code = _code6(row.code)
        identity = (code, row.trade_date)
        if identity in seen:
            raise ValueError(f"duplicate BaoStock status for {code} on {row.trade_date}")
        seen.add(identity)
        evidence = f"baostock:query_all_stock:{row.trade_date.isoformat()}:{code}"
        if _is_st_name(row.name):
            normalized.append(
                RiskFlag(
                    code,
                    "ST",
                    "VETO",
                    row.trade_date,
                    row.trade_date,
                    "BAOSTOCK",
                    evidence,
                )
            )
        if str(row.trade_status).strip() == "0":
            normalized.append(
                RiskFlag(
                    code,
                    "SUSPENDED",
                    "VETO",
                    row.trade_date,
                    row.trade_date,
                    "BAOSTOCK",
                    evidence,
                )
            )
    return tuple(sorted(normalized, key=lambda row: (row.effective_from, row.code, row.flag_type)))


def normalize_cninfo_announcement_flags(
    rows: Sequence[Announcement],
    *,
    is_trade_date: Callable[[date], bool],
    next_trade_date: Callable[[date], date],
    fallback_date: date | None = None,
) -> tuple[RiskFlag, ...]:
    normalized: list[RiskFlag] = []
    for row in rows:
        classified = classify_announcement_title(row.title)
        if classified is None:
            continue
        if not row.official_url:
            raise ValueError(f"CNInfo announcement has no official URL: {row.announcement_id}")
        if row.published_at is None:
            if fallback_date is None:
                raise ValueError("fallback_date is required for missing publication time")
            effective_from = next_trade_date(fallback_date)
        else:
            published = row.published_at
            if published.tzinfo is None or published.utcoffset() is None:
                published = published.replace(tzinfo=SHANGHAI)
            else:
                published = published.astimezone(SHANGHAI)
            published_date = published.date()
            if is_trade_date(published_date) and published.time() <= ANNOUNCEMENT_CUTOFF:
                effective_from = published_date
            else:
                effective_from = next_trade_date(published_date)
        flag_type, severity = classified
        normalized.append(
            RiskFlag(
                code=_code6(row.code),
                flag_type=flag_type,
                severity=severity,
                effective_from=effective_from,
                effective_to=None,
                source="CNINFO",
                evidence_ref=row.official_url,
            )
        )
    return tuple(
        sorted(normalized, key=lambda row: (row.effective_from, row.code, row.flag_type))
    )
