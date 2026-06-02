#!/usr/bin/env python3
"""基于已落库快讯 + Cursor Agent 生成财经 AI 解读。"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.deepseek_client import call_deepseek, is_llm_configured
from scripts.tools.fetch_eastmoney_macro_news import MacroNewsItem
from scripts.tools.market_session import detect_market_session
from scripts.tools.news_db import GEOPOLITICS_KEYWORDS, save_briefing_snapshot
from scripts.tools.news_sentiment import classify_news_sentiment, sentiment_label
from scripts.tools.wechat_format import format_ai_interpretation

TZ = ZoneInfo("Asia/Shanghai")

# 公开看板 AI 解读须剔除的持仓段（历史快照兼容）
_HOLDINGS_SECTION_RE = re.compile(
    r"(?:\n|^)[ \t]*📋[ \t]*持仓关注点[^\n]*\n.*?(?=(?:\n[ \t]*📊|\n[ \t]*📰|\n[ \t]*【[^】]*】)|\Z)",
    re.DOTALL,
)


def sanitize_public_ai_summary(text: str) -> str:
    """去掉「持仓关注点」及其中 P0～P4 等个人持仓提示（公开财经用）。"""
    if not text:
        return text
    cleaned = _HOLDINGS_SECTION_RE.sub("\n", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _pick_geopolitics(items: list[MacroNewsItem], limit: int = 5) -> list[MacroNewsItem]:
    picked: list[MacroNewsItem] = []
    for item in items:
        blob = f"{item.title} {item.summary}"
        if any(kw in blob for kw in GEOPOLITICS_KEYWORDS):
            picked.append(item)
        if len(picked) >= limit:
            break
    return picked


def _format_news_lines(title: str, items: list[MacroNewsItem], *, limit: int) -> str:
    lines = [title]
    if not items:
        lines.append("- 暂无")
        return "\n".join(lines)
    for idx, item in enumerate(items[:limit], start=1):
        time_part = f"{item.time} " if item.time else ""
        tag = sentiment_label(classify_news_sentiment(item.title, item.summary))
        lines.append(f"{idx}. [{tag}] {time_part}{item.title}")
        if item.summary and item.summary != item.title:
            summary = item.summary
            if len(summary) > 100:
                summary = summary[:100] + "…"
            lines.append(f"   {summary}")
    return "\n".join(lines)


def _current_slot(now: datetime | None = None) -> str:
    now = now or datetime.now(TZ)
    minute = (now.minute // 15) * 15
    return f"{now.hour:02d}:{minute:02d}"


def build_news_context(
    items: list[MacroNewsItem],
    *,
    news_limit: int = 8,
) -> str:
    geo = _pick_geopolitics(items, limit=5)
    geo_hrefs = {x.href for x in geo}
    domestic = [x for x in items if x.href not in geo_hrefs][:news_limit]
    blocks = [
        _format_news_lines("【国际地缘】", geo, limit=5),
        "",
        _format_news_lines("【国内财经】", domestic, limit=news_limit),
    ]
    return "\n".join(blocks)


def generate_news_ai_summary(
    items: list[MacroNewsItem],
    *,
    news_limit: int = 8,
    now: datetime | None = None,
) -> str:
    """使用 Cursor Agent（LLM_BACKEND=cursor）生成解读。"""
    os.environ.setdefault("LLM_BACKEND", "cursor")

    now = now or datetime.now(TZ)
    session = detect_market_session(now=now)
    news_blob = build_news_context(items, news_limit=news_limit)

    prompt = f"""以下是东财 7×24 最新财经快讯（{now.strftime('%Y-%m-%d %H:%M')}）：

{news_blob}

## 行情时效
{session.ai_session_hint(_current_slot(now))}

请输出看板「公开版」AI 综合解读，严格按下列格式（每个小节标题单独一行，小节之间空一行）：

【AI 综合解读】

📊 大盘与外围
（2-3 句：休市/收盘日期 + 地缘/原油/外围要点）

📰 国内要闻
· 要点一（一句）
· 要点二
· 要点三

要求：
1. 总字数 ≤400 字；全中文；禁止 markdown 表格与 **加粗**
2. 仅解读宏观与快讯，禁止绝对买卖指令
3. 禁止输出任何个人持仓、选股池、P0～P4、补仓/减仓/止损等账户操作提示
4. 基于上述快讯，不要编造未出现的事实"""

    if not is_llm_configured():
        return "【AI 综合解读】\n（跳过：LLM_BACKEND=cursor 未就绪，请 agent login）"

    try:
        content = call_deepseek(
            [
                {
                    "role": "system",
                    "content": "你是 A 股投资助手，输出简洁务实，全中文，善用空行分段。",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
        )
        return sanitize_public_ai_summary(format_ai_interpretation(content))
    except Exception as exc:  # noqa: BLE001
        return f"【AI 综合解读】\n（生成失败：{exc}）"


def save_news_ai_snapshot(
    items: list[MacroNewsItem],
    *,
    news_limit: int = 8,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(TZ)
    slot = _current_slot(now)
    ai_summary = generate_news_ai_summary(items, news_limit=news_limit, now=now)
    raw_text = build_news_context(items, news_limit=news_limit)
    save_briefing_snapshot(
        slot=slot,
        title="财经快讯解读",
        raw_text=raw_text,
        ai_summary=ai_summary,
        briefing_date=now.date(),
        created_at=now.replace(tzinfo=None),
    )
    return ai_summary


def main() -> int:
    import argparse

    from scripts.tools.news_db import load_recent_news

    parser = argparse.ArgumentParser(description="基于 MySQL 快讯生成 Cursor AI 解读")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()

    items = load_recent_news(hours=6, limit=max(args.limit * 2, 16))
    if not items:
        print("❌ 无快讯数据，请先运行 sync_macro_news", file=sys.stderr)
        return 1

    summary = save_news_ai_snapshot(items, news_limit=args.limit)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
