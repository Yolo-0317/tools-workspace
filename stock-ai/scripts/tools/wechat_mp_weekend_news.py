#!/usr/bin/env python3
"""周日休市要闻：按需 OpenCLI 拉取周末快讯 + 东财热股榜逐股匹配（不依赖定时 sync）。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.fetch_eastmoney_macro_news import MacroNewsItem, _normalize_items
from scripts.tools.news_db import _enrich_news_pick, _normalize_href, news_item_has_stock_signal
from scripts.tools.news_sentiment import classify_news_sentiment
from scripts.tools.wechat_mp_hot_stocks import HotStockRow, fetch_hot_stock_rows

TZ = ZoneInfo("Asia/Shanghai")


def resolve_hot_stock_anchor_date(*, now: datetime | None = None) -> date:
    """休市日东财人气榜实为上一交易日收盘快照的数据日。"""
    from stock_ai.trading_calendar import latest_a_share_trade_date

    return latest_a_share_trade_date(on_or_before=(now or datetime.now(TZ)).date())


def format_hot_stock_anchor_label(anchor: date) -> str:
    return f"{anchor.month}月{anchor.day}日收盘"


def _weekday_cn(d: date) -> str:
    return "周" + "一二三四五六日"[d.weekday()]


@dataclass(frozen=True)
class NewsTimeContext:
    """热股 news 稿的时间口径（休市/收盘批次共用）。"""

    now: datetime
    anchor_date: date
    anchor_label: str
    anchor_weekday_cn: str
    today_weekday_cn: str
    next_trade_date: date
    next_trade_weekday_cn: str
    is_off_market: bool
    is_weekend_batch: bool

    @property
    def verify_auction_phrase(self) -> str:
        return f"{self.next_trade_weekday_cn}竞价"

    @property
    def verify_title_suffix(self) -> str:
        return f"{self.next_trade_weekday_cn}怎么验"

    @property
    def intro_lede(self) -> str:
        if self.is_off_market:
            return (
                f"按{self.anchor_weekday_cn}人气序扫一遍；周末消息少的票，"
                f"重点盯{self.next_trade_weekday_cn}竞价与首小时量价。"
            )
        return (
            "按收盘人气序扫一遍；消息少的票，"
            f"重点盯{self.next_trade_weekday_cn}竞价与首小时量价。"
        )

    @property
    def llm_date_rule(self) -> str:
        today = self.now.strftime("%Y-%m-%d")
        return (
            f"发稿日 {today} {self.today_weekday_cn}。"
            f"验证动作写 {self.next_trade_weekday_cn}竞价或首小时，"
            f"勿写已过去的{self.today_weekday_cn}竞价。"
        )


def build_news_time_context(*, now: datetime | None = None) -> NewsTimeContext:
    from stock_ai.trading_calendar import next_a_share_trade_date

    now = now or datetime.now(TZ)
    today = now.date()
    anchor = resolve_hot_stock_anchor_date(now=now)
    anchor_label = format_hot_stock_anchor_label(anchor)
    batch = os.getenv("WECHAT_MP_NEWS_BATCH", "").strip()
    is_weekend_batch = batch == "weekend"
    is_off_market = is_weekend_batch or batch != "evening" and _is_off_market(today)
    if batch == "evening":
        is_off_market = False
    next_trade = next_a_share_trade_date(on_or_after=today + timedelta(days=1))
    return NewsTimeContext(
        now=now,
        anchor_date=anchor,
        anchor_label=anchor_label,
        anchor_weekday_cn=_weekday_cn(anchor),
        today_weekday_cn=_weekday_cn(today),
        next_trade_date=next_trade,
        next_trade_weekday_cn=_weekday_cn(next_trade),
        is_off_market=is_off_market,
        is_weekend_batch=is_weekend_batch,
    )


def _is_off_market(d: date) -> bool:
    from stock_ai.trading_calendar import is_off_market_day

    return is_off_market_day(d)


def fix_stale_auction_weekday(text: str, ctx: NewsTimeContext) -> str:
    """收盘批次已过完当日竞价时，纠正 LLM 误写的「今周X竞价」。"""
    if not text or ctx.is_off_market:
        return text
    stale = f"{ctx.today_weekday_cn}竞价"
    fresh = ctx.verify_auction_phrase
    if stale in text and stale != fresh:
        return text.replace(stale, fresh)
    return text


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def weekend_hot_stock_count() -> int:
    return max(5, min(12, _env_int("WECHAT_MP_WEEKEND_HOT_N", 10)))


def weekend_news_hours() -> int:
    """周六+周日窗口（小时）。"""
    return max(24, min(96, _env_int("WECHAT_MP_WEEKEND_NEWS_HOURS", 48)))


def weekday_hot_stock_news_hours() -> int:
    """交易日收盘批次：回溯近若干小时快讯。"""
    return max(12, min(72, _env_int("WECHAT_MP_WEEKDAY_HOT_NEWS_HOURS", 36)))


def hot_stock_news_hours() -> int:
    """按批次 env（WECHAT_MP_NEWS_BATCH）或 HOT_STOCK_NEWS_HOURS 覆盖。"""
    override = (os.getenv("WECHAT_MP_HOT_STOCK_NEWS_HOURS") or "").strip()
    if override:
        return max(12, min(96, int(override)))
    batch = (os.getenv("WECHAT_MP_NEWS_BATCH") or "").strip()
    if batch == "weekend":
        return weekend_news_hours()
    if batch == "evening":
        return weekday_hot_stock_news_hours()
    return weekday_hot_stock_news_hours()


def weekend_kuaixun_pool_limit() -> int:
    return max(60, min(200, _env_int("WECHAT_MP_WEEKEND_KUAIXUN_LIMIT", 120)))


def _stock_name_variants(name: str) -> list[str]:
    n = (name or "").strip()
    if not n:
        return []
    out = [n]
    for suffix in ("股份有限公司", "股份", "集团", "控股", "科技", "A", "Ａ"):
        if n.endswith(suffix) and len(n) > len(suffix) + 1:
            short = n[: -len(suffix)].strip()
            if len(short) >= 2:
                out.append(short)
    return list(dict.fromkeys(out))


def _item_blob(item: dict[str, Any]) -> str:
    return f"{item.get('title') or ''} {item.get('summary') or ''}"


def _news_matches_stock(item: dict[str, Any], stock: HotStockRow) -> bool:
    blob = _item_blob(item)
    code = str(stock.code).zfill(6)
    if code in blob:
        return True
    for variant in _stock_name_variants(stock.name):
        if len(variant) >= 2 and variant in blob:
            return True
    return False


def _match_score(
    item: dict[str, Any],
    stock: HotStockRow,
    *,
    engagement: dict[str, dict[str, int]] | None,
) -> float:
    if not _news_matches_stock(item, stock):
        return -1.0
    title = str(item.get("title") or "")
    blob = _item_blob(item)
    score = 0.0
    for variant in _stock_name_variants(stock.name):
        if variant in title:
            score += 120.0
            break
        if variant in blob:
            score += 80.0
            break
    if str(stock.code).zfill(6) in title:
        score += 60.0
    href = _normalize_href(str(item.get("href") or ""))
    eng = (engagement or {}).get(href) or {}
    score += float(int(eng.get("comment") or 0) * 10 + int(eng.get("read") or 0))
    if news_item_has_stock_signal(item):
        score += 15.0
    return score


def _parse_news_time_md(time_str: str, *, now: datetime) -> datetime | None:
    raw = (time_str or "").strip()
    if not raw:
        return None
    for fmt in ("%m-%d %H:%M", "%m月%d日 %H:%M"):
        try:
            dt = datetime.strptime(raw, fmt).replace(tzinfo=TZ)
            return dt.replace(year=now.year)
        except ValueError:
            continue
    if raw.startswith("今天") or raw.startswith("昨日"):
        hm = re.search(r"(\d{1,2}):(\d{2})", raw)
        if hm:
            base = now.date()
            if raw.startswith("昨日"):
                base = base - timedelta(days=1)
            return datetime(
                base.year,
                base.month,
                base.day,
                int(hm.group(1)),
                int(hm.group(2)),
                tzinfo=TZ,
            )
    return None


def _in_weekend_window(time_str: str, *, now: datetime, hours: int) -> bool:
    parsed = _parse_news_time_md(time_str, now=now)
    if parsed is None:
        return True
    since = now - timedelta(hours=hours)
    return parsed >= since


def _macro_to_dict(item: MacroNewsItem) -> dict[str, Any]:
    title = item.title.strip()
    summary = (item.summary or "").strip()
    sentiment = classify_news_sentiment(title, summary)
    return {
        "href": _normalize_href(item.href),
        "title": title,
        "summary": summary,
        "news_time": item.time,
        "source": item.source,
        "sentiment": sentiment,
    }


def fetch_weekend_kuaixun_pool(
    *,
    now: datetime | None = None,
    hours: int | None = None,
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    """OpenCLI 拉东财 7×24，过滤周末窗口，不写入 MySQL。"""
    from scripts.tools.fetch_eastmoney_quotes import (
        fetch_kuaixun_engagement_opencli,
        fetch_macro_news_opencli,
    )

    now = now or datetime.now(TZ)
    hours = hours if hours is not None else weekend_news_hours()
    lim = limit if limit is not None else weekend_kuaixun_pool_limit()

    raw = fetch_macro_news_opencli(limit=lim, close_browser=False)
    engagement = fetch_kuaixun_engagement_opencli(limit=lim, close_browser=True)
    macro_items = _normalize_items(raw, default_source="kuaixun")

    pool: list[dict[str, Any]] = []
    for macro in macro_items:
        row = _macro_to_dict(macro)
        if _in_weekend_window(str(row.get("news_time") or ""), now=now, hours=hours):
            pool.append(row)
    if not pool and macro_items:
        pool = [_macro_to_dict(m) for m in macro_items[:lim]]
    return pool, engagement


def synthetic_display_title(stock: HotStockRow, *, ctx: NewsTimeContext | None = None) -> str:
    """周末/收盘无快讯时，按涨跌幅与人气位生成列表小标题（非模板句）。"""
    ctx = ctx or build_news_time_context()
    name = stock.name
    chg = stock.change_pct
    rank = stock.rank
    verify = ctx.verify_title_suffix
    if chg >= 9.5:
        perf = "涨停级收涨"
    elif chg >= 5:
        perf = f"大涨{chg:+.1f}%"
    elif chg <= -7:
        perf = f"重挫{chg:.1f}%"
    elif chg < -2:
        perf = f"回调{chg:.1f}%"
    elif chg > 2:
        perf = f"收涨{chg:+.1f}%"
    elif chg > 0:
        perf = "小幅上涨"
    elif chg < 0:
        perf = "小幅回落"
    else:
        perf = "高位换手"
    if rank == 1:
        return f"{name}人气榜首，{perf}{verify}"
    if rank <= 3:
        return f"榜{rank}{name}{perf}，休市后盯什么" if ctx.is_off_market else f"榜{rank}{name}{perf}，收盘后盯什么"
    return f"{name}{perf}，人气第{rank}位"


def _synthetic_item_for_stock(
    stock: HotStockRow,
    *,
    now: datetime,
    anchor: date,
    anchor_label: str,
    ctx: NewsTimeContext,
) -> dict[str, Any]:
    """热股榜上有名、无该股单独快讯时，写休市/收盘观察（读者向，不含流水线术语）。"""
    title = synthetic_display_title(stock, ctx=ctx)
    chg = stock.change_pct
    chg_txt = (
        f"{ctx.anchor_weekday_cn}收涨约 {chg:+.2f}%"
        if chg
        else f"{ctx.anchor_weekday_cn}成交活跃"
    )
    if ctx.is_off_market:
        context = "休市期间消息面相对安静，就着榜单聊下一交易日怎么验证"
    else:
        context = "就着收盘人气榜聊下一交易日怎么验证"
    summary = (
        f"东财人气榜第{stock.rank}位，{chg_txt}。"
        f"{context}：先看{ctx.verify_auction_phrase}是否还有资金接力，"
        f"再看首小时量价是否与人气一致。"
        f"具体催化仍看公司公告与行业动向，别单凭排名下注。"
    )
    return {
        "href": f"synthetic://hot-stock/{stock.code}",
        "title": title,
        "summary": summary,
        "news_time": now.strftime("%m-%d %H:%M"),
        "source": "hot-stock-map",
        "sentiment": classify_news_sentiment(title, summary),
        "matched_stock_code": stock.code,
        "matched_stock_name": stock.name,
        "matched_stock_rank": stock.rank,
        "matched_stock_change_pct": stock.change_pct,
        "hot_stock_anchor_date": anchor.isoformat(),
        "hot_stock_anchor_label": anchor_label,
        "synthetic": True,
    }


def match_hot_stocks_to_news(
    hot_rows: list[HotStockRow],
    pool: list[dict[str, Any]],
    *,
    engagement: dict[str, dict[str, int]] | None = None,
    now: datetime | None = None,
    anchor: date | None = None,
    anchor_label: str | None = None,
) -> list[dict[str, Any]]:
    """10 只热股各配 1 条快讯（优先标题含股名/代码）。"""
    now = now or datetime.now(TZ)
    anchor = anchor or resolve_hot_stock_anchor_date(now=now)
    anchor_label = anchor_label or format_hot_stock_anchor_label(anchor)
    ctx = build_news_time_context(now=now)
    used_hrefs: set[str] = set()
    out: list[dict[str, Any]] = []

    for stock in hot_rows:
        scored: list[tuple[float, dict[str, Any]]] = []
        for item in pool:
            href = _normalize_href(str(item.get("href") or ""))
            if not href or href in used_hrefs:
                continue
            sc = _match_score(item, stock, engagement=engagement)
            if sc >= 0:
                scored.append((sc, item))
        scored.sort(key=lambda x: (-x[0], str(x[1].get("news_time") or "")))

        pick: dict[str, Any]
        if scored:
            pick = dict(scored[0][1])
        else:
            pick = _synthetic_item_for_stock(
                stock, now=now, anchor=anchor, anchor_label=anchor_label, ctx=ctx
            )

        href = _normalize_href(str(pick.get("href") or ""))
        used_hrefs.add(href)
        pick = dict(pick)
        pick["matched_stock_code"] = stock.code
        pick["matched_stock_name"] = stock.name
        pick["matched_stock_rank"] = stock.rank
        pick["matched_stock_change_pct"] = stock.change_pct
        pick["hot_stock_anchor_date"] = anchor.isoformat()
        pick["hot_stock_anchor_label"] = anchor_label
        out.append(_enrich_news_pick(pick, engagement=engagement))

    return out


def load_weekend_hot_stock_news_items(
    *,
    now: datetime | None = None,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """周日批次入口：热股 TopN × 周末快讯，不依赖 macro_news 定时同步。"""
    now = now or datetime.now(TZ)
    n = top_n if top_n is not None else weekend_hot_stock_count()
    anchor = resolve_hot_stock_anchor_date(now=now)
    anchor_label = format_hot_stock_anchor_label(anchor)

    hot_rows = fetch_hot_stock_rows(top_n=max(n, 12))[:n]
    if not hot_rows:
        raise RuntimeError("东财热股榜为空，无法生成周末要闻")

    pool, engagement = fetch_weekend_kuaixun_pool(now=now)
    items = match_hot_stocks_to_news(
        hot_rows,
        pool,
        engagement=engagement,
        now=now,
        anchor=anchor,
        anchor_label=anchor_label,
    )
    if len(items) < max(3, n // 2):
        raise RuntimeError(
            f"周末要闻匹配不足（{len(items)}/{n}），请检查 OpenCLI 快讯或热股榜"
        )
    return items
