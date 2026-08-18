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

# 分块标题：compact=订阅号正文（默认）；card=旧版深色引用块
_BLOCKQUOTE_BORDER = "#22d3ee"
_BLOCKQUOTE_BG = "#0f172a"
_BLOCKQUOTE_TITLE_COLOR = "#7dd3fc"
_BLOCKQUOTE_TITLE_SIZE = "17px"
_SECTION_ACCENT = "#1a5276"
_SECTION_TITLE_COLOR = "#1a5276"
_SECTION_TITLE_SIZE = "17px"
_SECTION_TITLE_SIZE_BRIEF = "16px"

_BLOCKQUOTE_TITLE_RE = re.compile(r"^>\s*(.+)\s*$")
_CN_SECTION_RE = re.compile(r"^[一二三四五六七八九十]、")
_SECTION_RE = _CN_SECTION_RE
_SENTIMENT_TAG_RE = re.compile(r"\[(利好|利空|中性)\]")
_PCT_RE = re.compile(r"([+\-]?\d+\.?\d*)%")
_BEAR_PCT_CTX_RE = re.compile(r"跌|下挫|回落|走低|收跌|破位|急跌|跌幅|大跌|暴跌|跌超|月跌|累计跌|一度跌|盘中跌|回调|调降")
_BULL_PCT_CTX_RE = re.compile(r"涨|上扬|反弹|走高|收涨|暴涨|急涨|涨幅|大涨|拉升|涨超|月涨|累计涨|一度涨|盘中涨|冲高|急升")
_EMPHASIS_PHRASES = ("我们认为", "值得关注的是", "向后看")
_TOP5_RANK_RE = re.compile(r"^(\d+)\.\s+.+")
_NEWS_ITEM_HEAD_RE = re.compile(
    r"^(\d+)\.\s*(?:\[(利好|利空|中性)\]|(利好|利空|中性)｜)\s*(.+)$"
)
_METRIC_BULLET_RE = re.compile(r"^·\s*([^：]+)：(.+)$")
_PLAN_LINE_RE = re.compile(r"^(明日计划|复盘|不做清单)：(.+)$")
_TRADER_FIELD_RE = re.compile(r"^(地位|量价资金|博弈|结论)：(.+)$")
_AI_COMMENT_LINE_RE = re.compile(r"^AI点评[：:]\s*(.+)$")
_SOP_POS_RE = re.compile(r"SOP倾向关注[：:]?")
_SOP_NEG_RE = re.compile(r"暂不纳入监控[：:]?")
_JOURNAL_TITLE_LINE_RE = re.compile(r"^研究员札记\s*\|")

_KNOWN_SECTION_TITLES = frozenset(
    {
        "盘面速览",
        "外围与资金",
        "结构判断",
        "为什么现在看",
        "产业链怎么拆",
        "盘面里谁在用价格说话",
        "和指数情绪怎么联动",
        "向后看要验证什么",
        "明天盯什么",
        "今天深写什么",
        "为啥盯这条",
        "为什么选这一题",
        "要闻精选",
        "筛选名单",
        "个股拆解",
        "组合特征",
        "待验证事项",
        "组合与纪律",
        "次日跟踪",
        "情绪与盘面",
        "龙头拆解",
        "主线与梯队",
        "明日计划与纪律",
        "为什么值得多一层",
        "开始前要准备什么",
        "安装与把应用接到 CLI",
        "bot 和用户两种身份",
        "三层命令怎么发现",
        "三个真在用的模式",
        "和自写 Python 脚本怎么选",
        "排错收藏",
        "在 Cursor 里怎么配",
    }
)


def code_block_html(code: str, *, lang: str = "") -> str:
    """公众号正文代码块（等宽、浅底、可换行）。"""
    _ = lang
    escaped = _escape_html(code.rstrip("\n"))
    return (
        '<section style="margin:8px 0 14px;padding:0;">'
        '<pre style="margin:0;padding:12px 10px;background:#f4f6f8;'
        "border:1px solid #dbe2ea;border-radius:8px;"
        "font-size:13px;line-height:1.58;color:#1e293b;"
        "white-space:pre-wrap;word-break:break-all;"
        'font-family:Menlo,Consolas,Monaco,monospace;">'
        f"<code>{escaped}</code></pre></section>"
    )


def rich_html_enabled() -> bool:
    raw = os.environ.get("WECHAT_MP_RICH_HTML", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def is_blockquote_title_line(line: str) -> bool:
    s = line.strip()
    bare = s.lstrip("> ").strip()
    if bare in _KNOWN_SECTION_TITLES:
        return True
    for title in _KNOWN_SECTION_TITLES:
        if bare.startswith(title) and len(bare) > len(title):
            return False
    for label in (
        "先说事实",
        "外面怎么传",
        "A股怎么动",
        "我们怎么看",
        "发生了什么",
        "网上在说什么",
        "盘面怎么反应",
        "AI怎么看",
        "AI 怎么看",
    ):
        if label in bare:
            return False
    if _CN_SECTION_RE.match(s):
        return True
    m = _BLOCKQUOTE_TITLE_RE.match(s)
    if not m:
        return False
    inner = m.group(1).strip()
    if len(inner) > 22 or re.search(r"[，。；;！？!?]", inner):
        return False
    return True


def normalize_blockquote_title(line: str) -> str:
    s = line.strip()
    m = _BLOCKQUOTE_TITLE_RE.match(s)
    if m:
        return m.group(1).strip()
    return s


def section_style() -> str:
    raw = os.environ.get("WECHAT_MP_SECTION_STYLE", "compact").strip().lower()
    return raw if raw in ("compact", "card") else "compact"


def blockquote_title_html_card(title: str) -> str:
    """旧版深色引用块（WECHAT_MP_SECTION_STYLE=card）。"""
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


def blockquote_body_html(lines: list[str]) -> str:
    """引用块正文（`> ` 行）：输出真 blockquote，勿在 <p> 里留 &gt;。"""
    inner = "<br/>".join(format_line_rich_html(ln) for ln in lines if ln.strip())
    return (
        '<blockquote style="margin: 12px 0; padding: 10px 14px; '
        f"border-left: 3px solid {_BLOCKQUOTE_BORDER}; background-color: #f8fafc; "
        'color: #444444; font-size: 15px; line-height: 1.72;">'
        f"{inner}</blockquote>"
    )


def tv_section_banner_html(title: str, *, tight_top: bool = False, first_section: bool = False) -> str:
    """影视稿分节：横幅渐变底 + 居中标题。"""
    text = _escape_html(normalize_blockquote_title(title))
    from scripts.tools.wechat_mp_layout import active_layout

    layout = active_layout()
    if tight_top:
        margin = layout.section_margin_tight_top
    elif first_section:
        margin = f"{layout.section_first_margin_top} 0 10px"
    else:
        margin = layout.section_margin
    return (
        f'<section style="margin:{margin};padding:14px 16px 12px;'
        "background:linear-gradient(135deg,#1a2744 0%,#4a2030 52%,#1a2744 100%);"
        'border-radius:8px;text-align:center;">'
        '<p style="margin:0;padding:0;font-size:17px;font-weight:700;color:#f8fafc;'
        'line-height:1.4;letter-spacing:0.03em;">'
        f"{text}</p></section>"
    )


def blockquote_title_html(title: str, *, tight_top: bool = False, first_section: bool = False, article_kind: str | None = None) -> str:
    """公众号分节标题：居中、加粗、主题色（非引用块）。"""
    kind = (article_kind or "").strip().lower()
    if kind == "tv_review":
        return tv_section_banner_html(title, tight_top=tight_top, first_section=first_section)
    text = _escape_html(normalize_blockquote_title(title))
    if section_style() == "card":
        return blockquote_title_html_card(normalize_blockquote_title(title))

    from scripts.tools.wechat_mp_layout import active_layout

    layout = active_layout()
    if tight_top:
        margin = layout.section_margin_tight_top
    elif first_section:
        margin = f"{layout.section_first_margin_top} 0 2px"
    else:
        margin = layout.section_margin

    size = _SECTION_TITLE_SIZE_BRIEF if layout.key == "brief" else _SECTION_TITLE_SIZE
    return (
        f'<p style="margin:{margin};padding:0;text-align:center;'
        f"font-size:{size};font-weight:700;color:{_SECTION_TITLE_COLOR};"
        'line-height:1.35;letter-spacing:0.03em;">'
        f"{text}</p>"
    )


OPENING_LEDE_KINDS = frozenset(
    {"sector", "hotspot", "market", "news", "tv_review", "discussion"}
)


def opening_lede_paragraph_style() -> str:
    """开篇结论段：略大于正文、居中、主题色。"""
    from scripts.tools.wechat_mp_layout import active_layout

    layout = active_layout()
    return (
        f"margin:{layout.para_margin};padding:0;"
        "text-align:center;line-height:1.55;"
        "font-size:17px;font-weight:700;"
        f"color:{_COLOR_ACCENT};letter-spacing:0.02em;"
    )


_CTA_LINE_RE = re.compile(r"^\[\[cta:([^\]]+)\]\]\s*$")
_HL_LINE_RE = re.compile(r"^\[\[hl:(.+)\]\]\s*$")


def parse_hl_line(line: str) -> str | None:
    """解析 [[hl:关键句]] 高亮行。"""
    m = _HL_LINE_RE.match((line or "").strip())
    if not m:
        return None
    return m.group(1).strip() or None


def discussion_highlight_html(text: str) -> str:
    """讨论稿关键句：居中浅底高亮。"""
    t = _escape_html((text or "").strip())
    if not t:
        return ""
    return (
        '<section style="margin:14px 0 16px;padding:10px 12px;text-align:center;'
        f"background-color:#eef6fc;border:1px solid #c5dce8;border-radius:8px;"
        'box-shadow:0 1px 4px rgba(26,82,118,0.06);">'
        '<p style="margin:0;padding:0;line-height:1.55;font-size:17px;'
        f'font-weight:700;color:{_COLOR_ACCENT};letter-spacing:0.02em;">'
        f"{t}</p></section>"
    )


def parse_cta_line(line: str) -> list[str] | None:
    """解析 [[cta:行1|行2|行3]] 引流框（竖线分行）。"""
    m = _CTA_LINE_RE.match((line or "").strip())
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split("|") if p.strip()]
    return parts or None


def cta_box_html(parts: list[str]) -> str:
    """关注/回复类引流：居中色块，中间行加大加粗。"""
    if not parts:
        return ""
    rows: list[str] = []
    for i, part in enumerate(parts):
        text = _escape_html(part)
        if i == len(parts) // 2 and len(parts) >= 2:
            rows.append(
                f'<span style="display:block;margin:6px 0;font-size:19px;'
                f'font-weight:700;color:#c0392b;letter-spacing:0.06em;">{text}</span>'
            )
        else:
            rows.append(
                f'<span style="display:block;margin:2px 0;font-size:16px;'
                f'font-weight:600;color:{_COLOR_ACCENT};">{text}</span>'
            )
    inner = "".join(rows)
    return (
        '<section style="margin:20px 0 22px;padding:18px 14px;text-align:center;'
        f"background-color:#eef6fc;border:2px solid {_COLOR_ACCENT};"
        'border-radius:10px;box-shadow:0 2px 8px rgba(26,82,118,0.08);">'
        f'<p style="margin:0;line-height:1.75;">{inner}</p></section>'
    )


def disclaimer_html(text: str, *, kind: str | None = None) -> str:
    """文末免责声明：居中、加字号、浅色底（与正文区分）。"""
    t = _escape_html(" ".join((text or "").split()))
    if not t:
        return ""
    k = (kind or "").strip().lower()
    if k in {"workspace", "temp", "tech", "lab", "dev"}:
        color, bg, border = "#5d6d7e", "#f0f4f8", "#c5d0dc"
    else:
        color, bg, border = "#c0392b", "#fff5f5", "#f5b7b1"
    return (
        f'<p style="margin:20px 0 12px;padding:12px 10px;text-align:center;'
        f"font-size:15px;line-height:1.65;color:{color};"
        f"background-color:{bg};border:1px solid {border};border-radius:8px;"
        f'letter-spacing:0.02em;">{t}</p>'
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


def _pct_color(num: str, *, prefix: str = "") -> str:
    try:
        value = float(num.replace("+", ""))
    except ValueError:
        return _COLOR_NEUT
    if num.startswith("-"):
        return _COLOR_BEAR
    if num.startswith("+"):
        return _COLOR_BULL
    if prefix:
        ctx = prefix[-10:]
        if _BEAR_PCT_CTX_RE.search(ctx):
            return _COLOR_BEAR
        if _BULL_PCT_CTX_RE.search(ctx):
            return _COLOR_BULL
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
        prefix = segment[max(0, m.start() - 10) : m.start()]
        events.append(
            (
                m.start(),
                m.end(),
                _span(_pct_color(num, prefix=prefix), _escape_html(m.group(0)), bold=True),
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


def _format_news_item_head(line: str) -> str | None:
    stripped = line.strip()
    m = _NEWS_ITEM_HEAD_RE.match(stripped)
    if not m:
        return None
    from scripts.tools.wechat_mp_layout import active_layout

    layout = active_layout()
    num, tag = m.group(1), m.group(2) or m.group(3)
    title = m.group(4).strip()
    tag_html = _span(_sentiment_color(tag), f"[{tag}]", bold=True)
    return (
        f'<span style="font-size:{layout.news_title_size};font-weight:700;'
        f'color:#1a1a1a;line-height:1.45;">'
        f"{_escape_html(num)}. {tag_html} "
        f"{_escape_html(title)}</span>"
    )


def format_line_rich_html(line: str) -> str:
    """单行纯文本 → 已转义且带受控 inline 样式的 HTML 片段。"""
    stripped = line.strip()
    if _SECTION_RE.match(stripped):
        return (
            f'<span style="font-size:{_SECTION_TITLE_SIZE};font-weight:700;'
            f'color:{_SECTION_TITLE_COLOR};">{_escape_html(stripped)}</span>'
        )

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
        news_head = _format_news_item_head(line)
        if news_head:
            return news_head
        return f"<strong>{_format_inline_spans(stripped)}</strong>"

    if stripped.startswith("数据日 "):
        return _span(_COLOR_NEUT, _escape_html(stripped))

    if stripped.startswith("   "):
        return _format_inline_spans(line.lstrip())

    ai_m = _AI_COMMENT_LINE_RE.match(stripped)
    if ai_m:
        body = ai_m.group(1).strip()
        return (
            f'<span style="color:{_COLOR_ACCENT};font-weight:600;">AI点评：</span>'
            f"{_apply_emphasis_phrases(_format_inline_spans(body))}"
        )

    return _apply_emphasis_phrases(_format_inline_spans(line))
