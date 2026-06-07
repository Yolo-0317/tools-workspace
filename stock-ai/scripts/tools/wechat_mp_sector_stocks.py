#!/usr/bin/env python3
"""sector 稿代表股样本：行业领涨 + 人气榜同行业 + 龙头池（搜一搜长尾，非荐股清单）。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_hot_theme import _is_valid_sector_board_name


@dataclass(frozen=True)
class SectorSampleStock:
    code: str
    name: str
    source: str
    theme: str
    detail: str = ""


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def sector_sample_max() -> int:
    return max(2, min(6, _env_int("WECHAT_MP_SECTOR_SAMPLE_MAX", 4)))


def sector_samples_per_theme() -> int:
    return max(1, min(3, _env_int("WECHAT_MP_SECTOR_SAMPLES_PER_THEME", 2)))


def theme_matches(industry: str, theme: str) -> bool:
    a = re.sub(r"\s+", "", (industry or "").strip())
    b = re.sub(r"\s+", "", (theme or "").strip())
    if not a or not b:
        return False
    return b in a or a in b


def _is_eligible(code: str, name: str) -> bool:
    from scripts.tools.wechat_mp_hot_stocks import is_hot_stock_eligible

    return is_hot_stock_eligible(code, name)


def _format_line(stock: SectorSampleStock) -> str:
    code = str(stock.code).zfill(6)
    tail = f" · {stock.detail}" if stock.detail else ""
    return f"- {stock.source} {stock.name}（{code}）题材{stock.theme}{tail}"


def _push(
    out: list[SectorSampleStock],
    seen: set[str],
    *,
    code: str,
    name: str,
    source: str,
    theme: str,
    detail: str = "",
    theme_counts: dict[str, int],
) -> None:
    c = str(code).split(".")[0].zfill(6)
    n = (name or "").strip()
    if not re.fullmatch(r"\d{6}", c) or c in seen or not _is_eligible(c, n):
        return
    th = (theme or "").strip() or "主线"
    if theme_counts.get(th, 0) >= sector_samples_per_theme():
        return
    seen.add(c)
    theme_counts[th] = theme_counts.get(th, 0) + 1
    out.append(
        SectorSampleStock(code=c, name=n, source=source, theme=th, detail=detail)
    )


def collect_sector_sample_stocks(
    theme_names: list[str],
    *,
    board_rows: list[dict] | None = None,
    hot_rows: list | None = None,
    industry_map: dict[str, str] | None = None,
) -> list[SectorSampleStock]:
    """纯函数：合并多源代表股（测试与成稿共用）。"""
    themes = [t for t in theme_names if t]
    if not themes:
        return []

    out: list[SectorSampleStock] = []
    seen: set[str] = set()
    per_theme: dict[str, int] = {t: 0 for t in themes}

    def theme_for_industry(industry: str) -> str | None:
        for t in themes:
            if theme_matches(industry, t):
                return t
        return None

    for row in board_rows or []:
        sector = str(row.get("sector") or row.get("f14") or "").strip()
        if not _is_valid_sector_board_name(sector):
            continue
        th = theme_for_industry(sector)
        if not th:
            continue
        chg = row.get("sector_chg")
        lchg = row.get("leader_chg")
        detail_parts = []
        if chg is not None:
            detail_parts.append(f"板块{chg}%")
        if lchg is not None:
            detail_parts.append(f"领涨{lchg}%")
        _push(
            out,
            seen,
            code=str(row.get("code") or row.get("leader_code") or ""),
            name=str(row.get("leader_name") or row.get("f128") or ""),
            source="行业领涨",
            theme=th,
            detail=" ".join(detail_parts),
            theme_counts=per_theme,
        )
        if len(out) >= sector_sample_max():
            return out[: sector_sample_max()]

    ind_map = industry_map or {}
    for row in hot_rows or []:
        code = getattr(row, "code", None) or (row.get("code") if isinstance(row, dict) else "")
        name = getattr(row, "name", None) or (row.get("name") if isinstance(row, dict) else "")
        industry = ind_map.get(str(code).zfill(6), "")
        th = theme_for_industry(industry) if industry else None
        if not th:
            continue
        rank = getattr(row, "rank", None) or (row.get("rank") if isinstance(row, dict) else "")
        chg = getattr(row, "change_pct", None)
        if chg is None and isinstance(row, dict):
            chg = row.get("change_pct")
        detail = f"人气榜第{rank}" if rank else "东财人气"
        if chg is not None:
            detail += f" 涨跌{chg}%"
        _push(
            out,
            seen,
            code=str(code),
            name=str(name),
            source="人气观察",
            theme=th,
            detail=detail,
            theme_counts=per_theme,
        )
        if len(out) >= sector_sample_max():
            return out[: sector_sample_max()]

    try:
        from scripts.tools.portfolio_db import load_emotion_cycle_checklist

        bundle = load_emotion_cycle_checklist(
            checklist_slot=os.getenv("WECHAT_MP_DRAGON_SLOT", "eod")
        ) or load_emotion_cycle_checklist()
        if bundle:
            for row in bundle.get("dragon_items") or []:
                th_raw = str(row.get("main_theme") or "").strip()
                th = theme_for_industry(th_raw) or (
                    th_raw if any(theme_matches(th_raw, t) for t in themes) else None
                )
                if not th:
                    continue
                bh = row.get("board_height")
                _push(
                    out,
                    seen,
                    code=str(row.get("ts_code") or "")[:6],
                    name=str(row.get("name") or "").strip(),
                    source="龙头观察",
                    theme=th,
                    detail=f"连板{int(bh or 1)}",
                    theme_counts=per_theme,
                )
                if len(out) >= sector_sample_max():
                    return out[: sector_sample_max()]
    except Exception:
        pass

    try:
        from scripts.tools.wechat_mp_hot_stocks import load_wechat_top5_hot_picks
        from scripts.tools.selection_watchlist import load_wechat_top5_selection_picks

        picks = []
        try:
            _, picks, _ = load_wechat_top5_hot_picks(top_n=8)
        except Exception:
            _, picks, _ = load_wechat_top5_selection_picks(top_n=8)
        for p in picks:
            industry = ind_map.get(p.code, "")
            th = theme_for_industry(industry) if industry else None
            if not th:
                continue
            _push(
                out,
                seen,
                code=p.code,
                name=p.name or p.code,
                source="选股观察",
                theme=th,
                detail=f"收盘{p.change_pct}%",
                theme_counts=per_theme,
            )
            if len(out) >= sector_sample_max():
                return out[: sector_sample_max()]
    except Exception:
        pass

    return out[: sector_sample_max()]


def collect_sector_sample_lines(theme_names: list[str]) -> list[str]:
    """成稿入口：OpenCLI 拉行业领涨 + 人气榜，合并代表股文本行。"""
    board_rows: list[dict] = []
    hot_rows: list = []
    industry_map: dict[str, str] = {}

    try:
        from scripts.tools.fetch_eastmoney_quotes import fetch_hot_industry_board_rows_opencli

        board_rows = fetch_hot_industry_board_rows_opencli(
            top_n=max(12, sector_sample_max() * 3)
        )
    except Exception:
        board_rows = []

    if os.getenv("WECHAT_MP_SECTOR_HOT_STOCKS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    ):
        try:
            from scripts.tools.wechat_mp_hot_stocks import fetch_hot_stock_rows

            hot_rows = fetch_hot_stock_rows(top_n=hot_fetch_top_n())
        except Exception:
            hot_rows = []

    try:
        from scripts.tools.portfolio_db import load_industry_map

        industry_map = load_industry_map()
    except Exception:
        industry_map = {}

    stocks = collect_sector_sample_stocks(
        theme_names,
        board_rows=board_rows,
        hot_rows=hot_rows,
        industry_map=industry_map,
    )
    if not stocks:
        return ["（暂无与主题直接对应的龙头/代表股，仅写产业链逻辑）"]
    return [_format_line(s) for s in stocks]


def hot_fetch_top_n() -> int:
    from scripts.tools.wechat_mp_hot_stocks import hot_fetch_top_n as _hot_n

    return _hot_n()
