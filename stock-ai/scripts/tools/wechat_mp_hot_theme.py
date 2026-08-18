#!/usr/bin/env python3
"""按交易日挖掘「当日热门行业/主题」（非写死科技词）。

**行业研究稿 `sector`（默认）**：OpenCLI 东财「行业板块」涨幅榜排名靠前项为主；
  不采用情绪周期/龙头池主线。失败时回退快讯+选股。

**标题钩子等（`discover_hot_themes`）**：仍可多源含情绪（`WECHAT_MP_HOT_THEME_EMOTION=0` 可关）。

供公众号 sector 稿选择当日主线。
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

TZ = ZoneInfo("Asia/Shanghai")

# 同进程内缓存东财行业榜，避免 sector + align 重复开浏览器
_SECTOR_BOARD_CACHE: tuple[str, list[ThemeScore]] | None = None


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def _emotion_themes_enabled() -> bool:
    return os.getenv("WECHAT_MP_HOT_THEME_EMOTION", "1").strip() not in {
        "0",
        "false",
        "no",
    }

# (keywords, 短标签用于标题, 单次命中加分)
_THEME_KEYWORD_RULES: tuple[tuple[tuple[str, ...], str, float], ...] = (
    (("半导体", "芯片", "光模块", "CPO", "硅光", "封测", "HBM", "算力", "存储"), "半导体", 1.4),
    (("原油", "油价", "布伦特", "OPEC", "油服", "炼化"), "油价", 1.3),
    (("黄金", "金价", "贵金属"), "黄金", 1.2),
    (("电力", "火电", "水电", "绿电", "电网"), "电力", 1.2),
    (("煤炭", "动力煤", "焦煤"), "煤炭", 1.2),
    (("地产", "房地产", "楼市"), "地产", 1.1),
    (("券商", "证券"), "券商", 1.1),
    (("银行", "降准", "LPR", "MLF"), "银行", 1.0),
    (("军工", "航天", "国防"), "军工", 1.1),
    (("医药", "创新药", "集采"), "医药", 1.1),
    (("消费", "白酒", "食品饮料"), "消费", 1.0),
    (("汽车", "新能源车", "锂电", "电池"), "新能源车", 1.2),
    (("钢铁", "有色", "铜", "铝", "稀土"), "有色", 1.1),
    (("化工", "磷化工", "氟化工"), "化工", 1.0),
    (("纺织", "服装", "轻工"), "轻工", 1.0),
    (("农业", "猪", "养殖"), "农业", 1.0),
    (("伊朗", "中东", "霍尔木兹", "以军"), "中东局势", 1.3),
    (("华为", "苹果链", "消费电子"), "华为链", 1.1),
    (("机器人", "人形"), "机器人", 1.1),
    (("数据要素", "信创", "软件"), "信创", 1.0),
)


@dataclass
class ThemeScore:
    name: str
    score: float = 0.0
    sources: list[str] = field(default_factory=list)

    def add(self, points: float, source: str) -> None:
        if points <= 0:
            return
        self.score += points
        if source not in self.sources:
            self.sources.append(source)


@dataclass
class HotThemeReport:
    trade_date: str
    edition: str
    themes: list[ThemeScore]
    primary: str
    title_tags: str
    research_hook: str
    fetched_at: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["themes"] = [asdict(t) for t in self.themes]
        return d


# 东财行业榜 OpenCLI 易误抓 Tab/导航（资金流、沪深京板块等），须过滤
_INVALID_SECTOR_BOARD_RE = re.compile(
    r"资金流|排行|沪深京|概念|地区|龙虎|"
    r"今日|5日|10日|板块榜|行业板块|"
    r"^板块$|^行业$|更多|全部|自选"
)


def _is_valid_sector_board_name(name: str) -> bool:
    n = re.sub(r"\s+", "", str(name or "").strip())
    if len(n) < 2 or len(n) > 12:
        return False
    if _INVALID_SECTOR_BOARD_RE.search(n):
        return False
    return True


def _fallback_sector_board_themes(*, top_n: int) -> list[ThemeScore]:
    """东财榜抓取失败或全是导航词时：用合并 Top5 所属行业 + 情绪主线回退。"""
    scores: dict[str, ThemeScore] = {}
    _collect_selection_themes(scores)
    try:
        from scripts.tools.portfolio_db import load_emotion_cycle_checklist

        bundle = load_emotion_cycle_checklist(checklist_slot="eod") or load_emotion_cycle_checklist()
        if bundle:
            hdr = bundle.get("header") or {}
            main = _normalize_theme_name(str(hdr.get("main_theme") or ""))
            if main and _is_valid_sector_board_name(main):
                _get(scores, main).add(5.0, "emotion_main_theme_fallback")
    except Exception:
        pass
    ranked = sorted(scores.values(), key=lambda t: (-t.score, t.name))
    ranked = [t for t in ranked if _is_valid_sector_board_name(t.name)]
    out: list[ThemeScore] = []
    for i, t in enumerate(ranked[:top_n]):
        out.append(
            ThemeScore(
                name=t.name,
                score=round(10.0 - i * 0.75, 2),
                sources=[*(t.sources or ["selection_fallback"]), "selection_fallback"],
            )
        )
    return out


def _normalize_theme_name(raw: str) -> str:
    s = re.sub(r"\s+", "", str(raw or "").strip())
    if not s or s in {"—", "-", "N/A", "未知", "nan"}:
        return ""
    for suffix in (
        "开采",
        "采选",
        "加工",
        "制造",
        "服务业",
        "服务",
        "行业",
        "产业",
        "Ⅱ",
        "Ⅲ",
    ):
        if len(s) > 3 and s.endswith(suffix):
            s = s[: -len(suffix)]
    return s[:12] if len(s) > 12 else s


def _bucket() -> dict[str, ThemeScore]:
    return {}


def _get(scores: dict[str, ThemeScore], name: str) -> ThemeScore:
    key = _normalize_theme_name(name)
    if not key:
        key = "盘面"
    if key not in scores:
        scores[key] = ThemeScore(name=key)
    return scores[key]


def _score_text_hits(
    scores: dict[str, ThemeScore],
    text: str,
    *,
    source: str,
    per_rule_cap: float = 2.0,
) -> None:
    blob = str(text or "")
    if not blob:
        return
    for keywords, label, weight in _THEME_KEYWORD_RULES:
        if any(kw in blob for kw in keywords):
            _get(scores, label).add(min(per_rule_cap, weight), source)


def _collect_emotion_themes(scores: dict[str, ThemeScore]) -> None:
    try:
        from scripts.tools.portfolio_db import load_emotion_cycle_checklist

        bundle = load_emotion_cycle_checklist(checklist_slot=os.getenv("WECHAT_MP_DRAGON_SLOT", "eod"))
        if not bundle:
            bundle = load_emotion_cycle_checklist()
        if not bundle:
            return
        hdr = bundle.get("header") or {}
        main = _normalize_theme_name(str(hdr.get("main_theme") or ""))
        if main:
            _get(scores, main).add(4.0, "emotion_main_theme")
        for row in bundle.get("dragon_items") or []:
            th = _normalize_theme_name(str(row.get("main_theme") or ""))
            if th:
                _get(scores, th).add(2.0, "emotion_dragon")
    except Exception:
        return


def _collect_news_themes(
    scores: dict[str, ThemeScore],
    *,
    edition: str,
) -> None:
    try:
        from scripts.tools.wechat_mp_market_edition import (
            load_top_news_for_edition,
            normalize_market_edition,
        )

        ed = normalize_market_edition(edition)
        items = load_top_news_for_edition(ed)
        for it in items[:12]:
            blob = f"{it.get('title') or ''} {it.get('summary') or ''}"
            _score_text_hits(scores, blob, source="macro_news", per_rule_cap=1.6)
    except Exception:
        return


def _collect_selection_themes(scores: dict[str, ThemeScore]) -> None:
    try:
        from scripts.tools.selection_results import merge_selection_strategies_df, pick_wechat_top5

        _, universe, _ = merge_selection_strategies_df()
        if universe is None or universe.empty:
            return
        top = pick_wechat_top5(universe, top_n=5)
        if top.empty or "所属行业" not in top.columns:
            return
        for _, row in top.iterrows():
            ind = _normalize_theme_name(str(row.get("所属行业") or ""))
            if ind:
                _get(scores, ind).add(2.5, "selection_top5")
    except Exception:
        return


def _collect_hot_sectors_opencli(scores: dict[str, ThemeScore]) -> None:
    for t in _fetch_eastmoney_industry_board_themes():
        _get(scores, t.name).add(t.score, "eastmoney_industry_board")


def _trade_date_iso(now: datetime | None = None) -> str:
    now = now or datetime.now(TZ)
    try:
        from scripts.tools.selection_results import merge_selection_strategies_df

        trade_d, _, _ = merge_selection_strategies_df()
        return trade_d.isoformat()
    except Exception:
        return now.date().isoformat()


def _fetch_eastmoney_industry_board_themes(
    *,
    top_n: int | None = None,
) -> list[ThemeScore]:
    """东财行业板块页涨幅榜顺序（排名越靠前 score 越高）。"""
    global _SECTOR_BOARD_CACHE

    top_n = top_n if top_n is not None else _env_int("WECHAT_MP_HOT_INDUSTRY_TOP_N", 8)
    td = _trade_date_iso()
    if _SECTOR_BOARD_CACHE and _SECTOR_BOARD_CACHE[0] == td:
        return list(_SECTOR_BOARD_CACHE[1][:top_n])

    themes: list[ThemeScore] = []
    try:
        from scripts.tools.fetch_eastmoney_quotes import fetch_hot_industry_sectors_opencli

        names = fetch_hot_industry_sectors_opencli(top_n=top_n, close_browser=True)
        for i, raw in enumerate(names):
            display = str(raw).strip().replace("\n", "")
            name = _normalize_theme_name(display) or display[:12]
            if not name or not _is_valid_sector_board_name(name):
                continue
            themes.append(
                ThemeScore(
                    name=name,
                    score=round(10.0 - i * 0.75, 2),
                    sources=["eastmoney_industry_board"],
                )
            )
    except Exception:
        themes = []

    if not themes:
        themes = _fallback_sector_board_themes(top_n=top_n)

    _SECTOR_BOARD_CACHE = (td, themes)
    return themes


def discover_sector_hot_themes(
    *,
    edition: str | None = "close",
    now: datetime | None = None,
) -> HotThemeReport:
    """行业研究稿专用：主线 = 东财行业板块榜前列（不用龙头/情绪主线）。"""
    from scripts.tools.wechat_mp_market_edition import normalize_market_edition

    now = now or datetime.now(TZ)
    ed = normalize_market_edition(edition)
    ranked = _fetch_eastmoney_industry_board_themes()

    if not ranked:
        scores: dict[str, ThemeScore] = {}
        _collect_news_themes(scores, edition=ed)
        _collect_selection_themes(scores)
        ranked = sorted(scores.values(), key=lambda t: (-t.score, t.name))

    if not ranked:
        primary = "盘面结构"
        title_tags = "盘面结构"
        research_hook = "东财行业榜未获取，仅作盘面结构观察（观察口径）。"
    else:
        primary = ranked[0].name
        from scripts.tools.wechat_mp_market_titles import join_market_title_tags

        tag_parts: list[str] = []
        for t in ranked[:2]:
            label = t.name if len(t.name) <= 6 else t.name[:6]
            if label and label not in tag_parts:
                tag_parts.append(label)
        title_tags = join_market_title_tags(tag_parts) if tag_parts else primary
        src = ranked[0].sources[0] if ranked[0].sources else "eastmoney_industry_board"
        research_hook = (
            f"行业主线取自东财行业板块涨幅榜排名靠前项（当前第一：{primary}，来源 {src}）。"
            "写作时拆产业链与量价，勿给买卖建议。"
        )

    return HotThemeReport(
        trade_date=_trade_date_iso(now),
        edition=ed,
        themes=ranked[:8],
        primary=primary,
        title_tags=title_tags[:14],
        research_hook=research_hook,
        fetched_at=now.isoformat(),
    )


def _collect_draft_blob_themes(scores: dict[str, ThemeScore], blob: str) -> None:
    if blob.strip():
        _score_text_hits(scores, blob, source="draft_blob", per_rule_cap=1.2)


def discover_hot_themes(
    *,
    edition: str | None = "close",
    draft_blob: str = "",
    include_opencli: bool | None = None,
    now: datetime | None = None,
) -> HotThemeReport:
    """返回排序后的主题报告；primary / title_tags 用于标题与行业稿。"""
    from scripts.tools.wechat_mp_market_edition import normalize_market_edition

    now = now or datetime.now(TZ)
    ed = normalize_market_edition(edition)
    if include_opencli is None:
        include_opencli = os.getenv("WECHAT_MP_HOT_THEME_OPENCLI", "0").strip() in {
            "1",
            "true",
            "yes",
        }

    scores: dict[str, ThemeScore] = {}
    if _emotion_themes_enabled():
        _collect_emotion_themes(scores)
    _collect_news_themes(scores, edition=ed)
    _collect_selection_themes(scores)
    if include_opencli:
        _collect_hot_sectors_opencli(scores)
    _collect_draft_blob_themes(scores, draft_blob)

    ranked = sorted(scores.values(), key=lambda t: (-t.score, t.name))
    ranked = [t for t in ranked if t.score > 0]

    if not ranked:
        primary = "盘面结构"
        title_tags = "盘面结构"
        research_hook = "结合当日指数广度与成交额，拆解资金主攻方向（观察口径）。"
    else:
        primary = ranked[0].name
        from scripts.tools.wechat_mp_market_titles import join_market_title_tags

        tag_parts: list[str] = []
        for t in ranked[:3]:
            label = t.name
            if len(label) > 6:
                label = label[:6]
            if label and label not in tag_parts:
                tag_parts.append(label)
            if len(tag_parts) >= 2:
                break
        title_tags = join_market_title_tags(tag_parts) if tag_parts else primary
        research_hook = (
            f"当日资金与舆情共振方向偏向「{primary}」"
            f"（信号：{', '.join(ranked[0].sources[:4])}）。"
            "写作时拆产业链/代表股量价，勿给买卖建议。"
        )

    return HotThemeReport(
        trade_date=_trade_date_iso(now),
        edition=ed,
        themes=ranked[:8],
        primary=primary,
        title_tags=title_tags[:14],
        research_hook=research_hook,
        fetched_at=now.isoformat(),
    )


def format_title_tags(report: HotThemeReport, *, max_len: int = 14) -> str:
    tags = (report.title_tags or report.primary or "盘面").strip()
    return tags[:max_len]


def pick_focus_themes(
    report: HotThemeReport | None = None,
    *,
    max_themes: int = 2,
    min_score: float = 1.5,
    edition: str | None = "close",
    include_opencli: bool | None = None,
    from_sector_board: bool = True,
) -> list[ThemeScore]:
    """取 1～2 个行业主题。`from_sector_board=True`（默认）= 东财榜排名，不看龙头主线。"""
    if from_sector_board:
        report = report or discover_sector_hot_themes(edition=edition)
        cap = max(1, min(int(max_themes), 3))
        if report.themes:
            return report.themes[:cap]
        return [ThemeScore(name=report.primary or "盘面结构", score=1.0, sources=["fallback"])]

    report = report or discover_hot_themes(
        edition=edition,
        include_opencli=include_opencli,
    )
    cap = max(1, min(int(max_themes), 3))
    picked = [t for t in report.themes if t.score >= min_score]
    if not picked and report.themes:
        picked = [report.themes[0]]
    if not picked:
        return [ThemeScore(name=report.primary or "盘面结构", score=1.0, sources=["fallback"])]
    return picked[:cap]


def build_sector_context_blob(report: HotThemeReport) -> str:
    """供 sector 稿 / evening_align prompt 注入。"""
    lines = [
        "【数据日热门行业 · 东财行业板块涨幅榜排名（非龙头池主线）】",
        f"数据日（ISO）：{report.trade_date} · 主线：{report.primary}",
        f"标题钩子：{report.title_tags}",
        report.research_hook,
        "",
        "候选主题（分高→低）：",
    ]
    for t in report.themes[:6]:
        lines.append(f"- {t.name}（{t.score:.1f}）← {', '.join(t.sources)}")
    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="挖掘当日公众号热门行业/主题")
    parser.add_argument("--edition", default="close")
    parser.add_argument("--opencli", action="store_true", help="discover_hot_themes 时叠加东财榜")
    parser.add_argument(
        "--sector",
        action="store_true",
        help="行业稿口径：仅东财行业板块榜（默认推荐）",
    )
    parser.add_argument("-o", "--output", default="")
    args = parser.parse_args()

    if args.sector or os.getenv("WECHAT_MP_SECTOR_THEME_SOURCE", "opencli").strip() == "opencli":
        report = discover_sector_hot_themes(edition=args.edition)
    else:
        report = discover_hot_themes(edition=args.edition, include_opencli=args.opencli)
    payload = report.to_dict()
    payload["sector_context"] = build_sector_context_blob(report)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        from pathlib import Path

        Path(args.output).write_text(text, encoding="utf-8")
        print(f"已写入 {args.output}", flush=True)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
