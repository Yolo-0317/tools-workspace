#!/usr/bin/env python3
"""微信公众号后台「内容分析」— OpenCLI 浏览器抓取（需 URL 带 token 或已登录会话）。

示例：
  uv run python -m scripts.tools.fetch_wechat_mp_analytics_opencli \\
    --analytics-url 'https://mp.weixin.qq.com/misc/appmsganalysis?action=report&type=daily_v2&token=...'
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
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

DAILY_URL = (
    "https://mp.weixin.qq.com/misc/appmsganalysis?action=report&type=daily_v2&lang=zh_CN"
)

CHECK_LOGIN_JS = r"""
JSON.stringify((() => {
  const t = (document.body.innerText || "");
  return { logged_in: !t.includes("请重新登录"), url: location.href };
})())
"""

EXTRACT_DAILY_JS = r"""
JSON.stringify((() => {
  const text = document.body.innerText || "";
  const traffic = {};
  const flowIdx = text.indexOf("流量来源");
  const flowBlock = flowIdx >= 0 ? text.slice(flowIdx, flowIdx + 1200) : "";
  const chartEnd = flowBlock.split("End of interactive chart.")[0] || "";
  const pcts = (chartEnd.match(/[\d.]+%/g) || []).filter(p => parseFloat(p) <= 100);
  const names = ["朋友圈","搜一搜","聊天会话","公众号主页","其它","公众号消息","推荐"];
  const present = names.filter(n => flowBlock.includes(n));
  for (let i = 0; i < present.length && i < pcts.length; i++) {
    traffic[present[i]] = pcts[i];
  }
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
  const pick = (re) => { const x = text.match(re); return x ? x[1] : null; };
  return {
    page: "daily_v2",
    url: location.href,
    account: pick(/通知中心\s*\n([^\n]+)/) || null,
    period_label: pick(/(昨日|最近\s*7\s*天|最近\s*30\s*天)/),
    overview: {
      read: pick(/阅读\s*(\d+)/),
      share: pick(/分享\s*(\d+)/),
      comment: pick(/留言\s*(\d+)/),
      read_users_total: pick(/阅读总人数[：:]\s*(\d+)/),
    },
    traffic_sources_pct: traffic,
    articles: uniq.slice(0, 30),
  };
})())
"""

EXTRACT_DETAIL_JS = r"""
JSON.stringify((() => {
  const text = document.body.innerText || "";
  const pick = (re) => { const x = text.match(re); return x ? x[1] : null; };
  const traffic = {};
  const block = text.split("阅读渠道构成")[1] || "";
  const m = block.match(/([\d.]+%)[\s\S]*?(朋友圈|聊天会话|公众号主页|其它|搜一搜|公众号消息|推荐)/g);
  if (m) {
    for (const line of m) {
      const pm = line.match(/^([\d.]+%)/);
      const nm = line.match(/(朋友圈|聊天会话|公众号主页|其它|搜一搜|公众号消息|推荐)$/);
      if (pm && nm) traffic[nm[1]] = pm[1];
    }
  }
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


def _load_json(raw: str, *, label: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} JSON 解析失败: {raw[:500]}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{label} 返回非对象")
    return data


def fetch_daily_report(*, url: str, wait_login: float = 0) -> dict[str, Any]:
    _open_page(url, label="内容分析 daily_v2")
    _run_opencli(["browser", "wait", "time", "4"], timeout=10)
    if wait_login > 0 and not _wait_login(timeout_sec=wait_login):
        raise RuntimeError("未登录公众号后台，请在 OpenCLI 窗口扫码登录后重试")
    st = _load_json(_eval_js(CHECK_LOGIN_JS), label="login")
    if not st.get("logged_in"):
        raise RuntimeError(
            "页面显示未登录。请用带 token 的 analytics-url，或在 OpenCLI 浏览器中登录 mp.weixin.qq.com"
        )
    return _load_json(_eval_js(EXTRACT_DAILY_JS, timeout=90), label="daily")


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
    parser.add_argument("--detail-top", type=int, default=3, help="抓取前 N 篇「详情」完读率等")
    parser.add_argument("-o", "--output", default="", help="输出 JSON 路径")
    parser.add_argument("--no-close-browser", action="store_true")
    args = parser.parse_args()

    import os

    url = (args.analytics_url or os.getenv("WECHAT_MP_ANALYTICS_URL") or DAILY_URL).strip()
    token = (args.token or os.getenv("WECHAT_MP_ADMIN_TOKEN") or "").strip()
    if token and "token=" not in url:
        url = _append_token(url, token)

    try:
        daily = fetch_daily_report(url=url, wait_login=args.wait_login)
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
