#!/usr/bin/env python3
"""公众号 A 股盘面稿：指数 + 外围 + 结构判断（要闻另开 news 槽位）。"""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.deepseek_client import call_deepseek, is_llm_configured
from scripts.tools.wechat_mp_public import PUBLIC_MP_WRITER_RULE, RESEARCHER_VOICE_RULE
from scripts.tools.wechat_mp_monetization import monetization_prompt_block
from scripts.tools.market_session import detect_market_session

TZ = ZoneInfo("Asia/Shanghai")

SECTION_MARKET = "> 盘面速览"
SECTION_GLOBAL = "> 外围与资金"
SECTION_VIEW = "> 结构判断"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def _fetch_market_block(session) -> list[str]:
    from scripts.tools.daily_briefing_report import (
        fetch_international_markets,
        fetch_market_indices,
    )

    lines = [session.header_note(), ""]
    lines.extend(fetch_market_indices())
    lines.append("")
    lines.append("国际市场简况：")
    intl = fetch_international_markets()
    lines.extend(intl[:8] if len(intl) > 8 else intl)
    return lines


def build_market_context_blob(
    *,
    now: datetime | None = None,
    edition: str | None = None,
) -> str:
    """组装给 LLM / 模板的盘面素材（不含快讯列表；快讯以素材块注入）。"""
    from scripts.tools.wechat_mp_market_edition import (
        build_market_news_context,
        edition_label,
        edition_writing_hint,
        normalize_market_edition,
    )

    now = now or datetime.now(TZ)
    ed = normalize_market_edition(edition)
    session = detect_market_session(now=now)
    news_blob, _items = build_market_news_context(ed, now=now)
    parts = [
        f"写作时间：{now.strftime('%Y-%m-%d %H:%M')}（{session.ai_session_hint(now.strftime('%H:%M'))}）",
        f"发稿时段：{edition_label(ed)}",
        edition_writing_hint(ed),
        "",
        "【A股盘面数据】",
        *_fetch_market_block(session),
        "",
        news_blob,
    ]
    return "\n".join(parts)


def _index_lines_from_blob(blob: str) -> list[str]:
    lines: list[str] = []
    for block_line in blob.splitlines():
        if block_line.startswith(
            ("上证指数", "深证成指", "创业板指", "沪深300", "科创50", "全A涨跌")
        ):
            lines.append(block_line)
    return lines or ["（指数数据获取失败，请稍后重试）"]


def _template_market_body(*, now: datetime | None = None) -> str:
    """无 LLM 时的研究员体例模板。"""
    now = now or datetime.now(TZ)
    blob = build_market_context_blob(now=now)
    lines = [
        SECTION_MARKET,
        *_index_lines_from_blob(blob),
        "",
        "指数收红并不等同于普涨，需对照涨跌家数看结构：若上涨家数偏少，"
        "往往意味着权重或少数主线在撑指数，操作上要更强调位置与纪律。",
        "",
        SECTION_GLOBAL,
        "隔夜欧美市场波动不大，港股方向对 A 股情绪仍有传导；"
        "若外围风险偏好抬升，北向与两融数据是否同步跟进，是验证逻辑的关键。",
        "原油与汇率若有异动，则优先影响周期与出口链的预期，而非一刀切看多或看空。",
        "",
        SECTION_VIEW,
        "我们认为，当前阶段仍宜「先看结构、再谈方向」：指数点位是结果，"
        "涨跌家数、量能与主线持续性才是原因。",
        "若指数与个股背离，短线更宜控节奏、减追高；若量能回升且梯队完整，"
        "再讨论加仓或扩面。向后看，外围变量与政策预期仍可能扰动节奏。",
    ]
    return "\n".join(lines)


def generate_researcher_market_body(
    *,
    now: datetime | None = None,
    edition: str | None = None,
) -> str:
    """资深研究员口吻正文（盘面 + 外围 + 结构判断；快讯融入评论，不列清单）。"""
    from scripts.tools.wechat_mp_market_edition import (
        edition_writing_hint,
        normalize_market_edition,
    )

    now = now or datetime.now(TZ)
    ed = normalize_market_edition(edition)
    context = build_market_context_blob(now=now, edition=ed)

    if not is_llm_configured():
        return _template_market_body(now=now)

    view_min = _env_int("WECHAT_MP_MARKET_VIEW_MIN", 380)
    view_max = _env_int("WECHAT_MP_MARKET_VIEW_MAX", 520)

    prompt = f"""你是一位从业15年的A股宏观策略研究员，为公众号撰写「A股评论稿」。
{PUBLIC_MP_WRITER_RULE}
{RESEARCHER_VOICE_RULE}

{context}

## 写作要求
0. **结论先行**：在 `{SECTION_MARKET}` 之前，先写 2 句（40-80字），含主要指数涨跌幅数字 + 结构判断（如指数与个股是否共振）；然后再写三节标题。若遗漏，成稿流水线会自动从「盘面速览」提炼。
1. 全文三节，节标题必须逐字使用以下三行（不要用「一、二、三」或数字序号）：
   {SECTION_MARKET}
   {SECTION_GLOBAL}
   {SECTION_VIEW}
2. 「盘面速览」180-260字：
   - 先逐条写出主要指数涨跌幅与全A涨跌家数（有则写，无则说明获取失败）
   - 再写 2-3 句结构解读：指数与个股是否共振、权重/中小盘谁更强、对下一交易节奏的含义
3. 「外围与资金」240-340字：
   - 概括上下文中的国际市场简况（美股/港股/原油等，有则写）
   - **将「财经快讯素材」中的宏观/产业要点自然融入**，写清事件→传导→对A股风险偏好或板块的影响
   - 说明对 A 股风险偏好、北向/两融预期的可能影响
   - 点 1 个需跟踪的验证指标（如美债收益率、油价、恒生科技等）
4. 「结构判断」{view_min}-{view_max}字：
   - 首段 1-2 句总判断（偏多/偏空/结构分化）
   - 中间拆 3 条逻辑链，每条含「现象 → 机制 → 板块映射」；**至少 1 条须承接快讯素材中的主线**
   - **「我们认为」「值得关注的是」「向后看」须各起一段**：段首单独成行，段与段之间空一行（勿挤在同一段）
   - 末段用「向后看」给 1-2 个观察点
   - 避免喊单、具体价位、个股推荐
5. 禁止 emoji、禁止【AI综合解读】、禁止 markdown 加粗与表格
6. 只使用上下文出现的事实，勿编造数据
6b. **移动端排版**：普通段落每段约 120 字内，超长须在句号处拆段；若用 `1. 2. 3.` 列表则每项单独一行
7. **禁止**编号列出快讯（不要「1. 2. 3.」、不要「今日要闻如下」「据快讯」）；读者应读到连贯评论而非新闻清单
8. **禁止**在正文写「免责声明」、括号免责、不构成投资建议等收尾句（文末由排版统一追加）
8. 时段要求：{edition_writing_hint(ed)}
{monetization_prompt_block("market")}"""

    try:
        content = call_deepseek(
            [
                {
                    "role": "system",
                    "content": (
                        "你是资深A股宏观研究员，文风冷静、有框架感，"
                        "像给不特定读者的公开盘后简报，而不是聊天机器人或作者日记。"
                        "禁止涉及作者个人持仓与账户。正文要够厚，避免一句带过。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=_env_int("WECHAT_MP_MARKET_MAX_TOKENS", 3200),
        )
        return content.strip()
    except Exception as exc:  # noqa: BLE001
        body = _template_market_body(now=now)
        return f"{body}\n\n（研究员点评生成失败：{exc}，以上为模板正文）"
