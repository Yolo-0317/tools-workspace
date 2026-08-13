"""Pure models and normalization for Eastmoney topic-pool snapshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
import re
from typing import Any, Literal, Mapping, Sequence


PoolKind = Literal["LIMIT_UP", "EXPLODED", "LIMIT_DOWN"]
Horizon = Literal["T1", "T3", "T5"]


@dataclass(frozen=True)
class PoolFact:
    trade_date: date
    pool_kind: PoolKind
    code: str
    name: str
    pct_chg: float | None
    amount_wan: float | None
    board_height: int | None
    main_theme: str | None
    first_seal_time: str | None
    last_seal_time: str | None
    reopen_count: int | None
    seal_amount_wan: float | None
    missing_fields: tuple[str, ...]
    raw_json: Mapping[str, Any]


@dataclass(frozen=True)
class NormalizedSnapshot:
    trade_date: date
    facts: tuple[PoolFact, ...]
    warnings: tuple[str, ...]
    snapshot_hash: str


@dataclass(frozen=True)
class SelectionAttribution:
    trade_date: date
    code: str
    strategy: str
    selected: bool
    rank_no: int | None
    score: float | None
    action: str | None
    attribution: str
    first_reason_code: str | None
    reason_codes: tuple[str, ...]
    evidence: Mapping[str, Any]
    rule_version: str


@dataclass(frozen=True)
class ForwardLabel:
    signal_date: date
    code: str
    horizon: Horizon
    outcome_date: date | None
    signal_close: float | None
    outcome_close: float | None
    close_return_pct: float | None
    max_return_pct: float | None
    max_drawdown_pct: float | None
    closed_limit_up: bool | None
    board_height: int | None
    data_complete: bool
    missing_fields: tuple[str, ...]
    label_version: str = "limit-up-forward-label-1.0.0"


_POOL_KINDS: dict[str, PoolKind] = {
    "zt": "LIMIT_UP",
    "zb": "EXPLODED",
    "dt": "LIMIT_DOWN",
}


def _optional_float(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value in (None, "", "-"):
        return None
    return int(value)


def _time_text(value: Any) -> str | None:
    if value in (None, "", "-"):
        return None
    digits = re.sub(r"\D", "", str(value)).zfill(6)[-6:]
    hour, minute, second = int(digits[:2]), int(digits[2:4]), int(digits[4:])
    if hour > 23 or minute > 59 or second > 59:
        raise ValueError(f"invalid Eastmoney time: {value}")
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def _board_height(raw: Mapping[str, Any], kind: PoolKind) -> int | None:
    value = _optional_int(raw.get("lbc"))
    if value is None:
        stats = raw.get("zttj")
        if isinstance(stats, Mapping):
            value = _optional_int(stats.get("ct") or stats.get("days"))
    if kind == "LIMIT_UP":
        value = max(value or 1, 1)
    return value


def _canonical_fact(fact: PoolFact) -> dict[str, Any]:
    value = asdict(fact)
    value["trade_date"] = fact.trade_date.isoformat()
    value["raw_json"] = dict(fact.raw_json)
    return value


def snapshot_hash(facts: Sequence[PoolFact]) -> str:
    ordered = sorted((_canonical_fact(item) for item in facts), key=lambda x: (x["pool_kind"], x["code"]))
    payload = json.dumps(ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_row(raw: Mapping[str, Any], trade_date: date, kind: PoolKind) -> PoolFact:
    code = str(raw.get("c") or "").split(".")[0].zfill(6)
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError(f"invalid A-share code: {raw.get('c')}")
    amount = _optional_float(raw.get("amount"))
    seal_amount = _optional_float(raw.get("fund"))
    optional = {
        "pct_chg": _optional_float(raw.get("zdp")),
        "amount_wan": amount / 10_000.0 if amount is not None else None,
        "main_theme": str(raw.get("hybk") or "").strip() or None,
        "first_seal_time": _time_text(raw.get("fbt")),
        "last_seal_time": _time_text(raw.get("lbt")),
        "reopen_count": _optional_int(raw.get("zbc")),
        "seal_amount_wan": seal_amount / 10_000.0 if seal_amount is not None else None,
    }
    missing = tuple(name for name, value in optional.items() if value is None)
    return PoolFact(
        trade_date=trade_date,
        pool_kind=kind,
        code=code,
        name=str(raw.get("n") or code).strip(),
        board_height=_board_height(raw, kind),
        raw_json=dict(raw),
        missing_fields=missing,
        **optional,
    )


def normalize_topic_pools(
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    trade_date: date,
) -> NormalizedSnapshot:
    missing_pools = [name for name in _POOL_KINDS if name not in pools]
    if missing_pools:
        raise ValueError(f"missing topic pool: {','.join(missing_pools)}")
    by_key: dict[tuple[str, str], PoolFact] = {}
    warnings: list[str] = []
    for source_kind, pool_kind in _POOL_KINDS.items():
        rows = pools[source_kind]
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            raise ValueError(f"topic pool must be a list: {source_kind}")
        for raw in rows:
            if not isinstance(raw, Mapping):
                raise ValueError(f"topic pool row must be an object: {source_kind}")
            fact = _normalize_row(raw, trade_date, pool_kind)
            key = (pool_kind, fact.code)
            previous = by_key.get(key)
            if previous is not None and previous != fact:
                raise ValueError(f"conflicting duplicate topic-pool row: {pool_kind}/{fact.code}")
            if previous is not None:
                warnings.append(f"duplicate:{pool_kind}:{fact.code}")
            by_key[key] = fact
    facts = tuple(sorted(by_key.values(), key=lambda item: (item.pool_kind, item.code)))
    return NormalizedSnapshot(
        trade_date=trade_date,
        facts=facts,
        warnings=tuple(warnings),
        snapshot_hash=snapshot_hash(facts),
    )
