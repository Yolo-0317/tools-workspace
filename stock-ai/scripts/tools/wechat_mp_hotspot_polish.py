#!/usr/bin/env python3
"""热点深评稿：段间钩子、字段换行、向后看末句。"""

from __future__ import annotations

import re

from scripts.tools.wechat_mp_prose import (
    HOTSPOT_BANNED_SECTION_TITLES,
    HOTSPOT_BOILERPLATE_PHRASES,
    HOTSPOT_SECTION_LEGACY_ALIASES,
    humanize_hotspot_boilerplate,
    humanize_hotspot_field_labels,
    normalize_hotspot_legacy_labels,
    strip_hotspot_meta_commentary,
    strip_hotspot_subheadings,
)
from scripts.tools.wechat_mp_sector_polish import sanitize_sector_reader_voice

_SECTION_BANNED = frozenset(HOTSPOT_BANNED_SECTION_TITLES) | frozenset(HOTSPOT_SECTION_LEGACY_ALIASES)

# 主题节改为自然段，不再使用四段问卷标签

# 「为什么选这一题」禁止暴露编审/选题过程（2026-07-12 用户定稿）
_HOTSPOT_SELECTION_LEAK_BANNED: tuple[str, ...] = (
    "候选五条",
    "五条候选",
    "在候选",
    "候选快讯",
    "其它候选",
    "其他候选",
    "没选其它",
    "为何没选",
    "故舍弃",
    "舍弃其余",
    "舍弃其他",
    "同批素材",
    "同批 news",
    "十条快讯清单",
    "十条快讯",
    "同批快讯",
    "不复述同批",
)
_WHY_PICK_PREFIX_RE = re.compile(r"^>?\s*为什么选这一题")

# 开篇/导语禁止：结构说明、阅读路径、编审预告（2026-07-12 用户定稿）
_HOTSPOT_READER_META_OPENING_RE = re.compile(
    r"(?:本篇|本文)(?:不)?复盘|快讯清单|单一变量|递进阅读|阅读路径|"
    r"下文先|选题逻辑|交代选题|单线展开|向后观察点|"
    r"只深写\s*1\s*个主题|只围绕.{0,48}这一|沿事件[—\-–].{0,40}展开"
)

_HOTSPOT_READER_META_PHRASES: tuple[str, ...] = (
    "本篇不复盘快讯清单",
    "本篇不复盘",
    "不复盘快讯清单",
    "递进阅读",
    "阅读路径",
    "下文先交代选题逻辑",
    "下文先",
    "交代选题逻辑",
    "再拆解传导与向后观察点",
    "沿事件—油价—板块映射—可验证指标递进阅读",
    "沿事件-油价-板块映射-可验证指标递进阅读",
    "只深写1个主题",
    "只深写 1 个主题",
    "单一变量",
    "单线展开",
)

# 模型把 system/user 提示词或自检过程写进正文（英文连写 / 只输出正文…）
# 命中后截断该行及之后（常会再贴一整篇「终稿」重写）
_LLM_PROCESS_LEAK_LINE_RE = re.compile(
    r"(?is)"
    r"(?:^\s*(?:\*+|-+\s*\*?)\s*)?(?:"
    r"Wait[-–—\s]*the\s*user|"
    r"Wait[-–—]?theuser|"
    r"I\s*need\s*to\s*remove|"
    r"Ineedto|"
    r"the\s*user\s*said|"
    r"usersaid|"
    r"data\s*acquisition\s*gaps?|"
    r"dataacquisition|"
    r"only\s*output\s*(?:the\s*)?markdown|"
    r"只输出正文\s*Markdown|"
    r"只输出正文|"
    r"不要解释|"
    r"Letme(?:also|output|refine)|"
    r"notinforbidden|"
    r"needatleastone|"
    r"Alsocheckforbidden|"
    r"forbiddenphrases|"
    r"说明[：:].{0,12}(?:数据源|指数层面)"
    r")"
)

_LLM_PROCESS_LEAK_INLINE_RE = re.compile(
    r"(?is)"
    r"[*［\[]?\s*(?:"
    r"Wait[-–—\s]*the\s*user.{0,240}?|"
    r"Wait[-–—]?theuser.{0,240}?|"
    r"I\s*need\s*to\s*remove.{0,200}?|"
    r"Ineedto.{0,200}?|"
    r"只输出正文\s*Markdown[，,：:].{0,80}?"
    r")(?:\*+|］|\])?"
)


def strip_llm_process_leak(text: str) -> str:
    """去掉模型把提示词/自检过程写进正文的残片；自检起整段截断。"""
    out = (text or "").strip()
    if not out:
        return out
    kept: list[str] = []
    for line in out.splitlines():
        if _LLM_PROCESS_LEAK_LINE_RE.search(line):
            break
        cleaned = _LLM_PROCESS_LEAK_INLINE_RE.sub("", line).strip()
        if cleaned in {"*", "**", "＊"}:
            continue
        if not line.strip():
            kept.append("")
        else:
            kept.append(cleaned)
    text2 = "\n".join(kept)
    text2 = _LLM_PROCESS_LEAK_INLINE_RE.sub("", text2)
    text2 = re.sub(r"\n{3,}", "\n\n", text2)
    return text2.strip()


def strip_llm_process_leak_html(content: str) -> str:
    """草稿 HTML：删掉含提示词自检的 <p>，并从首个自检段起截断后续重写。"""
    html = content or ""
    if not html:
        return html
    cps_m = re.search(
        r"<section\b[^>]*nodeleaf[^>]*>.*?</section>",
        html,
        flags=re.S | re.I,
    )
    cps_html = cps_m.group(0) if cps_m else ""

    cut_at: int | None = None
    for m in re.finditer(r"<p\b[^>]*>.*?</p>", html, flags=re.S | re.I):
        plain = re.sub(r"<[^>]+>", "", m.group(0))
        plain = (
            plain.replace("&quot;", '"')
            .replace("&#39;", "'")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
        )
        if _LLM_PROCESS_LEAK_LINE_RE.search(plain):
            cut_at = m.start()
            break
    if cut_at is None:
        return html

    head = html[:cut_at].rstrip()
    # 从被截掉的尾部抢救推荐引导与文末免责（若首稿未带）
    tail = html[cut_at:]
    footer_bits: list[str] = []
    for m in re.finditer(r"<p\b[^>]*>.*?</p>", tail, flags=re.S | re.I):
        plain = re.sub(r"<[^>]+>", "", m.group(0))
        plain = plain.replace("&quot;", '"').replace("&amp;", "&")
        if _LLM_PROCESS_LEAK_LINE_RE.search(plain):
            continue
        if "欢迎点文章下方" in plain or (
            "本文为作者个人" in plain and "非证券投资咨询" in plain
        ) or (
            "整理公开报道与网络讨论" in plain and "不代表本号立场" in plain
        ):
            footer_bits.append(m.group(0))
        elif plain.startswith("#") and len(plain) < 40 and "特朗普" in plain:
            # 截断残 tag，跳过
            continue

    out = head
    if cps_html and "mp-common-cpsad" not in out:
        # 插在文末风险提示段之前
        risk = re.search(
            r"<p\b[^>]*>[^<]*(?:非推荐名单|决策须独立判断)[^<]*</p>\s*$",
            out,
            flags=re.S | re.I,
        )
        if risk:
            out = out[: risk.start()] + cps_html + risk.group(0)
        else:
            out = out + cps_html
    for bit in footer_bits:
        if bit not in out:
            out += bit
    return out


def _is_hotspot_meta_opening(paragraph: str) -> bool:
    p = re.sub(r"\s+", "", paragraph or "")
    if len(p) < 24:
        return False
    if _HOTSPOT_READER_META_OPENING_RE.search(p):
        return True
    signals = (
        "本篇",
        "递进阅读",
        "阅读路径",
        "下文先",
        "选题逻辑",
        "单一变量",
        "快讯清单",
        "单线展开",
        "只深写",
        "只围绕",
    )
    return sum(1 for s in signals if s in p) >= 2


def sanitize_hotspot_reader_meta(text: str) -> str:
    """去掉开篇/导语中的结构说明、阅读路径、编审预告、提示词残片。"""
    text = strip_llm_process_leak((text or "").strip())
    text = _normalize_hotspot_legacy_sections(text)
    if not text:
        return text

    for phrase in _HOTSPOT_READER_META_PHRASES:
        text = text.replace(phrase, "")

    parts = re.split(r"\n\n+", text)
    kept: list[str] = []
    skipped_opening = False
    for part in parts:
        stripped = part.strip()
        if not stripped:
            continue
        if _LLM_PROCESS_LEAK_LINE_RE.search(stripped) or _LLM_PROCESS_LEAK_INLINE_RE.search(
            stripped
        ):
            continue
        if (
            not skipped_opening
            and not stripped.startswith(">")
            and not any(t in stripped for t in _SECTION_BANNED)
            and _is_hotspot_meta_opening(stripped)
        ):
            skipped_opening = True
            continue
        kept.append(stripped)

    out = "\n\n".join(kept).strip()
    out = re.sub(r"[；;，,]{2,}", "，", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def _sanitize_why_pick_paragraph(paragraph: str) -> str:
    """单段「为什么选这一题」正文：去掉候选/舍弃/对比其它标题等编审话术。"""
    out = paragraph or ""
    out = re.sub(r"在候选.{0,8}中[，,]?", "", out)
    out = re.sub(r"相较[「\"'][^」\"']{2,24}[」\"'][^。；！？\n]*?[；;，,]", "", out)
    out = re.sub(r"故选[^。；！？\n]{0,12}[；;，,]?", "", out)
    for phrase in _HOTSPOT_SELECTION_LEAK_BANNED:
        out = out.replace(phrase, "")
    out = re.sub(r"^在中[，,]?", "", out)
    out = re.sub(r"[；;，,]{2,}", "，", out)
    out = re.sub(r"\s+", "", out)
    out = re.sub(r"^[，。；、]+|[，。；、]+$", "", out)
    return out.strip()


def _drop_pure_selection_meta(text: str) -> str:
    kept: list[str] = []
    for paragraph in re.split(r"\n\n+", text or ""):
        stripped = paragraph.strip()
        if not stripped:
            continue
        if _WHY_PICK_PREFIX_RE.search(stripped) and any(
            marker in stripped for marker in _HOTSPOT_SELECTION_LEAK_BANNED
        ):
            continue
        kept.append(stripped)
    return "\n\n".join(kept).strip()


def sanitize_hotspot_selection_leak(text: str) -> str:
    """去掉候选/舍弃/对比其它标题等编审话术（全文）。"""
    text = strip_hotspot_subheadings(_normalize_hotspot_legacy_sections(text))
    parts = re.split(r"\n\n+", text or "")
    out: list[str] = []
    for part in parts:
        stripped = part.strip()
        if not stripped:
            continue
        if any(p in stripped for p in _HOTSPOT_SELECTION_LEAK_BANNED):
            cleaned = _sanitize_why_pick_paragraph(stripped)
            if cleaned:
                out.append(cleaned)
            continue
        out.append(stripped)
    return "\n\n".join(out).strip()


def _normalize_hotspot_legacy_sections(text: str) -> str:
    return normalize_hotspot_legacy_labels(text)


def strip_markdown_bold(text: str) -> str:
    """去掉 **加粗** 标记；公众号不渲染 Markdown，保留句内文字。"""
    out = (text or "").strip()
    if not out or "**" not in out:
        return out
    # 多行 **...** 整段
    out = re.sub(r"^\*\*(.+?)\*\*\s*$", r"\1", out, flags=re.MULTILINE)
    # 行内 **...**
    out = re.sub(r"\*\*(.+?)\*\*", r"\1", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def reflow_hotspot_body(text: str) -> str:
    """去掉小标题、粘连 ## 标题，收成纯段落。"""
    from scripts.tools.wechat_mp_prose import strip_hotspot_subheadings

    source = _drop_pure_selection_meta((text or "").strip())
    out = strip_hotspot_subheadings(
        humanize_hotspot_boilerplate(
            humanize_hotspot_field_labels(_normalize_hotspot_legacy_sections(source))
        )
    )
    if not out:
        return out

    out = re.sub(
        r"^#([^#\n]{6,72}?)(?=(?:7|8|9|\d)\d*月\d+日)",
        r"\1\n\n",
        out,
        flags=re.MULTILINE,
    )
    out = re.sub(r"\n{3,}", "\n\n", out)
    return strip_markdown_bold(out.strip())


_INDEX_POINT_RE = re.compile(
    r"(沪指|上证指数|深证成指|创业板指|科创50|沪深300|中证1000)"
    r"[^\d]{0,8}(\d{3,5}(?:\.\d+)?)"
)


def dedupe_hotspot_index_mentions(text: str) -> str:
    """去掉后段重复复述的指数点位（全文只保留首次出现的各指数）。"""
    paragraphs = [p.strip() for p in re.split(r"\n\n+", (text or "").strip()) if p.strip()]
    if not paragraphs:
        return text or ""
    seen: set[str] = set()
    out: list[str] = []
    for para in paragraphs:
        keys = [f"{name}:{pt}" for name, pt in _INDEX_POINT_RE.findall(para)]
        if keys and all(k in seen for k in keys):
            continue
        for k in keys:
            seen.add(k)
        if out and keys:
            names = {name for name, _ in _INDEX_POINT_RE.findall(para)}
            if names and names <= {n for n, _ in _INDEX_POINT_RE.findall(out[0])}:
                if not re.search(r"涨跌幅|涨停|跌停|换手|亿元|万股|[（(]\d{6}", para):
                    continue
        out.append(para)
    return "\n\n".join(out)


HOTSPOT_PARA_MAX_CHARS = 130


def reflow_hotspot_layout(text: str, *, max_chars: int = HOTSPOT_PARA_MAX_CHARS) -> str:
    """移动端排版：长段按句号拆成 2～4 句的短段，段间空一行。"""
    paragraphs = [p.strip() for p in re.split(r"\n\n+", (text or "").strip()) if p.strip()]
    if not paragraphs:
        return text or ""
    out: list[str] = []
    for para in paragraphs:
        if len(para) <= max_chars:
            out.append(para)
            continue
        sentences = [s for s in re.split(r"(?<=[。！？])", para) if s.strip()]
        if len(sentences) <= 1:
            out.append(para)
            continue
        buf = ""
        for sent in sentences:
            if len(buf) + len(sent) <= max_chars or not buf:
                buf += sent
                if len(buf) >= max_chars:
                    out.append(buf.strip())
                    buf = ""
            else:
                out.append(buf.strip())
                buf = sent
        if buf.strip():
            out.append(buf.strip())
    merged: list[str] = []
    for para in out:
        if merged and len(para) < 36 and len(merged[-1]) < max_chars:
            merged[-1] = merged[-1].rstrip() + para
        else:
            merged.append(para)
    return "\n\n".join(merged)


def delist_hotspot_body(text: str) -> str:
    """把编号清单收成段落叙述，避免像快讯列表。"""
    paragraphs = [p.strip() for p in re.split(r"\n\n+", (text or "").strip()) if p.strip()]
    out: list[str] = []
    for para in paragraphs:
        lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
        numbered = [ln for ln in lines if re.match(r"^[1-9][\.、．]\s*", ln)]
        if len(numbered) >= 2:
            items = [re.sub(r"^[1-9][\.、．]\s*", "", ln).strip() for ln in numbered]
            out.append("；".join(items).rstrip("；") + "。")
        elif len(lines) > 1 and all(len(ln) < 48 for ln in lines):
            out.append("".join(lines))
        else:
            out.append(para)
    return "\n\n".join(out)


def finalize_hotspot_body(
    body: str,
    *,
    trade_label: str,
    primary_theme: str,
) -> str:
    from scripts.tools.wechat_mp_public import sanitize_reader_data_gap

    text = sanitize_sector_reader_voice(body)
    text = sanitize_hotspot_reader_meta(text)
    text = sanitize_hotspot_selection_leak(text)
    text = sanitize_reader_data_gap(text, kind="hotspot")
    text = humanize_hotspot_field_labels(text)
    text = humanize_hotspot_boilerplate(text)
    text = strip_hotspot_meta_commentary(text)
    text = delist_hotspot_body(text)
    text = strip_hotspot_subheadings(text)
    text = reflow_hotspot_body(text)
    text = dedupe_hotspot_index_mentions(text)
    text = reflow_hotspot_layout(text)
    # hotspot 纯段落快评：不再追加「硬验证/露馅」式末句（与参考仿写口吻冲突）
    return text


def _section_paragraph(body: str, section_title: str) -> str:
    lines = body.splitlines()
    capture: list[str] = []
    in_sec = False
    for line in lines:
        bare = line.strip().lstrip("> ").strip()
        if bare == section_title:
            in_sec = True
            continue
        if in_sec and line.strip().startswith("> ") and bare != section_title:
            break
        if in_sec and line.strip():
            capture.append(line.strip())
    return "\n".join(capture)
