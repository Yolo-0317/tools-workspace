#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对 core_v3 五因子选股结果进行逐股 DeepSeek 分析。

默认行为：
1) 优先读 MySQL selection_daily_results（strategy=five_factor），CSV 兜底
2) 取前 N 只股票（按总分排序）
3) 逐股调用 DeepSeek 生成分析
4) 输出 Markdown + JSON 报告
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv


# 允许从 core_v3 直接运行并导入项目根模块
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# 加载环境变量
load_dotenv(dotenv_path=REPO_ROOT / ".env")
load_dotenv()

from tushare_mcp import _call_deepseek_api


DEFAULT_TECH_SCORE_THRESHOLD = 65.0
DEFAULT_NINE_DIMENSION_PROMPT = """
你是一位专业的A股量化分析师，拥有10年以上投资研究经验。请对以下股票进行九维分析。

## 分析标的
{stock_name}（{stock_code}）

## 基础数据
- 当前价格：{price}元
- 今日涨跌幅：{change}%
- 技术面评分：{tech_score}/100
- 技术面评级：{tech_rating}
- 关键支撑：{support}元
- 关键压力：{resistance}元

## 分析要求
1. 请**开启联网搜索**，获取该股票的最新资金面、基本面、财务面、估值面、消息面、情绪面、宏观面、筹码面数据
2. 按以下九维框架输出分析报告：
   - 技术面、资金面、消息面、基本面、财务面、估值面、情绪面、宏观面、筹码面
3. 每个维度给出：
   - 评分（1-5星）
   - 核心依据（具体数据）
4. 输出综合评级和操作建议（买点、止损、目标、仓位）
5. 最后给出风险提示和一句话总结

## 输出格式要求
请使用 Markdown 格式，包含表格和清晰的层级结构。
"""


def load_prompt_config() -> Tuple[str, float]:
    """
    尝试从 core_v3/prompt.py 读取模板与阈值。
    若文件为空或常量缺失，则使用内置兜底配置。
    """
    prompt = DEFAULT_NINE_DIMENSION_PROMPT
    threshold = DEFAULT_TECH_SCORE_THRESHOLD

    try:
        import importlib

        p = importlib.import_module("core_v3.prompt")
        prompt = getattr(p, "NINE_DIMENSION_PROMPT", prompt) or prompt
        threshold = float(getattr(p, "TECH_SCORE_THRESHOLD", threshold) or threshold)
    except Exception:
        # 不中断主流程，保持可运行
        pass

    return prompt, threshold


def resolve_five_factor_df(
    *,
    csv_path: Path | str | None = None,
    trade_date: str | None = None,
) -> tuple[pd.DataFrame, str, str]:
    """返回 (DataFrame, YYYYMMDD, 来源标识)。MySQL 优先。"""
    from scripts.tools.selection_results import resolve_selection_df, trade_date_to_str

    td, df, source = resolve_selection_df(
        trade_date=trade_date,
        csv_path=csv_path,
        strategy="five_factor",
    )
    date_str = trade_date_to_str(td)
    return df, date_str, source


def latest_five_factor_file() -> Tuple[Optional[Path], Optional[str]]:
    files = glob.glob(str(REPO_ROOT / "output" / "stock_selection_five_factor_*.csv"))
    if not files:
        return None, None
    files.sort(key=os.path.getmtime, reverse=True)
    latest = Path(files[0])
    m = re.search(r"(\d{8})$", latest.stem)
    date_str = m.group(1) if m else datetime.now().strftime("%Y%m%d")
    return latest, date_str


def detect_columns(df: pd.DataFrame) -> Dict[str, str]:
    candidates = {
        "code": ["代码", "ts_code", "code"],
        "price": ["收盘价", "close"],
        "change": ["涨幅%", "pct_chg", "今日涨幅%"],
        "score": ["总分", "技术分", "tech_score"],
        "support": ["支撑位", "support"],
        "resistance": ["压力位", "resistance"],
        "tags": ["策略标签", "tags"],
        "amount": ["成交额(万)", "amount"],
    }
    mapping: Dict[str, str] = {}
    for key, cols in candidates.items():
        mapping[key] = ""
        for c in cols:
            if c in df.columns:
                mapping[key] = c
                break
    if not mapping["code"]:
        raise ValueError("数据中未找到股票代码列（如 `代码`）")
    if not mapping["score"]:
        raise ValueError("数据中未找到评分列（如 `总分`）")
    return mapping


def to_rating(score: float) -> str:
    if score >= 85:
        return "A+（强势）"
    if score >= 78:
        return "A（较强）"
    if score >= 70:
        return "B（可关注）"
    if score >= 60:
        return "C（观察）"
    return "D（偏弱）"


def format_optional(v) -> str:
    if pd.isna(v):
        return "N/A"
    return str(v)


def build_stock_prompt(row: pd.Series, col: Dict[str, str], prompt_template: str) -> str:
    code = str(row[col["code"]]).split(".")[0].zfill(6)
    price = format_optional(row[col["price"]]) if col["price"] else "N/A"
    change = format_optional(row[col["change"]]) if col["change"] else "N/A"
    score = float(row[col["score"]])
    support = format_optional(row[col["support"]]) if col["support"] else "N/A"
    resistance = format_optional(row[col["resistance"]]) if col["resistance"] else "N/A"
    tags = format_optional(row[col["tags"]]) if col["tags"] else "N/A"
    amount = format_optional(row[col["amount"]]) if col["amount"] else "N/A"

    prompt_base = prompt_template.format(
        stock_name=f"候选股{code}",
        stock_code=code,
        price=price,
        change=change,
        tech_score=f"{score:.1f}",
        tech_rating=to_rating(score),
        support=support,
        resistance=resistance,
    )

    # 在模板基础上补充五因子分项，确保与 v3 输出衔接
    extras = []
    for k in ["趋势分(25)", "形态分(25)", "动量分(20)", "量能分(15)", "支撑压力分(15)", "量比", "RSI14", "MACD", "MACD_SIGNAL", "K", "D", "MA20斜率%", "MA60斜率%"]:
        if k in row.index:
            extras.append(f"- {k}：{format_optional(row[k])}")

    extra_text = "\n".join(extras) if extras else "- 无额外分项数据"

    output_requirements = """
## 补充要求（必须遵守）
1. 请优先结合已给出的五因子技术数据，不要虚构财务数据。
2. 如果无法确认某维度，请明确写“数据不足”，并给出保守结论。
3. 在文末输出一个“可执行计划”：
   - 建议动作（买入/观察/回避）
   - 建议入场区间
   - 止损位
   - 第一目标位
   - 触发失效条件
4. 用中文输出，结论清晰，避免空话。
"""

    return (
        f"{prompt_base}\n\n"
        f"## 五因子分项数据\n"
        f"- 成交额(万)：{amount}\n"
        f"- 策略标签：{tags}\n"
        f"{extra_text}\n\n"
        f"{output_requirements}"
    )


def analyze_stocks(
    df: pd.DataFrame,
    top_n: int,
    min_score: float,
    temperature: float,
    prompt_template: str,
) -> List[Dict[str, str]]:
    col = detect_columns(df)
    work_df = df.copy()
    work_df[col["score"]] = pd.to_numeric(work_df[col["score"]], errors="coerce")
    work_df = work_df.dropna(subset=[col["score"]])
    work_df = work_df[work_df[col["score"]] >= min_score]
    work_df = work_df.sort_values(by=[col["score"]], ascending=False).head(top_n)

    if work_df.empty:
        return []

    results: List[Dict[str, str]] = []
    for idx, (_, row) in enumerate(work_df.iterrows(), start=1):
        code = str(row[col["code"]]).split(".")[0].zfill(6)
        score = float(row[col["score"]])
        print(f"\n[{idx}/{len(work_df)}] 🤖 分析 {code}（总分 {score:.1f}）...")

        prompt = build_stock_prompt(row, col, prompt_template=prompt_template)
        try:
            analysis = _call_deepseek_api(prompt, temperature=temperature)
        except Exception as e:
            analysis = f"调用 DeepSeek 失败：{e}"

        results.append(
            {
                "code": code,
                "score": f"{score:.1f}",
                "tags": format_optional(row[col["tags"]]) if col["tags"] else "",
                "analysis": analysis,
            }
        )
        time.sleep(0.8)

    return results


def save_reports(results: List[Dict[str, str]], date_str: str, top_n: int, min_score: float) -> Tuple[Path, Path]:
    output_dir = REPO_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = output_dir / f"deepseek_v3_five_factor_review_{date_str}.md"
    json_path = output_dir / f"deepseek_v3_five_factor_review_{date_str}.json"

    with md_path.open("w", encoding="utf-8") as f:
        f.write(f"# DeepSeek 五因子逐股分析报告（{date_str}）\n\n")
        f.write(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- 分析数量：{len(results)}（top_n={top_n}）\n")
        f.write(f"- 最低分阈值：{min_score}\n\n")
        f.write("## 摘要\n\n")
        f.write("| 序号 | 代码 | 总分 | 策略标签 |\n")
        f.write("|---:|---|---:|---|\n")
        for i, r in enumerate(results, start=1):
            f.write(f"| {i} | {r['code']} | {r['score']} | {r['tags']} |\n")
        f.write("\n---\n\n")

        for i, r in enumerate(results, start=1):
            f.write(f"## {i}. {r['code']}（总分 {r['score']}）\n\n")
            f.write(r["analysis"].strip() + "\n\n")
            f.write("---\n\n")

    with json_path.open("w", encoding="utf-8") as jf:
        json.dump(
            {
                "generated_at": datetime.now().isoformat(),
                "top_n": top_n,
                "min_score": min_score,
                "results": results,
            },
            jf,
            ensure_ascii=False,
            indent=2,
        )

    return md_path, json_path


def main():
    prompt_template, tech_threshold = load_prompt_config()

    parser = argparse.ArgumentParser(description="DeepSeek 逐股分析 core_v3 五因子选股结果")
    parser.add_argument("--csv", type=str, default="", help="[可选] 指定输入 CSV，默认 MySQL 优先")
    parser.add_argument(
        "--trade-date",
        type=str,
        default="",
        help="YYYYMMDD，默认 MySQL/CSV 最新一批",
    )
    parser.add_argument("--top", type=int, default=5, help="分析前 N 只，默认 5")
    parser.add_argument(
        "--min-score",
        type=float,
        default=float(tech_threshold),
        help=f"最低评分阈值，默认取 prompt 配置（当前={tech_threshold:g}）",
    )
    parser.add_argument("--temperature", type=float, default=0.3, help="DeepSeek 温度参数，默认 0.3")
    args = parser.parse_args()

    from scripts.tools.deepseek_client import is_llm_configured

    if not is_llm_configured():
        raise RuntimeError(
            "未检测到 LLM 配置：请设置 DEEPSEEK_API_KEY，或 LLM_BACKEND=cursor 且已 agent login"
        )

    trade_date = args.trade_date.strip() or None
    if args.csv:
        csv_path = Path(args.csv).expanduser().resolve()
        df, date_str, source = resolve_five_factor_df(csv_path=csv_path, trade_date=trade_date)
        input_label = str(csv_path)
    else:
        df, date_str, source = resolve_five_factor_df(trade_date=trade_date)
        input_label = source

    print("=" * 80)
    print("🚀 DeepSeek 五因子逐股分析启动")
    print("=" * 80)
    print(f"数据来源: {input_label}")
    print(f"交易日期: {date_str}")
    print(f"Top N: {args.top}")
    print(f"最低分阈值: {args.min_score}")
    print(f"Temperature: {args.temperature}")

    if df.empty:
        raise RuntimeError(
            "五因子选股结果为空。请先运行 core_v3/stock_selection_five_factor_mysql.py"
        )

    results = analyze_stocks(
        df=df,
        top_n=max(1, int(args.top)),
        min_score=float(args.min_score),
        temperature=float(args.temperature),
        prompt_template=prompt_template,
    )
    if not results:
        raise RuntimeError("没有满足条件的股票可分析（请降低 --min-score 或检查输入文件）")

    md_path, json_path = save_reports(
        results=results,
        date_str=date_str or datetime.now().strftime("%Y%m%d"),
        top_n=args.top,
        min_score=args.min_score,
    )

    print("\n" + "=" * 80)
    print("✅ DeepSeek 逐股分析完成")
    print(f"Markdown 报告: {md_path}")
    print(f"JSON 结果: {json_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
