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


def parse_sop_review_text(code: str, review: str, *, name: str = "", score: float = 0.0) -> SopWatchMeta:
    meta = SopWatchMeta(code=code, name=name, score=score)
    match = TAG_RE.search(review)
    if match:
        meta.watch_worthy = match.group(1).strip() == "是"
        meta.decision = match.group(2).strip()
        meta.support = _parse_prices(match.group(3))
        meta.stop = _parse_single_price(match.group(4))
        meta.targets = _parse_prices(match.group(5))
        return meta

    decision_match = re.search(
        r"投资决策[：:]\s*\**([^*\n（(]+)",
        review,
    )
    if decision_match:
        meta.decision = decision_match.group(1).strip().strip("*")

    if any(k in review for k in WATCH_DECISIONS):
        meta.watch_worthy = True
    if "暂不操作" in meta.decision or "暂不操作" in review[-800:]:
        meta.watch_worthy = False

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

    if meta.decision in WATCH_DECISIONS:
        meta.watch_worthy = True

    return meta
