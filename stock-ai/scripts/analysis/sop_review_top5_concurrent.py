#!/usr/bin/env python3
"""综合选股 Top N：并发东财 SOP 采集 + DeepSeek 投资决策。"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT, ROOT / "core_v2"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

import pandas as pd
from dotenv import load_dotenv
from scripts.analysis.eastmoney_sop_extract import extract_and_save_batch
from scripts.tools.fetch_eastmoney_quotes import fetch_technical_summaries_batch_opencli
from scripts.tools.deepseek_client import call_deepseek, sop_llm_backend
from scripts.tools.holdings_context import load_full_decision_context
from scripts.tools.sop_watch_parse import SopWatchMeta, parse_sop_review_text
from scripts.tools.wechat_format import format_sop_wechat_summary

SOP_JSON_LATEST = ROOT / "output" / "sop_review_latest.json"


def _to_full_code(code: str) -> str:
    code_str = str(code).split(".")[0].zfill(6)
    if code_str.startswith(("60", "68")):
        return f"{code_str}.SH"
    return f"{code_str}.SZ"


def _technical_supplement(code: str, cache: dict[str, str] | None = None) -> str:
    """OpenCLI 东财 K 线补充均线/量能（优先用批量缓存）。"""
    if cache and code in cache:
        return cache[code]
    try:
        from scripts.tools.fetch_eastmoney_quotes import fetch_technical_summary_opencli

        return fetch_technical_summary_opencli(code, limit=60)
    except Exception as exc:  # noqa: BLE001
        return f"（技术面补充失败: {exc}）"


def _build_stock_meta(row: pd.Series) -> dict:
    code = str(row["代码"]).split(".")[0].zfill(6)
    return {
        "代码": code,
        "收盘价": float(row["收盘价"]),
        "涨幅%": float(row["涨幅%"]),
        "策略标签": str(row.get("策略标签", "")),
        "总分": float(row.get("总分", 0)),
        "建议动作": str(row.get("建议动作", "")),
        "信号分": row.get("信号分"),
        "趋势分": row.get("趋势分"),
        "动量分": row.get("动量分"),
        "成交额(万)": float(row.get("成交额(万)", 0)),
    }


def _load_names(codes: list[str], mysql_url: str) -> dict[str, str]:
    del mysql_url  # 保留签名兼容；名称由 portfolio_db（Tushare/持仓）解析
    from scripts.tools.portfolio_db import load_stock_names_by_codes

    return load_stock_names_by_codes(codes)


def _deepseek_single_review(
    meta: dict,
    preliminary_path: str,
    technical: str,
    holdings_context: str,
) -> tuple[str, str]:
    """对单只股票 SOP 初步报告做 DeepSeek 终审，返回 (code, markdown)."""
    code = meta["代码"]
    preliminary = Path(preliminary_path).read_text(encoding="utf-8")
    prompt = f"""你是专业 A 股分析师。请基于东财 SOP 初步报告，输出该股的**投资决策**（决策支持，非投资建议）。

## 选股信号（综合选股 Top 榜）
{json.dumps(meta, ensure_ascii=False, indent=2)}

## MySQL 技术面补充
{technical}

## 东财 SOP 初步报告
{preliminary}

## 必须遵循的决策上下文
{holdings_context}

## 输出要求（Markdown）
1. 数据校验（通过/异常）
2. 核心逻辑（3-4 句）
3. 支撑/压力/止损/目标位
4. **投资决策**：买入观察 / 持有 / 减仓 / 暂不操作（必须说明是否违反不追高、仓位限制等红线）
5. 主要风险（3 条以内）

6. **最后一行**必须输出机器可读标签（格式固定，勿加 markdown）：
WATCH: 是|否 | DECISION: 买入观察|暂不操作|持有|减仓 | SUPPORT: 7.38,7.26 | STOP: 7.10 | TARGET: 8.50,9.00
（值得关注填 WATCH: 是；支撑/止损/目标无则填 -）

全中文，禁止 markdown 表格。"""

    content = call_deepseek(
        [
            {
                "role": "system",
                "content": "专业、客观、简洁。结合持仓与操盘红线给出条件式建议。禁止开场白，直接从「1. 数据校验」开始输出。",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=3500,
        timeout=(10, 180),
        backend=sop_llm_backend(),
    )
    return code, content


def _deepseek_summary(
    per_stock: list[tuple[dict, str]],
    holdings_context: str,
    trade_date: str,
) -> str:
    """汇总 Top N 最终投资决策（微信摘要）。"""
    blocks = []
    for meta, review in per_stock:
        blocks.append(f"### {meta['代码']} 分{meta['总分']:.0f}\n{review[:1200]}")

    prompt = f"""以下是 {trade_date} 综合选股 Top{len(per_stock)} 的东财 SOP + DeepSeek 逐股分析。

{chr(10).join(blocks)}

## 决策上下文
{holdings_context}

请输出微信推送摘要（≤1000字），严格格式（小节之间空一行，禁止 **加粗**，禁止 markdown 表格）：

===WECHAT===
1) 📊 Top{len(per_stock)} SOP 投资决策

【代码 名称 · 分XX · 结论】
理由：一句
条件：止损/支撑/操作条件（如有）

（每只股票一块，块与块之间空一行）

2) 📋 结合持仓：明日优先动作
· P0～P4 各一句（单独一行）
· 总仓位一句

3) ⚠️ 今日最大风险
· 风险一
· 风险二
"""

    content = call_deepseek(
        [
            {"role": "system", "content": "简洁务实，全中文。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=3500,
        timeout=(10, 180),
        backend=sop_llm_backend(),
    )
    if "===WECHAT===" in content:
        raw = content.split("===WECHAT===", 1)[-1].strip()
    else:
        raw = content.strip()
    return format_sop_wechat_summary(raw)


def review_top5_sop_concurrent(
    csv_path: str | Path | None = None,
    *,
    top_n: int = 5,
    trade_date: date | str | None = None,
    sop_workers: int = 3,
    deepseek_workers: int = 3,
    holdings_context: str = "",
    holdings_codes: set[str] | None = None,
    save_report: bool = True,
) -> tuple[str, str | None, list[SopWatchMeta]]:
    """并发 SOP 采集 + DeepSeek 分析，返回 (微信摘要, 报告路径, 结构化监控元数据)。"""
    from scripts.tools.selection_results import resolve_selection_df, pick_selection_top, trade_date_to_str

    td, df, source = resolve_selection_df(trade_date=trade_date, csv_path=csv_path)
    if df.empty:
        raise ValueError("选股结果为空")

    if holdings_codes is None:
        holdings_codes, _ = load_full_decision_context()

    top = pick_selection_top(df.head(top_n * 4), top_n, holdings_codes=holdings_codes)
    if top.empty:
        print(
            "⚠️ Top5 无可执行动作候选，回退为按总分取前 N（含继续观察）",
            file=sys.stderr,
        )
        top = pick_selection_top(
            df.head(top_n * 4),
            top_n,
            holdings_codes=holdings_codes,
            eligible_actions=None,
        )
    if top.empty:
        top = df.head(top_n).copy()
    codes = [str(c).split(".")[0].zfill(6) for c in top["代码"].astype(str)]
    trade_date_str = trade_date_to_str(td)
    sop_dir = ROOT / "output" / "sop_preliminary" / trade_date_str
    sop_dir.mkdir(parents=True, exist_ok=True)
    print(f"📂 选股数据源: {source}", file=sys.stderr)

    mysql_url = os.environ.get("MYSQL_URL", "").replace("host.docker.internal", "127.0.0.1")
    context = holdings_context.strip() or "（无决策上下文）"
    if holdings_codes is None:
        holdings_codes, _ = load_full_decision_context()

    # 阶段 1：OpenCLI 单会话 SOP 采集 + 批量 K 线（不重复开关浏览器）
    print(f"🔍 OpenCLI SOP 采集 Top{len(codes)}...", file=sys.stderr)
    preliminary_map: dict[str, str] = {}
    technical_map: dict[str, str] = {}
    errors: dict[str, str] = {}

    try:
        batch_result = extract_and_save_batch(codes, sop_dir, chain_technical=True)
        if isinstance(batch_result, tuple):
            preliminary_map, technical_map = batch_result
        else:
            preliminary_map = batch_result
            technical_map = fetch_technical_summaries_batch_opencli(
                codes,
                reset_browser=True,
                close_browser=True,
            )
        for code, path in preliminary_map.items():
            print(f"  ✅ {code} -> {path}", file=sys.stderr)
        print(f"  📈 K 线批量摘要 {len(technical_map)} 只（单会话）", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        for c in codes:
            errors[c] = str(exc)
        print(f"  ❌ SOP 批量采集失败: {exc}", file=sys.stderr)

    # 阶段 2：并发 DeepSeek 逐股分析
    metas = [_build_stock_meta(row) for _, row in top.iterrows()]
    per_stock_reviews: list[tuple[dict, str]] = []

    def _review_one(meta: dict) -> tuple[str, str]:
        code = meta["代码"]
        if code not in preliminary_map:
            return code, f"（SOP 采集失败：{errors.get(code, '未知错误')}）"
        tech = _technical_supplement(code, technical_map)
        return _deepseek_single_review(meta, preliminary_map[code], tech, context)

    print(f"🤖 并发 DeepSeek 分析（workers={deepseek_workers}）...", file=sys.stderr)
    review_map: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=deepseek_workers) as pool:
        futures = {pool.submit(_review_one, m): m["代码"] for m in metas}
        for fut in as_completed(futures):
            code, review = fut.result()
            review_map[code] = review
            print(f"  ✅ {code} DeepSeek 完成", file=sys.stderr)

    for meta in metas:
        per_stock_reviews.append((meta, review_map.get(meta["代码"], "（无分析结果）")))

    watch_metas: list[SopWatchMeta] = []
    names_map = _load_names([m["代码"] for m in metas], mysql_url)
    for meta, review in per_stock_reviews:
        code = meta["代码"]
        parsed = parse_sop_review_text(
            code,
            review,
            name=names_map.get(code, code),
            score=float(meta.get("总分", 0)),
        )
        parsed.in_holdings = code in holdings_codes
        if parsed.in_holdings:
            parsed.watch_worthy = False
        watch_metas.append(parsed)

    # 阶段 3：汇总微信摘要
    wechat = _deepseek_summary(per_stock_reviews, context, trade_date_str)

    report_path: str | None = None
    if save_report:
        report_path = str(ROOT / "output" / f"stock_selection_combined_{trade_date_str}_sop_review.md")
        lines = [
            f"# 综合选股 Top{top_n} 东财 SOP + DeepSeek 投资决策",
            "",
            f"**生成时间**：{datetime.now():%Y-%m-%d %H:%M:%S}  ",
            f"**数据来源**：{source}  ",
            f"**SOP**：OpenCLI 单会话（SOP+K线） | **DeepSeek 并发数**：{deepseek_workers}",
            "",
            "---",
            "",
            "## 微信摘要",
            "",
            wechat,
            "",
            "---",
            "",
        ]
        for meta, review in per_stock_reviews:
            lines.extend(
                [
                    f"## {meta['代码']} | 分{meta['总分']:.0f} | {meta['建议动作']}",
                    "",
                    f"- 策略标签：{meta['策略标签']}",
                    f"- 选股技术：收盘 {meta['收盘价']:.2f} ({meta['涨幅%']:+.2f}%)",
                    "",
                    review,
                    "",
                    "---",
                    "",
                ]
            )
        Path(report_path).write_text("\n".join(lines), encoding="utf-8")
        print(f"📄 SOP 投资决策报告: {report_path}", file=sys.stderr)

    sop_payload = {
        "version": 1,
        "trade_date": trade_date_str,
        "source": source,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "wechat_summary": wechat,
        "reviews": [m.to_dict() for m in watch_metas],
    }
    SOP_JSON_LATEST.parent.mkdir(parents=True, exist_ok=True)
    SOP_JSON_LATEST.write_text(json.dumps(sop_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"📋 SOP 监控元数据: {SOP_JSON_LATEST}", file=sys.stderr)

    try:
        from scripts.tools.portfolio_db import save_sop_review_daily

        db_items: list[dict] = []
        for rank, (meta, review) in enumerate(per_stock_reviews, 1):
            code = meta["代码"]
            parsed = next((m for m in watch_metas if m.code == code), None)
            db_items.append(
                {
                    "rank_no": rank,
                    "code": code,
                    "name": names_map.get(code) or (parsed.name if parsed else code),
                    "score": float(meta.get("总分", 0)),
                    "decision": parsed.decision if parsed else "",
                    "watch_worthy": parsed.watch_worthy if parsed else False,
                    "close_price": float(meta.get("收盘价", 0)),
                    "change_pct": float(meta.get("涨幅%", 0)),
                    "strategy_label": str(meta.get("策略标签", "")),
                    "action_hint": str(meta.get("建议动作", "")),
                    "support": parsed.support if parsed else [],
                    "stop": parsed.stop if parsed else None,
                    "targets": parsed.targets if parsed else [],
                    "in_holdings": parsed.in_holdings if parsed else False,
                    "review_md": review,
                    "raw_json": parsed.to_dict() if parsed else {},
                }
            )
        sop_db = save_sop_review_daily(
            trade_date_str,
            strategy="combined",
            selection_source=source,
            generated_at=sop_payload["generated_at"],
            wechat_summary=wechat,
            report_path=report_path,
            items=db_items,
        )
        print(
            f"💾 MySQL sop_review_daily: {sop_db['trade_date']} items={sop_db['items']}",
            file=sys.stderr,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ SOP MySQL 入库失败: {exc}", file=sys.stderr)

    return wechat, report_path, watch_metas


def main() -> int:
    load_dotenv(ROOT / ".env")
    import argparse

    parser = argparse.ArgumentParser(description="Top N 并发东财 SOP + DeepSeek 投资决策")
    parser.add_argument("csv_file", nargs="?", help="[可选] 选股 CSV，默认 MySQL 优先")
    parser.add_argument("--trade-date", default=None, help="YYYYMMDD，默认最新交易日")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--sop-workers", type=int, default=1, help="已弃用：OpenCLI 单会话顺序采集")
    parser.add_argument("--deepseek-workers", type=int, default=3, help="DeepSeek API 并发数")
    parser.add_argument("--wechat-only", action="store_true")
    args = parser.parse_args()

    from scripts.tools.selection_results import parse_trade_date

    td = parse_trade_date(args.trade_date) if args.trade_date else None
    csv_path = Path(args.csv_file) if args.csv_file else None

    _, decision_context = load_full_decision_context()
    wechat, report_path, _watch_metas = review_top5_sop_concurrent(
        csv_path,
        top_n=args.top,
        trade_date=td,
        sop_workers=args.sop_workers,
        deepseek_workers=args.deepseek_workers,
        holdings_context=decision_context,
    )
    print(wechat)
    if not args.wechat_only and report_path:
        print(f"\n📄 完整报告: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
