#!/usr/bin/env python3
"""流量主优化：完读率、文中广告位、垂直关键词提示、文末互动（不违背公开稿红线）。"""

from __future__ import annotations

import os
import re
from typing import Literal

DraftKind = Literal["sector", "hotspot", "hot_business", "silver", "short_drama_feature", "market", "news", "workspace", "temp"]

_DISCLAIMER_MARKS = (
    "本文为作者个人复盘笔记",
    "本文为作者个人市场信息整理",
    "本文为作者个人工程笔记",
    "本文为个人体验与信息整理",
    "本文为作者个人投资日记",  # 旧稿兼容：拆分免责声明，新稿勿再使用
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
    "hotspot": ("报道", "网友", "争议", "公开", "多方", "事件"),
    "hot_business": ("品牌", "公司", "产品", "成本", "渠道", "竞争"),
    "silver": ("退休", "生活", "夫妻", "子女", "睡眠", "运动", "养老金", "消费", "防骗"),
    "short_drama_feature": ("短剧", "主角", "冲突", "反转", "继续看"),
    "tv_review": ("报道", "网友", "争议", "公开", "多方", "事件"),
    "sector": ("产业链", "复盘", "结构", "量价", "行业"),
    "market": ("复盘", "结构", "盯盘", "避坑", "收盘"),
    "news": ("复盘", "盯盘", "避坑", "快讯"),
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
    "hotspot": (
        "【阅读】标题前 15 字含可搜实体（案由/片名/事件/数字），表意完整；勿 #A股 打头。"
        "【完读】纯段落长文；首段直接写人+事；社会争议呈现多方；"
        "禁止导读腔、热榜播报、盘面三线对照套话；单段宜短。"
        "【垂直词】自然出现报道/争议/公开信息等，勿堆砌财经词。"
    ),
    "hot_business": (
        "【阅读】标题前 15 字出现品牌、公司或具体产品，明确热点背后的商业问题。"
        "【完读】沿事实、收入成本、渠道竞争、普通人影响和待验证指标递进；纯段落长文。"
        "【垂直词】自然出现品牌/公司/产品/成本/渠道/竞争，事实与推断分开。"
    ),
    "silver": (
        "【阅读】标题直接呈现退休生活中的具体问题，不添加固定栏目名前缀。"
        "【完读】从生活场景开篇，用 3 至 5 个自然小标题解释原因并给出可执行步骤。"
        "【垂直词】关系稿自然出现夫妻/子女/边界；健康稿出现睡眠/饮食/运动/体检/习惯；"
        "钱财稿出现养老金/消费/防骗/旅游/直播购物，避免堆砌。"
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
    "short_drama_feature": (
        "如果是你站在主角的位置，会接下这个几乎没人敢碰的难题吗？",
        "故事停在这里，你更想先看到真相揭开，还是主角完成反击？",
    ),
    "silver": (
        "退休生活里，你现在最想先理顺关系、健康，还是钱财安排？欢迎留言说说。",
        "刚退休时你最不适应的是哪件小事？留言聊聊自己的办法。",
    ),
    "sector": (
        "今日主线行业里，你更看产业链哪一段？留言说说。",
        "热点行业稿，你更信新闻催化还是盘面量价？欢迎交流。",
    ),
    "market": (
        "看完结构判断，你更关注哪条产业链？留言说说。",
        "指数与广度背离时，你一般怎么读结构？欢迎交流。",
    ),
    "news": (
        "十条里哪一条最可能影响你的板块？留言聊聊。",
        "地缘和金价两条，你更信哪条传导？说说看法。",
    ),
    "workspace": (
        "你的收盘自动化是脚本还是定时任务？留言交换踩坑。",
        "五类日更稿，你最想先看哪一类？可以投票式留言。",
    ),
    "english_buddy": (
        "你家娃跟读更怕「说得慢」还是「说得不对」？留言聊聊。",
        "幼儿园课文你会自己贴进列表吗？欢迎交流踩坑。",
    ),
    "harryputter": (
        "你试过 HarryPutter 这类句级听读吗？卡在哪一步留言说说。",
        "文本和朗读音频英美式不一致时你怎么对齐？欢迎交流。",
    ),
    "temp": (
        "飞书自动化你更信 OpenAPI 还是官方 CLI？留言说说踩坑。",
        "bot 和用户身份你怎么分工？欢迎交流。",
    ),
}

_FOLLOW_HOOK_DEFAULT = (
    "我们会继续整理社会与文娱热点；星标本号，下一篇不易漏看。"
)

# 微信审核违规：关注后回复关键词领资料类诱导
_WRITING_REPLY_INDUCMENT_RES = (
    re.compile(r"[。；;]?关注后回复[「『\"]?写作[」』\"]?[^。\n]*"),
    re.compile(
        r"[。；;]?回复[「『\"]?写作[」』\"]?[^。\n]*(?:笔记|技巧|资料|领取)[^。\n]*"
    ),
    re.compile(r"可领大模型辅助写作技巧笔记[。]?"),
    re.compile(r"大模型辅助写作技巧笔记[。]?"),
)

# 阅读 → 关注（与留言问句、推荐 ♡ 分开；推荐流陌生读者主转化点）
_FOLLOW_HOOK_BY_KIND: dict[str, str] = {
    "hotspot": _FOLLOW_HOOK_DEFAULT,
    "hot_business": _FOLLOW_HOOK_DEFAULT,
    "silver": "我们会继续整理退休生活里的关系、健康和钱财问题；星标本号，下一篇不易漏看。",
    "tv_review": _FOLLOW_HOOK_DEFAULT,
    "tv": _FOLLOW_HOOK_DEFAULT,
}

_FOLLOW_HOOK_MARKERS: tuple[str, ...] = (
    "星标本号",
    "下一篇不易漏看",
    "我们会继续整理社会与文娱热点",
    "回复「写作」",
    "大模型辅助写作",
    "有讨论度的公共热点",
    "我们会持续写有讨论度的",
)


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


def follow_hook_enabled() -> bool:
    raw = os.getenv("WECHAT_MP_FOLLOW_HOOK", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


# 社会热点 / 话题讨论不加财经号「推荐 ♡ / 复盘的朋友」引导
_NO_RECOMMEND_HOOK_KINDS = frozenset({
    "guba",
    "hotspot",
    "hot_business",
    "silver",
    "short_drama_feature",
    "tv_review",
    "tv",
    "film",
    "movie",
})


def recommend_hook_applies_to_kind(kind: str | None) -> bool:
    return (kind or "").strip().lower() not in _NO_RECOMMEND_HOOK_KINDS


_RECOMMEND_HOOK_MARKERS = (
    "推荐 ♡",
    "推荐♡",
    "点「推荐",
    "点右下角推荐",
    "点文章下方「推荐」",
)


def default_recommend_hook_line() -> str:
    return (
        os.getenv("WECHAT_MP_RECOMMEND_HOOK_TEXT", "").strip()
        or "若这篇对你有用，欢迎点文章下方「推荐」，也方便推给同样关心这类话题的朋友。"
    )


def default_follow_hook_line(kind: str) -> str:
    custom = os.getenv("WECHAT_MP_FOLLOW_HOOK_TEXT", "").strip()
    if custom:
        return custom
    return _FOLLOW_HOOK_BY_KIND.get((kind or "").strip().lower(), "")


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


def append_follow_hook(body: str, *, kind: str) -> str:
    """文末引导关注（搜一搜陌生读者 → 关注 + 星标）。"""
    k = (kind or "").strip().lower()
    if not follow_hook_enabled() or k not in _FOLLOW_HOOK_BY_KIND:
        return body
    if any(m in body for m in _FOLLOW_HOOK_MARKERS):
        return body
    line = default_follow_hook_line(k)
    if not line:
        return body
    return f"{body.rstrip()}\n\n{line}"


def strip_writing_reply_inducement(text: str) -> str:
    """去掉「关注/回复写作领笔记」类诱导（微信审核违规）。"""
    if not text:
        return text
    out = text
    for pat in _WRITING_REPLY_INDUCMENT_RES:
        out = pat.sub("", out)
    out = re.sub(r"。{2,}", "。", out)
    out = re.sub(r"[；;]\s*$", "", out, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def strip_follow_hook(body: str) -> str:
    """去掉文末关注引导（repush / 旧稿兜底）。"""
    if not body:
        return body
    body = strip_writing_reply_inducement(body)
    lines = body.splitlines()
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if any(m in last for m in _FOLLOW_HOOK_MARKERS):
            lines.pop()
            continue
        break
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def append_recommend_hook(body: str, *, kind: str) -> str:
    """文末引导点「推荐 ♡」（朋友推荐流；非点赞/在看套路）。"""
    if not recommend_hook_applies_to_kind(kind):
        return body
    if not recommend_hook_enabled():
        return body
    if any(m in body for m in _RECOMMEND_HOOK_MARKERS):
        return body
    line = default_recommend_hook_line()
    if not line:
        return body
    return f"{body.rstrip()}\n\n{line}"


def strip_recommend_hook(body: str) -> str:
    """去掉文末财经推荐引导（repush / 旧稿兜底）。"""
    if not body:
        return body
    lines = body.splitlines()
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if any(m in last for m in _RECOMMEND_HOOK_MARKERS) or "复盘的朋友" in last:
            lines.pop()
            continue
        break
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def polish_for_traffic(
    body: str,
    *,
    kind: str,
    engagement_kind: str | None = None,
) -> str:
    """成稿后处理：文末互动问句 + 星标关注 + 推荐♡引导（不含免责声明）。"""
    if not monetization_enabled():
        return body
    k = (kind or "").strip().lower()
    body = append_engagement_hook(body, kind=kind, engagement_kind=engagement_kind)
    body = append_follow_hook(body, kind=kind)
    if k in _NO_RECOMMEND_HOOK_KINDS:
        body = strip_recommend_hook(body)
        return strip_writing_reply_inducement(body)
    body = append_recommend_hook(body, kind=kind)
    return strip_writing_reply_inducement(body)


def split_disclaimer(body: str) -> tuple[str, str]:
    for mark in _DISCLAIMER_MARKS:
        if mark in body:
            core, _, tail = body.partition(mark)
            return core.rstrip(), mark + tail
    return body, ""


_TRAILING_DISCLAIMER_LINE_RE = re.compile(
    r"^(?:"
    r"本文为作者个人复盘笔记|"
    r"本文为作者个人市场信息整理|"
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
    if "不代表本号立场" in s and "公开报道" in s:
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
