#!/usr/bin/env python3
"""Run combined stock selection and print a WeChat-friendly Top5 + SOP summary."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT, ROOT / "core_v2"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from datetime import date

from scripts.tools.deepseek_client import is_llm_configured
from scripts.tools.holdings_context import load_full_decision_context

TOP_N = 5


def _fix_mysql_url(url: str) -> str:
    return url.replace("host.docker.internal", "127.0.0.1")


def _load_names(engine, codes: list[str]) -> dict[str, str]:
    from scripts.tools.portfolio_db import load_stock_names_by_codes

    return load_stock_names_by_codes(codes, engine=engine)


def _format_aux_pools(trade_date: date, holdings_codes: set[str]) -> str:
    """B轨 watch + ma5 + 五因子 摘要（Top5 仍仅 combined）。"""
    from scripts.tools.portfolio_db import load_selection_daily_results
    from scripts.tools.selection_results import sort_selection_df

    lines = ["", "📋 辅助观察池（非 Top5 / 不自动 SOP）", ""]
    for strat, title in (
        ("watch", "B轨观察"),
        ("ma5", "MA5回踩"),
        ("five_factor", "五因子"),
    ):
        td, rows = load_selection_daily_results(trade_date, strategy=strat)
        if not rows:
            lines.append(f"· {title}：无")
            continue
        df = sort_selection_df(pd.DataFrame(rows)).head(5)
        lines.append(f"· {title}（{len(rows)} 只，示 Top5）：")
        for i, (_, row) in enumerate(df.iterrows(), 1):
            code = str(row.get("代码", "")).split(".")[0].zfill(6)
            held = " 📌" if code in holdings_codes else ""
            action = row.get("建议动作", "—")
            tags = row.get("策略标签", "")
            score = row.get("总分", 0)
            lines.append(
                f"  {i}. {code}{held} | {tags} | 分{score} | {action}"
            )
    return "\n".join(lines)


def _format_report(
    df: pd.DataFrame,
    trade_date: str,
    holdings_codes: set[str],
    names: dict[str, str],
) -> str:
    if "总分" in df.columns:
        df = df.sort_values(by=["总分", "标签数", "成交额(万)"], ascending=False)

    lines = [
        f"📈 综合选股 Top{TOP_N} ({trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]})",
        "",
    ]

    for i, (_, row) in enumerate(df.head(TOP_N).iterrows(), 1):
        code = str(row["代码"]).zfill(6)
        name = names.get(code, "")
        label = f"{name}({code})" if name else code
        held = " 📌持仓" if code in holdings_codes else ""
        lines.append(
            f"{i}. {label}{held} | {row['策略标签']} | 分{row['总分']:.0f} | "
            f"{row['收盘价']:.2f} ({row['涨幅%']:+.2f}%) | {row['建议动作']}"
        )

    lines.append("")
    lines.append("⚠️ 策略信号仅供参考，不构成投资建议")
    return "\n".join(lines)


def _run_ai_review(trade_date: date, holdings_context: str) -> str:
    if not is_llm_configured():
        return "🤖 DeepSeek 审查 + 持仓建议\n（跳过：未配置 LLM；DEEPSEEK_API_KEY 或 LLM_BACKEND=cursor）"
    try:
        from scripts.analysis.ai_review_combined_top5 import review_combined_top5

        wechat, report_path = review_combined_top5(
            top_n=TOP_N,
            trade_date=trade_date,
            holdings_context=holdings_context,
        )
        if report_path:
            print(f"📄 AI 审查报告: {report_path}", file=sys.stderr)
        return wechat
    except Exception as exc:  # noqa: BLE001
        return f"🤖 DeepSeek 审查 + 持仓建议\n（失败：{exc}）"


def _run_sop_review(
    trade_date: date,
    holdings_context: str,
    holdings_codes: set[str],
    sop_workers: int,
    deepseek_workers: int,
) -> str:
    if not is_llm_configured():
        return "🔬 东财 SOP + 投资决策\n（跳过：未配置 LLM；DEEPSEEK_API_KEY 或 LLM_BACKEND=cursor）"
    try:
        from scripts.analysis.sop_review_top5_concurrent import review_top5_sop_concurrent

        wechat, report_path, watch_metas = review_top5_sop_concurrent(
            top_n=TOP_N,
            trade_date=trade_date,
            sop_workers=sop_workers,
            deepseek_workers=deepseek_workers,
            holdings_context=holdings_context,
            holdings_codes=holdings_codes,
        )
        if report_path:
            print(f"📄 SOP 投资决策报告: {report_path}", file=sys.stderr)
        n_watch = sum(1 for m in watch_metas if m.watch_worthy and not m.in_holdings)
        print(f"👀 SOP 值得关注（非持仓）: {n_watch} 只 → 次日 5 分钟监控", file=sys.stderr)
        return f"🔬 东财 SOP Top{TOP_N} 投资决策\n\n{wechat}"
    except Exception as exc:  # noqa: BLE001
        return f"🔬 东财 SOP + 投资决策\n（失败：{exc}）"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="综合选股 + Top5 SOP 报告")
    parser.add_argument(
        "--no-sop",
        action="store_true",
        help="跳过东财 SOP（改用轻量 DeepSeek 简评，不推荐）",
    )
    parser.add_argument("--sop-workers", type=int, default=1, help="OpenCLI 单会话 SOP（参数保留兼容）")
    parser.add_argument("--deepseek-workers", type=int, default=3, help="DeepSeek 并发数")
    parser.add_argument(
        "--skip-selection",
        action="store_true",
        help="跳过 combined 扫描（已由 run_parallel_selection 跑完）",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    mysql_url = os.environ.get("MYSQL_URL", "")
    if not mysql_url:
        print("❌ 未配置 MYSQL_URL")
        return 1
    os.environ["MYSQL_URL"] = _fix_mysql_url(mysql_url)

    if not args.skip_selection:
        from stock_selection_combined import main as run_selection

        run_selection()
    else:
        print("⏭️ 跳过 combined 扫描（--skip-selection）", file=sys.stderr)

    from scripts.tools.selection_results import resolve_selection_df, pick_selection_top, trade_date_to_str

    try:
        trade_date, df, source = resolve_selection_df()
    except FileNotFoundError as exc:
        print(f"❌ {exc}")
        return 1

    trade_date_str = trade_date_to_str(trade_date)
    print(f"📂 选股数据源: {source}", file=sys.stderr)

    holdings_codes, decision_context = load_full_decision_context()
    top_df = pick_selection_top(
        df.head(TOP_N * 4),
        TOP_N,
        holdings_codes=holdings_codes,
        max_per_industry=2,
    )
    if top_df.empty:
        print(
            "⚠️ Top5 无可执行动作候选，回退为按总分取前 N（含继续观察）",
            file=sys.stderr,
        )
        top_df = pick_selection_top(
            df.head(TOP_N * 4),
            TOP_N,
            holdings_codes=holdings_codes,
            max_per_industry=2,
            eligible_actions=None,
        )
    if top_df.empty:
        top_df = df.head(TOP_N)
    top_codes = [str(c).zfill(6) for c in top_df.head(TOP_N)["代码"].astype(str).tolist()]
    engine = create_engine(os.environ["MYSQL_URL"])
    names = _load_names(engine, top_codes)

    sections = [
        _format_report(top_df, trade_date_str, holdings_codes, names),
        _format_aux_pools(trade_date, holdings_codes),
        "",
    ]

    if args.no_sop:
        ai_block = _run_ai_review(trade_date, decision_context)
    else:
        ai_block = _run_sop_review(
            trade_date,
            decision_context,
            holdings_codes,
            sop_workers=args.sop_workers,
            deepseek_workers=args.deepseek_workers,
        )
    sections.append(ai_block)

    from scripts.tools.selection_watchlist import export_ai_artifact

    export_ai_artifact(ai_block)
    print("\n".join(sections))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
