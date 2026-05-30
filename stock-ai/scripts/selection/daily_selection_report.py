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

from scripts.tools.holdings_context import load_full_decision_context

TOP_N = 5


def _fix_mysql_url(url: str) -> str:
    return url.replace("host.docker.internal", "127.0.0.1")


def _load_names(engine, codes: list[str]) -> dict[str, str]:
    names: dict[str, str] = {}
    if not codes:
        return names
    placeholders = ", ".join(f":c{i}" for i in range(len(codes)))
    params = {f"c{i}": c for i, c in enumerate(codes)}
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT ts_code, name FROM stock_basic WHERE ts_code IN ({placeholders})"
                ),
                params,
            ).fetchall()
        for row in rows:
            code = str(row.ts_code).split(".")[0]
            names[code] = row.name
    except Exception:
        pass
    return names


def _format_report(
    csv_path: Path,
    trade_date: str,
    holdings_codes: set[str],
    names: dict[str, str],
) -> str:
    df = pd.read_csv(csv_path)
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


def _run_ai_review(csv_path: Path, holdings_context: str) -> str:
    if not os.getenv("DEEPSEEK_API_KEY"):
        return "🤖 DeepSeek 审查 + 持仓建议\n（跳过：未配置 DEEPSEEK_API_KEY）"
    try:
        from scripts.analysis.ai_review_combined_top5 import review_combined_top5

        wechat, report_path = review_combined_top5(
            csv_path,
            top_n=TOP_N,
            holdings_context=holdings_context,
        )
        if report_path:
            print(f"📄 AI 审查报告: {report_path}", file=sys.stderr)
        return wechat
    except Exception as exc:  # noqa: BLE001
        return f"🤖 DeepSeek 审查 + 持仓建议\n（失败：{exc}）"


def _run_sop_review(
    csv_path: Path,
    holdings_context: str,
    holdings_codes: set[str],
    sop_workers: int,
    deepseek_workers: int,
) -> str:
    if not os.getenv("DEEPSEEK_API_KEY"):
        return "🔬 东财 SOP + 投资决策\n（跳过：未配置 DEEPSEEK_API_KEY）"
    try:
        from scripts.analysis.sop_review_top5_concurrent import review_top5_sop_concurrent

        wechat, report_path, watch_metas = review_top5_sop_concurrent(
            csv_path,
            top_n=TOP_N,
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
    parser.add_argument("--sop-workers", type=int, default=3, help="Playwright 并发数")
    parser.add_argument("--deepseek-workers", type=int, default=3, help="DeepSeek 并发数")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    mysql_url = os.environ.get("MYSQL_URL", "")
    if not mysql_url:
        print("❌ 未配置 MYSQL_URL")
        return 1
    os.environ["MYSQL_URL"] = _fix_mysql_url(mysql_url)

    from stock_selection_combined import main as run_selection

    run_selection()

    output_dir = ROOT / "output"
    csv_files = sorted(output_dir.glob("stock_selection_combined_*.csv"))
    if not csv_files:
        print("❌ 选股完成但未找到输出 CSV")
        return 1

    csv_path = csv_files[-1]
    trade_date = csv_path.stem.replace("stock_selection_combined_", "")

    holdings_codes, decision_context = load_full_decision_context()
    df = pd.read_csv(csv_path)
    top_codes = [str(c).zfill(6) for c in df.head(TOP_N)["代码"].astype(str).tolist()]
    engine = create_engine(os.environ["MYSQL_URL"])
    names = _load_names(engine, top_codes)

    sections = [_format_report(csv_path, trade_date, holdings_codes, names), ""]

    if args.no_sop:
        ai_block = _run_ai_review(csv_path, decision_context)
    else:
        ai_block = _run_sop_review(
            csv_path,
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
