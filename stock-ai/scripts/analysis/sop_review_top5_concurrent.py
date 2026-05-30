#!/usr/bin/env python3
"""综合选股 Top N：并发东财 SOP 采集 + DeepSeek 投资决策。"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT, ROOT / "core_v2"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from scripts.analysis.eastmoney_sop_extract import _extract_worker
from scripts.tools.holdings_context import load_full_decision_context


def _call_deepseek(messages: list, max_retries: int = 3) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY 未设置")

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 3500,
    }

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=180)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            last_err = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    raise RuntimeError(str(last_err))


def _to_full_code(code: str) -> str:
    code_str = str(code).split(".")[0].zfill(6)
    if code_str.startswith(("60", "68")):
        return f"{code_str}.SH"
    return f"{code_str}.SZ"


def _technical_supplement(code: str, mysql_url: str) -> str:
    """从 MySQL 补充均线/量能，弥补行情页盘后为空。"""
    code6 = str(code).split(".")[0].zfill(6)
    try:
        engine = create_engine(mysql_url)
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT trade_date, close, pct_chg, vol, amount
                    FROM stock_daily
                    WHERE ts_code = :code
                    ORDER BY trade_date DESC
                    LIMIT 60
                    """
                ),
                {"code": code6},
            ).fetchall()
        if not rows:
            return "（MySQL 无历史数据）"

        df = pd.DataFrame(rows, columns=["trade_date", "close", "pct_chg", "vol", "amount"])
        df = df.sort_values("trade_date")
        closes = df["close"].astype(float)
        vols = df["vol"].astype(float)
        latest = df.iloc[-1]
        ma5 = closes.tail(5).mean()
        ma20 = closes.tail(20).mean()
        ma60 = closes.tail(60).mean()
        vol20 = vols.tail(20).mean()
        vol_ratio = float(latest["vol"]) / vol20 if vol20 else 0

        return (
            f"收盘 {float(latest['close']):.2f}元 ({float(latest['pct_chg']):+.2f}%) | "
            f"MA5={ma5:.2f} MA20={ma20:.2f} MA60={ma60:.2f} | "
            f"量比(相对20日均量)={vol_ratio:.2f}x | 交易日={latest['trade_date']}"
        )
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

全中文，禁止 markdown 表格。"""

    content = _call_deepseek(
        [
            {"role": "system", "content": "专业、客观、简洁。结合持仓与操盘红线给出条件式建议。"},
            {"role": "user", "content": prompt},
        ]
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

请输出微信推送摘要（≤1000字），格式：
===WECHAT===
1) 📊 Top{len(per_stock)} SOP 投资决策（每只 1-2 行：结论+关键条件）
2) 📋 结合持仓：明日优先动作（对齐 P0~P4）
3) ⚠️ 今日最大风险（1-2 句）
禁止 markdown 表格。"""

    content = _call_deepseek(
        [
            {"role": "system", "content": "简洁务实，全中文。"},
            {"role": "user", "content": prompt},
        ]
    )
    if "===WECHAT===" in content:
        return content.split("===WECHAT===", 1)[-1].strip()
    return content.strip()


def review_top5_sop_concurrent(
    csv_path: str | Path,
    *,
    top_n: int = 5,
    sop_workers: int = 3,
    deepseek_workers: int = 3,
    holdings_context: str = "",
    save_report: bool = True,
) -> tuple[str, str | None]:
    """并发 SOP 采集 + DeepSeek 分析，返回 (微信摘要, 报告路径)。"""
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    if df.empty:
        raise ValueError("选股 CSV 为空")
    if "总分" in df.columns:
        df = df.sort_values(by=["总分", "标签数", "成交额(万)"], ascending=False)

    top = df.head(top_n).copy()
    codes = [str(c).split(".")[0].zfill(6) for c in top["代码"].astype(str)]
    trade_date = csv_path.stem.replace("stock_selection_combined_", "")
    sop_dir = ROOT / "output" / "sop_preliminary" / trade_date
    sop_dir.mkdir(parents=True, exist_ok=True)

    mysql_url = os.environ.get("MYSQL_URL", "").replace("host.docker.internal", "127.0.0.1")
    context = holdings_context.strip() or "（无决策上下文）"

    # 阶段 1：并发 Playwright 采集
    print(f"🔍 并发 SOP 采集 Top{len(codes)}（workers={sop_workers}）...", file=sys.stderr)
    preliminary_map: dict[str, str] = {}
    errors: dict[str, str] = {}

    worker_args = [(c, str(sop_dir)) for c in codes]
    with ProcessPoolExecutor(max_workers=sop_workers) as pool:
        futures = {pool.submit(_extract_worker, a): a[0] for a in worker_args}
        for fut in as_completed(futures):
            code, path, err = fut.result()
            if err:
                errors[code] = err
                print(f"  ❌ {code} SOP 失败: {err}", file=sys.stderr)
            else:
                preliminary_map[code] = path
                print(f"  ✅ {code} -> {path}", file=sys.stderr)

    # 阶段 2：并发 DeepSeek 逐股分析
    metas = [_build_stock_meta(row) for _, row in top.iterrows()]
    per_stock_reviews: list[tuple[dict, str]] = []

    def _review_one(meta: dict) -> tuple[str, str]:
        code = meta["代码"]
        if code not in preliminary_map:
            return code, f"（SOP 采集失败：{errors.get(code, '未知错误')}）"
        tech = _technical_supplement(code, mysql_url) if mysql_url else "（未配置 MYSQL_URL）"
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

    # 阶段 3：汇总微信摘要
    wechat = _deepseek_summary(per_stock_reviews, context, trade_date)

    report_path: str | None = None
    if save_report:
        report_path = str(csv_path.with_name(f"{csv_path.stem}_sop_review.md"))
        lines = [
            f"# 综合选股 Top{top_n} 东财 SOP + DeepSeek 投资决策",
            "",
            f"**生成时间**：{datetime.now():%Y-%m-%d %H:%M:%S}  ",
            f"**数据来源**：{csv_path.name}  ",
            f"**SOP 并发数**：{sop_workers} | **DeepSeek 并发数**：{deepseek_workers}",
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

    return wechat, report_path


def main() -> int:
    load_dotenv(ROOT / ".env")
    import argparse

    parser = argparse.ArgumentParser(description="Top N 并发东财 SOP + DeepSeek 投资决策")
    parser.add_argument("csv_file", nargs="?", help="选股 CSV（默认取最新 combined）")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--sop-workers", type=int, default=3, help="Playwright 并发数")
    parser.add_argument("--deepseek-workers", type=int, default=3, help="DeepSeek API 并发数")
    parser.add_argument("--wechat-only", action="store_true")
    args = parser.parse_args()

    if args.csv_file:
        csv_path = Path(args.csv_file)
    else:
        files = sorted((ROOT / "output").glob("stock_selection_combined_*.csv"))
        if not files:
            print("❌ 未找到 output/stock_selection_combined_*.csv")
            return 1
        csv_path = files[-1]

    _, decision_context = load_full_decision_context()
    wechat, report_path = review_top5_sop_concurrent(
        csv_path,
        top_n=args.top,
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
