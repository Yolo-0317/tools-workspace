"""公众号日更正文：宏观 / Top5 / 龙头 / 工作区技术分享。"""

from __future__ import annotations

import os
import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.news_ai_interpret import sanitize_public_ai_summary
from scripts.tools.portfolio_db import load_emotion_cycle_checklist
from scripts.tools.wechat_format import normalize_wechat_spacing
from scripts.tools.wechat_mp_client import text_to_html
from scripts.tools.wechat_mp_prose import humanize_mp_text

TZ = ZoneInfo("Asia/Shanghai")
TITLE_MAX = 32
WEEKDAY_CN = "一二三四五六日"
DISCLAIMER = (
    "本文为作者个人投资日记与信息整理，不构成投资建议。"
    "市场有风险，决策自负。"
)


def _clip_wechat_title(text: str, *, max_len: int = TITLE_MAX) -> str:
    """公众号标题上限 32 字；优先在 ｜、· 处截断。"""
    text = re.sub(r"\s+", "", (text or "").strip())
    if len(text) <= max_len:
        return text
    for sep in ("｜", "·", "：", "—"):
        parts = text.split(sep)
        buf = ""
        for i, part in enumerate(parts):
            chunk = part if i == 0 else sep + part
            if len(buf) + len(chunk) <= max_len:
                buf += chunk
            else:
                break
        if buf:
            return buf
    return text[:max_len]


def _cn_date(d: date | datetime) -> str:
    if isinstance(d, datetime):
        d = d.date()
    return f"{d.month}月{d.day}日"


def _weekday_cn(d: date) -> str:
    return f"周{WEEKDAY_CN[d.weekday()]}"


def _session_label(slot: str) -> str:
    try:
        hour = int(str(slot).split(":")[0])
    except ValueError:
        return "复盘"
    if hour >= 15:
        return "收盘"
    if hour >= 11:
        return "午间"
    return "盘中"


def _extract_market_hook(ai: str, *, max_len: int = 14) -> str:
    """从宏观 AI 摘要提炼标题钩子（题材/事件关键词）。"""
    candidates: list[tuple[int, str]] = []
    for line in ai.splitlines():
        s = line.strip()
        if not s or s.startswith("【"):
            continue
        score = 0
        if re.match(r"^[\-·]", s) or re.match(r"^\d+\.", s):
            score += 2
        if s.startswith(("📊", "📰", "📋", "👀", "⚠️")):
            s = s[1:].strip()
            score += 1
        s = re.sub(r"^\d+\.\s*", "", s)
        s = re.sub(r"^\[.*?\]\s*", "", s)
        s = re.sub(r"^[\-·]\s*", "", s)
        if len(s) < 6:
            continue
        if re.search(r"(仍是|主要|整体|总体|来看|方面)", s) and score < 2:
            continue
        if re.search(r"(拟约|收购|销量|立案|子公司|\d+\.\d+亿)", s):
            score -= 3
        for cut in ("，", "。", "；", "：", " "):
            if cut in s:
                s = s.split(cut, 1)[0]
        s = s.strip()
        if 4 <= len(s) <= 28:
            candidates.append((score, s))
    candidates.sort(key=lambda x: (-x[0], -len(x[1])))
    plain = [c[1] for c in candidates]
    if not plain:
        return "宏观快讯与外围脉络"

    priority = (
        "中东",
        "霍尔木兹",
        "原油",
        "服务业",
        "半导体",
        "政策",
        "板块",
        "华为",
        "电力",
        "煤炭",
        "情绪",
        "扩能",
    )
    for kw in priority:
        for c in plain:
            if kw in c:
                return c[:max_len]

    hook = plain[0][:max_len]
    if len(plain) >= 2 and len(hook) < max_len - 1:
        second = plain[1][: max(4, max_len - len(hook) - 1)]
        combo = f"{hook}·{second}"
        return combo[:max_len]
    return hook


def _compress_market_tags(ai: str) -> str:
    """标题用短标签（更易做引流句）。"""
    blob = ai
    pairs = (
        ("霍尔木兹", "霍尔木兹"),
        ("中东", "中东局势"),
        ("原油", "油价"),
        ("服务业", "服务业"),
        ("半导体", "半导体"),
        ("华为", "华为链"),
        ("山东", "山东政策"),
        ("涨停", "涨停潮"),
        ("跌停", "亏钱效应"),
    )
    tags: list[str] = []
    for kw, label in pairs:
        if kw in blob and label not in tags:
            tags.append(label)
        if len(tags) >= 2:
            break
    if tags:
        return "+".join(tags)
    return _extract_market_hook(ai, max_len=10)


def _pick_clickbait_title(options: list[str]) -> str:
    """优先选用带悬念、且不超过 32 字的标题。"""
    ranked = sorted(
        options,
        key=lambda t: (
            ("？" in t or "?" in t or "！" in t),
            "必读" in t or "别漏" in t or "先看" in t,
            -len(t),
        ),
        reverse=True,
    )
    for text in ranked:
        clipped = _clip_wechat_title(text)
        if 10 <= len(clipped) <= TITLE_MAX:
            return clipped
    return _clip_wechat_title(options[0])


def _market_title(ai: str, *, now: datetime, slot: str) -> str:
    tags = _compress_market_tags(ai)
    wd = _weekday_cn(now.date())
    sess = _session_label(slot)
    return _pick_clickbait_title(
        [
            f"{wd}{sess}必读｜{tags}，明天怎么跟？",
            f"收盘别漏看！{tags}正在改写盘面？",
            f"{wd}盘后一文｜{tags}，机会藏哪？",
            f"A股{sess}复盘：{tags}，一文捋清",
        ]
    )


def _market_digest(ai: str, *, now: datetime, slot: str) -> str:
    tags = _compress_market_tags(ai)
    return (
        f"【{now.strftime('%m-%d')} {_session_label(slot)}】{tags}——"
        "地缘、政策与板块节奏，3分钟读完今日盘面逻辑。"
        "个人日记，非荐股。"
    )[:128]


def _top5_title(picks: list[Any], *, trade_date: date) -> str:
    names = [str(getattr(p, "name", "") or "").strip() for p in picks]
    names = [n for n in names if n and not n.isdigit()]
    n = len(names) or len(picks)
    wd = _weekday_cn(trade_date)
    if len(names) >= 2:
        a, b = names[0], names[1]
        return _pick_clickbait_title(
            [
                f"{a}领衔{n}只！收盘信号出炉，明日盯啥？",
                f"刚筛出{n}只｜{a}、{b}，明天怎么走？",
                f"{wd}盘后值得看：{a}等{n}只技术信号",
            ]
        )
    if names:
        return _pick_clickbait_title(
            [
                f"{names[0]}收盘出信号！明日重点就看它？",
                f"{wd}甄选1只｜{names[0]}，逻辑一次说透",
            ]
        )
    return _clip_wechat_title(f"{wd}盘后｜{n}只技术信号，别错过？")


def _top5_digest(picks: list[Any], *, trade_date: date) -> str:
    names = [str(getattr(p, "name", "") or "") for p in picks[:3] if getattr(p, "name", None)]
    names_s = "、".join(names) if names else "当日标的"
    top = picks[0] if picks else None
    score = f"{getattr(top, 'score', 0):.0f}分" if top else ""
    return (
        f"收盘刚跑完综合选股：{names_s} 等 {len(picks)} 只进入观察。"
        f"技术评分{score}，附宏观逻辑与纪律提示——非荐股，仅供复盘。"
    )[:128]


def _dragon_lead_name(dragons: list[dict[str, Any]]) -> tuple[str, str, int | None]:
    if not dragons:
        return "", "", None
    d0 = dragons[0]
    code = str(d0.get("ts_code") or "").split(".")[0].zfill(6)
    name = str(d0.get("name") or "").strip()
    if not name or re.fullmatch(r"\d{6}", name):
        from scripts.tools.portfolio_db import load_stock_names_by_codes

        name = load_stock_names_by_codes([code]).get(code, "")
    short = (name[:4] if name else "龙头") or "龙头"
    boards = d0.get("board_height")
    boards_s = f"{boards}板" if boards is not None else ""
    return short, boards_s, boards if isinstance(boards, int) else None


def _dragon_title(hdr: dict[str, Any], dragons: list[dict[str, Any]], *, trade_date: date) -> str:
    phase = str(hdr.get("phase") or "情绪").strip()
    theme = str(hdr.get("main_theme") or "").strip()[:6]
    lead, boards_s, _ = _dragon_lead_name(dragons)
    wd = _weekday_cn(trade_date)
    phase_hint = {
        "退潮": "退潮也别瞎割",
        "发酵": "发酵期盯龙头",
        "高潮": "高潮更要防摔",
        "冰点": "冰点敢不敢试",
        "分歧": "分歧日别追高",
        "启动": "启动先小仓跟",
    }.get(phase, f"{phase[:2]}期")

    return _pick_clickbait_title(
        [
            f"{phase_hint}？{theme}主线+{lead}{boards_s}",
            f"{wd}游资轨｜{theme}{lead}{boards_s}，一文读懂",
            f"情绪{phase[:2]}怎么玩？{lead}{boards_s}还在榜",
        ]
    )


def _dragon_digest(hdr: dict[str, Any], dragons: list[dict[str, Any]], *, trade_date: date) -> str:
    phase = hdr.get("phase") or "—"
    theme = hdr.get("main_theme") or "—"
    pool = "、".join(
        str(d.get("name") or d.get("ts_code") or "")[:6] for d in dragons[:3]
    ) or "暂无"
    return (
        f"今日情绪「{phase}」，主线 {theme}，龙头池 {pool}。"
        "炸板率、仓位上限与明日计划一次看完——游资观察日记，非操作建议。"
    )[:128]


# 旧版/测试草稿标题（清理用）
OBSOLETE_DRAFT_TITLE_PATTERNS = (
    re.compile(r"^市场评论\s"),
    re.compile(r"^选股Top5宏观"),
    re.compile(r"^龙头宏观\s"),
    re.compile(r"^宏观复盘\s"),
    re.compile(r"逻辑观察$"),
    re.compile(r"^6月\d+日收盘｜(?!.*[？?！])"),  # 上一版平淡标题
    re.compile(r"^6月\d+日甄选｜(?!.*[？?！])"),
    re.compile(r"^6月\d+日｜退潮｜"),  # 上一版龙头标题
)


def is_obsolete_draft_title(title: str) -> bool:
    from scripts.tools.wechat_mp_client import normalize_draft_text

    title = normalize_draft_text((title or "").strip())
    if not title:
        return False
    if any(p.search(title) for p in OBSOLETE_DRAFT_TITLE_PATTERNS):
        return True
    # 自动脚本旧版（无悬念标点）
    if re.match(r"^6月\d+日(收盘|甄选)｜", title) and not re.search(r"[？?！]", title):
        return True
    if re.match(r"^6月\d+日｜", title) and "｜" in title[6:] and not re.search(r"[？?！]", title):
        return True
    return False

# Top5 公众号正文去掉持仓操作段（SOP 微信摘要里的 2) 结合持仓）
_TOP5_HOLDINGS_SECTION_RE = re.compile(
    r"(?:\n|^)\s*2\)\s*[^\n]*持仓[^\n]*\n.*",
    re.DOTALL,
)


def _author() -> str:
    return os.getenv("WECHAT_MP_AUTHOR", "R2D2")[:16]


def _source_url() -> str:
    return os.getenv("WECHAT_MP_SOURCE_URL", "").strip()[:1024]


def _article_shell(
    *,
    title: str,
    digest: str,
    body_text: str,
) -> dict[str, str]:
    article: dict[str, str] = {
        "title": title[:32],
        "author": _author(),
        "digest": digest[:128],
        "content": text_to_html(body_text),
        "article_type": "news",
    }
    hub = _source_url()
    if hub:
        article["content_source_url"] = hub
    return article


def _redact_account_hints(line: str) -> str:
    """公众号公开稿弱化个人账户仓位表述。"""
    line = re.sub(r"仓位\s*[\d.]+%[^；。\n]*", "仓位纪律约束", line)
    line = re.sub(r"P[0-5][^\n]*", "", line)
    return line.strip()


def sanitize_top5_public_text(text: str) -> str:
    """去掉 Top5 SOP 摘要中的持仓操作建议，保留个股宏观评述。"""
    if not text:
        return text
    cleaned = _TOP5_HOLDINGS_SECTION_RE.sub("\n", text)
    cleaned = re.sub(
        r"(?:\n|^)\s*3\)\s*[^\n]*风险[^\n]*\n.*",
        "\n",
        cleaned,
        count=1,
        flags=re.DOTALL,
    )
    cleaned = sanitize_public_ai_summary(cleaned)
    lines = [_redact_account_hints(ln) for ln in cleaned.splitlines()]
    cleaned = "\n".join(ln for ln in lines if ln)
    return normalize_wechat_spacing(cleaned.strip())


def build_market_article() -> dict[str, str]:
    from scripts.tools.wechat_mp_market_article import (
        build_market_context_blob,
        generate_researcher_market_body,
    )

    now = datetime.now(TZ)
    slot = now.strftime("%H:%M")
    raw_body = generate_researcher_market_body(now=now)
    _, news_blob = build_market_context_blob(now=now)
    title = _market_title(news_blob, now=now, slot=slot)
    body = humanize_mp_text(f"{raw_body}\n\n{DISCLAIMER}")
    digest = _market_digest(news_blob, now=now, slot=slot)
    return _article_shell(title=title, digest=digest, body_text=body)


def build_top5_article() -> dict[str, str]:
    from scripts.tools.selection_watchlist import enrich_pick_names, load_wechat_top5_picks
    from scripts.tools.wechat_mp_top5_article import generate_top5_trader_body

    td, picks, _source = load_wechat_top5_picks()
    picks = enrich_pick_names(picks)
    if not picks:
        raise RuntimeError("选股 Top5 为空，请先运行综合选股任务")

    title = _top5_title(picks, trade_date=td)
    raw_body = generate_top5_trader_body(picks, trade_date=td, pool_source=_source)
    body = humanize_mp_text(f"{raw_body}\n\n{DISCLAIMER}")
    digest = _top5_digest(picks, trade_date=td)
    return _article_shell(title=title, digest=digest, body_text=body)


def build_workspace_article() -> dict[str, str]:
    from scripts.tools.wechat_mp_workspace_article import (
        generate_workspace_overview_body,
        workspace_overview_digest,
        workspace_overview_title,
    )

    from scripts.tools.wechat_format import normalize_wechat_spacing, strip_markdown_for_wechat
    from scripts.tools.wechat_mp_public import sanitize_public_mp_text

    title = workspace_overview_title()
    raw_body = generate_workspace_overview_body()
    merged = normalize_wechat_spacing(
        strip_markdown_for_wechat(f"{raw_body}\n\n{DISCLAIMER}")
    )
    body = sanitize_public_mp_text(merged)
    digest = workspace_overview_digest()
    return _article_shell(title=title, digest=digest, body_text=body)


def build_dragons_article(*, checklist_slot: str | None = None) -> dict[str, str]:
    from scripts.tools.wechat_mp_dragons_article import generate_dragons_trader_body

    slot = (checklist_slot or os.getenv("WECHAT_MP_DRAGON_SLOT", "eod")).strip()
    bundle = load_emotion_cycle_checklist(checklist_slot=slot)
    if not bundle:
        bundle = load_emotion_cycle_checklist()
    if not bundle:
        raise RuntimeError(
            "无情绪周期/龙头数据，请先运行 sync_emotion_cycle 或 emotion_cycle_checklist save"
        )

    hdr = bundle["header"]
    dragons = bundle.get("dragon_items") or []
    td_val = hdr.get("trade_date")
    if isinstance(td_val, date):
        td_date = td_val
    else:
        td_date = datetime.fromisoformat(str(td_val)[:10]).date()

    title = _dragon_title(hdr, dragons, trade_date=td_date)
    raw_body = generate_dragons_trader_body(bundle, checklist_slot=slot)
    body = humanize_mp_text(f"{raw_body}\n\n{DISCLAIMER}")
    digest = _dragon_digest(hdr, dragons, trade_date=td_date)
    return _article_shell(title=title, digest=digest, body_text=body)


DRAFT_KINDS = ("market", "top5", "dragons", "workspace")


def build_article(kind: str) -> dict[str, str]:
    k = kind.strip().lower()
    if k == "market":
        return build_market_article()
    if k == "top5":
        return build_top5_article()
    if k in {"dragons", "dragon", "leaders"}:
        return build_dragons_article()
    if k in {"workspace", "tech", "lab", "dev"}:
        return build_workspace_article()
    raise ValueError(f"未知 kind={kind!r}，可选: {', '.join(DRAFT_KINDS)}")
