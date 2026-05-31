#!/usr/bin/env python3
"""从东方财富网页抓取宏观/7×24 财经快讯（OpenCLI Browser）。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

CHROME_PATH = os.getenv(
    "CHROME_EXECUTABLE",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
KUAIXUN_URL = "https://kuaixun.eastmoney.com/"
HOME_URL = "https://www.eastmoney.com/"

EXTRACT_KUAIXUN_JS = """
() => {
  const items = [];
  document.querySelectorAll('.news_item').forEach(el => {
    const time = el.querySelector('.news_time')?.innerText?.trim() || '';
    const a = el.querySelector('a[href*="/a/"]');
    const text = (a?.innerText || '').replace(/\\s+/g, ' ').trim();
    const href = a?.href || '';
    if (text && href) items.push({ time, text, href, source: 'kuaixun' });
  });
  const seen = new Set();
  return items.filter(x => {
    if (seen.has(x.href)) return false;
    seen.add(x.href);
    return true;
  });
}
"""

EXTRACT_HOME_JS = """
() => {
  const items = [];
  document.querySelectorAll('a[href*="/a/"]').forEach(a => {
    const title = (a.innerText || '').replace(/\\s+/g, ' ').trim();
    const href = a.href || '';
    if (!href.includes('finance.eastmoney.com/a/')) return;
    if (title.length < 6 || title.length > 80) return;
    if (title.includes('点击查看') || title.includes('评论')) return;
    items.push({ title, href, source: 'home' });
  });
  const seen = new Set();
  return items.filter(x => {
    if (seen.has(x.href)) return false;
    seen.add(x.href);
    return true;
  });
}
"""


@dataclass
class MacroNewsItem:
    title: str
    summary: str
    time: str
    href: str
    source: str


def _split_title_summary(text: str) -> tuple[str, str]:
    cleaned = re.sub(r"\[点击查看全文\]", "", text).strip()
    match = re.match(r"【([^】]+)】(.+)", cleaned, re.DOTALL)
    if match:
        title = match.group(1).strip()
        summary = re.sub(r"\s+", " ", match.group(2)).strip()
        return title, summary
    title = cleaned[:80].strip()
    return title, cleaned


def _normalize_items(raw_items: list[dict], *, default_source: str) -> list[MacroNewsItem]:
    items: list[MacroNewsItem] = []
    seen: set[str] = set()
    for raw in raw_items:
        href = str(raw.get("href") or "").strip()
        if not href or href in seen:
            continue
        seen.add(href)
        text = str(raw.get("text") or raw.get("title") or "").strip()
        if not text:
            continue
        title, summary = _split_title_summary(text)
        items.append(
            MacroNewsItem(
                title=title,
                summary=summary,
                time=str(raw.get("time") or "").strip(),
                href=href,
                source=str(raw.get("source") or default_source),
            )
        )
    return items


def fetch_macro_news(*, limit: int = 15, include_home: bool = True) -> list[MacroNewsItem]:
    from scripts.tools.fetch_eastmoney_quotes import fetch_macro_news_opencli

    _ = include_home  # 首页要闻后续可扩展 OpenCLI
    raw_items = fetch_macro_news_opencli(limit=limit)
    return _normalize_items(raw_items, default_source="kuaixun")


def format_report(items: list[MacroNewsItem], *, fetched_at: datetime | None = None) -> str:
    now = fetched_at or datetime.now()
    lines = [
        f"【{now.strftime('%Y-%m-%d')} 宏观财经 · 东财7×24快讯】",
        f"采集时间：{now.strftime('%H:%M:%S')}",
        "",
    ]
    if not items:
        lines.append("暂无快讯数据，请稍后重试。")
    else:
        for idx, item in enumerate(items, start=1):
            time_part = f"{item.time} " if item.time else ""
            lines.append(f"{idx}. {time_part}{item.title}")
            if item.summary and item.summary != item.title:
                summary = item.summary
                if len(summary) > 120:
                    summary = summary[:120] + "…"
                lines.append(f"   {summary}")
    lines.extend(
        [
            "",
            "来源：东方财富网",
            KUAIXUN_URL,
            "（决策支持，非投资建议）",
        ]
    )
    return "\n".join(lines)


def _push_wechat(text: str) -> None:
    from scripts.tools.wechat_acp_push_text import send_wechat_acp_text

    send_wechat_acp_text(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取东财宏观/7×24 财经快讯")
    parser.add_argument("--limit", type=int, default=15, help="最多输出条数（默认 15）")
    parser.add_argument(
        "--no-home",
        action="store_true",
        help="不补充抓取 eastmoney.com 首页要闻",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="输出格式（默认 text）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="写入文件路径（默认 stdout）",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="抓取后推送到微信（wechat-acp，供脚本直接调用）",
    )
    args = parser.parse_args()

    try:
        items = fetch_macro_news(limit=args.limit, include_home=not args.no_home)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 抓取失败: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        payload = {
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "source": KUAIXUN_URL,
            "items": [asdict(x) for x in items],
        }
        content = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        content = format_report(items)

    out_path = args.output
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content + "\n", encoding="utf-8")
        print(f"已写入: {out_path}", file=sys.stderr)
    elif not args.push:
        print(content)

    if args.push:
        try:
            _push_wechat(content)
            print("✅ 已推送到微信", file=sys.stderr)
        except SystemExit as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"❌ 微信推送失败: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
