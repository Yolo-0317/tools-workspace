#!/usr/bin/env python3
"""DeepSeek AI review for combined stock selection Top N."""

from __future__ import annotations

import json
import os
import sys
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

from scripts.tools.holdings_context import load_full_decision_context


def _call_deepseek(messages: list, max_retries: int = 3) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY 未设置")

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.5,
        "max_tokens": 3000,
    }

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            last_err = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        if attempt < max_retries - 1:
            continue
    raise RuntimeError(str(last_err))


def _build_stock_rows(df: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for _, row in df.iterrows():
        code = str(row["代码"]).split(".")[0].zfill(6)
        item = {
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
        rows.append(item)
    return rows


def review_combined_top5(
    csv_path: str | Path,
    top_n: int = 5,
    *,
    holdings_context: str = "",
    save_report: bool = True,
) -> tuple[str, str | None]:
    """Return (wechat_summary, report_path).

    holdings_context should be the full decision pack from load_full_decision_context().
    """
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    if df.empty:
        raise ValueError("选股 CSV 为空")

    if "总分" in df.columns:
        df = df.sort_values(by=["总分", "标签数", "成交额(万)"], ascending=False)
    top = df.head(top_n).copy()
    stocks = _build_stock_rows(top)

    context_block = holdings_context.strip() or "（无决策上下文）"
    prompt = f"""你是 A 股技术面分析师。以下 {len(stocks)} 只股票来自「综合选股」Top{len(stocks)}。

## Top{len(stocks)} 技术数据
{json.dumps(stocks, ensure_ascii=False, indent=2)}

## 必须遵循的完整决策上下文
{context_block}

## 你的任务
1. **所有操作建议必须严格符合上述「A.高级操盘策略」+「B.持仓执行卡」的全部逻辑**，包括但不限于：
   - 仓位：Kelly/单股≤30%、单笔风险≤2%、金字塔分批、情绪周期动态仓位（第十节）
   - 止损：三线止损、时间止损、动态风控（第二节）
   - 技术：量价配合、MA/MACD/RSI/BOLL 多指标共振（第十一节）
   - 环境：涨跌家数/冰点空仓/指数繁荣个股普跌降仓（第十、十八节）
   - 资金：北向/两融/龙虎榜仅作辅助（第十二节）
   - 做T：仅底仓+灵活仓，深套禁止做T补仓（第十三节）
   - 主线：极简龙头/不追连板/不追伪龙头（第十五节）
   - 收息：除权除息与分红节点（第十六节）
   - 频率：控制换手、盈亏比≥2:1（第十七节）
   - 制度：T+1、涨跌停、100股整数倍（文首制度红线）
   - 李佛摩尔/海龟/达利欧及心理铁律（第六、八节）
   - 持仓执行卡 P0~P4 计划、个股止损/目标位
2. 若 Top5 建议与操盘逻辑冲突，必须**明确拒绝**并说明原因（例如「虽技术信号强但违反不追高规则」）。
3. 新开仓建议必须给出：试探仓位比例（≤30%单股上限内）、止损位（≤5%）、是否符合盈亏比>2:1。

请输出两部分，严格按格式：

===WECHAT===
（微信推送，总字数不超过 1200 字）
1) 🤖 DeepSeek Top{len(stocks)} 简评（每只 2 行）
2) 📋 结合持仓操作建议（四类：持有观察/反弹减仓/候选新开仓/暂不操作）
3) 📐 操盘逻辑校验（列出本次实际应用的 5-8 条关键规则，如「-5%硬止损」「P1广州发展8.3清仓」「单股≤30%」）
4) 💡 明日优先动作（1-2 句，必须对齐 P0~P4 计划）
禁止 markdown 表格

===REPORT===
（完整 Markdown，说明每条建议引用了哪些操盘逻辑条目）
"""

    content = _call_deepseek(
        [
            {
                "role": "system",
                "content": "专业、客观、简洁。这是决策支持，不是投资建议。",
            },
            {"role": "user", "content": prompt},
        ]
    )

    wechat = content
    report_body = content
    if "===WECHAT===" in content:
        parts = content.split("===REPORT===", 1)
        wechat_part = parts[0].split("===WECHAT===", 1)[-1].strip()
        report_body = parts[1].strip() if len(parts) > 1 else content
        wechat = wechat_part

    report_path: str | None = None
    if save_report:
        report_path = str(csv_path.with_name(f"{csv_path.stem}_ai_review.md"))
        header = (
            f"# 综合选股 DeepSeek AI 审查\n\n"
            f"**生成时间**：{datetime.now():%Y-%m-%d %H:%M:%S}  \n"
            f"**数据来源**：{csv_path.name}  \n\n---\n\n"
        )
        Path(report_path).write_text(header + report_body, encoding="utf-8")

    return wechat.strip(), report_path


def main() -> int:
    load_dotenv(ROOT / ".env")
    import argparse

    parser = argparse.ArgumentParser(description="综合选股 DeepSeek Top5 审查")
    parser.add_argument("csv_file", help="选股结果 CSV")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--wechat-only", action="store_true")
    parser.add_argument(
        "--holdings-file",
        default=str(Path.home() / ".qclaw/workspace/持仓执行卡.md"),
    )
    args = parser.parse_args()

    from scripts.tools.holdings_context import load_full_decision_context

    _, decision_context = load_full_decision_context(Path(args.holdings_file))
    wechat, report_path = review_combined_top5(
        args.csv_file,
        args.top,
        holdings_context=decision_context,
    )
    if args.wechat_only:
        print(wechat)
    else:
        print(wechat)
        if report_path:
            print(f"\n📄 完整报告: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
