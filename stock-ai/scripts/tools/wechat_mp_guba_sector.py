#!/usr/bin/env python3
"""东财股吧 sector 摘要：按链拆帖（每帖 ≤3 个 $话题$）+ 方案 A CTA → 飞书 / guba 槽。"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_hot_theme import (
    HotThemeReport,
    ThemeScore,
    discover_sector_hot_themes,
    pick_focus_themes,
)
from scripts.tools.wechat_mp_sector_article import (
    format_sector_trade_label,
    resolve_sector_trade_date,
)
from scripts.tools.wechat_mp_sector_stocks import (
    SectorSampleStock,
    collect_sector_sample_stocks,
)

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[2]
GUBA_OUTPUT_PATH = ROOT / "output" / "wechat_mp_guba_latest.txt"

# 引流：不写微信/公众号/外链；读者搜同名 IP（东财合规）
GUBA_CTA_A = (
    "本帖为东财人气榜收盘对照摘要（3只/帖，非荐股）。"
    "同一交易日快讯与验证清单在牛马也智能同步更新，搜「牛马也智能」看完整版。"
    "仅供结构参考。"
)
GUBA_TITLE_MAX = 36
GUBA_DISCLAIMER = "个人观点，不构成投资建议；市场有风险，决策自负。"


@dataclass(frozen=True)
class GubaHotEnrichment:
    """人气 Top12 股吧干货：指数、板块、快讯、行业。"""

    industry_map: dict[str, str]
    top_boards: tuple[tuple[str, float], ...]
    sector_themes: tuple[str, ...]
    news_by_code: dict[str, dict[str, Any]]
    index_parts: dict[str, str]
    index_breadth: str
    next_trade_weekday: str
    all_by_code: dict[str, SectorSampleStock]


_ARCHETYPE_RULES: tuple[tuple[tuple[str, ...], str, str, str], ...] = (
    (("面板", "显示", "光电"), "面板/显示", "偏消费电子与周期定价", "看面板指数与龙头溢价"),
    (("半导体", "集成电路", "靶材", "特气", "电子"), "半导体上游", "常与材料/设备/特气链条联动", "看材料板块是否共振"),
    (("工程", "建设", "实业"), "半导体工程/洁净室", "与产线资本开支、材料热度同向", "看工程链条是否有跟风"),
    (("化工", "氟", "气体", "新材", "科技"), "化工新材料", "常在氟化工/电子化学品里找辨识度", "看是否压过板块均值"),
    (("通信", "光纤", "光模块"), "光通信", "与算力/传输叙事相关", "看通信设备板块是否同步"),
    (("电力", "发电", "火电"), "电力", "偏公用事业/能源定价", "看电力板块与煤价/政策是否同向"),
    (("磷", "化肥", "化工"), "磷化工/化肥", "偏资源与涨价链", "看磷化工榜位能否连续"),
    (("影视", "传媒", "游戏", "数科"), "内容/传媒", "偏主题与流量叙事", "看题材是否一日游"),
    (("银行", "证券", "保险"), "金融", "偏指数与政策贝塔", "看宽基是否同步"),
)


def _stock_change_pct(stock: SectorSampleStock) -> float | None:
    m = re.search(r"涨跌([+-]?[\d.]+)%", stock.detail or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _stock_rank(stock: SectorSampleStock) -> int:
    m = re.search(r"Top(\d+)", stock.theme or "")
    if m:
        return int(m.group(1))
    m = re.search(r"人气第(\d+)", stock.detail or "")
    return int(m.group(1)) if m else 0


def _format_pct(value: float) -> str:
    return f"{value:+.2f}%".replace("+-", "+")


def _clip_text(text: str, max_len: int = 48) -> str:
    t = re.sub(r"\s+", "", (text or "").strip())
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _infer_archetype(stock: SectorSampleStock, industry: str) -> tuple[str, str, str]:
    blob = f"{industry}{stock.name}"
    for keys, label, chain, watch in _ARCHETYPE_RULES:
        if any(k in blob for k in keys):
            return label, chain, watch
    return "主线题材", "宜对照板块强弱与快讯", "看相对板块溢价"


def _parse_index_snapshot() -> tuple[dict[str, str], str]:
    parts: dict[str, str] = {}
    breadth = ""
    try:
        from scripts.tools.daily_briefing_report import fetch_market_indices

        lines = fetch_market_indices()
    except Exception:
        return parts, breadth
    labels = (
        ("上证", "上证指数"),
        ("深证", "深证成指"),
        ("创业板", "创业板指"),
        ("科创50", "科创50"),
    )
    for key, label in labels:
        for line in lines:
            if label not in line:
                continue
            m = re.search(
                r"([\d.]+)\s*\([^,]+,\s*([+-]?[\d.]+%)\)",
                line,
            )
            if m:
                parts[key] = f"{m.group(1)}（{m.group(2)}）"
            break
    for line in lines:
        if "上涨" in line and "下跌" in line:
            breadth = line.strip()
            break
    return parts, breadth


def _collect_guba_hot_enrichment(
    rows: list[Any],
    *,
    edition: str | None = "close",
) -> GubaHotEnrichment:
    from scripts.tools.portfolio_db import load_industry_map
    from scripts.tools.wechat_mp_hot_stocks import HotStockRow
    from scripts.tools.wechat_mp_weekend_news import (
        build_news_time_context,
        fetch_weekend_kuaixun_pool,
        hot_stock_news_hours,
        match_hot_stocks_to_news,
        resolve_hot_stock_anchor_date,
        format_hot_stock_anchor_label,
    )

    samples = [_hot_row_to_sample(r) for r in rows]
    industry_map = {}
    try:
        industry_map = load_industry_map()
    except Exception:
        pass

    top_boards: list[tuple[str, float]] = []
    sector_themes: list[str] = []
    try:
        from scripts.tools.fetch_eastmoney_quotes import fetch_hot_industry_board_rows_opencli

        board_rows = fetch_hot_industry_board_rows_opencli(top_n=8, close_browser=True)
        for row in board_rows or []:
            name = str(row.get("sector") or row.get("f14") or "").strip()
            chg = row.get("sector_chg")
            if not name or chg is None:
                continue
            try:
                top_boards.append((name, float(chg)))
            except (TypeError, ValueError):
                continue
    except Exception:
        pass

    try:
        report = discover_sector_hot_themes(edition=edition)
        sector_themes = [t.name for t in pick_focus_themes(report, edition=edition) if t.name][:2]
    except Exception:
        pass

    news_by_code: dict[str, dict[str, Any]] = {}
    try:
        os.environ.setdefault("WECHAT_MP_NEWS_BATCH", "evening")
        now = datetime.now(TZ)
        anchor = resolve_hot_stock_anchor_date(now=now)
        anchor_label = format_hot_stock_anchor_label(anchor)
        hot_rows = [
            HotStockRow(
                rank=int(getattr(r, "rank", 0) or 0),
                code=str(getattr(r, "code", "") or "").zfill(6),
                name=str(getattr(r, "name", "") or ""),
                change_pct=float(getattr(r, "change_pct", 0) or 0),
            )
            for r in rows
        ]
        pool, engagement = fetch_weekend_kuaixun_pool(now=now, hours=hot_stock_news_hours())
        matched = match_hot_stocks_to_news(
            hot_rows,
            pool,
            engagement=engagement,
            now=now,
            anchor=anchor,
            anchor_label=anchor_label,
        )
        for item in matched:
            code = str(item.get("matched_stock_code") or "").zfill(6)
            if code:
                news_by_code[code] = item
    except Exception:
        pass

    index_parts, index_breadth = _parse_index_snapshot()
    ctx = build_news_time_context()
    all_by_code = {str(s.code).zfill(6): s for s in samples}
    return GubaHotEnrichment(
        industry_map=industry_map,
        top_boards=tuple(top_boards[:5]),
        sector_themes=tuple(sector_themes),
        news_by_code=news_by_code,
        index_parts=index_parts,
        index_breadth=index_breadth,
        next_trade_weekday=ctx.next_trade_weekday_cn,
        all_by_code=all_by_code,
    )


def _hot_group_narrative(group: list[SectorSampleStock]) -> str:
    strong = [s for s in group if (_stock_change_pct(s) or 0) >= 5]
    weak = [s for s in group if (_stock_change_pct(s) or 0) < 0]
    flat = [s for s in group if s not in strong and s not in weak]
    if strong and weak:
        return "指数分化下「强材料/弱龙头」并存，不是同一套叙事"
    if len(strong) >= 2:
        return "多只涨停级叠加上榜，更像主线里找辨识度"
    if weak and not strong:
        return "整体承压但讨论度仍高，偏分歧消化"
    if flat:
        return "涨跌不大但人气靠前，宜盯后续量价"
    return "人气与涨跌需分开看，别混为一谈"


def _hot_intro_paragraph(
    *,
    trade_label: str,
    rank_lo: int,
    rank_hi: int,
    group: list[SectorSampleStock],
    ctx: GubaHotEnrichment,
) -> str:
    topic_blob = "、".join(format_guba_topic(s) for s in group)
    fact_bits = []
    for s in group:
        chg = _stock_change_pct(s)
        rank = _stock_rank(s)
        if chg is not None and rank:
            fact_bits.append(f"第{rank}约{_format_pct(chg)}")
    facts = "、".join(fact_bits) if fact_bits else "见下文"
    idx_bits = []
    for key in ("上证", "创业板", "科创50"):
        if key in ctx.index_parts:
            m = re.search(r"（([+-]?[\d.]+%)）", ctx.index_parts[key])
            if m:
                idx_bits.append(f"{key}{m.group(1)}")
    idx_line = "，".join(idx_bits)
    narrative = _hot_group_narrative(group)
    para = (
        f"{topic_blob} 包揽东财人气榜第{rank_lo}-{rank_hi}，"
        f"{trade_label}分别约 {facts}。"
    )
    if idx_line:
        para += f"{idx_line}——"
    para += narrative + "。"
    return para


def _hot_why_block(group: list[SectorSampleStock], ctx: GubaHotEnrichment) -> str:
    lines: list[str] = []
    for i, stock in enumerate(group, 1):
        code = str(stock.code).zfill(6)
        industry = ctx.industry_map.get(code, "")
        label, chain, watch = _infer_archetype(stock, industry)
        chg = _stock_change_pct(stock)
        rank = _stock_rank(stock)
        news = ctx.news_by_code.get(code) or {}
        title = str(news.get("title") or "").strip()
        synthetic = news.get("synthetic")
        catalyst = ""
        if title and not synthetic:
            catalyst = f"快讯侧：{_clip_text(title, 42)}。"
        elif chg is not None and chg >= 9.5:
            catalyst = "涨停级收涨叠加上榜，更像资金在主线里找辨识度。"
        elif chg is not None and chg <= -3 and rank <= 5:
            catalyst = "高讨论+收跌，典型「价跌量不散」，观察是否企稳而非追跌杀。"
        elif chg is not None and abs(chg) < 2:
            catalyst = "涨跌不大但人气靠前，重点看次日竞价是否还有接力。"
        else:
            catalyst = f"{label}属性，{chain}。"
        lines.append(
            f"{i}）{format_guba_topic(stock)}：{chain}；{catalyst}{watch}。"
        )
    return "【为什么现在看】\n" + "\n".join(lines)


def _peer_mover_in_top12(
    group: list[SectorSampleStock],
    ctx: GubaHotEnrichment,
    *,
    min_chg: float = 8.0,
) -> SectorSampleStock | None:
    group_codes = {str(s.code).zfill(6) for s in group}
    best: SectorSampleStock | None = None
    best_chg = min_chg
    for code, s in ctx.all_by_code.items():
        if code in group_codes:
            continue
        chg = _stock_change_pct(s)
        if chg is not None and chg >= best_chg:
            best_chg = chg
            best = s
    return best


def _hot_structure_block(group: list[SectorSampleStock], ctx: GubaHotEnrichment) -> str:
    lines = ["【当日结构（对照用）】"]
    idx_notes: list[str] = []
    sh = ctx.index_parts.get("上证", "")
    cyb = ctx.index_parts.get("创业板", "")
    kc = ctx.index_parts.get("科创50", "")
    if sh and cyb:
        idx_notes.append("宽基：深弱沪稳或成长分化时，别用单一上证判断材料/设备情绪")
    if kc and "+" in kc:
        idx_notes.append("科创相对抗跌时，Top12 里材料/特气/工程票占比往往更高")
    if idx_notes:
        lines.append("· " + idx_notes[0])
    if len(idx_notes) > 1:
        lines.append("· " + idx_notes[1])

    board_names = [n for n, _ in ctx.top_boards[:4]]
    theme_names = list(ctx.sector_themes)
    board_blob = "、".join(theme_names or board_names[:3]) or "当日行业榜前列"
    lines.append(
        f"· 板块侧：东财行业榜前列含「{board_blob}」等，"
        "Top12 里同链条个股占多席时，说明主线偏硬科技/资源上游，不是纯小票乱飞"
    )

    industries = [
        ctx.industry_map.get(str(s.code).zfill(6), _infer_archetype(s, "")[0])
        for s in group
    ]
    uniq = list(dict.fromkeys(industries))
    if len(uniq) >= 2:
        lines.append(
            f"· 本帖三只分属不同链条（{' / '.join(uniq[:3])}）——同日上榜但驱动不同，"
            "不宜当成一个板块无脑捆绑"
        )
    peer = _peer_mover_in_top12(group, ctx)
    if peer:
        chg = _stock_change_pct(peer)
        lines.append(
            f"· 榜内参照：{peer.name}（{str(peer.code).zfill(6)}）同日约 {_format_pct(chg or 0)}，"
            "可用来对照本帖三只相对板块是领涨还是跟风"
        )
    return "\n".join(lines)


def _hot_sample_block(group: list[SectorSampleStock], ctx: GubaHotEnrichment) -> str:
    lines = ["【盘面样本（仅结构观察，非建议）】"]
    for stock in group:
        chg = _stock_change_pct(stock)
        rank = _stock_rank(stock)
        industry = ctx.industry_map.get(str(stock.code).zfill(6), "")
        label, chain, watch = _infer_archetype(stock, industry)
        chg_s = _format_pct(chg) if chg is not None else "—"
        if chg is not None and chg >= 5:
            tail = f"偏{label}领涨辨识度；看次日能否仍压过板块均值"
        elif chg is not None and chg < 0 and rank <= 5:
            tail = f"「高讨论+收跌」——若后续人气仍前5而跌幅收敛，更像分歧消化"
        else:
            tail = f"与{label}热度同向；看链条是否持续有跟风"
        lines.append(
            f"{format_guba_topic(stock)}：人气第{rank}，{chg_s}，{tail}。"
        )
    return "\n".join(lines)


def _hot_verify_block(group: list[SectorSampleStock], ctx: GubaHotEnrichment) -> str:
    topics = "、".join(format_guba_topic(s) for s in group)
    wd = ctx.next_trade_weekday
    weak_leader = next(
        (s for s in group if (_stock_change_pct(s) or 0) < 0 and _stock_rank(s) <= 5),
        None,
    )
    lines = [
        "【向后看·3个验证点】",
        f"1. 东财人气：{topics} 能否连续 2 日留在 Top12"
        + (f"（尤其 {format_guba_topic(weak_leader)} 能否「价稳榜在」）" if weak_leader else "")
        + "。",
        f"2. 板块溢价：三只相对各自行业指数是否仍强；{wd}竞价与首小时量价是否与人气一致。",
    ]
    theme0 = ctx.sector_themes[0] if ctx.sector_themes else "主线板块"
    lines.append(
        f"3. 证伪：若 {theme0} 退潮但三只仍高位换手，更偏短线情绪；"
        "若主线继续强而本帖弱票仍弱，说明资金在链内「弃弱留强」。"
    )
    return "\n".join(lines)


@dataclass(frozen=True)
class GubaSectorPost:
    title: str
    body: str
    trade_label: str
    themes: tuple[str, ...]
    stocks: tuple[SectorSampleStock, ...]

    @property
    def full_text(self) -> str:
        return f"【标题】\n{self.title}\n\n【正文】\n{self.body}"


@dataclass(frozen=True)
class GubaSplitPost:
    """东财单条动态：标题与正文分开交付，每帖个股话题 ≤ guba_max_stocks_per_post()。"""

    index: int
    total: int
    label: str
    title: str
    body: str
    stocks: tuple[SectorSampleStock, ...] = ()

    @property
    def full_text(self) -> str:
        return f"【标题】\n{self.title}\n\n【正文】\n{self.body}"


def guba_max_stocks_per_post() -> int:
    """东财单帖 $话题$ 上限（默认 3）。"""
    try:
        return max(1, min(3, int(os.getenv("WECHAT_MP_GUBA_MAX_STOCKS_PER_POST", "3"))))
    except ValueError:
        return 3


def guba_stock_count() -> int:
    try:
        return max(3, min(4, int(os.getenv("WECHAT_MP_GUBA_STOCK_N", "4"))))
    except ValueError:
        return 4


def guba_mode() -> str:
    """hot12=东财人气 Top12 拆 4 帖（默认）；sector=行业链 sector 同源。"""
    raw = os.getenv("WECHAT_MP_GUBA_MODE", "hot12").strip().lower()
    if raw in ("hot", "hot_stock", "top12"):
        return "hot12"
    return raw or "hot12"


def guba_hot_stock_total() -> int:
    try:
        return max(3, min(20, int(os.getenv("WECHAT_MP_GUBA_HOT_N", "12"))))
    except ValueError:
        return 12


def guba_posts_per_day() -> int:
    try:
        return max(1, min(6, int(os.getenv("WECHAT_MP_GUBA_POSTS", "4"))))
    except ValueError:
        return 4


def guba_exchange_suffix(code: str) -> str:
    c = str(code).split(".")[0].zfill(6)
    if c.startswith(("60", "68")):
        return "SH"
    if c.startswith(("00", "30")):
        return "SZ"
    if c.startswith(("83", "87", "92")):
        return "BJ"
    return "SZ"


def format_guba_topic(stock: SectorSampleStock) -> str:
    code = str(stock.code).split(".")[0].zfill(6)
    name = re.sub(r"\s+", "", (stock.name or code).strip())
    return f"${name}({guba_exchange_suffix(code)}{code})$"


def _guba_title_topics_complete(title: str) -> bool:
    """标题内每个 $话题$ 须完整闭合，禁止出现半段代码。"""
    if "$" not in title:
        return True
    tags = re.findall(r"\$[^$]+\([A-Z]{2}\d{6}\)\$", title)
    return len(tags) * 2 == title.count("$")


def _short_theme_pair(theme_names: list[str], *, max_len: int = 10) -> str:
    names = [re.sub(r"\s+", "", (t or "").strip()) for t in theme_names[:2] if t]
    if not names:
        return "盘面"
    if len(names) == 1:
        return names[0][:max_len]
    a, b = names[0], names[1]
    pair = f"{a}+{b}"
    if len(pair) <= max_len:
        return pair
    return f"{a[:4]}+{b[:4]}"


def _pick_title_stocks(
    stocks: list[SectorSampleStock],
    theme_names: list[str],
) -> list[SectorSampleStock]:
    """标题优先两链各 1 只领涨；凑不齐再按列表顺序补。"""
    from scripts.tools.wechat_mp_sector_stocks import theme_matches

    picks: list[SectorSampleStock] = []
    for th in theme_names[:2]:
        for s in stocks:
            if s in picks:
                continue
            if theme_matches(s.theme, th) or s.theme == th:
                picks.append(s)
                break
    for s in stocks:
        if len(picks) >= 2:
            break
        if s not in picks:
            picks.append(s)
    return picks


def compose_guba_title(
    trade_label: str,
    theme_names: list[str],
    stocks: list[SectorSampleStock],
    *,
    max_len: int = GUBA_TITLE_MAX,
) -> str:
    """东财标题 ≤36 字：宁可少放话题，也不截断 $简称(SH/SZ代码)$。"""
    picks = _pick_title_stocks(stocks, theme_names)
    themes_short = _short_theme_pair(theme_names)
    for n in (2, 1):
        if len(picks) < n:
            continue
        topics = " ".join(format_guba_topic(s) for s in picks[:n])
        for tmpl in (
            f"{trade_label}｜{themes_short}共振 {topics}",
            f"{trade_label}｜{themes_short} {topics}",
            f"{trade_label}｜{topics}",
            f"{trade_label} {topics}",
        ):
            cand = tmpl.strip()
            if len(cand) <= max_len and _guba_title_topics_complete(cand):
                return cand
    if picks:
        one = format_guba_topic(picks[0])
        for prefix in (f"{trade_label}｜{themes_short} ", f"{trade_label} "):
            cand = (prefix + one).strip()
            if len(cand) <= max_len and _guba_title_topics_complete(cand):
                return cand
    return trade_label[:max_len]


def _board_theme_chg(theme_names: list[str]) -> dict[str, str]:
    """主题名 → 板块涨幅描述（如「约+9%」）。"""
    out: dict[str, str] = {}
    try:
        from scripts.tools.wechat_mp_sector_stocks import theme_matches
        from scripts.tools.fetch_eastmoney_quotes import fetch_hot_industry_board_rows_opencli

        rows = fetch_hot_industry_board_rows_opencli(
            top_n=max(12, len(theme_names) * 4), close_browser=True
        )
    except Exception:
        return out
    for row in rows or []:
        sector = str(row.get("sector") or row.get("f14") or "").strip()
        chg = row.get("sector_chg")
        if chg is None:
            continue
        for th in theme_names:
            if th in out:
                continue
            if theme_matches(sector, th) or theme_matches(th, sector):
                try:
                    out[th] = f"约{float(chg):+.1f}%".replace("+-", "-")
                except (TypeError, ValueError):
                    out[th] = f"约{chg}%"
    return out


def _index_hook_line() -> str:
    try:
        from scripts.tools.daily_briefing_report import fetch_market_indices

        lines = fetch_market_indices()
    except Exception:
        return ""
    parts: list[str] = []
    for line in lines[:3]:
        m = re.search(r"(上证|深证|创业板[^:]*|沪深300)[^:]*:\s*([\d.]+)\s*\([^,]+,\s*([+-]?[\d.]+%)\)", line)
        if m:
            parts.append(f"{m.group(1)}{m.group(3)}")
    breadth = ""
    for line in lines:
        if "上涨" in line and "下跌" in line:
            breadth = line.strip()
            break
    hook = "，".join(parts)
    if breadth:
        hook = f"{hook}；{breadth}" if hook else breadth
    return hook


def _stock_fact_line(stock: SectorSampleStock) -> str:
    detail = (stock.detail or "").strip()
    if detail:
        return detail
    src = (stock.source or "观察").strip()
    return f"{src}样本，仅结构观察"


def _group_stocks_by_theme(
    stocks: list[SectorSampleStock],
    themes: list[str],
) -> list[tuple[str, list[SectorSampleStock]]]:
    buckets: dict[str, list[SectorSampleStock]] = {t: [] for t in themes}
    other: list[SectorSampleStock] = []
    for s in stocks:
        th = (s.theme or "").strip()
        placed = False
        for t in themes:
            if th == t or t in th or th in t:
                buckets[t].append(s)
                placed = True
                break
        if not placed:
            other.append(s)
    groups: list[tuple[str, list[SectorSampleStock]]] = []
    for t in themes:
        if buckets[t]:
            groups.append((t, buckets[t]))
    if other:
        groups.append(("相关样本", other))
    return groups


def _unique_guba_topic_count(text: str) -> int:
    return len(set(re.findall(r"\$[^$]+\([A-Z]{2}\d{6}\)\$", text)))


def _stock_from_topic_tag(tag: str) -> SectorSampleStock | None:
    m = re.match(r"\$([^$]+)\(([A-Z]{2})(\d{6})\)\$", tag.strip())
    if not m:
        return None
    return SectorSampleStock(
        code=m.group(3),
        name=m.group(1),
        source="盘面样本",
        theme="",
        detail="",
    )


def _build_single_theme_guba_body(
    *,
    trade_label: str,
    theme_name: str,
    group: list[SectorSampleStock],
    chg: str,
    index_line: str = "",
) -> str:
    topic_blob = "、".join(format_guba_topic(s) for s in group)
    chg_bit = f"{theme_name}{chg}" if chg else theme_name
    first_para = f"{topic_blob} 所在链条，{trade_label}{chg_bit}。"
    if index_line:
        first_para += index_line

    why_block = (
        f"{theme_name}{(' ' + chg) if chg else ''}偏行业主线，"
        "与盘面需对照指数风格看。"
    )
    chain_block = (
        f"{theme_name}：上游资源/制造 - 中游加工 - 下游应用与定价；看量价是否同步。"
    )
    sample_lines = [f"{theme_name}链："]
    for s in group:
        sample_lines.append(f"{format_guba_topic(s)}：{_stock_fact_line(s)}。")
    sample_block = "\n".join(sample_lines)

    verify_topics = "、".join(format_guba_topic(s) for s in group)
    verify_block = (
        "【向后看·3个验证点】\n"
        f"1. 东财行业榜：{theme_name}能否连续上榜。\n"
        f"2. {verify_topics} 相对各自板块溢价是否收敛。\n"
        "3. 若指数仍强但该板块跌出榜前五，则共振更偏短线定价。"
    )

    return "\n\n".join(
        [
            first_para,
            "【为什么现在看】\n" + why_block,
            "【产业链怎么拆】\n" + chain_block,
            "【盘面样本（仅结构观察）】\n" + sample_block,
            verify_block,
            GUBA_CTA_A,
            GUBA_DISCLAIMER,
        ]
    )


def _build_guba_splits_from_parts(
    *,
    trade_label: str,
    theme_names: list[str],
    stocks: list[SectorSampleStock],
    chg_map: dict[str, str],
    index_line: str = "",
) -> list[GubaSplitPost]:
    """按行业链拆帖，每帖个股话题不超过东财上限。"""
    max_per = guba_max_stocks_per_post()
    groups = _group_stocks_by_theme(stocks, theme_names[:2])
    chunks: list[tuple[str, list[SectorSampleStock]]] = []
    for theme_label, group in groups:
        capped = group[:max_per]
        if not capped:
            continue
        if len(group) > max_per:
            for i in range(0, len(group), max_per):
                chunks.append((theme_label, group[i : i + max_per]))
        else:
            chunks.append((theme_label, capped))

    if not chunks:
        fallback = stocks[:max_per]
        label = theme_names[0] if theme_names else "盘面"
        chunks = [(label, fallback)]

    total = len(chunks)
    splits: list[GubaSplitPost] = []
    for idx, (theme_label, group) in enumerate(chunks, 1):
        chg = chg_map.get(theme_label, "")
        title = compose_guba_title(trade_label, [theme_label], group)
        body = _build_single_theme_guba_body(
            trade_label=trade_label,
            theme_name=theme_label,
            group=group,
            chg=chg,
            index_line=index_line if idx == 1 else "",
        )
        splits.append(
            GubaSplitPost(
                index=idx,
                total=total,
                label=theme_label,
                title=title,
                body=body,
                stocks=tuple(group),
            )
        )
    return splits


def format_guba_splits_text(splits: list[GubaSplitPost]) -> str:
    parts: list[str] = []
    for sp in splits:
        parts.append(f"=== 帖{sp.index}/{sp.total} · {sp.label} ===")
        parts.append(f"【标题】\n{sp.title}")
        parts.append(f"【正文】\n{sp.body}")
    return "\n\n".join(parts) + "\n"


def guba_splits_to_combined_post(
    splits: list[GubaSplitPost],
    *,
    trade_label: str,
    theme_names: list[str],
    stocks: list[SectorSampleStock],
) -> GubaSectorPost:
    """合并多帖为单条 GubaSectorPost（草稿箱 / 备忘录兼容）。"""
    if len(splits) == 1:
        sp = splits[0]
        return GubaSectorPost(
            title=sp.title,
            body=sp.body,
            trade_label=trade_label,
            themes=tuple(theme_names),
            stocks=tuple(stocks),
        )
    if guba_mode() == "hot12":
        title = f"{trade_label}｜人气Top12"[:GUBA_TITLE_MAX]
    else:
        title = compose_guba_title(trade_label, theme_names, stocks)
    body = "\n\n".join(
        f"--- 帖{sp.index}/{sp.total} · {sp.label} ---\n{sp.body}" for sp in splits
    )
    return GubaSectorPost(
        title=title,
        body=body,
        trade_label=trade_label,
        themes=tuple(theme_names),
        stocks=tuple(stocks),
    )


def split_guba_post_from_body(post: GubaSectorPost) -> list[GubaSplitPost]:
    """从旧版合并稿或缓存正文按「XX链：」拆成多帖（无 stocks 元数据时）。"""
    trade_label = post.trade_label
    chg_map: dict[str, str] = {}
    for line in post.body.splitlines():
        m = re.match(r"^(.+?)\s+(约[+-]?[\d.]+%)偏行业主线", line.strip())
        if m:
            chg_map[m.group(1).strip()] = m.group(2)

    index_line = ""
    for line in post.body.splitlines():
        if line.strip().startswith("$") and "所在链条" in line:
            tail = line.split("。", 1)
            if len(tail) > 1 and ("上证" in tail[1] or "深证" in tail[1]):
                index_line = tail[1]
            break

    in_sample = False
    current_theme: str | None = None
    theme_stocks: dict[str, list[SectorSampleStock]] = {}
    for line in post.body.splitlines():
        s = line.strip()
        if s.startswith("【盘面样本"):
            in_sample = True
            continue
        if in_sample and s.startswith("【"):
            break
        if not in_sample:
            continue
        if s.endswith("链："):
            current_theme = s[:-2].strip()
            theme_stocks.setdefault(current_theme, [])
            continue
        if current_theme and s.startswith("$"):
            tag = re.match(r"(\$[^$]+\([A-Z]{2}\d{6}\)\$)", s)
            if tag:
                st = _stock_from_topic_tag(tag.group(1))
                if st:
                    theme_stocks[current_theme].append(
                        SectorSampleStock(
                            code=st.code,
                            name=st.name,
                            source=st.source,
                            theme=current_theme,
                            detail=s.split("：", 1)[-1].rstrip("。"),
                        )
                    )

    if not theme_stocks:
        return [
            GubaSplitPost(
                index=1,
                total=1,
                label="合并稿",
                title=post.title,
                body=post.body,
            )
        ]

    chunks: list[tuple[str, list[SectorSampleStock]]] = []
    max_per = guba_max_stocks_per_post()
    for theme_label, group in theme_stocks.items():
        for i in range(0, len(group), max_per):
            chunks.append((theme_label, group[i : i + max_per]))

    total = len(chunks)
    splits: list[GubaSplitPost] = []
    for idx, (theme_label, group) in enumerate(chunks, 1):
        chg = chg_map.get(theme_label, "")
        title = compose_guba_title(trade_label, [theme_label], group)
        body = _build_single_theme_guba_body(
            trade_label=trade_label,
            theme_name=theme_label,
            group=group,
            chg=chg,
            index_line=index_line if idx == 1 else "",
        )
        splits.append(
            GubaSplitPost(
                index=idx,
                total=total,
                label=theme_label,
                title=title,
                body=body,
                stocks=tuple(group),
            )
        )
    return splits


def resolve_guba_splits(*, edition: str | None = "close") -> list[GubaSplitPost]:
    use_cache = os.getenv("WECHAT_MP_GUBA_USE_CACHE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    if use_cache:
        cached = load_guba_splits_from_cache()
        if cached:
            print(f"OK 东财股吧拆帖 · 沿用缓存 {GUBA_OUTPUT_PATH}", file=sys.stderr)
            return cached
    splits = build_guba_split_posts(edition=edition)
    return splits


def _theme_stock_count(stocks: list[SectorSampleStock], theme: str) -> int:
    from scripts.tools.wechat_mp_sector_stocks import theme_matches

    return sum(
        1
        for s in stocks
        if theme_matches(s.theme, theme) or s.theme == theme
    )


def _theme_keywords(theme: str) -> list[str]:
    t = re.sub(r"\s+", "", (theme or "").strip())
    if not t:
        return []
    kws = [t]
    for frag in re.split(r"[+及与/]", t):
        if len(frag) >= 2:
            kws.append(frag)
    if len(t) >= 4:
        kws.append(t[:4])
    return list(dict.fromkeys(kws))


def _stock_matches_theme_loose(
    *,
    theme: str,
    name: str,
    industry: str,
) -> bool:
    from scripts.tools.wechat_mp_sector_stocks import theme_matches

    if theme_matches(industry, theme) or theme_matches(theme, industry):
        return True
    blob = f"{name}{industry}"
    return any(kw in blob for kw in _theme_keywords(theme) if len(kw) >= 2)


def _supplement_stocks(
    stocks: list[SectorSampleStock],
    theme_names: list[str],
    *,
    board_rows: list[dict],
    hot_rows: list[Any],
    industry_map: dict[str, str],
    target: int,
    board_constituents: dict[str, list[dict]] | None = None,
) -> list[SectorSampleStock]:
    """补满 3～4 只：双主线时尽量每链 2 只（领涨 + 人气/选股）。"""
    from scripts.tools.wechat_mp_sector_stocks import theme_matches

    seen = {str(s.code).zfill(6) for s in stocks}
    out = list(stocks)
    per_theme = 2 if len(theme_names) >= 2 else target

    def try_add(
        code: str,
        name: str,
        source: str,
        theme: str,
        detail: str = "",
        *,
        theme_cap: int | None = None,
    ) -> bool:
        if len(out) >= target:
            return False
        c = str(code).split(".")[0].zfill(6)
        n = re.sub(r"\s+", "", (name or "").strip())
        if not re.fullmatch(r"\d{6}", c) or c in seen or not n:
            return False
        from scripts.tools.wechat_mp_hot_stocks import is_hot_stock_eligible

        if not is_hot_stock_eligible(c, n):
            return False
        cap = theme_cap if theme_cap is not None else per_theme
        if _theme_stock_count(out, theme) >= cap:
            return False
        seen.add(c)
        out.append(
            SectorSampleStock(code=c, name=n, source=source, theme=theme, detail=detail)
        )
        return True

    def fill_theme(th: str) -> None:
        while _theme_stock_count(out, th) < per_theme and len(out) < target:
            added = False
            for row in board_rows or []:
                sector = str(row.get("sector") or "").strip()
                if not theme_matches(sector, th) and not theme_matches(th, sector):
                    continue
                chg = row.get("leader_chg")
                detail = f"领涨{chg}%" if chg is not None else "板块样本"
                if try_add(
                    str(row.get("code") or row.get("leader_code") or ""),
                    str(row.get("leader_name") or ""),
                    "行业领涨",
                    th,
                    detail,
                ):
                    added = True
            for row in hot_rows or []:
                code = getattr(row, "code", None) or (
                    row.get("code") if isinstance(row, dict) else ""
                )
                name = getattr(row, "name", None) or (
                    row.get("name") if isinstance(row, dict) else ""
                )
                industry = industry_map.get(str(code).zfill(6), "")
                if not _stock_matches_theme_loose(
                    theme=th, name=str(name), industry=industry
                ):
                    continue
                chg = getattr(row, "change_pct", None)
                if chg is None and isinstance(row, dict):
                    chg = row.get("change_pct")
                rank = getattr(row, "rank", None) or (
                    row.get("rank") if isinstance(row, dict) else ""
                )
                detail = f"人气榜第{rank}" if rank else "人气观察"
                if chg is not None:
                    detail += f" 涨跌{chg}%"
                if try_add(str(code), str(name), "人气观察", th, detail):
                    added = True
            board_code = ""
            for brow in board_rows or []:
                sector = str(brow.get("sector") or "").strip()
                if theme_matches(sector, th) or theme_matches(th, sector):
                    board_code = str(brow.get("board_code") or "").strip()
                    break
            if board_code and _theme_stock_count(out, th) < per_theme:
                rows = (board_constituents or {}).get(board_code) or []
                for row in rows:
                    chg = row.get("change_pct")
                    detail = f"涨跌{chg}%" if chg is not None else "板块跟风"
                    if try_add(
                        str(row.get("code") or ""),
                        str(row.get("name") or ""),
                        "板块跟风",
                        th,
                        detail,
                    ):
                        added = True
                        if _theme_stock_count(out, th) >= per_theme:
                            break
            if not added:
                break

    for th in theme_names[:2]:
        fill_theme(th)

    if len(out) < target:
        try:
            from scripts.tools.wechat_mp_hot_stocks import load_wechat_top5_hot_picks
            from scripts.tools.selection_watchlist import load_wechat_top5_selection_picks

            picks = []
            try:
                _, picks, _ = load_wechat_top5_hot_picks(top_n=12)
            except Exception:
                _, picks, _ = load_wechat_top5_selection_picks(top_n=12)
            for p in picks:
                if len(out) >= target:
                    break
                industry = industry_map.get(p.code, "")
                th = next(
                    (t for t in theme_names if theme_matches(industry, t)),
                    theme_names[0] if theme_names else "主线",
                )
                try_add(
                    p.code,
                    p.name or p.code,
                    "选股观察",
                    th,
                    f"收盘{p.change_pct}%",
                    theme_cap=per_theme,
                )
        except Exception:
            pass

    # 最后兜底：放宽每链上限，优先凑满 target
    if len(out) < target:
        for row in board_rows or []:
            if len(out) >= target:
                break
            sector = str(row.get("sector") or "").strip()
            th = next((t for t in theme_names if theme_matches(sector, t)), None)
            if not th:
                continue
            try_add(
                str(row.get("code") or row.get("leader_code") or ""),
                str(row.get("leader_name") or ""),
                "行业领涨",
                th,
                f"领涨{row.get('leader_chg')}%"
                if row.get("leader_chg") is not None
                else "板块样本",
                theme_cap=target,
            )
        for row in hot_rows or []:
            if len(out) >= target:
                break
            code = getattr(row, "code", None) or (
                row.get("code") if isinstance(row, dict) else ""
            )
            name = getattr(row, "name", None) or (
                row.get("name") if isinstance(row, dict) else ""
            )
            industry = industry_map.get(str(code).zfill(6), "")
            th = next(
                (
                    t
                    for t in theme_names
                    if _stock_matches_theme_loose(
                        theme=t, name=str(name), industry=industry
                    )
                ),
                None,
            )
            if not th:
                continue
            try_add(str(code), str(name), "人气观察", th, "人气补充", theme_cap=target)

    return out[:target]


def _collect_guba_sector_context(*, edition: str | None = "close") -> dict[str, Any]:
    report = discover_sector_hot_themes(edition=edition)
    themes = pick_focus_themes(report, edition=edition)
    theme_names = [t.name for t in themes if t.name] or ["盘面结构"]
    trade_date = resolve_sector_trade_date(report)
    trade_label = format_sector_trade_label(trade_date, edition=edition)

    board_rows: list[dict] = []
    board_constituents: dict[str, list[dict]] = {}
    hot_rows: list[Any] = []
    industry_map: dict[str, str] = {}
    try:
        from scripts.tools.fetch_eastmoney_quotes import (
            _close_browser_if,
            fetch_hot_industry_board_rows_opencli,
            fetch_industry_board_constituents,
        )

        board_rows = fetch_hot_industry_board_rows_opencli(top_n=32, close_browser=False)
        for row in board_rows:
            bc = str(row.get("board_code") or "").strip()
            if bc and bc not in board_constituents:
                board_constituents[bc] = fetch_industry_board_constituents(
                    bc, top_n=12, close_browser=False, reset_browser=False
                )
        _close_browser_if(True)
    except Exception:
        pass
    if os.getenv("WECHAT_MP_SECTOR_HOT_STOCKS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    ):
        try:
            from scripts.tools.wechat_mp_hot_stocks import fetch_hot_stock_rows

            hot_rows = fetch_hot_stock_rows(top_n=24)
        except Exception:
            pass
    try:
        from scripts.tools.portfolio_db import load_industry_map

        industry_map = load_industry_map()
    except Exception:
        pass

    os.environ["WECHAT_MP_SECTOR_SAMPLE_MAX"] = str(guba_stock_count())
    os.environ["WECHAT_MP_SECTOR_SAMPLES_PER_THEME"] = "2"
    stocks = collect_sector_sample_stocks(
        theme_names,
        board_rows=board_rows,
        hot_rows=hot_rows,
        industry_map=industry_map,
    )
    stocks = _supplement_stocks(
        stocks,
        theme_names,
        board_rows=board_rows,
        hot_rows=hot_rows,
        industry_map=industry_map,
        target=guba_stock_count(),
        board_constituents=board_constituents,
    )

    chg_map = _board_theme_chg(theme_names)
    index_line = _index_hook_line()
    return {
        "trade_label": trade_label,
        "theme_names": theme_names,
        "stocks": stocks,
        "chg_map": chg_map,
        "index_line": index_line,
    }


def _hot_row_to_sample(row: Any) -> SectorSampleStock:
    rank = int(getattr(row, "rank", 0) or 0)
    code = str(getattr(row, "code", "") or "").zfill(6)
    name = re.sub(r"\s+", "", str(getattr(row, "name", "") or code).strip())
    chg = getattr(row, "change_pct", None)
    detail = f"人气第{rank}位" if rank else "东财人气榜"
    if chg is not None:
        try:
            detail += f"，涨跌{float(chg):+.2f}%".replace("+-", "-")
        except (TypeError, ValueError):
            pass
    return SectorSampleStock(
        code=code,
        name=name,
        source="东财人气榜",
        theme=f"Top{rank}" if rank else "人气",
        detail=detail,
    )


def compose_hot_guba_title(
    trade_label: str,
    rank_lo: int,
    rank_hi: int,
    stocks: list[SectorSampleStock],
    *,
    max_len: int = GUBA_TITLE_MAX,
) -> str:
    tag = f"Top{rank_lo}-{rank_hi}"
    for n in (2, 1):
        if len(stocks) < n:
            continue
        topics = " ".join(format_guba_topic(s) for s in stocks[:n])
        for tmpl in (
            f"{trade_label}｜人气{tag} {topics}",
            f"{trade_label}｜{tag} {topics}",
            f"{trade_label} {topics}",
        ):
            cand = tmpl.strip()
            if len(cand) <= max_len and _guba_title_topics_complete(cand):
                return cand
    return f"{trade_label}｜人气{tag}"[:max_len]


def _build_hot_stock_guba_body(
    *,
    trade_label: str,
    rank_lo: int,
    rank_hi: int,
    group: list[SectorSampleStock],
    ctx: GubaHotEnrichment,
) -> str:
    intro = _hot_intro_paragraph(
        trade_label=trade_label,
        rank_lo=rank_lo,
        rank_hi=rank_hi,
        group=group,
        ctx=ctx,
    )
    return "\n\n".join(
        [
            intro,
            _hot_why_block(group, ctx),
            _hot_structure_block(group, ctx),
            _hot_sample_block(group, ctx),
            _hot_verify_block(group, ctx),
            GUBA_CTA_A,
            GUBA_DISCLAIMER,
        ]
    )


def build_guba_hot_stock_splits(*, edition: str | None = "close") -> list[GubaSplitPost]:
    """东财人气 TopN → 4 帖 × 3 只 $话题$（默认 Top12）。"""
    from scripts.tools.wechat_mp_hot_stocks import fetch_hot_stock_rows

    total = guba_hot_stock_total()
    per_post = guba_max_stocks_per_post()
    n_posts = guba_posts_per_day()
    need = min(total, n_posts * per_post)

    rows = fetch_hot_stock_rows(top_n=max(total, need))
    if len(rows) < per_post:
        import time

        time.sleep(2)
        rows = fetch_hot_stock_rows(top_n=max(total, need))
    samples = [_hot_row_to_sample(r) for r in rows[:need]]
    if len(samples) < per_post:
        raise RuntimeError(
            f"东财人气榜可用 {len(samples)} 只（需至少 {per_post}），请检查 OpenCLI"
        )

    ctx = _collect_guba_hot_enrichment(rows[:need], edition=edition)

    trade_date = datetime.now(TZ).date()
    try:
        from scripts.tools.wechat_mp_sector_article import format_sector_trade_label

        trade_label = format_sector_trade_label(trade_date, edition=edition)
    except Exception:
        trade_label = f"{trade_date.month}月{trade_date.day}日收盘"

    splits: list[GubaSplitPost] = []
    chunks: list[list[SectorSampleStock]] = []
    for i in range(n_posts):
        chunk = samples[i * per_post : (i + 1) * per_post]
        if chunk:
            chunks.append(chunk)

    total_posts = len(chunks)
    for idx, group in enumerate(chunks, 1):
        ranks = [
            int(re.sub(r"\D", "", s.theme) or 0)
            for s in group
            if (s.theme or "").startswith("Top")
        ]
        rank_lo = min(ranks) if ranks else (idx - 1) * per_post + 1
        rank_hi = max(ranks) if ranks else rank_lo + len(group) - 1
        label = f"人气Top{rank_lo}-{rank_hi}"
        title = compose_hot_guba_title(trade_label, rank_lo, rank_hi, group)
        body = _build_hot_stock_guba_body(
            trade_label=trade_label,
            rank_lo=rank_lo,
            rank_hi=rank_hi,
            group=group,
            ctx=ctx,
        )
        splits.append(
            GubaSplitPost(
                index=idx,
                total=total_posts,
                label=label,
                title=title,
                body=body,
                stocks=tuple(group),
            )
        )
    return splits


def build_guba_sector_split_posts(*, edition: str | None = "close") -> list[GubaSplitPost]:
    """sector 行业链 → 拆帖（每帖 ≤3 个 $话题$）。"""
    ctx = _collect_guba_sector_context(edition=edition)
    return _build_guba_splits_from_parts(
        trade_label=ctx["trade_label"],
        theme_names=ctx["theme_names"],
        stocks=ctx["stocks"],
        chg_map=ctx["chg_map"],
        index_line=ctx["index_line"],
    )


def build_guba_split_posts(*, edition: str | None = "close") -> list[GubaSplitPost]:
    """生成东财拆帖列表（每帖 ≤3 个 $话题$）。"""
    if guba_mode() == "hot12":
        return build_guba_hot_stock_splits(edition=edition)
    return build_guba_sector_split_posts(edition=edition)


def build_guba_sector_post(*, edition: str | None = "close") -> GubaSectorPost:
    splits = build_guba_split_posts(edition=edition)
    if not splits:
        raise RuntimeError("无股吧拆帖")
    trade_label = (
        splits[0].title.split("｜", 1)[0].strip()
        if "｜" in splits[0].title
        else splits[0].title[:12]
    )
    theme_names = [sp.label for sp in splits]
    stocks = [s for sp in splits for s in sp.stocks]
    return guba_splits_to_combined_post(
        splits,
        trade_label=trade_label,
        theme_names=theme_names,
        stocks=stocks,
    )


def pinned_notes_title(*, folder: str | None = None) -> str:
    """固定备忘录标题，每日覆盖同一条，避免在列表里找新 note。"""
    folder = (folder or os.getenv("WECHAT_MP_GUBA_NOTES_FOLDER") or "东财股吧").strip()
    pin = (os.getenv("WECHAT_MP_GUBA_NOTES_PIN") or "最新待发").strip() or "最新待发"
    return f"{folder}·{pin}"


def write_mac_notes(
    title: str,
    body: str,
    *,
    folder: str | None = None,
) -> str:
    """写入 Mac「备忘录」固定条目（覆盖更新）；返回 note 标题。"""
    note_title = pinned_notes_title(folder=folder)
    header = f"【{title}】\n\n"
    note_body = header + body if not body.lstrip().startswith("【") else body

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".txt", delete=False
    ) as tf:
        tf.write(note_body)
        body_path = tf.name

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    # 先唤醒 Notes，再覆盖固定标题（不每日新建，避免 iCloud/列表卡顿）
    subprocess.run(["open", "-ga", "Notes"], check=False, capture_output=True, timeout=15)
    script = f'''
set bodyPath to POSIX file "{body_path}"
set noteTitle to "{esc(note_title)}"
set noteBody to (read bodyPath as «class utf8»)
tell application "Notes"
    activate
    try
        set theNote to first note whose name is noteTitle
        set body of theNote to noteBody
    on error
        make new note with properties {{name:noteTitle, body:noteBody}}
    end try
end tell
'''
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=45,
        )
    finally:
        Path(body_path).unlink(missing_ok=True)
    return note_title


def _parse_guba_title_body_block(lines: list[str]) -> tuple[str, str] | None:
    title = ""
    body = ""
    section: str | None = None
    buf: list[str] = []
    for line in lines:
        s = line.strip()
        if s == "【标题】":
            if section == "title":
                title = "\n".join(buf).strip()
            buf = []
            section = "title"
            continue
        if s == "【正文】":
            if section == "title":
                title = "\n".join(buf).strip()
            buf = []
            section = "body"
            continue
        if section in ("title", "body"):
            buf.append(line)
    if section == "body":
        body = "\n".join(buf).strip()
    if title and body:
        return title, body
    return None


def load_guba_splits_from_cache(*, max_age_hours: int = 36) -> list[GubaSplitPost] | None:
    """读取拆帖缓存（=== 帖N/M · 主题 ===）；旧版单帖则现场拆分。"""
    if not GUBA_OUTPUT_PATH.is_file():
        return None
    try:
        age_h = (datetime.now(TZ).timestamp() - GUBA_OUTPUT_PATH.stat().st_mtime) / 3600
        if age_h > max_age_hours:
            return None
        text = GUBA_OUTPUT_PATH.read_text(encoding="utf-8")
    except OSError:
        return None

    if "=== 帖" not in text:
        parsed = _parse_guba_title_body_block(text.splitlines())
        if not parsed:
            return None
        title, body = parsed
        trade_label = title.split("｜", 1)[0].strip() if "｜" in title else title[:12]
        legacy = GubaSectorPost(
            title=title,
            body=body,
            trade_label=trade_label,
            themes=(),
            stocks=(),
        )
        return split_guba_post_from_body(legacy)

    splits: list[GubaSplitPost] = []
    current_meta: re.Match[str] | None = None
    block_lines: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^=== 帖(\d+)/(\d+) · (.+?) ===$", line.strip())
        if m:
            if current_meta is not None:
                parsed = _parse_guba_title_body_block(block_lines)
                if parsed:
                    splits.append(
                        GubaSplitPost(
                            index=int(current_meta.group(1)),
                            total=int(current_meta.group(2)),
                            label=current_meta.group(3).strip(),
                            title=parsed[0],
                            body=parsed[1],
                        )
                    )
            current_meta = m
            block_lines = []
            continue
        if current_meta is not None:
            block_lines.append(line)

    if current_meta is not None:
        parsed = _parse_guba_title_body_block(block_lines)
        if parsed:
            splits.append(
                GubaSplitPost(
                    index=int(current_meta.group(1)),
                    total=int(current_meta.group(2)),
                    label=current_meta.group(3).strip(),
                    title=parsed[0],
                    body=parsed[1],
                )
            )
    return splits or None


def load_guba_post_from_cache(*, max_age_hours: int = 36) -> GubaSectorPost | None:
    """读取 output/wechat_mp_guba_latest.txt（当日备份），避免重复拉行情。"""
    splits = load_guba_splits_from_cache(max_age_hours=max_age_hours)
    if splits:
        trade_label = splits[0].title.split("｜", 1)[0].strip() if "｜" in splits[0].title else splits[0].title[:12]
        themes = tuple(sp.label for sp in splits)
        stocks = tuple(s for sp in splits for s in sp.stocks)
        return guba_splits_to_combined_post(
            splits,
            trade_label=trade_label,
            theme_names=list(themes),
            stocks=list(stocks),
        )

    if not GUBA_OUTPUT_PATH.is_file():
        return None
    try:
        age_h = (datetime.now(TZ).timestamp() - GUBA_OUTPUT_PATH.stat().st_mtime) / 3600
        if age_h > max_age_hours:
            return None
        text = GUBA_OUTPUT_PATH.read_text(encoding="utf-8")
    except OSError:
        return None
    parsed = _parse_guba_title_body_block(text.splitlines())
    if not parsed:
        return None
    title, body = parsed
    trade_label = title.split("｜", 1)[0].strip() if "｜" in title else title[:12]
    return GubaSectorPost(
        title=title,
        body=body,
        trade_label=trade_label,
        themes=(),
        stocks=(),
    )


def _resolve_guba_post(*, edition: str | None = "close") -> GubaSectorPost:
    use_cache = os.getenv("WECHAT_MP_GUBA_USE_CACHE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    if use_cache:
        cached = load_guba_post_from_cache()
        if cached is not None:
            print(f"OK 东财股吧 · 沿用缓存 {GUBA_OUTPUT_PATH}", file=sys.stderr)
            return cached
    return build_guba_sector_post(edition=edition)


def guba_copy_safe_text(text: str) -> str:
    """股吧复制用：去掉不可见字符、替换易乱码符号，保留中文标点。"""
    import unicodedata

    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    for old, new in (
        ("→", "-"),
        ("->", "-"),
        ("｜", "|"),
        ("·", "."),
        ("…", "..."),
        ("♡", ""),
        ("【", "["),
        ("】", "]"),
        ("\u00a0", " "),
        ("\ufeff", ""),
    ):
        text = text.replace(old, new)
    return text


def render_guba_copy_html(body: str) -> str:
    """历史兼容：股吧稿已改纯文本 content；保留供单测。"""
    return body


def build_guba_draft_article(*, edition: str | None = "close") -> dict[str, str]:
    """公众号 guba 槽：纯文本 content（无 HTML），避免 mp 编辑器复制乱码。"""
    post = _resolve_guba_post(edition=edition)
    GUBA_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    GUBA_OUTPUT_PATH.write_text(post.full_text + "\n", encoding="utf-8")

    draft_title = guba_copy_safe_text(f"东财股吧·{post.trade_label}")[:32]
    digest = guba_copy_safe_text(post.title[:128])
    raw_body = (
        "复制到东财 App 发动态（先复制[标题]，再复制[正文]）。\n\n"
        f"[标题]\n{post.title}\n\n"
        f"[正文]\n{post.body}"
    )
    body = guba_copy_safe_text(raw_body.strip())
    # 微信 API 接受纯文本 content；勿包 <p>/<br>，否则 mp 网页编辑器复制易乱码。
    content = body

    from scripts.tools.wechat_mp_content import _author
    from scripts.tools.wechat_mp_monetization import comment_settings
    from scripts.tools.wechat_mp_seo import clip_digest

    article: dict[str, str] = {
        "title": draft_title,
        "author": _author(),
        "digest": clip_digest(digest),
        "body_text": body,
        "content": content,
        "article_type": "news",
    }
    article.update({k: str(v) for k, v in comment_settings().items()})
    return article


def sync_guba_sector_to_wechat_draft(*, edition: str | None = "close") -> GubaSectorPost:
    """股吧正文 → 公众号草稿箱 guba 槽。"""
    from scripts.tools.wechat_mp_client import get_material_image_meta, pick_thumb_for_draft_kind
    from scripts.tools.wechat_mp_draft_slots import upsert_draft_article

    article = build_guba_draft_article(edition=edition)
    post = _resolve_guba_post(edition=edition)
    thumb, terr = pick_thumb_for_draft_kind("sector")
    if terr or not thumb:
        thumb, terr = pick_thumb_for_draft_kind("market")
    if terr or not thumb:
        raise RuntimeError(f"股吧草稿封面失败: {terr}")
    media_id, action, err = upsert_draft_article("guba", article, thumb_media_id=thumb)
    if err:
        raise RuntimeError(err)
    meta, _ = get_material_image_meta(thumb or "")
    cover = meta.get("name") if meta else ""
    print(
        f"OK 东财股吧 → 草稿箱[guba] {action} media_id={media_id} · {article['title']} · 封面={cover}",
        file=sys.stderr,
    )
    return post


def sync_guba_sector_delivery(
    *,
    edition: str | None = "close",
    splits: list[GubaSplitPost] | None = None,
) -> GubaSectorPost:
    """生成股吧拆帖 → 本地备份 + 公众号 guba 槽 +（可选）飞书 / 备忘录。"""
    if splits is None:
        splits = resolve_guba_splits(edition=edition)
    post = guba_splits_to_combined_post(
        splits,
        trade_label=splits[0].title.split("｜", 1)[0].strip()
        if splits and "｜" in splits[0].title
        else (splits[0].title[:12] if splits else ""),
        theme_names=[sp.label for sp in splits],
        stocks=[s for sp in splits for s in sp.stocks],
    )
    GUBA_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    GUBA_OUTPUT_PATH.write_text(format_guba_splits_text(splits), encoding="utf-8")
    print(
        f"OK 东财股吧 {len(splits)} 帖 → {GUBA_OUTPUT_PATH}",
        file=sys.stderr,
    )

    if os.getenv("WECHAT_MP_GUBA_DRAFT", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    ):
        try:
            sync_guba_sector_to_wechat_draft(edition=edition)
        except Exception as exc:
            print(f"WARN 股吧草稿箱失败（已保留 {GUBA_OUTPUT_PATH}）: {exc}", file=sys.stderr)

    if os.getenv("WECHAT_MP_GUBA_NOTES", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        try:
            note_name = write_mac_notes(post.title, post.full_text)
            print(f"OK 东财股吧 → 备忘录「{note_name}」", file=sys.stderr)
        except Exception as exc:
            print(f"WARN 备忘录写入失败: {exc}", file=sys.stderr)
            _guba_fallback_delivery(post.full_text)

    if os.getenv("WECHAT_MP_GUBA_FEISHU", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        try:
            push_guba_splits_to_feishu(splits)
        except Exception as exc:
            print(f"WARN 股吧飞书推送失败: {exc}", file=sys.stderr)

    if os.getenv("WECHAT_MP_GUBA_WECHAT", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        try:
            push_guba_post_to_wechat(post)
        except Exception as exc:
            print(f"WARN 股吧微信推送失败: {exc}", file=sys.stderr)
    return post


def sync_guba_sector_to_mac_notes(*, edition: str | None = "close") -> GubaSectorPost:
    """兼容旧名：等同 sync_guba_sector_delivery。"""
    return sync_guba_sector_delivery(edition=edition)


def format_guba_text_for_wechat_push(text: str) -> str:
    """微信机器人会吞半角 $，推送用全角＄并在文首说明替换。"""
    header = (
        "东财股吧·待发\n"
        "说明：微信会吃掉半角美元符；下文话题用全角＄包裹。"
        "粘贴到东财前，全文把全角＄替换成半角美元符即可。\n\n"
    )
    return header + text.replace("$", "＄")


def push_guba_post_to_wechat(post: GubaSectorPost) -> None:
    """纯文本推送到 wechat-acp（半角 $ 可能被吞，见 format_guba_text_for_wechat_push）。"""
    from scripts.tools.wechat_acp_push_text import send_wechat_acp_text

    msg = format_guba_text_for_wechat_push(post.full_text)
    ids = send_wechat_acp_text(msg)
    print(f"OK 东财股吧 → 微信 segments={len(ids)}", file=sys.stderr)


def push_guba_splits_to_feishu(splits: list[GubaSplitPost]) -> None:
    """飞书分帖推送：每帖标题、正文各一条，半角 $话题$ 可原样复制到东财。"""
    import time

    from stock_ai.notify import send_to_lark

    if not splits:
        raise RuntimeError("无股吧拆帖可推送")

    sent = 0
    for sp in splits:
        tag = f"帖{sp.index}/{sp.total}·{sp.label}"
        ok_title = send_to_lark(sp.title, prefix="")
        time.sleep(0.3)
        ok_body = send_to_lark(sp.body, prefix="")
        time.sleep(0.3)
        if not ok_title or not ok_body:
            raise RuntimeError(f"飞书 webhook 发送失败: {tag}")
        sent += 2
    print(f"OK 东财股吧 → 飞书 {len(splits)} 帖 × 2 条 = {sent} 消息", file=sys.stderr)


def push_guba_post_to_feishu(post: GubaSectorPost) -> None:
    """兼容旧调用：合并稿现场拆帖后分条推飞书。"""
    splits = (
        _build_guba_splits_from_parts(
            trade_label=post.trade_label,
            theme_names=list(post.themes) or ["盘面"],
            stocks=list(post.stocks),
            chg_map=_board_theme_chg(list(post.themes)),
            index_line="",
        )
        if post.stocks
        else split_guba_post_from_body(post)
    )
    push_guba_splits_to_feishu(splits)


def _guba_fallback_delivery(body: str) -> None:
    """Notes 不可用时：剪贴板 + 用文本编辑打开备份文件。"""
    try:
        subprocess.run(["pbcopy"], input=body, text=True, check=False, timeout=10)
        print("OK 东财股吧正文已复制到剪贴板（备忘录失败兜底）", file=sys.stderr)
    except OSError as exc:
        print(f"WARN 剪贴板兜底失败: {exc}", file=sys.stderr)
    try:
        subprocess.run(["open", "-e", str(GUBA_OUTPUT_PATH)], check=False, timeout=15)
    except OSError:
        pass


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="sector → 东财股吧 → 草稿箱 guba 槽 / 备忘录")
    parser.add_argument("--edition", default="close")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写入")
    parser.add_argument("--no-draft", action="store_true", help="不推公众号草稿箱")
    parser.add_argument("--notes", action="store_true", help="同时写 Mac 备忘录")
    parser.add_argument("--no-wechat", action="store_true", help="不推送到微信")
    parser.add_argument("--feishu", action="store_true", help="推送到飞书")
    parser.add_argument("--no-feishu", action="store_true", help="不推送到飞书")
    args = parser.parse_args()
    if args.no_draft:
        os.environ["WECHAT_MP_GUBA_DRAFT"] = "0"
    if args.notes:
        os.environ["WECHAT_MP_GUBA_NOTES"] = "1"
    if args.no_wechat:
        os.environ["WECHAT_MP_GUBA_WECHAT"] = "0"
    if args.feishu:
        os.environ["WECHAT_MP_GUBA_FEISHU"] = "1"
    if args.no_feishu:
        os.environ["WECHAT_MP_GUBA_FEISHU"] = "0"
    splits = resolve_guba_splits(edition=args.edition)
    print(format_guba_splits_text(splits))
    if not args.dry_run:
        sync_guba_sector_delivery(edition=args.edition, splits=splits)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
