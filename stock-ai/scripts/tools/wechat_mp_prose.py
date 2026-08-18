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
    """将裸节标题行规范为 `> 标题`；粘连「标题+正文」同行时强制拆行。"""
    text = demote_numbered_section_lines(text)
    title_set = set(titles)
    out: list[str] = []
    for line in text.splitlines():
        bare = line.strip().lstrip("> ").strip()
        if bare in title_set:
            out.append(mp_section_header(bare))
            continue
        split_done = False
        for title in sorted(title_set, key=len, reverse=True):
            m = re.match(
                rf"^(?:>\s*)?{re.escape(title)}(?=[^\n\s])(.*)$",
                line.strip(),
            )
            if m:
                body = (m.group(1) or "").strip()
                out.append(mp_section_header(title))
                if body:
                    out.append(body)
                split_done = True
                break
        if not split_done:
            out.append(line)
    return "\n".join(out)


MARKET_SECTION_TITLES: tuple[str, ...] = ("盘面速览", "外围与资金", "结构判断")
# 旧模板节名（成稿时洗掉，不再要求出现）
HOTSPOT_SECTION_TITLES: tuple[str, ...] = ()
HOTSPOT_BANNED_SECTION_TITLES: tuple[str, ...] = (
    "为啥盯这条",
    "明天盯什么",
    "为什么选这一题",
    "今天深写什么",
    "向后看要验证什么",
)
HOTSPOT_SECTION_LEGACY_ALIASES: dict[str, str] = {
    "为什么选这一题": "",
    "今天深写什么": "",
    "向后看要验证什么": "",
    "为啥盯这条": "",
    "明天盯什么": "",
}
# 成稿不再使用四段问卷标签；保留常量供旧稿清洗与测试引用
HOTSPOT_FIELD_LABELS: tuple[str, ...] = ()
HOTSPOT_RIGID_FIELD_LABELS: tuple[str, ...] = (
    "先说事实：",
    "先说事实:",
    "外面怎么传：",
    "外面怎么传:",
    "A股怎么动：",
    "A股怎么动:",
    "我们怎么看：",
    "我们怎么看:",
    "发生了什么：",
    "发生了什么:",
    "网上在说什么：",
    "网上在说什么:",
    "盘面怎么反应：",
    "盘面怎么反应:",
    "AI怎么看：",
    "AI怎么看:",
    "AI 怎么看：",
    "AI 怎么看:",
)
HOTSPOT_FIELD_LEGACY_ALIASES: dict[str, str] = {
    "发生了什么：": "",
    "发生了什么:": "",
    "网上在说什么：": "",
    "网上在说什么:": "",
    "盘面怎么反应：": "",
    "盘面怎么反应:": "",
    "AI怎么看：": "",
    "AI怎么看:": "",
    "AI 怎么看：": "",
    "AI 怎么看:": "",
    "先说事实：": "",
    "先说事实:": "",
    "外面怎么传：": "",
    "外面怎么传:": "",
    "A股怎么动：": "",
    "A股怎么动:": "",
    "我们怎么看：": "",
    "我们怎么看:": "",
}


def humanize_hotspot_field_labels(text: str) -> str:
    """去掉「先说事实/外面怎么传…」问卷标签，收成自然段。"""
    out = text or ""
    for label in HOTSPOT_RIGID_FIELD_LABELS:
        out = out.replace(label, "")
    for old, new in HOTSPOT_FIELD_LEGACY_ALIASES.items():
        out = out.replace(old, new)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return humanize_hotspot_boilerplate(out.strip())


HOTSPOT_BOILERPLATE_PHRASES: tuple[str, ...] = (
    "我们认为",
    "值得关注的是",
    "向后看",
    "综上所述",
    "值得注意的是",
    "与此同时",
    "为啥盯这条",
    "明天盯什么",
    "今天深写",
    "深写这条",
    "因为它牵动",
    "叙事溢价",
    "情绪溢价",
    "热搜给故事",
    "写在备忘录",
    "核对不过",
    "三条线",
    "分层看",
    "公开报道里",
    "值得先记住",
    "盘面一句",
    "热搜在聊",
    "双榜讨论",
    "不难发现",
    "需要指出的是",
    "简而言之",
    "总而言之",
    "值得一提的是",
    "硬验证",
    "复述评论",
    "网上怎么说",
    "露馅",
)

_CN_YEAR_DIGITS = "〇零○一二三四五六七八九"
_CN_YEAR_RE = re.compile(rf"([{_CN_YEAR_DIGITS}]{{4}})年")
_CN_DURATION_RE = re.compile(
    rf"(?<![0-9])((?:近|约|逾|超)?)([{_CN_YEAR_DIGITS}十]{{1,4}})年"
)
_CN_DIGIT_MAP = str.maketrans(
    {
        "〇": "0",
        "零": "0",
        "○": "0",
        "一": "1",
        "二": "2",
        "三": "3",
        "四": "4",
        "五": "5",
        "六": "6",
        "七": "7",
        "八": "8",
        "九": "9",
    }
)


def _cn_numeral_to_int(raw: str) -> int | None:
    s = (raw or "").strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if not all(c in _CN_YEAR_DIGITS or c == "十" for c in s):
        return None
    if s == "十":
        return 10
    if s.startswith("十"):
        tail = s[1:].translate(_CN_DIGIT_MAP) or "0"
        return 10 + int(tail)
    if "十" in s:
        head, _, tail = s.partition("十")
        hi = int(head.translate(_CN_DIGIT_MAP) or "0")
        lo = int((tail or "0").translate(_CN_DIGIT_MAP) or "0")
        return hi * 10 + lo
    digits = s.translate(_CN_DIGIT_MAP)
    return int(digits) if digits.isdigit() else None


def normalize_arabic_year_numerals(text: str) -> str:
    """年份/刑期等用阿拉伯数字：二〇一八年→2018年，六年→6年。"""

    def _year_repl(m: re.Match[str]) -> str:
        n = _cn_numeral_to_int(m.group(1))
        if n is None or n < 1900 or n > 2099:
            return m.group(0)
        return f"{n}年"

    def _dur_repl(m: re.Match[str]) -> str:
        prefix, cn = m.group(1), m.group(2)
        n = _cn_numeral_to_int(cn)
        if n is None or n < 1 or n > 99:
            return m.group(0)
        return f"{prefix}{n}年"

    out = _CN_YEAR_RE.sub(_year_repl, text or "")
    return _CN_DURATION_RE.sub(_dur_repl, out)


HOTSPOT_META_COMMENTARY_RE: tuple[re.Pattern[str], ...] = (
    re.compile(r"公开报道里[^。；\n]{0,28}[：:，,]\s*"),
    re.compile(r"值得先记住[：:，,]?\s*"),
    re.compile(r"盘面一句[：:，,]\s*"),
    re.compile(r"热搜在聊[「\"][^」\"\n]{2,32}[」\"][，,。]?\s*"),
    re.compile(r"双榜讨论[^。；\n]{0,24}[：:，,]\s*"),
    re.compile(r"据[^，。；\n]{1,10}(消息|报道)[，,]\s*"),
    re.compile(r"不难发现[，,]\s*"),
    re.compile(r"需要指出的是[，,]\s*"),
    re.compile(r"简而言之[，,]\s*"),
    re.compile(r"总而言之[，,]\s*"),
    re.compile(r"值得一提的是[，,]\s*"),
    re.compile(r"来源公开信息[^。]*"),
    re.compile(r"值得注意的是[，,]?\s*"),
    re.compile(r"这是对[「\"']?网上怎么说[」\"']?的硬验证[^。]*"),
    re.compile(r"而不是复述评论[。]?"),
    re.compile(r"舆情里喊得最响[^。]*露馅[^。]*"),
)


def strip_hotspot_meta_commentary(text: str) -> str:
    """去掉「公开报道里有一条…」「值得先记住」等元叙述。"""
    out = text or ""
    for pat in HOTSPOT_META_COMMENTARY_RE:
        out = pat.sub("", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def strip_hotspot_subheadings(text: str) -> str:
    """热点深评：去掉全部 `> ` / `#` 小标题，只保留正文段落。"""
    lines: list[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.startswith("> "):
            bare = stripped[2:].strip()
            # 粘连「> 标题正文」：去掉短标题前缀，保留正文
            if len(bare) > 24 and not re.search(r"[。！？；;]$", bare[:18]):
                for n in range(min(18, len(bare)), 3, -1):
                    head = bare[:n]
                    if re.search(r"[，,、：:]$", head) or len(head) <= 6:
                        continue
                    tail = bare[n:].lstrip("，,、：: ")
                    if len(tail) >= 12:
                        lines.append(tail)
                        break
                else:
                    continue
            else:
                continue
            continue
        if re.match(r"^#+\s*\S", stripped):
            continue
        lines.append(line)
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def humanize_hotspot_sections(text: str) -> str:
    """去掉旧模板节名行，最终去掉全部小标题。"""
    out = text or ""
    banned = set(HOTSPOT_BANNED_SECTION_TITLES) | set(HOTSPOT_SECTION_LEGACY_ALIASES)
    for title in banned:
        if not title:
            continue
        out = re.sub(rf"^>\s*{re.escape(title)}\s*$", "", out, flags=re.MULTILINE)
        out = re.sub(rf"^#{{1,6}}\s*{re.escape(title)}\s*$", "", out, flags=re.MULTILINE)
        out = re.sub(rf"^#{{1,6}}{re.escape(title)}\s*$", "", out, flags=re.MULTILINE)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return strip_hotspot_subheadings(out.strip())


def humanize_hotspot_boilerplate(text: str) -> str:
    """去掉研报口播套话，收成研究员自然叙述。"""
    out = text or ""
    out = re.sub(r"我们认为[，,]?\s*", "", out)
    out = re.sub(r"值得关注的是[，,]?\s*", "", out)
    out = re.sub(r"向后看[，,]?\s*", "", out)
    out = re.sub(r"值得注意的是[，,]?\s*", "", out)
    out = re.sub(r"今天深写[^。；\n]{0,40}[，,]?\s*", "", out)
    out = re.sub(r"深写[「\"']?[^」\"'\n]{2,24}[」\"']?[，,]?\s*", "", out)
    out = re.sub(r"因为它牵动[^。；\n]{0,24}[，,]?\s*", "", out)
    out = re.sub(r"叙事溢价", "", out)
    out = re.sub(r"情绪溢价", "", out)
    out = strip_hotspot_meta_commentary(out)
    out = normalize_arabic_year_numerals(out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return humanize_hotspot_sections(out.strip())


def normalize_hotspot_legacy_labels(text: str) -> str:
    """hotspot：洗掉旧节名与问卷标签。"""
    out = text or ""
    for old, new in HOTSPOT_SECTION_LEGACY_ALIASES.items():
        if new:
            out = out.replace(old, new)
        else:
            out = re.sub(rf"^>\s*{re.escape(old)}\s*$", "", out, flags=re.MULTILINE)
            out = out.replace(old, "")
    return humanize_hotspot_field_labels(out)
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
