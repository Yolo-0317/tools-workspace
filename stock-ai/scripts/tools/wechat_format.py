#!/usr/bin/env python3
"""微信战报 / AI 解读排版（空行分段、去 Markdown、提取干净摘要）。"""

from __future__ import annotations

import re

# 选股日志行前缀（不应出现在战报 AI 摘要中）
_LOG_LINE_PREFIXES = (
    "🔍 ",
    "🤖 并发",
    "  ✅ ",
    "  ❌ ",
    "📄 ",
    "📋 SOP",
    "👀 ",
    "🚀 ",
    "✓ ",
    "⚠️ 未能",
    "==================================================",
    "📡 ",
    "        代码",
)

_SECTION_HEADER_RE = re.compile(
    r"^(\d+\)|【AI 综合解读】|📊|📰|📋|👀|⚠️|🔬|🤖)"
)


def strip_markdown_for_wechat(text: str) -> str:
    """去掉微信里常显多余的 Markdown 标记。"""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    return text


_CODE_FENCE_RE = re.compile(r"```(\w*)\n([\s\S]*?)```", re.MULTILINE)


def split_body_code_fences(text: str) -> list[tuple[str, str, str]]:
    """
    按 ``` 围栏切段。返回 (kind, lang, chunk)：
    kind=prose|code；code 时 lang 可为空。
    """
    parts: list[tuple[str, str, str]] = []
    last = 0
    for m in _CODE_FENCE_RE.finditer(text):
        if m.start() > last:
            parts.append(("prose", "", text[last : m.start()]))
        lang = (m.group(1) or "").strip()
        code = (m.group(2) or "").rstrip("\n")
        parts.append(("code", lang, code))
        last = m.end()
    if last < len(text):
        parts.append(("prose", "", text[last:]))
    return parts or [("prose", "", text)]


def prepare_static_mp_body(text: str) -> str:
    """技术静态稿：保留 ``` 代码块，仅对散文部分去 Markdown。"""
    chunks: list[str] = []
    for kind, lang, chunk in split_body_code_fences(text):
        if kind == "code":
            header = f"```{lang}\n" if lang else "```\n"
            chunks.append(f"{header}{chunk}\n```")
        else:
            chunks.append(strip_markdown_for_wechat(chunk))
    return normalize_wechat_spacing("\n\n".join(chunks))


def normalize_wechat_spacing(text: str) -> str:
    """统一空行：大段之间留一行，去掉首尾空白与连续三行以上空行。"""
    lines = [ln.rstrip() for ln in text.strip().splitlines()]
    out: list[str] = []
    blank_run = 0
    for i, line in enumerate(lines):
        if not line.strip():
            blank_run += 1
            if blank_run <= 1 and out:
                out.append("")
            continue
        blank_run = 0
        # 编号小节 / emoji 小标题前加空行（首行除外）
        if out and _SECTION_HEADER_RE.match(line.strip()):
            if out[-1] != "":
                out.append("")
        out.append(line)
    # 列表项之间：若上一行也是列表且当前非空，保持紧凑；长列表项后可选空行由 prompt 控制
    return "\n".join(out).strip()


def format_ai_interpretation(text: str) -> str:
    """AI 综合解读 / SOP 摘要统一排版。"""
    text = strip_markdown_for_wechat(text)
    lines = text.splitlines()
    out: list[str] = []
    emoji_headers = ("📊", "📰", "📋", "👀", "⚠️")
    for line in lines:
        s = line.strip()
        if not s:
            if out and out[-1] != "":
                out.append("")
            continue
        if s == "【AI 综合解读】" and out and out[-1] != "":
            out.append("")
        if s.startswith(emoji_headers) and out and out[-1] != "":
            out.append("")
        out.append(s)
    text = normalize_wechat_spacing("\n".join(out))
    if text and not text.startswith("【AI 综合解读】"):
        if "【AI 综合解读】" in text:
            text = text[text.index("【AI 综合解读】") :]
        else:
            text = f"【AI 综合解读】\n\n{text}"
    return text


def extract_sop_ai_section(full_text: str) -> str:
    """从选股完整日志中提取 SOP / DeepSeek 微信摘要（跳过进度与重复 Top5 列表）。"""
    markers = ("🔬 东财 SOP Top", "🔬 东财 SOP", "🤖 DeepSeek 审查")
    start = -1
    for m in markers:
        idx = full_text.find(m)
        if idx >= 0:
            start = idx
            break
    if start < 0:
        return ""

    chunk = full_text[start:]
    lines: list[str] = []
    in_summary = False
    for line in chunk.splitlines():
        s = line.strip()
        if not s:
            if in_summary and lines and lines[-1] != "":
                lines.append("")
            continue
        if any(s.startswith(p) for p in _LOG_LINE_PREFIXES):
            continue
        if s.startswith("📈 综合选股 Top"):
            continue
        if re.match(r"^\d+\.\s+\d{6}", s):
            continue
        if s == "⚠️ 策略信号仅供参考，不构成投资建议":
            continue
        in_summary = True
        lines.append(line.rstrip())

    return format_sop_wechat_summary("\n".join(lines))


def format_sop_wechat_summary(text: str) -> str:
    """SOP 微信摘要：去 Markdown + 小节间空行。"""
    text = strip_markdown_for_wechat(text)
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            if out and out[-1] != "":
                out.append("")
            continue
        # 个股 bullet：- 600863 或 - 000725 京东方A
        if re.match(r"^-\s+\d{6}\b", s):
            if out and out[-1] != "":
                out.append("")
        # 编号小节 1) 2) 3)
        elif re.match(r"^\d+\)\s", s) and out and out[-1] != "":
            out.append("")
        # 风险/动作子 bullet（P0、追高等）保持紧凑，仅在 3) 小节内
        out.append(line.rstrip())
    return normalize_wechat_spacing("\n".join(out))
