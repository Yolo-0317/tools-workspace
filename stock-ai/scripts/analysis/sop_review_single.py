#!/usr/bin/env python3
"""单只股票：东财 SOP 采集 + DeepSeek 终审 + 微信推送。"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT, ROOT / "core_v2"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from dotenv import load_dotenv

from scripts.analysis.eastmoney_sop_extract import extract_and_save_batch
from scripts.analysis.sop_review_top5_concurrent import (
    _load_names,
    _technical_supplement,
)
from scripts.tools.deepseek_client import call_deepseek, is_llm_configured
from scripts.tools.holdings_context import load_full_decision_context
from scripts.tools.sop_watch_parse import parse_sop_review_text


def _deepseek_full_report(
    meta: dict,
    preliminary_path: str,
    technical: str,
    holdings_context: str,
    *,
    stock_name: str = "",
) -> tuple[str, str]:
    """单股完整 SOP 报告（与 investment-agent 对话格式一致）。"""
    import json

    code = meta["代码"]
    name = (stock_name or code).strip()
    preliminary = Path(preliminary_path).read_text(encoding="utf-8")
    prompt = f"""你是专业 A 股分析师。基于东财 SOP 初步报告，输出**完整投资决策报告**（决策支持，非投资建议）。

## 选股信号
{json.dumps(meta, ensure_ascii=False, indent=2)}

## MySQL 技术面补充
{technical}

## 东财 SOP 初步报告
{preliminary}

## 必须遵循的决策上下文（持仓、仓位、P0～P4、禁止规则）
{holdings_context}

## 输出格式（严格按此结构，全中文，禁止开场白）

## {name}（{code}）· 东财 SOP 分析

**持仓状态**：[在持仓中/不在持仓中；若在持仓说明股数与成本]
**账户约束**：[总仓位%、可用资金、相关红线如单日涨幅>5%不追高]

---

### 一、行情与技术（截至最近交易日收盘）

| 项目 | 数据 |
|------|------|
| [填收盘价、涨跌幅、区间、换手量比、均线、估值等关键项] | |

**技术解读**：[2～4 句：趋势、量价、是否踩红线]

### 二、资金面

[主力/超大单/大单/中单/小单净流入与解读，2～4 句]

### 三、基本面（注明行业类型：电力/周期/消费等）

| 指标 | 最新期 | 对比期 |
|------|--------|--------|
| [营收、净利、EPS、ROE 等 2～4 行] | |

**结论**：[估值方法（电力看 PB/股息，周期不看 PE 等）+ 1～2 句判断]

**消息面**：[近期 1～2 条关键事件]

### 四、与你持仓的关系

[对比用户现有持仓中同行业/同主题标的，说明是否重复敞口、是否应先执行 P0～P4 计划；2～4 句]

### 五、关键位

| 类型 | 价位 |
|------|------|
| 支撑 | [具体价位，逗号分隔] |
| 压力 | [具体价位] |
| 止损参考 | [价位与条件] |
| 目标参考 | [价位区间] |

### 六、决策（条件式，非投资建议）

**结论：[买入观察/持有/减仓/暂不操作 之一，加一句概括]**

**理由**（编号 1. 2. 3. 4.，每条一句，须提及仓位红线、不追高规则是否触发）

**若后续考虑介入，可设条件**（须满足后再评估，非指令）
- **理想**：[具体价位与量能条件]
- **次优**：[备选条件]
- **放弃**：[何种情形不做]

**主要风险**（编号 1. 2. 3.）
1. [技术/资金风险]
2. [基本面/事件风险]
3. [仓位/操作风险]

---

**WATCH**：[值得关注/暂不关注]
**DECISION**：[买入观察|暂不操作|持有|减仓]
**SUPPORT**：[支撑价，逗号分隔，无则 -]
**STOP**：[止损价，无则 -]
**TARGET**：[目标价，逗号分隔，无则 -]

WATCH: 是|否 | DECISION: 买入观察|暂不操作|持有|减仓 | SUPPORT: x,x | STOP: x | TARGET: x,x

要求：
- 数据从初步报告提取，勿编造；缺失则写「未获取」
- 电力/公用事业优先 PB、股息，周期股警惕 PE 陷阱
- 最后一行 WATCH: 机器标签必须单独成行、格式固定
- 允许 Markdown 表格；禁止 ** 以外多余 markdown 标题层级"""

    content = call_deepseek(
        [
            {
                "role": "system",
                "content": (
                    "专业、客观、结合用户持仓与操盘红线。禁止开场白，直接从「## 股票名」标题开始。"
                    "输出须完整、可分段阅读，适合微信推送。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=5000,
        timeout=(10, 240),
    )
    return code, content


def meta_from_row(row: dict) -> dict:
    code = str(row.get("代码") or row.get("code") or "").split(".")[0].zfill(6)
    if not code or code == "000000":
        raise ValueError("无效股票代码")
    return {
        "代码": code,
        "收盘价": float(row.get("收盘价") or row.get("close") or 0),
        "涨幅%": float(row.get("涨幅%") or row.get("pct_chg") or 0),
        "策略标签": str(row.get("策略标签") or row.get("strategy_label") or ""),
        "总分": float(row.get("总分") or row.get("score") or 0),
        "建议动作": str(row.get("建议动作") or row.get("action_hint") or ""),
        "信号分": row.get("信号分"),
        "趋势分": row.get("趋势分"),
        "动量分": row.get("动量分"),
        "成交额(万)": float(row.get("成交额(万)") or row.get("amount") or 0),
    }


def format_single_wechat(meta: dict, review_md: str, parsed) -> str:
    """与看板「SOP 审查」展开的 review_md 完全一致，不做二次摘要。"""
    _ = (meta, parsed)
    return review_md.strip()


def review_single_and_push_wechat(
    code: str,
    *,
    row: dict | None = None,
    trade_date: str | None = None,
    push: bool = True,
) -> dict:
    """执行单股 SOP，可选推微信。返回摘要与报告路径。"""
    if not is_llm_configured():
        raise RuntimeError("未配置 DeepSeek（DEEPSEEK_API_KEY 或 LLM_BACKEND）")

    load_dotenv(ROOT / ".env")
    os.environ["MYSQL_URL"] = os.environ.get("MYSQL_URL", "").replace(
        "host.docker.internal", "127.0.0.1"
    )

    code = str(code).split(".")[0].zfill(6)
    meta = meta_from_row(row) if row else meta_from_row({"代码": code})
    if meta["代码"] != code:
        meta["代码"] = code

    day = (trade_date or datetime.now().strftime("%Y%m%d")).replace("-", "")[:8]
    sop_dir = ROOT / "output" / "sop_preliminary" / "on_demand" / day
    sop_dir.mkdir(parents=True, exist_ok=True)

    holdings_codes, context = load_full_decision_context()
    context = context.strip() or "（无决策上下文）"

    batch_result = extract_and_save_batch([code], sop_dir, chain_technical=True)
    if isinstance(batch_result, tuple):
        paths, tech_map = batch_result
        preliminary_path = paths[code]
        technical = _technical_supplement(code, tech_map)
    else:
        preliminary_path = batch_result[code]
        technical = _technical_supplement(code)

    mysql_url = os.environ.get("MYSQL_URL", "")
    names = _load_names([code], mysql_url)

    stock_name = names.get(code, code)
    _, review_md = _deepseek_full_report(
        meta,
        preliminary_path,
        technical,
        context,
        stock_name=stock_name,
    )

    parsed = parse_sop_review_text(
        code,
        review_md,
        name=names.get(code, code),
        score=float(meta.get("总分") or 0),
    )
    parsed.in_holdings = code in holdings_codes
    if parsed.in_holdings:
        parsed.watch_worthy = False

    wechat = format_single_wechat(meta, review_md, parsed)
    report_path = ROOT / "output" / f"sop_single_{code}_{day}_{datetime.now():%H%M%S}.md"
    report_path.write_text(
        "\n".join(
            [
                f"# {code} {names.get(code, '')} 东财 SOP 完整报告",
                "",
                f"**生成时间**：{datetime.now():%Y-%m-%d %H:%M:%S}",
                f"**选股日**：{day}",
                f"**初步报告**：{preliminary_path}",
                "",
                "---",
                "",
                review_md,
            ]
        ),
        encoding="utf-8",
    )

    pushed = False
    push_error: str | None = None
    if push:
        try:
            from scripts.tools.wechat_acp_push_text import send_wechat_acp_text

            send_wechat_acp_text(wechat)
            pushed = True
        except Exception as exc:  # noqa: BLE001
            push_error = str(exc)

    return {
        "code": code,
        "name": names.get(code, parsed.name or code),
        "trade_date": day,
        "decision": parsed.decision,
        "wechat_text": wechat,
        "report_path": str(report_path),
        "preliminary_path": preliminary_path,
        "wechat_pushed": pushed,
        "push_error": push_error,
        "review_md": review_md,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="单股东财 SOP + 微信推送")
    parser.add_argument("code", help="6 位代码")
    parser.add_argument("--trade-date", default=None, help="YYYYMMDD")
    parser.add_argument("--no-push", action="store_true")
    args = parser.parse_args()

    result = review_single_and_push_wechat(
        args.code,
        trade_date=args.trade_date,
        push=not args.no_push,
    )
    print(result["wechat_text"])
    if result.get("push_error"):
        print(f"⚠️ 微信推送失败: {result['push_error']}", file=sys.stderr)
        return 1
    print(f"\n📄 报告: {result['report_path']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
