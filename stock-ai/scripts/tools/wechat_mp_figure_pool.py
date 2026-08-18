"""公众号正文插图池：manifest 目录 + 当日去重分配。"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
INLINE_ROOT = ROOT / "assets" / "wechat_mp" / "inline"
MANIFEST_PATH = INLINE_ROOT / "manifest.json"
USAGE_PATH = ROOT / "data" / "wechat_mp_figure_usage.json"
TZ = ZoneInfo("Asia/Shanghai")

# 当前财经稿 inline 池（勿含家居、厨房等旧商品垂直素材）
FIGURE_DOMAIN_TAGS: frozenset[str] = frozenset(
    {
        "market",
        "chart",
        "trading",
        "screen",
        "tech",
        "ai",
        "finance",
        "selection",
        "emotion",
        "workspace",
    }
)

def figure_matches_domain(tags: tuple[str, ...]) -> bool:
    return bool(set(tags) & FIGURE_DOMAIN_TAGS)


# 兼容旧 4 张图
_LEGACY_FILES = (
    "inline-market-chart.jpg",
    "inline-market-screen.jpg",
    "inline-global-finance.jpg",
    "inline-ai-tech.jpg",
)


@dataclass(frozen=True)
class InlineFigure:
    file: str
    tags: tuple[str, ...]
    caption: str


@dataclass(frozen=True)
class FigureSlot:
    """插图锚点：在某节前/节后插入。"""

    key: str
    anchor: str  # before | after
    section: str
    tags: tuple[str, ...]
    caption: str | None = None


def _today() -> str:
    return datetime.now(TZ).date().isoformat()


def _load_manifest() -> list[InlineFigure]:
    if not MANIFEST_PATH.is_file():
        return _legacy_catalog()
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return _legacy_catalog()
    out: list[InlineFigure] = []
    for row in data.get("figures") or []:
        fname = str(row.get("file") or "").strip()
        if not fname:
            continue
        tags = tuple(str(t).strip() for t in (row.get("tags") or []) if str(t).strip())
        caption = str(row.get("caption") or "").strip() or "配图"
        if not figure_matches_domain(tags):
            continue
        out.append(InlineFigure(file=fname, tags=tags, caption=caption))
    return out or _legacy_catalog()


def _legacy_catalog() -> list[InlineFigure]:
    return [
        InlineFigure("inline-market-chart.jpg", ("market", "chart"), "主要指数与涨跌家数一览"),
        InlineFigure("inline-global-finance.jpg", ("global", "finance"), "外围市场与资金流向"),
        InlineFigure("inline-market-screen.jpg", ("screen", "tech"), "资金向核心资产与科技链条聚集"),
        InlineFigure("inline-ai-tech.jpg", ("tech", "ai"), "科技链与宏观变量交织"),
    ]


def _load_usage() -> tuple[str, set[str]]:
    if not USAGE_PATH.is_file():
        return _today(), set()
    try:
        data = json.loads(USAGE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return _today(), set()
    day = str(data.get("date") or "")
    if day != _today():
        return _today(), set()
    used = {str(x) for x in (data.get("used") or []) if x}
    return day, used


def _save_usage(used: set[str]) -> None:
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"date": _today(), "used": sorted(used), "updated_at": datetime.now(TZ).isoformat()}
    USAGE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def reset_daily_usage(*, force: bool = False) -> None:
    if force and USAGE_PATH.is_file():
        USAGE_PATH.unlink()


def list_available_figures() -> list[InlineFigure]:
    catalog = _load_manifest()
    return [f for f in catalog if (INLINE_ROOT / f.file).is_file() and figure_matches_domain(f.tags)]


def _score(candidate: InlineFigure, tags: tuple[str, ...]) -> int:
    if not tags:
        return 0
    return sum(1 for t in tags if t in candidate.tags)


def _pick_index(candidates: list[InlineFigure], key: str) -> int:
    if not candidates:
        return 0
    digest = hashlib.sha256(f"{_today()}:{key}".encode()).hexdigest()
    return int(digest, 16) % len(candidates)


def allocate_figure(*, key: str, tags: tuple[str, ...], caption: str | None = None) -> tuple[str, str]:
    """从池里选一张当日未用过的图；用尽后允许复用。"""
    catalog = list_available_figures()
    if not catalog:
        raise FileNotFoundError(
            "无可用 inline 插图（须含 market/chart/screen 等标签），"
            "请检查 manifest 并运行 download_wechat_mp_inline_figures"
        )

    _day, used = _load_usage()
    fresh = [c for c in catalog if c.file not in used]
    pool = fresh or [c for c in catalog if c.file not in _LEGACY_FILES] or catalog

    ranked = sorted(pool, key=lambda c: (_score(c, tags), c.file), reverse=True)
    top_score = _score(ranked[0], tags) if ranked else 0
    tier = [c for c in ranked if _score(c, tags) == top_score] or ranked
    pick = tier[_pick_index(tier, key)]
    cap = (caption or pick.caption).strip()
    used.add(pick.file)
    _save_usage(used)
    return pick.file, cap


def resolve_caption(entry: InlineFigure, override: str | None) -> str:
    return (override or entry.caption).strip()
