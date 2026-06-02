"""公众号正文 → 受控富文本 HTML（加粗 / 颜色，转义后再插标签）。"""

from __future__ import annotations

import os
import re

from scripts.tools.wechat_mp_client import _escape_html

# A 股阅读习惯：涨/利好偏红，跌/利空偏绿
_COLOR_BULL = "#c0392b"
_COLOR_BEAR = "#1a7f37"
_COLOR_NEUT = "#666666"
_COLOR_ACCENT = "#1a5276"

# 分块标题引用块（科技感）
_BLOCKQUOTE_BORDER = "#22d3ee"
_BLOCKQUOTE_BG = "#0f172a"
_BLOCKQUOTE_TITLE_COLOR = "#7dd3fc"
_BLOCKQUOTE_TITLE_SIZE = "17px"

_BLOCKQUOTE_TITLE_RE = re.compile(r"^>\s*(.+)\s*$")
_CN_SECTION_RE = re.compile(r"^[一二三四五六七八九十]、")
_SECTION_RE = _CN_SECTION_RE
_SENTIMENT_TAG_RE = re.compile(r"\[(利好|利空|中性)\]")
_PCT_RE = re.compile(r"([+\-]?\d+\.?\d*)%")
_EMPHASIS_PHRASES = ("我们认为", "值得关注的是", "向后看")
_TOP5_RANK_RE = re.compile(r"^(\d+)\.\s+.+")
_METRIC_BULLET_RE = re.compile(r"^·\s*([^：]+)：(.+)$")
_PLAN_LINE_RE = re.compile(r"^(明日计划|复盘|不做清单)：(.+)$")
_TRADER_FIELD_RE = re.compile(r"^(地位|量价资金|博弈|结论)：(.+)$")
_SOP_POS_RE = re.compile(r"SOP倾向关注[：:]?")
_SOP_NEG_RE = re.compile(r"暂不纳入监控[：:]?")
_JOURNAL_TITLE_LINE_RE = re.compile(r"^研究员札记\s*\|")


def rich_html_enabled() -> bool:
    raw = os.environ.get("WECHAT_MP_RICH_HTML", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def is_blockquote_title_line(line: str) -> bool:
    s = line.strip()
    return bool(_BLOCKQUOTE_TITLE_RE.match(s) or _CN_SECTION_RE.match(s))


def normalize_blockquote_title(line: str) -> str:
    s = line.strip()
    m = _BLOCKQUOTE_TITLE_RE.match(s)
    if m:
        return m.group(1).strip()
    return s


def blockquote_title_html(title: str) -> str:
    """公众号分块标题 → 科技感引用块（大字加粗）。"""
    text = normalize_blockquote_title(title)
    inner = (
        f'<span style="color: {_BLOCKQUOTE_TITLE_COLOR}; font-size: {_BLOCKQUOTE_TITLE_SIZE}; '
        f'font-weight: 700; letter-spacing: 0.03em;">{_escape_html(text)}</span>'
    )
    return (
        '<blockquote style="margin: 16px 0 10px; padding: 12px 16px; '
        f"border-left: 4px solid {_BLOCKQUOTE_BORDER}; background-color: {_BLOCKQUOTE_BG}; "
        'border-radius: 0 8px 8px 0; '
        'box-shadow: inset 0 0 0 1px rgba(34, 211, 238, 0.12);">'
        f"{inner}</blockquote>"
    )


def strip_journal_title_lines(text: str) -> str:
    """去掉正文首行「研究员札记 | …」（历史 LLM 输出兼容）。"""
    lines: list[str] = []
    for line in text.splitlines():
        if _JOURNAL_TITLE_LINE_RE.match(line.strip()):
            continue
        lines.append(line)
    merged = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", merged).strip()


def _sentiment_color(tag: str) -> str:
    return {"利好": _COLOR_BULL, "利空": _COLOR_BEAR, "中性": _COLOR_NEUT}.get(tag, _COLOR_NEUT)


def _pct_color(num: str) -> str:
    try:
        value = float(num.replace("+", ""))
    except ValueError:
        return _COLOR_NEUT
    if value > 0:
        return _COLOR_BULL
    if value < 0:
        return _COLOR_BEAR
    return _COLOR_NEUT


def _span(color: str, text: str, *, bold: bool = False) -> str:
    weight = " font-weight: 600;" if bold else ""
    return f'<span style="color: {color};{weight}">{text}</span>'


def _merge_spans(events: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    events.sort(key=lambda x: x[0])
    merged: list[tuple[int, int, str]] = []
    end = -1
    for start, stop, html in events:
        if start < end:
            continue
        merged.append((start, stop, html))
        end = stop
    return merged


def _apply_emphasis_phrases(escaped: str) -> str:
    out = escaped
    for phrase in _EMPHASIS_PHRASES:
        esc_phrase = _escape_html(phrase)
        if esc_phrase in out and f"<strong>{esc_phrase}</strong>" not in out:
            out = out.replace(esc_phrase, f"<strong>{esc_phrase}</strong>", 1)
    return out


def _apply_sop_tags(escaped: str) -> str:
    out = escaped

    def _wrap_pos(m: re.Match[str]) -> str:
        return _span(_COLOR_BULL, _escape_html(m.group(0)), bold=True)

    def _wrap_neg(m: re.Match[str]) -> str:
        return _span(_COLOR_NEUT, _escape_html(m.group(0)), bold=True)

    out = _SOP_POS_RE.sub(_wrap_pos, out)
    out = _SOP_NEG_RE.sub(_wrap_neg, out)
    return out


def _format_stock_score_line(line: str) -> str | None:
    m = re.match(r"^(.+?)（(\d+)分）：(.+)$", line.strip())
    if not m:
        return None
    name, score, decision = m.group(1), m.group(2), m.group(3)
    dec = decision.strip()
    if any(k in dec for k in ("买入", "关注", "建仓", "加仓")):
        dec_color = _COLOR_BULL
    elif any(k in dec for k in ("观望", "暂不", "减仓", "回避")):
        dec_color = _COLOR_NEUT
    else:
        dec_color = _COLOR_NEUT
    return (
        f"<strong>{_escape_html(name)}</strong>"
        f"{_span(_COLOR_ACCENT, _escape_html(f'（{score}分）'), bold=True)}"
        f"{_span(dec_color, _escape_html(f'：{dec}'), bold=True)}"
    )


def _format_metric_bullet(line: str) -> str | None:
    m = _METRIC_BULLET_RE.match(line.strip())
    if not m:
        return None
    label, value = m.group(1), m.group(2)
    value_html = _format_inline_spans(value)
    return f"<strong>{_escape_html(label)}</strong>：{value_html}"


def _format_inline_spans(segment: str) -> str:
    """对片段做标签/涨跌幅着色（片段内不再拆 emphasis）。"""
    events: list[tuple[int, int, str]] = []
    for m in _SENTIMENT_TAG_RE.finditer(segment):
        tag = m.group(1)
        events.append(
            (
                m.start(),
                m.end(),
                _span(_sentiment_color(tag), _escape_html(m.group(0)), bold=True),
            )
        )
    for m in _PCT_RE.finditer(segment):
        num = m.group(1)
        events.append(
            (
                m.start(),
                m.end(),
                _span(_pct_color(num), _escape_html(m.group(0)), bold=True),
            )
        )
    if not events:
        return _apply_sop_tags(_escape_html(segment))

    parts: list[str] = []
    cursor = 0
    for start, stop, html in _merge_spans(events):
        if cursor < start:
            parts.append(_apply_sop_tags(_escape_html(segment[cursor:start])))
        parts.append(html)
        cursor = stop
    if cursor < len(segment):
        parts.append(_apply_sop_tags(_escape_html(segment[cursor:])))
    return "".join(parts)


def format_line_rich_html(line: str) -> str:
    """单行纯文本 → 已转义且带受控 inline 样式的 HTML 片段。"""
    stripped = line.strip()
    if _SECTION_RE.match(stripped):
        return f"<strong>{_escape_html(stripped)}</strong>"

    stock_line = _format_stock_score_line(line)
    if stock_line:
        return stock_line

    metric_line = _format_metric_bullet(line)
    if metric_line:
        return metric_line

    trader_m = _TRADER_FIELD_RE.match(stripped)
    if trader_m:
        label, body = trader_m.group(1), trader_m.group(2)
        return (
            f"<strong>{_escape_html(label)}：</strong>"
            f"{_apply_emphasis_phrases(_format_inline_spans(body))}"
        )

    plan_m = _PLAN_LINE_RE.match(stripped)
    if plan_m:
        label, body = plan_m.group(1), plan_m.group(2)
        return (
            f"<strong>{_escape_html(label)}：</strong>"
            f"{_apply_emphasis_phrases(_format_inline_spans(body))}"
        )

    if _TOP5_RANK_RE.match(stripped):
        return f"<strong>{_format_inline_spans(stripped)}</strong>"

    if stripped.startswith("数据日 "):
        return _span(_COLOR_NEUT, _escape_html(stripped))

    if stripped.startswith("   "):
        return _format_inline_spans(line.lstrip())

    return _apply_emphasis_phrases(_format_inline_spans(line))
