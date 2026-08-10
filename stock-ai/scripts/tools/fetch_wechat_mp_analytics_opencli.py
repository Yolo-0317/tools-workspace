#!/usr/bin/env python3
"""微信公众号后台「内容分析」— OpenCLI 浏览器抓取（需 URL 带 token 或已登录会话）。

流量来源 **只读页面** `.highcharts-container`（流量分析 · 流量来源柱图）。
须先把 `.weui-desktop-picker__date-range` 设到目标区间（单日 begin=end）。

示例：
  uv run python -m scripts.tools.fetch_wechat_mp_analytics_opencli \\
    --token 227362845 \\
    --begin-date 2026-06-15 --end-date 2026-06-15

  # 逐日从页面柱图拉推荐占比
  uv run python -m scripts.tools.fetch_wechat_mp_analytics_opencli \\
    --token 227362845 --daily-series --series-begin 2026-06-02 --series-end 2026-06-16
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
TZ = ZoneInfo("Asia/Shanghai")

from scripts.tools.fetch_eastmoney_quotes import (  # noqa: E402
    _close_browser_if,
    _eval_js,
    _open_page,
    _run_opencli,
)
from scripts.tools.wechat_mp_analytics_page import (  # noqa: E402
    CLICK_PERIOD_TAG_JS,
    EXTRACT_HIGHCHARTS_TRAFFIC_JS,
    SET_FLOW_DATE_RANGE_JS,
    parse_ymd,
)

DAILY_URL = (
    "https://mp.weixin.qq.com/misc/appmsganalysis?action=report&type=daily_v2&lang=zh_CN"
)

PERIOD_LABELS = {
    "yesterday": "昨日",
    "7d": "最近 7 天",
    "30d": "最近 30 天",
}

CHECK_LOGIN_JS = r"""
JSON.stringify((() => {
  const t = (document.body.innerText || "");
  return { logged_in: !t.includes("请重新登录"), url: location.href };
})())
"""

EXTRACT_OVERVIEW_JS = r"""
JSON.stringify((() => {
  const text = document.body.innerText || "";
  const pick = (re) => { const x = text.match(re); return x ? x[1] : null; };
  const flowPicker = [...document.querySelectorAll(".weui-desktop-picker__date-range")].find((p) => {
    let el = p;
    for (let i = 0; i < 20 && el; i++) {
      if ((el.innerText || "").includes("流量分析")) return true;
      el = el.parentElement;
    }
    return false;
  });
  const flowDates = flowPicker
    ? [...flowPicker.querySelectorAll("input")].map((i) => i.value)
    : [];
  return {
    account: pick(/通知中心\s*\n([^\n]+)/),
    period_label: pick(/(昨日|最近\s*7\s*天|最近\s*30\s*天)/),
    overview: {
      read: pick(/数据概况[\s\S]{0,220}?阅读\s*(\d+)/) || pick(/阅读\s*(\d+)/),
      share: pick(/分享\s*(\d+)/),
      comment: pick(/留言\s*(\d+)/),
      read_users_total: pick(/阅读总人数[：:]\s*([\d,]+)/),
    },
    flow_date_range: flowDates.length === 2 ? { start: flowDates[0], end: flowDates[1] } : null,
  };
})())
"""

EXTRACT_ARTICLES_JS = r"""
JSON.stringify((() => {
  const text = document.body.innerText || "";
  const articles = [];
  const rowRe = /([^\t\n]+?)\s+发表时间：(\d{4}\/\d{2}\/\d{2})\s+(\d+)\s+([\d.]+%)/g;
  let rm;
  while ((rm = rowRe.exec(text)) !== null) {
    const title = rm[1].replace(/\s+/g, " ").trim();
    if (title.length < 6 || title.includes("内容标题")) continue;
    articles.push({
      title,
      publish_date: rm[2].replace(/\//g, "-"),
      read_users: parseInt(rm[3], 10),
      read_share_pct: rm[4],
    });
  }
  const uniq = [];
  const seen = new Set();
  for (const a of articles) {
    const k = a.title + a.publish_date;
    if (seen.has(k)) continue;
    seen.add(k);
    uniq.push(a);
  }
  return uniq.slice(0, 30);
})())
"""

EXTRACT_DETAIL_JS = r"""
JSON.stringify((() => {
  const text = document.body.innerText || "";
  const pick = (re) => { const x = text.match(re); return x ? x[1] : null; };
  const traffic = {};
  const block = text.split("阅读渠道构成")[1] || "";
  const re = /([\d.]+%)\s*(朋友圈|聊天会话|公众号主页|其它|搜一搜|公众号消息|推荐)/g;
  let m;
  while ((m = re.exec(block)) !== null) traffic[m[2]] = m[1];
  return {
    page: "detail",
    url: location.href,
    title: pick(/已通知内容\s*([^\n]+)/) || pick(/\n([^\n]{8,60})\n本页面仅统计/),
    read_users: pick(/阅读\s*(\d+)\s*人/),
    avg_read_minutes: pick(/平均阅读时长\s*([\d.]+)\s*分钟/),
    finish_read_rate: pick(/完读率\s*([\d.]+)%/),
    follow_after_read: pick(/阅读后关注\s*(\d+)\s*人/),
    share_users: pick(/分享\s*(\d+)\s*人/),
    traffic_sources_pct: traffic,
  };
})())
"""

FIND_DETAIL_LINKS_JS = r"""
JSON.stringify((() => {
  return [...document.querySelectorAll("a")]
    .filter(a => (a.innerText||"").trim() === "详情" && a.href.includes("detailpage"))
    .map(a => ({ href: a.href, context: (a.closest("tr")?.innerText || "").slice(0, 120) }))
    .slice(0, 12);
})())
"""


def _append_token(url: str, token: str) -> str:
    if not token:
        return url
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    q["token"] = [token]
    query = "&".join(f"{k}={v[0]}" for k, v in q.items())
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{query}&lang=zh_CN"


def _token_from_url(url: str) -> str:
    return (parse_qs(urlparse(url).query).get("token") or [""])[0]


def _wait_login(*, timeout_sec: float) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        raw = _eval_js(CHECK_LOGIN_JS, timeout=20)
        try:
            st = json.loads(raw)
        except json.JSONDecodeError:
            time.sleep(2)
            continue
        if st.get("logged_in"):
            return True
        time.sleep(3)
    return False


def _load_json(raw: str, *, label: str) -> Any:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} JSON 解析失败: {raw[:500]}") from exc
    return data


def _apply_period_tag(period: str) -> dict[str, Any]:
    label = PERIOD_LABELS.get(period, period)
    raw = _eval_js(f"({CLICK_PERIOD_TAG_JS})({json.dumps(label)})", timeout=30)
    st = _load_json(raw, label="period_click")
    _run_opencli(["browser", "wait", "time", "3"], timeout=10)
    return st


def _apply_flow_date_range(start: date, end: date) -> dict[str, Any]:
    js = f"({SET_FLOW_DATE_RANGE_JS})({json.dumps(start.isoformat())}, {json.dumps(end.isoformat())})"
    raw = _eval_js(js, timeout=180)
    return _load_json(raw, label="set_date_range")


def _extract_highcharts_traffic() -> dict[str, Any]:
    return _load_json(_eval_js(EXTRACT_HIGHCHARTS_TRAFFIC_JS, timeout=90), label="highcharts")


def fetch_daily_report(
    *,
    url: str,
    wait_login: float = 0,
    period: str | None = None,
    begin_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    _open_page(url, label="内容分析 daily_v2")
    _run_opencli(["browser", "wait", "time", "4"], timeout=10)
    if wait_login > 0 and not _wait_login(timeout_sec=wait_login):
        raise RuntimeError("未登录公众号后台，请在 OpenCLI 窗口扫码登录后重试")
    st = _load_json(_eval_js(CHECK_LOGIN_JS), label="login")
    if not st.get("logged_in"):
        raise RuntimeError(
            "页面显示未登录。请用带 token 的 analytics-url，或在 OpenCLI 浏览器中登录 mp.weixin.qq.com"
        )

    token = _token_from_url(url)
    date_range: dict[str, str] | None = None
    date_set_result: dict[str, Any] | None = None

    if period:
        date_set_result = {"period_tag": _apply_period_tag(period)}
        if period == "7d" and not begin_date:
            end_date = date.today()
            begin_date = end_date - timedelta(days=6)
    elif begin_date and end_date:
        date_set_result = _apply_flow_date_range(begin_date, end_date)
        date_range = {"start": begin_date.isoformat(), "end": end_date.isoformat()}

    highcharts = _extract_highcharts_traffic()
    source_api: dict[str, Any] | None = None

    overview = _load_json(_eval_js(EXTRACT_OVERVIEW_JS, timeout=60), label="overview")
    articles = _load_json(_eval_js(EXTRACT_ARTICLES_JS, timeout=60), label="articles")

    traffic_sources_pct: dict[str, str] = {}
    traffic_meta: dict[str, Any] = {"from": None}
    if isinstance(highcharts, dict) and highcharts.get("traffic_sources_pct"):
        traffic_sources_pct = dict(highcharts["traffic_sources_pct"])
        traffic_meta = {
            "from": "highcharts-container",
            "container_id": highcharts.get("container_id"),
            "paired": highcharts.get("paired"),
        }
    elif isinstance(source_api, dict) and source_api.get("traffic_sources_pct"):
        traffic_sources_pct = dict(source_api["traffic_sources_pct"])
        traffic_meta = {
            "from": "api",
            "total_read_uv": source_api.get("total_read_uv"),
            "source_breakdown": source_api.get("source_breakdown"),
            "api_url": source_api.get("url"),
        }

    return {
        "page": "daily_v2",
        "url": url,
        "account": overview.get("account"),
        "period_label": overview.get("period_label"),
        "date_range": date_range or overview.get("flow_date_range"),
        "date_set_result": date_set_result,
        "overview": overview.get("overview") or {},
        "traffic_sources_pct": traffic_sources_pct,
        "traffic_meta": traffic_meta,
        "highcharts_traffic": highcharts,
        "source_api": None,
        "articles": articles if isinstance(articles, list) else [],
    }


def fetch_daily_traffic_series_page(
    *,
    url: str,
    start: date,
    end: date,
    wait_login: float = 0,
) -> list[dict[str, Any]]:
    """逐日设流量 picker 为 D–D，读 highcharts 渠道占比（页面真源）。"""
    _open_page(url, label="内容分析 daily_v2")
    _run_opencli(["browser", "wait", "time", "4"], timeout=10)
    if wait_login > 0 and not _wait_login(timeout_sec=wait_login):
        raise RuntimeError("未登录公众号后台，请在 OpenCLI 窗口扫码登录后重试")
    st = _load_json(_eval_js(CHECK_LOGIN_JS), label="login")
    if not st.get("logged_in"):
        raise RuntimeError("页面显示未登录")

    rows: list[dict[str, Any]] = []
    d = start
    while d <= end:
        date_set = _apply_flow_date_range(d, d)
        hc = _extract_highcharts_traffic()
        if not (hc.get("traffic_sources_pct") or {}).get("推荐"):
            _run_opencli(["browser", "wait", "time", "2"], timeout=10)
            hc = _extract_highcharts_traffic()
        overview = _load_json(_eval_js(EXTRACT_OVERVIEW_JS, timeout=60), label="overview")
        ov = overview.get("overview") or {}
        pct_map = hc.get("traffic_sources_pct") or {}
        rows.append(
            {
                "date": d.isoformat(),
                "picker_dates": date_set.get("dates"),
                "picker_ok": date_set.get("ok"),
                "推荐": pct_map.get("推荐"),
                "traffic_sources_pct": pct_map,
                "read_users_total": ov.get("read_users_total"),
                "highcharts_ok": hc.get("ok"),
                "date_set_result": date_set,
            }
        )
        d += timedelta(days=1)
    return rows


def fetch_article_details(links: list[dict[str, Any]], *, max_n: int = 3) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in links[:max_n]:
        href = str(item.get("href") or "")
        if not href:
            continue
        _open_page(href, label="detail")
        _run_opencli(["browser", "wait", "time", "3"], timeout=10)
        detail = _load_json(_eval_js(EXTRACT_DETAIL_JS, timeout=60), label="detail")
        detail["list_context"] = item.get("context")
        out.append(detail)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenCLI 抓取公众号内容分析")
    parser.add_argument(
        "--analytics-url",
        default="",
        help="已登录后台 URL（含 token），默认 WECHAT_MP_ANALYTICS_URL 或 daily_v2",
    )
    parser.add_argument("--token", default="", help="mp 后台 token（可代替 URL 中的 token）")
    parser.add_argument("--wait-login", type=float, default=0, help="等待扫码登录秒数")
    parser.add_argument(
        "--period",
        choices=sorted(PERIOD_LABELS.keys()),
        default="",
        help="数据概况快捷标签：yesterday / 7d / 30d",
    )
    parser.add_argument("--begin-date", default="", help="流量分析日期范围起始 YYYY-MM-DD")
    parser.add_argument("--end-date", default="", help="流量分析日期范围结束 YYYY-MM-DD")
    parser.add_argument(
        "--daily-series",
        action="store_true",
        help="逐日从页面柱图拉渠道占比（须 --series-begin / --series-end）",
    )
    parser.add_argument("--series-begin", default="", help="daily-series 起始 YYYY-MM-DD")
    parser.add_argument("--series-end", default="", help="daily-series 结束 YYYY-MM-DD")
    parser.add_argument("--detail-top", type=int, default=3, help="抓取前 N 篇「详情」完读率等")
    parser.add_argument("-o", "--output", default="", help="输出 JSON 路径")
    parser.add_argument("--no-close-browser", action="store_true")
    args = parser.parse_args()

    import os

    url = (args.analytics_url or os.getenv("WECHAT_MP_ANALYTICS_URL") or DAILY_URL).strip()
    token = (args.token or os.getenv("WECHAT_MP_ADMIN_TOKEN") or _token_from_url(url) or "").strip()
    if token and "token=" not in url:
        url = _append_token(url, token)

    begin_date = parse_ymd(args.begin_date) if args.begin_date else None
    end_date = parse_ymd(args.end_date) if args.end_date else None
    if (begin_date and not end_date) or (end_date and not begin_date):
        parser.error("--begin-date 与 --end-date 需同时指定")

    series_begin = parse_ymd(args.series_begin) if args.series_begin else None
    series_end = parse_ymd(args.series_end) if args.series_end else None
    if args.daily_series:
        if not series_begin or not series_end:
            parser.error("--daily-series 须同时指定 --series-begin 与 --series-end")

    try:
        if args.daily_series:
            assert series_begin and series_end
            rows = fetch_daily_traffic_series_page(
                url=url,
                start=series_begin,
                end=series_end,
                wait_login=args.wait_login,
            )
            payload = {
                "fetched_at": datetime.now(TZ).isoformat(),
                "source": "mp.weixin.qq.com-opencli-page",
                "method": "highcharts-container per day",
                "series_begin": series_begin.isoformat(),
                "series_end": series_end.isoformat(),
                "days": rows,
            }
            out = Path(args.output) if args.output else ROOT / "output" / "wechat_mp_traffic_series_page.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            print(f"\n已写入 {out}", file=sys.stderr)
            return 0

        daily = fetch_daily_report(
            url=url,
            wait_login=args.wait_login,
            period=args.period or None,
            begin_date=begin_date,
            end_date=end_date,
        )
        links_raw = _eval_js(FIND_DETAIL_LINKS_JS, timeout=30)
        links = json.loads(links_raw) if links_raw else []
        details: list[dict[str, Any]] = []
        if args.detail_top > 0 and links:
            details = fetch_article_details(links, max_n=args.detail_top)

        payload = {
            "fetched_at": datetime.now(TZ).isoformat(),
            "source": "mp.weixin.qq.com-opencli",
            "daily": daily,
            "article_details": details,
        }
        out = Path(args.output) if args.output else ROOT / "output" / "wechat_mp_analytics_latest.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print(f"\n已写入 {out}", file=sys.stderr)
        return 0
    finally:
        _close_browser_if(not args.no_close_browser)


if __name__ == "__main__":
    raise SystemExit(main())
