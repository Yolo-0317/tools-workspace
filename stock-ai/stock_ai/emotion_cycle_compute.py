"""情绪周期日检：从 MySQL stock_daily 计算并入库。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

TZ = ZoneInfo("Asia/Shanghai")

EMOTION_PHASES = ("冰点", "启动", "发酵", "高潮", "分歧", "退潮")

POSITION_CAP_BY_PHASE: dict[str, float] = {
    "冰点": 10.0,
    "启动": 40.0,
    "发酵": 60.0,
    "高潮": 75.0,
    "分歧": 40.0,
    "退潮": 0.0,
}

ACTION_BY_PHASE: dict[str, str] = {
    "冰点": "空仓",
    "启动": "试错",
    "发酵": "观察",
    "高潮": "持仓",
    "分歧": "观察",
    "退潮": "空仓",
}


@dataclass
class DragonCandidate:
    ts_code: str
    name: str
    board_height: int
    main_theme: str
    checklist_pass: int
    amount_wan: float
    pct_chg: float
    notes: str = ""


@dataclass
class EmotionMetrics:
    trade_date: date
    limit_up_count: int
    limit_down_count: int
    up_count: int
    down_count: int
    flat_count: int
    max_board_height: int
    limit_up_premium_pct: float | None
    explode_rate_pct: float | None
    total_amount_yi: float | None
    theme_count: int
    main_theme: str
    phase: str
    phase_vs_yesterday: str | None
    position_cap_pct: float
    allow_new_open: bool
    action_summary: str
    dragon_items: list[DragonCandidate] = field(default_factory=list)
    exclude_list: str = ""
    data_source: str = "mysql-stock_daily"
    raw_json: dict[str, Any] = field(default_factory=dict)


def _code6(ts_code: str) -> str:
    return str(ts_code).split(".")[0].zfill(6)


def _limit_threshold(code: str) -> float:
    c = _code6(code)
    if c.startswith(("688", "689", "30")):
        return 19.5
    if c.startswith("92"):
        return 29.5
    return 9.5


def _is_limit_up(code: str, pct: float | None) -> bool:
    if pct is None:
        return False
    return pct >= _limit_threshold(code) - 0.05


def _is_limit_down(code: str, pct: float | None) -> bool:
    if pct is None:
        return False
    th = _limit_threshold(code)
    return pct <= -(th - 0.05)


def _is_st(name: str) -> bool:
    n = (name or "").upper()
    return "ST" in n or "*ST" in n


def get_engine() -> Engine | None:
    from scripts.tools.portfolio_db import mysql_url

    url = mysql_url()
    if not url:
        return None
    return create_engine(url)


def latest_trade_date(engine: Engine, *, on_or_before: date | None = None) -> date | None:
    sql = "SELECT MAX(trade_date) AS d FROM stock_daily"
    params: dict[str, Any] = {}
    if on_or_before:
        sql = "SELECT MAX(trade_date) AS d FROM stock_daily WHERE trade_date <= :d"
        params["d"] = on_or_before.isoformat()
    with engine.connect() as conn:
        row = conn.execute(text(sql), params).fetchone()
    if not row or row.d is None:
        return None
    val = row.d
    return val if isinstance(val, date) else datetime.strptime(str(val)[:10], "%Y-%m-%d").date()


def previous_trade_date(engine: Engine, trade_date: date) -> date | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT MAX(trade_date) AS d FROM stock_daily "
                "WHERE trade_date < :d"
            ),
            {"d": trade_date.isoformat()},
        ).fetchone()
    if not row or row.d is None:
        return None
    val = row.d
    return val if isinstance(val, date) else datetime.strptime(str(val)[:10], "%Y-%m-%d").date()


def _load_names(engine: Engine, codes: list[str]) -> dict[str, str]:
    if not codes:
        return {}
    from scripts.tools.portfolio_db import load_stock_names_by_codes

    return load_stock_names_by_codes(codes, engine=engine)


def _load_industries(engine: Engine, codes: list[str]) -> dict[str, str]:
    from scripts.tools.portfolio_db import load_industry_map

    full = load_industry_map(engine=engine)
    if not codes:
        return full
    want = {_code6(c) for c in codes}
    return {k: v for k, v in full.items() if _code6(k) in want}


def _load_day_bars(engine: Engine, trade_date: date) -> pd.DataFrame:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT ts_code, open, high, low, close, pct_chg, amount, vol
                FROM stock_daily
                WHERE trade_date = :d
                """
            ),
            {"d": trade_date.isoformat()},
        ).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r._mapping) for r in rows])
    df["code"] = df["ts_code"].astype(str).map(_code6)
    return df


def _load_history_for_codes(
    engine: Engine,
    codes: list[str],
    end_date: date,
    *,
    lookback: int = 20,
) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame()
    start = end_date - timedelta(days=lookback * 2)
    placeholders = ", ".join(f":c{i}" for i in range(len(codes)))
    params: dict[str, Any] = {f"c{i}": c for i, c in enumerate(codes)}
    params["start"] = start.isoformat()
    params["end"] = end_date.isoformat()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT ts_code, trade_date, close, pct_chg
                FROM stock_daily
                WHERE trade_date BETWEEN :start AND :end
                  AND ts_code IN ({placeholders})
                ORDER BY ts_code, trade_date
                """
            ),
            params,
        ).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r._mapping) for r in rows])
    df["code"] = df["ts_code"].astype(str).map(_code6)
    return df


def _board_height(code: str, hist: pd.DataFrame, trade_date: date) -> int:
    sub = hist[hist["code"] == _code6(code)].copy()
    if sub.empty:
        return 0
    sub["trade_date"] = sub["trade_date"].apply(
        lambda v: v if isinstance(v, date) else datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    )
    sub = sub[sub["trade_date"] <= trade_date].sort_values("trade_date")
    if sub.empty:
        return 0
    last = sub.iloc[-1]
    if last["trade_date"] != trade_date:
        return 0
    if not _is_limit_up(code, float(last["pct_chg"]) if last["pct_chg"] is not None else None):
        return 0
    streak = 0
    for _, row in sub.iloc[::-1].iterrows():
        pct = row.get("pct_chg")
        if _is_limit_up(code, float(pct) if pct is not None else None):
            streak += 1
        else:
            break
    return streak


def _explode_stats(df: pd.DataFrame) -> tuple[int, int, float | None]:
    touched = 0
    closed = 0
    for _, row in df.iterrows():
        code = row["code"]
        pct = row.get("pct_chg")
        close = row.get("close")
        high = row.get("high")
        if close is None or high is None or pct is None:
            continue
        pct_f = float(pct)
        if _is_limit_up(code, pct_f):
            closed += 1
            touched += 1
            continue
        if pct_f <= 0:
            continue
        prev = float(close) / (1 + pct_f / 100.0)
        if prev <= 0:
            continue
        high_pct = (float(high) - prev) / prev * 100.0
        th = _limit_threshold(code)
        if high_pct >= th - 0.8:
            touched += 1
    if touched == 0:
        return 0, closed, None
    exploded = max(0, touched - closed)
    return exploded, closed, round(exploded / touched * 100.0, 2)


def _yesterday_limit_premium(
    engine: Engine,
    trade_date: date,
    prev_date: date | None,
) -> float | None:
    if not prev_date:
        return None
    prev_df = _load_day_bars(engine, prev_date)
    today_df = _load_day_bars(engine, trade_date)
    if prev_df.empty or today_df.empty:
        return None
    prev_codes = {
        row["code"]
        for _, row in prev_df.iterrows()
        if _is_limit_up(row["code"], float(row["pct_chg"]) if row["pct_chg"] is not None else None)
    }
    if not prev_codes:
        return None
    today_map = {
        row["code"]: float(row["pct_chg"])
        for _, row in today_df.iterrows()
        if row["pct_chg"] is not None
    }
    vals = [today_map[c] for c in prev_codes if c in today_map]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 2)


def _fmt_amount_wan(wan: float) -> str:
    if wan >= 100_000:
        return f"成交额{wan / 10_000:.1f}亿"
    return f"成交额{wan:.0f}万"


def _dominant_theme(limit_df: pd.DataFrame, industries: dict[str, str]) -> tuple[str, int]:
    if limit_df.empty:
        return "", 0
    themes: dict[str, int] = {}
    for _, row in limit_df.iterrows():
        ind = (industries.get(row["code"]) or "未知").strip()
        if not ind or ind == "未知":
            continue
        themes[ind] = themes.get(ind, 0) + 1
    if not themes:
        return "", 0
    sorted_themes = sorted(themes.items(), key=lambda x: (-x[1], x[0]))
    main = sorted_themes[0][0]
    active = sum(1 for _, n in themes.items() if n >= 3)
    return main, max(active, len(sorted_themes[:5]))


def _score_dragon(
    *,
    board_height: int,
    main_theme: str,
    dominant_theme: str,
    amount_wan: float,
    pct: float,
    is_st: bool,
) -> int:
    score = 0
    if board_height >= 2:
        score += 1
    if board_height >= max(2, 1):
        score += 1
    if dominant_theme and main_theme == dominant_theme:
        score += 1
    if amount_wan >= 5000:
        score += 1
    if 2 <= pct <= 10.5:
        score += 1
    if not is_st:
        score += 1
    if board_height >= 3:
        score += 1
    return min(score, 7)


def infer_phase(
    *,
    limit_up: int,
    limit_down: int,
    max_board: int,
    explode_rate: float | None,
    theme_count: int,
    premium: float | None,
) -> str:
    er = explode_rate if explode_rate is not None else 0.0
    if limit_down >= 30:
        return "退潮"
    if limit_down >= 15 and max_board <= 3:
        return "分歧"
    if er >= 40 and max_board <= 3:
        return "冰点"
    if max_board >= 5 and limit_up >= 40:
        return "发酵"
    if max_board >= 4 and limit_up >= 55:
        return "高潮"
    if max_board >= 3 and limit_up >= 40:
        return "启动"
    if limit_up >= 40 and (premium or 0) >= 1.0:
        return "启动"
    if limit_up <= 20 and max_board <= 2:
        return "冰点"
    if er >= 30:
        return "分歧"
    if theme_count > 3:
        return "分歧"
    return "启动" if limit_up >= 30 else "冰点"


def _phase_rank(phase: str) -> int:
    order = ["冰点", "退潮", "分歧", "启动", "发酵", "高潮"]
    try:
        return order.index(phase)
    except ValueError:
        return 0


def compute_emotion_metrics(
    engine: Engine,
    trade_date: date,
    *,
    prev_phase: str | None = None,
) -> EmotionMetrics:
    df = _load_day_bars(engine, trade_date)
    if df.empty:
        raise RuntimeError(f"stock_daily 无数据: {trade_date.isoformat()}")

    codes = df["code"].tolist()
    names = _load_names(engine, codes)
    industries = _load_industries(engine, codes)

    df["name"] = df["code"].map(lambda c: names.get(c, c))
    df["pct"] = pd.to_numeric(df["pct_chg"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    mask_valid = ~df["code"].str.startswith("92")
    df = df[mask_valid]
    df = df[~df["name"].map(_is_st)]

    up = int((df["pct"] > 0).sum())
    down = int((df["pct"] < 0).sum())
    flat = int((df["pct"] == 0).sum())

    limit_up_df = df[df.apply(lambda r: _is_limit_up(r["code"], r["pct"]), axis=1)]
    limit_down_count = int(df.apply(lambda r: _is_limit_down(r["code"], r["pct"]), axis=1).sum())

    exploded, _, explode_rate = _explode_stats(df)

    prev_td = previous_trade_date(engine, trade_date)
    premium = _yesterday_limit_premium(engine, trade_date, prev_td)

    total_amount_yi = round(float(df["amount"].sum()) / 100_000.0, 2)

    main_theme, theme_count = _dominant_theme(limit_up_df, industries)

    limit_codes = limit_up_df["code"].tolist()
    hist = _load_history_for_codes(engine, limit_codes, trade_date)
    board_map: dict[str, int] = {}
    for code in limit_codes:
        board_map[code] = _board_height(code, hist, trade_date)

    max_board = max(board_map.values()) if board_map else 0

    phase = infer_phase(
        limit_up=len(limit_up_df),
        limit_down=limit_down_count,
        max_board=max_board,
        explode_rate=explode_rate,
        theme_count=theme_count,
        premium=premium,
    )

    if prev_phase:
        diff = _phase_rank(phase) - _phase_rank(prev_phase)
        if diff > 0:
            phase_vs = "升温"
        elif diff < 0:
            phase_vs = "降温"
        else:
            phase_vs = "持平"
    else:
        phase_vs = None

    cap = POSITION_CAP_BY_PHASE.get(phase, 20.0)
    allow = phase in {"启动", "发酵", "高潮"} and (explode_rate or 0) < 40
    if premium is not None and premium < 1.0:
        allow = allow and phase == "发酵"
    action = ACTION_BY_PHASE.get(phase, "观察")

    dragons: list[DragonCandidate] = []
    candidates = limit_up_df.copy()
    candidates["board_height"] = candidates["code"].map(lambda c: board_map.get(c, 1))
    candidates["amount_wan"] = candidates["amount"] / 10.0
    candidates = candidates.sort_values(
        ["board_height", "amount"], ascending=[False, False]
    )
    for _, row in candidates.head(20).iterrows():
        bh = int(row["board_height"] or 1)
        if bh < 2:
            continue
        code = row["code"]
        ind = (industries.get(code) or main_theme or "").strip()
        amt = float(row["amount_wan"])
        pct = float(row["pct"])
        score = _score_dragon(
            board_height=bh,
            main_theme=ind,
            dominant_theme=main_theme,
            amount_wan=amt,
            pct=pct,
            is_st=_is_st(str(row["name"])),
        )
        if score < 5:
            continue
        dragons.append(
            DragonCandidate(
                ts_code=code,
                name=str(row["name"]),
                board_height=bh,
                main_theme=ind,
                checklist_pass=score,
                amount_wan=amt,
                pct_chg=pct,
                notes=_fmt_amount_wan(amt),
            )
        )
        if len(dragons) >= 3:
            break

    exclude = "跟风杂毛"
    if phase in {"冰点", "退潮"}:
        exclude += "；连板接力"
    if theme_count > 3:
        exclude += "；多题材混战"

    return EmotionMetrics(
        trade_date=trade_date,
        limit_up_count=len(limit_up_df),
        limit_down_count=limit_down_count,
        up_count=up,
        down_count=down,
        flat_count=flat,
        max_board_height=max_board,
        limit_up_premium_pct=premium,
        explode_rate_pct=explode_rate,
        total_amount_yi=total_amount_yi,
        theme_count=theme_count,
        main_theme=main_theme,
        phase=phase,
        phase_vs_yesterday=phase_vs,
        position_cap_pct=cap,
        allow_new_open=allow,
        action_summary=action,
        dragon_items=dragons,
        exclude_list=exclude,
        raw_json={
            "exploded_count": exploded,
            "prev_trade_date": prev_td.isoformat() if prev_td else None,
            "computed_at": datetime.now(TZ).isoformat(timespec="seconds"),
        },
    )


def metrics_to_payload(metrics: EmotionMetrics) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    header = {
        "limit_up_count": metrics.limit_up_count,
        "limit_down_count": metrics.limit_down_count,
        "up_down_ratio": (
            "盘中"
            if metrics.up_count == 0
            and metrics.down_count == 0
            and "intraday" in metrics.data_source
            else f"{metrics.up_count}:{metrics.down_count}"
        ),
        "max_board_height": metrics.max_board_height,
        "limit_up_premium_pct": metrics.limit_up_premium_pct,
        "explode_rate_pct": metrics.explode_rate_pct,
        "total_amount_yi": metrics.total_amount_yi,
        "theme_count": metrics.theme_count,
        "phase": metrics.phase,
        "phase_vs_yesterday": metrics.phase_vs_yesterday,
        "position_cap_pct": metrics.position_cap_pct,
        "allow_new_open": 1 if metrics.allow_new_open else 0,
        "main_theme": metrics.main_theme,
        "main_theme_is_new": 0,
        "drain_market": 0,
        "action_summary": metrics.action_summary,
        "exclude_list": metrics.exclude_list,
        "review_notes": f"自动采集({metrics.data_source})",
        "raw_json": {
            **metrics.raw_json,
            "data_source": metrics.data_source,
            "flat_count": metrics.flat_count,
        },
    }
    dragons = [
        {
            "ts_code": d.ts_code,
            "name": d.name,
            "board_height": d.board_height,
            "main_theme": d.main_theme,
            "checklist_pass": d.checklist_pass,
            "notes": d.notes,
            "raw_json": {"pct_chg": d.pct_chg, "amount_wan": d.amount_wan},
        }
        for d in metrics.dragon_items
    ]
    return header, dragons


def resolve_sync_trade_date(
    engine: Engine,
    *,
    checklist_slot: str,
    explicit: date | str | None = None,
) -> date:
    if explicit:
        if isinstance(explicit, str):
            return datetime.strptime(explicit[:10], "%Y-%m-%d").date()
        return explicit
    now = datetime.now(TZ)
    latest = latest_trade_date(engine)
    if latest is None:
        raise RuntimeError("stock_daily 无交易日")
    slot = (checklist_slot or "eod").strip()
    if slot == "intraday":
        return now.date()
    if slot == "pre_market":
        # 盘前：用已入库最近交易日（周一早盘即上周五）
        if now.weekday() < 5 and now.hour < 15:
            return latest
        return latest
    return latest


def is_intraday_session(now: datetime | None = None) -> bool:
    """A 股连续竞价时段（含午休）。"""
    from datetime import time

    now = now or datetime.now(TZ)
    if now.weekday() >= 5:
        return False
    t = now.time()
    return (time(9, 30) <= t <= time(11, 30)) or (time(13, 0) <= t <= time(15, 0))


def compute_emotion_metrics_intraday(
    engine: Engine,
    trade_date: date,
    *,
    prev_phase: str | None = None,
) -> EmotionMetrics:
    """盘中情绪：东财涨停/炸板/跌停池 + 昨日涨停溢价（批量 HTTP 行情）。"""
    from stock_ai.emotion_intraday_fetch import fetch_all_topic_pools, parse_zt_row

    pools = fetch_all_topic_pools(trade_date)
    zt_raw = pools.get("zt") or []
    zb_raw = pools.get("zb") or []
    dt_raw = pools.get("dt") or []

    zt_rows = [parse_zt_row(r) for r in zt_raw]
    zt_rows = [r for r in zt_rows if r["code"] and not _is_st(r["name"])]

    limit_up_count = len(zt_rows)
    limit_down_count = len(dt_raw)
    zb_count = len(zb_raw)
    touched = limit_up_count + zb_count
    explode_rate = round(zb_count / touched * 100.0, 2) if touched else None

    prev_td = previous_trade_date(engine, trade_date)
    premium = _yesterday_limit_premium_intraday(engine, trade_date, prev_td)

    themes: dict[str, int] = {}
    for row in zt_rows:
        th = (row.get("main_theme") or "").strip()
        if th:
            themes[th] = themes.get(th, 0) + 1
    if themes:
        main_theme = max(themes.items(), key=lambda x: (x[1], x[0]))[0]
        theme_count = sum(1 for _, n in themes.items() if n >= 3)
        theme_count = max(theme_count, min(len(themes), 5))
    else:
        main_theme, theme_count = "", 0

    max_board = max((int(r["board_height"]) for r in zt_rows), default=0)

    phase = infer_phase(
        limit_up=limit_up_count,
        limit_down=limit_down_count,
        max_board=max_board,
        explode_rate=explode_rate,
        theme_count=theme_count,
        premium=premium,
    )

    if prev_phase:
        diff = _phase_rank(phase) - _phase_rank(prev_phase)
        if diff > 0:
            phase_vs = "升温"
        elif diff < 0:
            phase_vs = "降温"
        else:
            phase_vs = "持平"
    else:
        phase_vs = None

    cap = POSITION_CAP_BY_PHASE.get(phase, 20.0)
    allow = phase in {"启动", "发酵", "高潮"} and (explode_rate or 0) < 40
    if premium is not None and premium < 1.0:
        allow = allow and phase == "发酵"
    action = ACTION_BY_PHASE.get(phase, "观察")

    dragons: list[DragonCandidate] = []
    sorted_zt = sorted(
        zt_rows,
        key=lambda r: (int(r["board_height"]), float(r["amount_wan"])),
        reverse=True,
    )
    for row in sorted_zt:
        bh = int(row["board_height"])
        if bh < 2:
            continue
        ind = (row.get("main_theme") or main_theme or "").strip()
        amt = float(row["amount_wan"])
        pct = float(row["pct_chg"])
        score = _score_dragon(
            board_height=bh,
            main_theme=ind,
            dominant_theme=main_theme,
            amount_wan=amt,
            pct=pct,
            is_st=_is_st(str(row["name"])),
        )
        if score < 5:
            continue
        dragons.append(
            DragonCandidate(
                ts_code=row["code"],
                name=str(row["name"]),
                board_height=bh,
                main_theme=ind,
                checklist_pass=score,
                amount_wan=amt,
                pct_chg=pct,
                notes=_fmt_amount_wan(amt),
            )
        )
        if len(dragons) >= 3:
            break

    exclude = "跟风杂毛"
    if phase in {"冰点", "退潮"}:
        exclude += "；连板接力"
    if theme_count > 3:
        exclude += "；多题材混战"

    total_amount_yi = round(sum(float(r["amount_wan"]) for r in zt_rows) / 10_000.0, 2)

    return EmotionMetrics(
        trade_date=trade_date,
        limit_up_count=limit_up_count,
        limit_down_count=limit_down_count,
        up_count=0,
        down_count=0,
        flat_count=0,
        max_board_height=max_board,
        limit_up_premium_pct=premium,
        explode_rate_pct=explode_rate,
        total_amount_yi=total_amount_yi if total_amount_yi > 0 else None,
        theme_count=theme_count,
        main_theme=main_theme,
        phase=phase,
        phase_vs_yesterday=phase_vs,
        position_cap_pct=cap,
        allow_new_open=allow,
        action_summary=action,
        dragon_items=dragons,
        exclude_list=exclude,
        data_source="eastmoney-topic-pool-intraday",
        raw_json={
            "exploded_count": zb_count,
            "prev_trade_date": prev_td.isoformat() if prev_td else None,
            "computed_at": datetime.now(TZ).isoformat(timespec="seconds"),
            "zt_pool_size": limit_up_count,
            "zb_pool_size": zb_count,
        },
    )


def _yesterday_limit_premium_intraday(
    engine: Engine,
    trade_date: date,
    prev_date: date | None,
) -> float | None:
    """盘中不重算昨涨停溢价（避免上百只逐股 OpenCLI）；阶段 gate 以涨停/炸板/连板为主。"""
    return None


def sync_emotion_cycle(
    *,
    trade_date: date | str | None = None,
    checklist_slot: str = "eod",
    engine: Engine | None = None,
) -> dict[str, Any]:
    from scripts.tools.portfolio_db import (
        load_emotion_cycle_checklist,
        save_emotion_cycle_checklist,
    )

    eng = engine or get_engine()
    if eng is None:
        raise RuntimeError("未配置 MYSQL_URL")

    slot = checklist_slot.strip() or "eod"
    if slot == "intraday" and not is_intraday_session():
        return {"skipped": True, "reason": "非交易时段", "checklist_slot": slot}

    td = resolve_sync_trade_date(eng, checklist_slot=slot, explicit=trade_date)

    prev_bundle = load_emotion_cycle_checklist(
        previous_trade_date(eng, td) if previous_trade_date(eng, td) else td,
        checklist_slot="eod",
        engine=eng,
    )
    prev_phase = None
    if prev_bundle and prev_bundle.get("header"):
        prev_phase = str(prev_bundle["header"].get("phase") or "") or None

    if slot == "intraday":
        metrics = compute_emotion_metrics_intraday(eng, td, prev_phase=prev_phase)
    else:
        metrics = compute_emotion_metrics(eng, td, prev_phase=prev_phase)
    header, dragons = metrics_to_payload(metrics)
    stats = save_emotion_cycle_checklist(td, header, checklist_slot=slot, dragon_items=dragons)
    return {
        **stats,
        "phase": metrics.phase,
        "limit_up_count": metrics.limit_up_count,
        "dragon_count": len(dragons),
        "data_source": metrics.data_source,
    }
