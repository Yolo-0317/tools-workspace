#!/usr/bin/env python3
"""流量主优化：完读率、文中广告位、垂直关键词提示、文末互动（不违背公开稿红线）。"""

from __future__ import annotations

import os
import re
from typing import Literal

DraftKind = Literal["sector", "market", "news", "top5", "dragons", "workspace", "temp"]

_DISCLAIMER_MARKS = (
    "本文为作者个人投资日记",
    "本文为作者个人工程笔记",
    "本文为个人体验与信息整理",
)

# 财经/科技垂直词（自然植入，勿堆砌；匹配高 eCPM + 搜一搜停留）
TRAFFIC_VERTICAL_WORDS = (
    "复盘",
    "收盘复盘",
    "结构",
    "避坑",
    "盯盘",
    "攻略",
    "量能",
    "量价",
    "产业链",
    "梯队",
    "龙头",
    "情绪",
    "量化",
    "自动化",
    "MySQL",
    "脚本",
)

# 按稿型优先检查的垂直词（traffic 清单 ≥ WECHAT_MP_VERTICAL_WORDS_MIN 个命中）
VERTICAL_HINTS_BY_KIND: dict[str, tuple[str, ...]] = {
    "sector": ("产业链", "复盘", "结构", "量价", "行业"),
    "market": ("复盘", "结构", "盯盘", "避坑", "收盘"),
    "news": ("复盘", "盯盘", "避坑", "快讯"),
    "top5": ("结构", "盯盘", "避坑", "攻略", "收盘信号"),
    "dragons": ("龙头", "梯队", "避坑", "复盘", "情绪"),
    "workspace": ("自动化", "脚本", "量化", "复盘"),
    "temp": ("自动化", "脚本", "CLI", "复盘"),
}

# 按稿型给 LLM 的额外写作要求（荐股红线仍由 PUBLIC_MP_WRITER_RULE 约束）
_MONETIZATION_PROMPT: dict[str, str] = {
    "sector": (
        "【阅读】标题前 15 字含 A股/行业/产业链；摘要含「行业研究」。"
        "【完读】五节阅读路径预告；节间轻过渡「·」（成稿会补，勿写「往下看」）；"
        "「向后看要验证什么」末句「若…则…露馅」式悬念；单段宜短。"
        "【垂直词】勿堆砌热词；清单/对照表利于搜一搜停留。"
    ),
    "market": (
        "【阅读】标题含收盘复盘或盘前/午间词；与 edition 一致。"
        "【完读】盘面→外围→结构阅读路径；节间「·」轻过渡；结构判断末句若则验证。"
        "「盘面速览」须有数字；单段宜短。"
        "【垂直词】原创分类财经/科技；勿标题党。"
    ),
    "news": (
        "【阅读】标题含快讯/要闻；10 条结构清晰。"
        "【完读】导语预告递进阅读；条与条之间「·」轻过渡（成稿会补）；"
        "每条摘要+AI点评；第 3 条后宜分段跳读。"
    ),
    "top5": (
        "【阅读】公众号标题由系统生成（领衔股+只数句式），**正文禁止**复述该标题或「收盘信号出炉/明日盯啥」问句。"
        "【完读】「筛选名单」开篇须预告阅读路径（逐只拆→组合→待验证）；"
        "个股之间用简短过渡吊读（成稿会补「·」开头的衔接句，勿写「往下看」）；"
        "「待验证事项」末句用「若…则…谁先…」式可验证悬念；禁分数与买卖暗示。"
        "【垂直词】正文声明观察池、非荐股。"
    ),
    "dragons": (
        "【阅读】公众号标题由系统生成（情绪{阶段}怎么玩？{龙头}{N}板还在榜），"
        "**正文禁止**复述该标题或同构问句；开篇直接从「> 情绪与盘面」写数字事实。"
        "【完读】开篇数字+阅读路径；龙头拆解间「·」轻过渡；节间桥接；"
        "「明日计划与纪律」末句退潮/修复若则验证；650～1100 字。"
        "【垂直词】清单体/梯队表，利于收藏与搜一搜停留。"
    ),
    "workspace": (
        "【完读与流量】首段场景化（收盘一刻钟跑什么）；"
        "自然提自动化、脚本、量化、MySQL 等科技词；"
        "公众号草稿小节可写「复盘四坑位怎么覆写」类攻略表述。"
    ),
    "temp": (
        "【完读与流量】首段写清读者能学会什么（工具/接入/踩坑）；"
        "自然提 CLI、自动化、Cursor 等词；禁止出现槽位、临稿、转链接给用户等运维话术。"
    ),
}

_ENGAGEMENT_POOL: dict[str, tuple[str, ...]] = {
    "sector": (
        "今日主线行业里，你更看产业链哪一段？留言说说。",
        "热点行业稿，你更信新闻催化还是盘面量价？欢迎交流。",
    ),
    "market": (
        "看完结构判断，你明天更盯周期还是科技？留言说说。",
        "指数涨、个股跌的日子，你一般怎么控节奏？欢迎交流。",
    ),
    "news": (
        "十条里哪一条最可能影响你的板块？留言聊聊。",
        "地缘和金价两条，你更信哪条传导？说说看法。",
    ),
    "top5": (
        "五只里你更想看哪条结构的后续验证？可以点名。",
        "综合选股和单策略信号，你平时更信哪路？留言讨论。",
    ),
    "dragons": (
        "退潮日你习惯空仓还是小仓试错？留言交流纪律。",
        "空间板断板后，你盯梯队还是直接休息？说说你的做法。",
    ),
    "workspace": (
        "你的收盘自动化是脚本还是定时任务？留言交换踩坑。",
        "五类日更稿，你最想先看哪一类？可以投票式留言。",
    ),
    "english_buddy": (
        "你家娃跟读更怕「说得慢」还是「说得不对」？留言聊聊。",
        "幼儿园课文你会自己贴进列表吗？欢迎交流踩坑。",
    ),
    "temp": (
        "飞书自动化你更信 OpenAPI 还是官方 CLI？留言说说踩坑。",
        "bot 和用户身份你怎么分工？欢迎交流。",
    ),
    "commerce": (
        "你家厨房台面大概多宽？欢迎留言，方便后来的人对照。",
        "调料架和插排固定，你更先解决哪一个？",
        "如果只能留一件小收纳，你会选哪类？",
    ),
}


def monetization_enabled() -> bool:
    raw = os.getenv("WECHAT_MP_MONETIZE", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def vertical_words_min() -> int:
    """traffic 清单要求正文命中垂直词个数（默认 2）。"""
    try:
        return max(1, int(os.getenv("WECHAT_MP_VERTICAL_WORDS_MIN", "2")))
    except ValueError:
        return 2


def vertical_hints_for_kind(kind: str) -> tuple[str, ...]:
    k = (kind or "").strip().lower()
    return VERTICAL_HINTS_BY_KIND.get(k, TRAFFIC_VERTICAL_WORDS)


def count_vertical_hits(text: str, kind: str) -> list[str]:
    plain = text or ""
    return [w for w in vertical_hints_for_kind(kind) if w in plain]


def ad_checkpoint_enabled() -> bool:
    """文中广告由微信流量主自动插入，正文默认不留人工标记位。"""
    raw = os.getenv("WECHAT_MP_AD_CHECKPOINT", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def engagement_hook_enabled() -> bool:
    raw = os.getenv("WECHAT_MP_ENGAGEMENT_HOOK", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def recommend_hook_enabled() -> bool:
    raw = os.getenv("WECHAT_MP_RECOMMEND_HOOK", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


_RECOMMEND_HOOK_MARKERS = ("推荐 ♡", "推荐♡", "点「推荐", "点右下角推荐")


def default_recommend_hook_line() -> str:
    return (
        os.getenv("WECHAT_MP_RECOMMEND_HOOK_TEXT", "").strip()
        or "若这篇对你有用，欢迎点文章下方「推荐 ♡」，也方便推给同样在复盘的朋友。"
    )


def monetization_prompt_block(kind: str) -> str:
    if not monetization_enabled():
        return ""
    block = _MONETIZATION_PROMPT.get(kind.strip().lower(), "")
    return f"\n{block}\n" if block else ""


def comment_settings() -> dict[str, int]:
    """草稿 API 可传的留言开关（默认开评论以促互动，仅粉丝可评可 env 关）。"""
    def _b(name: str, default: int) -> int:
        raw = os.getenv(name, str(default)).strip().lower()
        return 0 if raw in ("0", "false", "no", "off") else 1

    return {
        "need_open_comment": _b("WECHAT_MP_NEED_OPEN_COMMENT", 1),
        "only_fans_can_comment": _b("WECHAT_MP_ONLY_FANS_COMMENT", 0),
    }


_AD_SEPARATOR = "\n\n· · ·\n\n"


def _insert_after_section(body: str, section_title: str) -> str:
    """在第一个 `> section` 块结束后（下一节 `>` 前）插入文中广告建议位。"""
    lines = body.splitlines()
    out: list[str] = []
    in_section = False
    inserted = False
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        stripped = line.strip()
        if stripped.startswith("> ") and section_title in stripped:
            in_section = True
            i += 1
            continue
        if in_section and not inserted and stripped.startswith("> ") and section_title not in stripped:
            out.insert(len(out) - 1, _AD_SEPARATOR.strip())
            inserted = True
            in_section = False
        i += 1
    if inserted:
        return "\n".join(out)
    return body


def _insert_after_news_item(body: str, after_item: int = 3) -> str:
    """要闻稿：第 N 条快讯块之前插入分隔（即第 3 条后、第 4 条前）。"""
    lines = body.splitlines()
    starts = [i for i, line in enumerate(lines) if re.match(r"^\d+\.", line.strip())]
    if len(starts) <= after_item:
        return body
    insert_at = starts[after_item]
    block = ["", _AD_SEPARATOR.strip(), ""]
    return "\n".join(lines[:insert_at] + block + lines[insert_at:])


def insert_inarticle_ad_checkpoint(body: str, *, kind: str) -> str:
    if not ad_checkpoint_enabled():
        return body
    k = kind.strip().lower()
    if k in {"sector", "industry"}:
        return _insert_after_section(body, "产业链怎么拆")
    if k == "market":
        return _insert_after_section(body, "盘面速览")
    if k == "news":
        return _insert_after_news_item(body, after_item=3)
    if k == "top5":
        return _insert_after_section(body, "筛选名单")
    if k == "dragons":
        return _insert_after_section(body, "情绪与盘面")
    if k in {"workspace", "temp"}:
        return _insert_after_section(body, "它是什么") if k == "workspace" else body
    return body


def append_engagement_hook(
    body: str,
    *,
    kind: str,
    engagement_kind: str | None = None,
) -> str:
    if not engagement_hook_enabled():
        return body
    pool_key = (engagement_kind or kind).strip().lower()
    pool = _ENGAGEMENT_POOL.get(pool_key)
    if not pool:
        return body
    all_hooks = (p for hooks in _ENGAGEMENT_POOL.values() for p in hooks)
    if any(p[:12] in body for p in all_hooks):
        return body
    title_hint = ""
    for line in body.splitlines():
        if line.strip().startswith("> "):
            title_hint = line.strip()[2:6]
            break
    idx = sum(ord(c) for c in (title_hint or kind)) % len(pool)
    hook = pool[idx]
    return f"{body.rstrip()}\n\n{hook}"


def append_recommend_hook(body: str, *, kind: str) -> str:
    """文末引导点「推荐 ♡」（朋友推荐流；非点赞/在看套路）。"""
    del kind
    if not recommend_hook_enabled():
        return body
    if any(m in body for m in _RECOMMEND_HOOK_MARKERS):
        return body
    line = default_recommend_hook_line()
    if not line:
        return body
    return f"{body.rstrip()}\n\n{line}"


def polish_for_traffic(
    body: str,
    *,
    kind: str,
    engagement_kind: str | None = None,
) -> str:
    """成稿后处理：文末互动问句 + 推荐♡引导（不含免责声明）。"""
    if not monetization_enabled():
        return body
    body = append_engagement_hook(body, kind=kind, engagement_kind=engagement_kind)
    return append_recommend_hook(body, kind=kind)


def split_disclaimer(body: str) -> tuple[str, str]:
    for mark in _DISCLAIMER_MARKS:
        if mark in body:
            core, _, tail = body.partition(mark)
            return core.rstrip(), mark + tail
    return body, ""


_TRAILING_DISCLAIMER_LINE_RE = re.compile(
    r"^(?:"
    r"本文为作者个人投资日记|"
    r"本文为作者个人工程笔记|"
    r"本文为个人体验与信息整理|"
    r".*不构成投资建议.*|"
    r"以上仅为市场观察|"
    r"市场有风险|"
    r"决策自负"
    r")",
    re.I,
)


def _is_inline_disclaimer_line(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 160:
        return False
    if _TRAILING_DISCLAIMER_LINE_RE.match(s):
        return True
    if "免责声明" in s and re.search(r"不构成|投资需谨慎|买卖推荐|仅供参考", s):
        return True
    if re.search(r"不构成任何投资|仅代表作者.*观点", s):
        return True
    return False


def strip_inline_disclaimer_blocks(text: str) -> str:
    """去掉正文任意位置的 LLM 免责段（文末统一由 disclaimer_html 输出）。"""
    lines: list[str] = []
    for line in text.splitlines():
        if _is_inline_disclaimer_line(line):
            continue
        lines.append(line.rstrip())
    merged = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", merged).strip()


def strip_trailing_disclaimer_from_core(text: str) -> str:
    """去掉正文末尾 LLM 自带的免责句，避免与统一免责块重复。"""
    return strip_inline_disclaimer_blocks(text)
