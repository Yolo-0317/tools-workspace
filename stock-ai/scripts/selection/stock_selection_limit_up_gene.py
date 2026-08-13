#!/usr/bin/env python3
"""Full-market limit-up-gene lane; shadow-only until promotion succeeds."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Mapping

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from core_v2.board_filters import passes_base_filter
from stock_ai.limit_up_gene_watch import PRECISION_POLICY, evaluate_limit_up_gene_candidate
from stock_ai.limit_up_logic import LimitUpContext, analyze_limit_up_logic


ROOT = Path(__file__).resolve().parents[2]
STRATEGY = "limit_up_gene_watch"


def _code6(value: object) -> str:
    return str(value).split(".")[0].zfill(6)


def _as_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    compact = str(value).strip().replace("-", "")[:8]
    return datetime.strptime(compact, "%Y%m%d").date()


def _json_default(value: object) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def run_selection(
    df_all: pd.DataFrame,
    *,
    names: Mapping[str, str],
    risks: Mapping[str, tuple[bool, tuple[str, ...]]],
    trade_date: date | str | None = None,
) -> pd.DataFrame:
    """Evaluate each stock using only bars available at the requested close."""
    columns = [
        "代码", "名称", "收盘价", "涨幅%", "成交额(万)", "总分", "建议动作",
        "策略标签", "涨停基因", "延续概率", "失败概率", "缺失字段", "数据截止",
        "决策周期", "当前仓位建议", "入场触发", "失效条件", "追高纪律", "原始指标",
    ]
    if df_all.empty:
        return pd.DataFrame(columns=columns)
    required = {"ts_code", "trade_date", "open", "high", "low", "close", "pct_chg", "amount"}
    missing = required.difference(df_all.columns)
    if missing:
        raise ValueError(f"daily panel missing columns: {sorted(missing)}")

    panel = df_all.copy()
    panel["trade_date"] = pd.to_datetime(panel["trade_date"]).dt.date
    cutoff = _as_date(trade_date) if trade_date is not None else panel["trade_date"].max()
    panel = panel[panel["trade_date"] <= cutoff]
    if panel.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []
    observed_at = datetime.combine(cutoff, time(15, 0)).astimezone()
    for ts_code, group in panel.groupby("ts_code", sort=False):
        bars = group.sort_values("trade_date")
        latest = bars.iloc[-1]
        if latest["trade_date"] != cutoff:
            continue
        code = _code6(ts_code)
        name = str(names.get(code) or code)
        material_risk, risk_reasons = risks.get(code, (False, ()))
        context = LimitUpContext(
            material_risk=bool(material_risk),
            material_risk_reasons=tuple(risk_reasons),
            observed_at=observed_at,
        )
        result = analyze_limit_up_logic(
            code,
            name,
            bars.tail(60).to_dict(orient="records"),
            context,
            is_st="ST" in name.upper(),
        )
        amount_qian = float(latest["amount"] or 0.0)
        candidate = evaluate_limit_up_gene_candidate(
            result,
            amount_wan=amount_qian / 10.0,
            base_filter_passed=passes_base_filter(
                str(ts_code), float(latest["close"]), amount_qian
            ),
            policy=PRECISION_POLICY,
        )
        if candidate is None:
            continue
        raw = dict(candidate.metrics)
        raw.update(
            {
                "data_cutoff": cutoff.isoformat(),
                "identity": result.identity,
                "drivers": result.drivers,
                "suppressors": result.suppressors,
                "risk_reasons": tuple(risk_reasons),
            }
        )
        box_high = result.consolidation_high
        last_limit_low = result.last_limit_up_low
        entry_trigger = (
            f"收盘放量突破并站上{box_high:.2f}，次日回踩不破再评估"
            if box_high is not None
            else "放量突破近期平台且次日回踩不破再评估"
        )
        invalidation = (
            f"收盘跌破首板低点{last_limit_low:.2f}或出现放量破位"
            if last_limit_low is not None
            else "收盘跌破近期平台或出现放量破位"
        )
        rows.append(
            {
                "代码": code,
                "名称": name,
                "收盘价": float(latest["close"]),
                "涨幅%": float(latest["pct_chg"]),
                "成交额(万)": round(amount_qian / 10.0, 2),
                "总分": candidate.score,
                "建议动作": candidate.action,
                "策略标签": "+".join(candidate.tags),
                "涨停基因": result.gene,
                "延续概率": result.paths.continuation,
                "失败概率": result.paths.failure,
                "缺失字段": json.dumps(candidate.missing_fields, ensure_ascii=False),
                "数据截止": cutoff.isoformat(),
                "决策周期": "3-5个交易日",
                "当前仓位建议": "0%（观察期）",
                "入场触发": entry_trigger,
                "失效条件": invalidation,
                "追高纪律": "当日涨幅超过5%不追；一字板或无回踩确认不追",
                "原始指标": json.dumps(raw, ensure_ascii=False, default=_json_default),
            }
        )
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns).sort_values(
        ["总分", "延续概率", "成交额(万)"], ascending=False
    ).reset_index(drop=True)


def _load_panel(engine, trade_date: date) -> pd.DataFrame:
    start = trade_date - timedelta(days=120)
    return pd.read_sql(
        text(
            """
            SELECT ts_code, trade_date, open, high, low, close, pct_chg, amount
            FROM stock_daily
            WHERE trade_date BETWEEN :start AND :end
            ORDER BY ts_code, trade_date
            """
        ),
        engine,
        params={"start": start, "end": trade_date},
    )


def _load_local_names(engine) -> dict[str, str]:
    """Use existing MySQL facts only; a shadow lane must not trigger browser enrichment."""
    try:
        rows = pd.read_sql(
            text(
                """
                SELECT ts_code, name FROM stock_basic WHERE name IS NOT NULL
                UNION ALL
                SELECT ts_code, name FROM stock_profile WHERE name IS NOT NULL
                """
            ),
            engine,
        )
    except Exception:
        return {}
    return {
        _code6(row.ts_code): str(row.name).strip()
        for row in rows.itertuples(index=False)
        if str(row.name or "").strip()
    }


def _load_risks(codes: list[str], names: Mapping[str, str], *, engine) -> dict[str, tuple[bool, tuple[str, ...]]]:
    if not codes:
        return {}
    from stock_ai.news_impact import ProbabilityPaths, StockContext, analyze_stock_news_impact
    from stock_ai.news_impact.providers import load_news_coverage
    from scripts.tools.portfolio_db import load_stock_profiles_by_codes

    now = datetime.now().astimezone()
    coverage = load_news_coverage(engine=engine, now=now)
    profiles = load_stock_profiles_by_codes(codes, engine=engine)
    out: dict[str, tuple[bool, tuple[str, ...]]] = {}
    for code in codes:
        profile = profiles.get(code, {})
        result = analyze_stock_news_impact(
            StockContext(
                code=code,
                name=names.get(code, code),
                industry=str(profile.get("industry") or ""),
                concepts=tuple(profile.get("concepts") or ()),
            ),
            list(coverage.events),
            ProbabilityPaths(35, 45, 20),
            now=now,
            existing_holding=False,
        )
        out[code] = (result.veto.new_risk_forbidden, tuple(result.veto.reasons))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="涨停基因蓄势影子选股")
    parser.add_argument("--trade-date")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args(argv)

    load_dotenv(ROOT / ".env")
    mysql_url = os.getenv("MYSQL_URL", "").replace("host.docker.internal", "127.0.0.1")
    if not mysql_url:
        raise RuntimeError("未配置 MYSQL_URL")
    engine = create_engine(mysql_url, pool_pre_ping=True)
    if args.trade_date:
        cutoff = _as_date(args.trade_date)
    else:
        with engine.connect() as conn:
            cutoff = conn.execute(text("SELECT MAX(trade_date) FROM stock_daily")).scalar()
        if cutoff is None:
            raise RuntimeError("stock_daily 没有交易数据")

    panel = _load_panel(engine, cutoff)
    from scripts.tools.portfolio_db import save_selection_daily_results

    names = _load_local_names(engine)
    preselected = run_selection(panel, trade_date=cutoff, names=names, risks={})
    preselected_codes = preselected["代码"].astype(str).tolist() if not preselected.empty else []
    risks = _load_risks(preselected_codes, names, engine=engine)
    result = run_selection(panel, trade_date=cutoff, names=names, risks=risks).head(max(0, args.limit))
    if not args.report_only:
        save_selection_daily_results(
            cutoff,
            result.to_dict(orient="records"),
            strategy=STRATEGY,
            enrich_names=False,
        )
    print(f"{cutoff.isoformat()} {STRATEGY}: {len(result)} candidates")
    if not result.empty:
        print(result.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
