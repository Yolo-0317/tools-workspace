#!/usr/bin/env python3
"""选股结果读取：MySQL selection_daily_results 优先，CSV 兜底。"""

from __future__ import annotations

import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

import pandas as pd

from stock_ai.news_impact import NewsEvent

from scripts.tools.portfolio_db import (
    latest_selection_trade_date,
    load_selection_daily_results,
    save_selection_daily_results,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "output"


def parse_trade_date(value: date | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    s = str(value).strip().replace("-", "")
    if len(s) >= 8 and s[:8].isdigit():
        return datetime.strptime(s[:8], "%Y%m%d").date()
    return datetime.fromisoformat(str(value)[:10]).date()


def trade_date_to_str(value: date | str) -> str:
    d = parse_trade_date(value)
    if d is None:
        raise ValueError(f"无效 trade_date: {value}")
    return d.strftime("%Y%m%d")


def find_latest_selection_csv(output_dir: Path | None = None) -> Path | None:
    output_dir = output_dir or OUTPUT_DIR
    files = sorted(output_dir.glob("stock_selection_combined_*.csv"))
    return files[-1] if files else None


def parse_trade_date_from_csv(path: Path) -> date:
    m = re.search(r"(\d{8})$", path.stem)
    if m:
        return datetime.strptime(m.group(1), "%Y%m%d").date()
    return datetime.now().date()


def sort_selection_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    sort_cols = [c for c in ("总分", "标签数", "成交额(万)", "形态分(25)", "涨幅%") if c in df.columns]
    if not sort_cols:
        return df
    return df.sort_values(by=sort_cols, ascending=False)


TOP5_ELIGIBLE_ACTIONS = frozenset(
    {"强势关注", "观察买入", "小仓埋伏", "持有"}
)

# 公众号 Top5：默认合并多策略候选后按总分重选（见 load_wechat_top5_picks）
DEFAULT_WECHAT_TOP5_STRATEGIES = ("short_term_trade", "combined", "five_factor", "ma5", "watch")

_STRATEGY_DISPLAY = {
    "combined": "综合",
    "five_factor": "五因子",
    "ma5": "MA5",
    "bottom_breakout": "底部突破",
    "watch": "观察池",
    "short_term_trade": "短线交易候选",
}


def wechat_top5_strategies() -> tuple[str, ...]:
    raw = os.getenv(
        "WECHAT_MP_TOP5_STRATEGIES",
        ",".join(DEFAULT_WECHAT_TOP5_STRATEGIES),
    )
    out = tuple(s.strip() for s in raw.split(",") if s.strip())
    return out or DEFAULT_WECHAT_TOP5_STRATEGIES


def _strategy_label(strategy: str) -> str:
    return _STRATEGY_DISPLAY.get(strategy, strategy)


def merge_selection_strategies_df(
    *,
    trade_date: date | str | None = None,
    strategies: Sequence[str] | None = None,
    include_news: bool = True,
    news_events: Sequence[NewsEvent] | None = None,
    now: datetime | None = None,
) -> tuple[date, pd.DataFrame, str]:
    """
    合并多策略选股结果：同代码保留总分最高行，并标注策略来源。
    返回 (trade_date, 已按总分排序的 DataFrame, 来源说明)。
    """
    strategies = tuple(strategies or wechat_top5_strategies())
    explicit = parse_trade_date(trade_date) if trade_date else None
    anchor = explicit or latest_selection_trade_date(strategy="combined")
    if anchor is None:
        for strat in strategies:
            anchor = latest_selection_trade_date(strategy=strat)
            if anchor:
                break
    if anchor is None:
        raise FileNotFoundError("未找到任何策略的选股交易日")

    resolved_td: date = anchor
    frames: list[pd.DataFrame] = []
    loaded: list[str] = []

    for strat in strategies:
        try:
            td, rows = load_selection_daily_results(
                anchor,
                strategy=strat,
                enrich_names=False,
            )
            if not rows:
                continue
            df = pd.DataFrame(rows)
            df["策略来源"] = _strategy_label(strat)
            frames.append(df)
            loaded.append(f"{strat}({len(rows)})")
        except Exception:
            continue

    if not frames or resolved_td is None:
        raise FileNotFoundError(
            f"未找到可合并的选股结果（strategies={strategies}，date={explicit or 'latest'}）"
        )

    merged = pd.concat(frames, ignore_index=True)
    if "代码" not in merged.columns:
        raise ValueError("选股结果缺少「代码」列")

    merged["_code6"] = merged["代码"].astype(str).str.split(".").str[0].str.zfill(6)
    if "总分" in merged.columns:
        merged["_score"] = pd.to_numeric(merged["总分"], errors="coerce").fillna(0)
    else:
        merged["_score"] = 0.0

    # 同代码保留最高分；策略来源合并展示
    merged = merged.sort_values(by=["_score"], ascending=False)
    best_rows: list[pd.Series] = []
    sources_by_code: dict[str, list[str]] = {}
    for _, row in merged.iterrows():
        code = row["_code6"]
        src = str(row.get("策略来源", ""))
        sources_by_code.setdefault(code, [])
        if src and src not in sources_by_code[code]:
            sources_by_code[code].append(src)

    seen: set[str] = set()
    for _, row in merged.iterrows():
        code = row["_code6"]
        if code in seen:
            continue
        seen.add(code)
        out = row.copy()
        out["策略来源"] = "+".join(sources_by_code.get(code, [src]))
        best_rows.append(out)

    out_df = pd.DataFrame(best_rows).drop(columns=["_code6", "_score"], errors="ignore")
    out_df = sort_selection_df(out_df)
    source = f"merge[{','.join(loaded)}]@{resolved_td.isoformat()}"
    if include_news:
        from stock_ai.dual_pool_selection import merge_dual_pool_rows

        resolved_now = now or datetime.now().astimezone()
        coverage_status = "完整"
        resolved_events: Sequence[NewsEvent]
        if news_events is not None:
            resolved_events = news_events
        else:
            try:
                from stock_ai.news_impact.providers import load_news_coverage

                coverage = load_news_coverage(now=resolved_now)
                resolved_events = coverage.events
                if coverage.missing_scopes:
                    coverage_status = "不足"
            except Exception:
                resolved_events = ()
                coverage_status = "不足"
        dual_pool = merge_dual_pool_rows(
            out_df.to_dict(orient="records"),
            resolved_events,
            now=resolved_now,
            coverage_status=coverage_status,
        )
        out_df = sort_selection_df(pd.DataFrame(dual_pool.technical_rows))
        source += f"+dual-pool[{coverage_status}]"
    return resolved_td, out_df, source


def pick_selection_top(
    df: pd.DataFrame,
    top_n: int = 5,
    *,
    holdings_codes: set[str] | None = None,
    max_per_industry: int = 2,
    eligible_actions: frozenset[str] | None = TOP5_ELIGIBLE_ACTIONS,
    account_position_pct: float | None = None,
) -> pd.DataFrame:
    """Top N：剔除持仓 + 同行业上限；投顾阶段 0 仅情报池（继续观察/持有）。"""
    if df.empty or top_n <= 0:
        return df.iloc[0:0].copy()

    if eligible_actions is TOP5_ELIGIBLE_ACTIONS:
        try:
            from stock_ai.advisor_selection import top5_eligible_actions as _advisor_eligible

            pct = account_position_pct if account_position_pct is not None else 0.0
            adv = _advisor_eligible(account_position_pct=pct)
            if adv is not None:
                eligible_actions = adv
        except ImportError:
            pass

    holdings_codes = holdings_codes or set()
    picked: list[int] = []
    industry_count: dict[str, int] = {}

    for idx, row in df.iterrows():
        if len(picked) >= top_n:
            break
        pool_source = str(row.get("候选池来源", "technical") or "technical")
        if pool_source in {"event_watch", "vetoed"}:
            continue
        code = str(row.get("代码", "")).split(".")[0].zfill(6)
        if code in holdings_codes:
            continue
        action = str(row.get("建议动作", "")).strip()
        if eligible_actions is not None and action and action not in eligible_actions:
            continue
        raw_industry = row.get("所属行业")
        if raw_industry is None or (isinstance(raw_industry, float) and pd.isna(raw_industry)):
            industry_key = None
        else:
            industry_key = str(raw_industry).strip()
            if industry_key in {"", "N/A", "nan", "-", "--"}:
                industry_key = None
        if industry_key is not None and industry_count.get(industry_key, 0) >= max_per_industry:
            continue
        picked.append(idx)
        if industry_key is not None:
            industry_count[industry_key] = industry_count.get(industry_key, 0) + 1

    if not picked:
        return df.iloc[0:0].copy()
    return df.loc[picked].copy()


def import_csv_to_db(csv_path: Path | str, *, strategy: str = "combined") -> int:
    """一次性将 CSV 导入 MySQL（供迁移或补录）。"""
    path = Path(csv_path)
    df = pd.read_csv(path, encoding="utf-8-sig")
    if df.empty:
        return 0
    trade_date = parse_trade_date_from_csv(path)
    df = df.where(pd.notnull(df), None)
    rows = df.to_dict(orient="records")
    return save_selection_daily_results(trade_date, rows, strategy=strategy)


def resolve_selection_df(
    *,
    trade_date: date | str | None = None,
    csv_path: Path | str | None = None,
    strategy: str = "combined",
) -> tuple[date, pd.DataFrame, str]:
    """返回 (trade_date, 已排序 DataFrame, 来源标识)。"""
    explicit = parse_trade_date(trade_date) if trade_date else None
    strat = (strategy or "combined").strip() or "combined"

    if csv_path:
        path = Path(csv_path)
        df = pd.read_csv(path, encoding="utf-8-sig")
        td = explicit or parse_trade_date_from_csv(path)
        return td, sort_selection_df(df), f"csv:{path.name}"

    if explicit:
        td, rows = load_selection_daily_results(explicit, strategy=strat)
        if rows:
            return explicit, sort_selection_df(pd.DataFrame(rows)), f"mysql:{strat}"
        fallback = OUTPUT_DIR / f"stock_selection_combined_{explicit.strftime('%Y%m%d')}.csv"
        if strat == "combined" and fallback.exists():
            df = pd.read_csv(fallback, encoding="utf-8-sig")
            return explicit, sort_selection_df(df), f"csv-fallback:{fallback.name}"
        if strat == "five_factor":
            ff = OUTPUT_DIR / f"stock_selection_five_factor_{explicit.strftime('%Y%m%d')}.csv"
            if ff.exists():
                df = pd.read_csv(ff, encoding="utf-8-sig")
                return explicit, sort_selection_df(df), f"csv-fallback:{ff.name}"
        raise FileNotFoundError(f"未找到 {explicit} 的选股结果（MySQL / CSV，strategy={strat}）")

    latest = latest_selection_trade_date(strategy=strat)
    if latest:
        td, rows = load_selection_daily_results(latest, strategy=strat)
        if rows:
            return td or latest, sort_selection_df(pd.DataFrame(rows)), f"mysql:{strat}"

    if strat == "five_factor":
        files = sorted(OUTPUT_DIR.glob("stock_selection_five_factor_*.csv"))
    else:
        files = sorted(OUTPUT_DIR.glob("stock_selection_combined_*.csv"))
    path = files[-1] if files else None
    if path is None:
        raise FileNotFoundError(
            f"未找到选股结果（MySQL selection_daily_results 或 CSV，strategy={strat}）"
        )
    df = pd.read_csv(path, encoding="utf-8-sig")
    return parse_trade_date_from_csv(path), sort_selection_df(df), f"csv:{path.name}"


# 收盘 enrich：五策略合并后按总分取 Top5（与公众号 pick 规则一致）
ENRICH_UNIFIED_TOP5_STRATEGIES = (
    "combined",
    "watch",
    "ma5",
    "five_factor",
    "bottom_breakout",
)


def pick_unified_top5(
    *,
    trade_date: date | str | None = None,
    top_n: int = 5,
    strategies: Sequence[str] | None = None,
) -> tuple[date, list[str], str]:
    """
    合并多策略选股池后取 Top N 代码（去重、同代码保留最高分行）。
    返回 (trade_date, code6 列表, 来源说明)。
    """
    strategies = tuple(strategies or ENRICH_UNIFIED_TOP5_STRATEGIES)
    td, universe, source = merge_selection_strategies_df(
        trade_date=trade_date,
        strategies=strategies,
    )
    top_df = pick_wechat_top5(universe, top_n=top_n)
    if top_df.empty:
        return td, [], source
    codes = [
        str(row.get("代码", "")).split(".")[0].zfill(6)
        for _, row in top_df.iterrows()
        if str(row.get("代码", "")).strip()
    ]
    codes = list(dict.fromkeys(c for c in codes if c))
    return td, codes[:top_n], source


def pick_wechat_top5(
    df: pd.DataFrame,
    *,
    top_n: int = 5,
    score_only: bool | None = None,
) -> pd.DataFrame:
    """公众号 Top5：按总分重选（默认不筛持仓；可按环境变量放宽动作过滤）。"""
    if score_only is None:
        score_only = os.getenv("WECHAT_MP_TOP5_SCORE_ONLY", "1").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
    if score_only:
        eligible = None
    else:
        try:
            from stock_ai.advisor_selection import top5_eligible_actions

            eligible = top5_eligible_actions()
            if eligible is None:
                eligible = TOP5_ELIGIBLE_ACTIONS
        except ImportError:
            eligible = TOP5_ELIGIBLE_ACTIONS
    return pick_selection_top(
        sort_selection_df(df),
        top_n,
        holdings_codes=set(),
        eligible_actions=eligible,
    )
