#!/usr/bin/env python3
"""公众号正文：去 emoji / AI 模板痕迹，改成可读的投资日记口吻。"""

from __future__ import annotations

import re

from scripts.tools.wechat_format import normalize_wechat_spacing, strip_markdown_for_wechat

# 常见 emoji 与装饰符号（战报 / SOP 用）
_EMOJI_CHARS_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "\uFE0F"
    "]+",
    flags=re.UNICODE,
)

_SECTION_PREFIX = {
    "📊": "一、盘面与外围",
    "📰": "二、国内要闻",
    "📋": "三、持仓与计划",
    "👀": "三、观察要点",
    "⚠️": "四、风险备忘",
    "🔬": "",
    "🤖": "",
    "📈": "",
    "📡": "",
    "📄": "",
}

_BRACKET_STOCK_RE = re.compile(
    r"【\s*(\d{6})\s*([^·】\n]+?)\s*·\s*分\s*([\d.]+)\s*·\s*([^】\n]+)\s*】"
)

_NUMBERED_SECTION_RE = re.compile(r"^(\d+)\)\s*(.+)$")


def _strip_emojis(text: str) -> str:
    return _EMOJI_CHARS_RE.sub("", text)


def _rewrite_section_line(line: str) -> str:
    s = line.strip()
    for emoji, title in _SECTION_PREFIX.items():
        if s.startswith(emoji):
            rest = _strip_emojis(s[len(emoji) :]).strip()
            if not title:
                return rest
            if rest in ("大盘与外围", "国内要闻", "持仓关注点"):
                return title
            if rest.startswith(title.lstrip("一二三四五六七八九十、")):
                return rest
            return f"{title}：{rest}" if rest else title
    return _strip_emojis(s)


def _rewrite_stock_brackets(text: str) -> str:
    def _repl(m: re.Match[str]) -> str:
        name = m.group(2).strip()
        score = float(m.group(3))
        decision = m.group(4).strip()
        return f"{name}（{score:.0f}分）：{decision}"

    return _BRACKET_STOCK_RE.sub(_repl, text)


def _rewrite_numbered_sections(line: str) -> str:
    m = _NUMBERED_SECTION_RE.match(line.strip())
    if not m:
        return line
    num, rest = m.group(1), _rewrite_section_line(m.group(2))
    rest = rest.strip()
    if not rest or "Top" in rest and "SOP" in rest:
        return "（一）个股结论"
    if "持仓" in rest:
        return ""
    if "风险" in rest:
        return "（二）风险与纪律"
    cn = ("一", "二", "三", "四", "五")
    idx = int(num) - 1
    prefix = cn[idx] if 0 <= idx < len(cn) else num
    return f"（{prefix}）{rest}" if rest else ""


def _drop_boilerplate_lines(line: str) -> str | None:
    s = line.strip()
    if not s:
        return ""
    drop_exact = {
        "【AI 综合解读】",
        "【市场宏观评论】",
        "【龙头观察池】",
    }
    if s in drop_exact:
        return None
    if s.startswith("---"):
        return None
    if "策略信号仅供参考" in s:
        return None
    if s.startswith("🔬") or s.startswith("🤖"):
        return _rewrite_section_line(s)
    if "东财 SOP" in s or "SOP Top" in s:
        return None
    if s.startswith("理由：") or s.startswith("条件："):
        return s
    return s


def _rewrite_inline_phrases(line: str) -> str:
    s = line
    replacements = (
        (" 📌已持仓", ""),
        ("📌已持仓", ""),
        (" ✅ SOP值得关注（", "：SOP倾向关注（"),
        (" ⏸ SOP暂不监控（", "：暂不纳入监控（"),
        ("SOP值得关注（", "SOP倾向关注（"),
        ("SOP暂不监控（", "暂不纳入监控（"),
        (" → 次日5分钟监控", "，已列入次日盘中观察"),
        (" · SOP", "；SOP"),
    )
    for old, new in replacements:
        s = s.replace(old, new)
    s = _strip_emojis(s)
    s = re.sub(r"^[\-·]\s*", "", s)
    s = re.sub(r"^(\d+)\.\s*\[([^\]]+)\]\s*", r"\1. \2｜", s)
    return s.strip()


def humanize_mp_text(text: str) -> str:
    """战报 / SOP 原文 → 公众号正文（无 emoji、少 AI 腔）。"""
    text = strip_markdown_for_wechat(text)
    text = _rewrite_stock_brackets(text)

    out: list[str] = []
    for raw in text.splitlines():
        dropped = _drop_boilerplate_lines(raw)
        if dropped is None:
            continue
        if dropped == "":
            if out and out[-1] != "":
                out.append("")
            continue

        line = _rewrite_section_line(dropped.strip())
        if _NUMBERED_SECTION_RE.match(line):
            line = _rewrite_numbered_sections(line)
            if not line:
                continue
        line = _rewrite_inline_phrases(line)
        if not line:
            continue

        if re.match(r"^[\-·]", dropped.strip()) or re.match(r"^\d+\.\s*\[", dropped.strip()):
            line = _rewrite_inline_phrases(dropped.strip().lstrip("·- "))

        if line.startswith("──") and line.endswith("──"):
            inner = line.strip("─ ").strip()
            line = inner if inner else ""

        out.append(line.rstrip())

    merged = normalize_wechat_spacing("\n".join(out))
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    from scripts.tools.wechat_mp_public import sanitize_public_mp_text
    from scripts.tools.wechat_mp_rich_html import strip_journal_title_lines

    merged = strip_journal_title_lines(merged.strip())
    merged = demote_numbered_section_lines(merged)
    return sanitize_public_mp_text(merged)


def mp_section_header(title: str) -> str:
    """公众号分节标题（`> 标题` → 富文本居中样式）。"""
    bare = title.strip().lstrip("> ").strip()
    return f"> {bare}" if bare else title


_CN_NUMBERED_SECTION_RE = re.compile(r"^[一二三四五六七八九十]+、(.+)$")


def demote_numbered_section_lines(text: str) -> str:
    """「一、标题」→ `> 标题`（公众号小标题禁止一二三序号）。"""
    out: list[str] = []
    for line in text.splitlines():
        bare = line.strip()
        m = _CN_NUMBERED_SECTION_RE.match(bare)
        if m:
            out.append(mp_section_header(m.group(1).strip()))
        else:
            out.append(line)
    return "\n".join(out)


def ensure_blockquote_sections(text: str, titles: tuple[str, ...]) -> str:
    """将裸节标题行规范为 `> 标题`，供 text_to_html 渲染居中小标题。"""
    text = demote_numbered_section_lines(text)
    title_set = set(titles)
    out: list[str] = []
    for line in text.splitlines():
        bare = line.strip().lstrip("> ").strip()
        if bare in title_set:
            out.append(mp_section_header(bare))
        else:
            out.append(line)
    return "\n".join(out)


MARKET_SECTION_TITLES: tuple[str, ...] = ("盘面速览", "外围与资金", "结构判断")
SECTOR_SECTION_TITLES: tuple[str, ...] = (
    "为什么现在看",
    "产业链怎么拆",
    "盘面里谁在用价格说话",
    "和指数情绪怎么联动",
    "向后看要验证什么",
)

# 「结构判断」内段首小结：独立成段，移动端更易跳读
_STRUCTURE_VIEW_BREAK_PHRASES: tuple[str, ...] = (
    "我们认为",
    "值得关注的是",
    "向后看",
    "第一条逻辑链",
    "第二条逻辑链",
    "第三条逻辑链",
    "第一条",
    "第二条",
    "第三条",
    "第一，",
    "第二，",
    "第三，",
    "具体看三条逻辑链：",
)


def _split_text_at_phrases(text: str, phrases: tuple[str, ...]) -> str:
    """在段中指定短语前插入空行（短语已在段首则不动）。"""
    out = text.strip()
    if not out:
        return out
    for phrase in sorted(phrases, key=len, reverse=True):
        # 句号/分号后的小结另起段
        out = re.sub(
            rf"([。；！？])\s*{re.escape(phrase)}",
            rf"\1\n\n{phrase}",
            out,
        )
        # 无标点但句中突然出现的小结
        out = re.sub(
            rf"(?<=[^\n。；！？])\s*{re.escape(phrase)}",
            rf"\n\n{phrase}",
            out,
        )
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def reflow_market_structure_section(text: str) -> str:
    """「> 结构判断」块内：我们认为 / 值得关注的是 / 向后看 等分段。"""
    lines = text.splitlines()
    out: list[str] = []
    in_view = False

    for line in lines:
        stripped = line.strip()
        bare = stripped.lstrip("> ").strip()

        if bare == "结构判断":
            in_view = True
            out.append(line)
            continue

        if in_view and stripped.startswith("> ") and bare != "结构判断":
            in_view = False

        if in_view and stripped and not stripped.startswith("> ") and not stripped.startswith("[[fig:"):
            for sub in _split_text_at_phrases(stripped, _STRUCTURE_VIEW_BREAK_PHRASES).splitlines():
                out.append(sub)
            continue

        out.append(line)

    return "\n".join(out)


NEWS_SECTION_TITLES: tuple[str, ...] = ("要闻精选",)
TOP5_SECTION_TITLES: tuple[str, ...] = ("筛选名单", "个股拆解", "组合特征", "待验证事项")
DRAGON_SECTION_TITLES: tuple[str, ...] = (
    "情绪与盘面",
    "龙头拆解",
    "主线与梯队",
    "明日计划与纪律",
)


def format_top5_list_prose(
    picks: list,
    *,
    trade_date,
    watch_date,
    sop_reviews: list[dict] | None = None,
    for_public: bool = True,
) -> str:
    """选股列表（公众号专用，无 emoji）。for_public=True 时不暴露作者持仓。"""
    from scripts.tools.selection_watchlist import load_sop_reviews

    sop_reviews = sop_reviews if sop_reviews is not None else load_sop_reviews()
    review_by_code = {str(r["code"]).zfill(6): r for r in sop_reviews}
    use_sop = bool(sop_reviews)

    td = f"{trade_date.month}月{trade_date.day}日"
    wd = f"{watch_date.month}月{watch_date.day}日"
    lines = [
        (
            f"{td}收盘后，多策略候选合并筛选 {len(picks)} 只标的"
            f"（综合/五因子/MA5 等）；结构跟踪日（{wd}）核对量价与板块。"
        ),
        "",
    ]
    for i, p in enumerate(picks, 1):
        lines.append(f"{i}. {p.name}（{p.code}）")
        lines.append(
            f"   策略标签 {p.label}；收盘 {p.close:.2f} 元（{p.change_pct:+.2f}%）"
        )
        if use_sop:
            sop = review_by_code.get(p.code, {})
            theme = str(sop.get("theme") or sop.get("sector") or "").strip()
            if theme:
                lines.append(f"   库内审查主题：{theme}")

    lines.extend(
        [
            "",
            "说明：以上为收盘选股结果的结构清单，供复盘对照；"
            + (
                "与任何个人持仓无关，不含买卖建议。"
                if for_public
                else "不含买卖建议。"
            ),
        ]
    )
    return "\n".join(lines)
