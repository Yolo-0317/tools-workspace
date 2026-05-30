#!/usr/bin/env python3
"""解析东财 SOP DeepSeek 终审中的机器可读标签与关键价位。"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

TAG_RE = re.compile(
    r"WATCH:\s*(是|否)\s*\|\s*DECISION:\s*([^|]+?)\s*\|\s*SUPPORT:\s*([^|]*?)\s*\|\s*STOP:\s*([^|]*?)\s*\|\s*TARGET:\s*(.+?)\s*$",
    re.MULTILINE,
)

WATCH_DECISIONS = frozenset({"买入观察", "观察买入", "小仓埋伏"})
SKIP_DECISIONS = frozenset({"暂不操作", "放弃", "拒绝", "持有", "减仓"})


@dataclass
class SopWatchMeta:
    code: str
    name: str = ""
    score: float = 0.0
    decision: str = ""
    watch_worthy: bool = False
    support: list[float] = field(default_factory=list)
    stop: float | None = None
    targets: list[float] = field(default_factory=list)
    in_holdings: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_prices(raw: str) -> list[float]:
    text = (raw or "").strip()
    if not text or text in {"-", "无", "NA", "None"}:
        return []
    out: list[float] = []
    for part in re.split(r"[,，、/]", text):
        m = re.search(r"([\d.]+)", part)
        if m:
            out.append(float(m.group(1)))
    return out


def _parse_single_price(raw: str) -> float | None:
    prices = _parse_prices(raw)
    return prices[0] if prices else None


def _normalize_decision(decision: str) -> str:
    text = (decision or "").strip().strip("*")
    for sep in ("（", "(", "：", ":", "—", "-"):
        if sep in text:
            text = text.split(sep, 1)[0].strip()
    return text


def _decision_implies_watch(decision: str) -> bool | None:
    """DECISION 优先于 WATCH 标签。返回 None 表示无法从决策判定。"""
    norm = _normalize_decision(decision)
    if not norm:
        return None
    if norm in SKIP_DECISIONS or any(sk in norm for sk in SKIP_DECISIONS):
        return False
    if norm in WATCH_DECISIONS:
        return True
    for watch in WATCH_DECISIONS:
        if watch in norm:
            return True
    return None


def _finalize_watch(meta: SopWatchMeta, *, tag_watch: bool | None = None) -> SopWatchMeta:
    meta.decision = _normalize_decision(meta.decision)
    implied = _decision_implies_watch(meta.decision)
    if implied is not None:
        meta.watch_worthy = implied
    elif tag_watch is not None:
        meta.watch_worthy = tag_watch
    else:
        meta.watch_worthy = False
    return meta


def parse_sop_review_text(code: str, review: str, *, name: str = "", score: float = 0.0) -> SopWatchMeta:
    meta = SopWatchMeta(code=code, name=name, score=score)
    match = TAG_RE.search(review)
    if match:
        tag_watch = match.group(1).strip() == "是"
        meta.decision = match.group(2).strip()
        meta.support = _parse_prices(match.group(3))
        meta.stop = _parse_single_price(match.group(4))
        meta.targets = _parse_prices(match.group(5))
        return _finalize_watch(meta, tag_watch=tag_watch)

    decision_match = re.search(
        r"投资决策[：:]\s*\**([^*\n]+)",
        review,
    )
    if decision_match:
        meta.decision = decision_match.group(1).strip().strip("*")

    stop_match = re.search(r"止损位[：:]\s*\**([\d.]+)", review)
    if stop_match:
        meta.stop = float(stop_match.group(1))

    support_block = review
    if "支撑位" in review:
        start = review.find("支撑位")
        end = review.find("压力位", start)
        support_block = review[start:end if end > start else start + 120]
    meta.support = _parse_prices(support_block)

    target_block = review
    if "目标位" in review:
        start = review.find("目标位")
        target_block = review[start : start + 160]
    meta.targets = _parse_prices(target_block)

    return _finalize_watch(meta, tag_watch=None)


def reparse_watch_meta(meta_dict: dict) -> dict:
    """从已存 JSON 条目重算 watch_worthy（不重跑 SOP）。"""
    meta = SopWatchMeta(
        code=str(meta_dict.get("code", "")).zfill(6),
        name=str(meta_dict.get("name") or ""),
        score=float(meta_dict.get("score") or 0),
        decision=str(meta_dict.get("decision") or ""),
        support=list(meta_dict.get("support") or []),
        stop=meta_dict.get("stop"),
        targets=list(meta_dict.get("targets") or []),
        in_holdings=bool(meta_dict.get("in_holdings")),
    )
    if meta.stop is not None:
        meta.stop = float(meta.stop)
    finalized = _finalize_watch(meta, tag_watch=bool(meta_dict.get("watch_worthy")))
    if finalized.in_holdings:
        finalized.watch_worthy = False
    return finalized.to_dict()
