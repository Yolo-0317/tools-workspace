#!/usr/bin/env python3
"""A 股 market 标题模板池与按日轮换（盘前 / 午间 / 盘后）。"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Literal

MarketEdition = Literal["pre", "midday", "close"]

# 占位符：{wd} 周几；{tags} 当日钩子（如 油价+半导体）
MARKET_TITLE_TEMPLATES: dict[MarketEdition, tuple[str, ...]] = {
    "pre": (
        "{wd}盘前｜{tags}，开局盯什么？",
        "开市前三分钟：{tags}怎么读？",
        "隔夜到盘前｜{tags}与A股映射？",
        "{wd}开盘前｜{tags}先看哪条？",
        "集合竞价前：{tags}定不调？",
        "盘前一页纸｜{tags}影响哪条线？",
        "{wd}开市｜{tags}，竞价盯啥？",
        "隔夜三件：{tags}怎么映射？",
        "{tags}到A股｜开盘先看哪？",
        "别等9:25才看：{tags}？",
        "{wd}早读｜{tags}与外围？",
        "开盘结构：{tags}先看哪？",
        "外盘夜里变了：{tags}？",
        "{wd}9:25前｜{tags}怎么接？",
        "盘前速览：{tags}牵哪线？",
        "竞价前最后一眼：{tags}？",
        "{wd}开盘｜{tags}与指数节奏？",
        "隔夜→开盘：{tags}怎么读？",
        "先看外围：{tags}映射A股？",
        "{wd}盘前速读｜{tags}三条线？",
    ),
    "midday": (
        "{wd}午间｜{tags}，午后怎么走？",
        "半日结构：{tags}怎么接？",
        "{wd}午盘｜{tags}与指数同频吗？",
        "上午走完：{tags}午后看哪？",
        "涨指数不涨股？{tags}怎么读？",
        "{wd}半日｜{tags}与个股背离？",
        "午盘三条线：{tags}？",
        "上午主线：{tags}能延续吗？",
        "午间一页：{tags}与午后节奏？",
        "双创强、个股弱？{tags}？",
        "{wd}11:30｜{tags}怎么接？",
        "半日复盘：{tags}与情绪？",
        "午后盯什么：{tags}？",
        "指数与广度：{tags}同频吗？",
        "上午收官：{tags}牵哪线？",
        "{wd}午间速览｜{tags}结构？",
        "半日结论：{tags}午后验证啥？",
        "午前资金往哪：{tags}？",
        "{wd}午评｜{tags}与梯队？",
        "上午强、下午呢：{tags}？",
    ),
    "close": (
        "A股收盘复盘｜{tags}怎么读？",
        "收盘复盘·A股｜{tags}牵动哪些线？",
        "{wd}A股收盘｜{tags}，结构怎么看？",
        "A股收盘｜{tags}，结构怎么看？",
        "收盘复盘：{tags}牵动哪些线？",
        "{wd}盘后｜{tags}与指数同频吗？",
        "今日收盘三条线：{tags}？",
        "指数涨、个股跌？{tags}怎么接？",
        "收盘结构：{tags}先看哪？",
        "{wd}收市｜{tags}与明日节奏？",
        "三条线收盘：{tags}？",
        "今日盘面：{tags}定基调？",
        "{wd}复盘｜{tags}与广度？",
        "收盘一页纸：{tags}？",
        "结构怎么走：{tags}？",
        "{wd}17:00｜{tags}与情绪？",
        "今日收评：{tags}牵哪线？",
        "涨少跌多？{tags}怎么读？",
        "收盘速览：{tags}与明日盯盘？",
        "{wd}盘后一页｜{tags}结构？",
        "今日三条验证：{tags}？",
        "指数与个股：{tags}同频吗？",
        "收市结论：{tags}先看哪？",
    ),
}

_EDITION_ROTATE_OFFSET = {"pre": 1, "midday": 2, "close": 3}


def format_market_title(template: str, *, wd: str, tags: str) -> str:
    return template.format(wd=wd, tags=tags)


def build_market_title_options(
    edition: MarketEdition,
    *,
    wd: str,
    tags: str,
) -> list[str]:
    return [
        format_market_title(t, wd=wd, tags=tags)
        for t in MARKET_TITLE_TEMPLATES.get(edition, ())
    ]


def rotate_options(options: list[str], *, seed: int) -> list[str]:
    if not options:
        return []
    n = len(options)
    start = seed % n
    return options[start:] + options[:start]


def load_recent_market_titles(
    edition: str,
    *,
    log_path,
    days: int = 7,
    today: date | None = None,
) -> list[str]:
    """从 title log 读取近 N 天同 edition 已用标题。"""
    if not log_path.is_file():
        return []
    try:
        import json

        data = json.loads(log_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    ref = today or date.today()
    out: list[str] = []
    for i in range(days):
        d = (ref - timedelta(days=i)).isoformat()
        row = data.get(d)
        if isinstance(row, dict) and row.get(edition):
            out.append(str(row[edition]))
    return out


def pick_rotated_market_title(
    options: list[str],
    *,
    now: datetime,
    edition: MarketEdition,
    peer_title: str | None = None,
    recent_titles: list[str] | None = None,
    clip_fn,
    too_similar_fn,
) -> str:
    """按日期轮换模板顺序，并避开 peer / 近 7 日同 edition 标题。"""
    from scripts.tools.wechat_mp_content import TITLE_MAX
    from scripts.tools.wechat_mp_seo import title_search_rank_key

    seed = now.date().toordinal() + _EDITION_ROTATE_OFFSET.get(edition, 0)
    rotated = rotate_options(options, seed=seed)
    ordered = sorted(
        rotated,
        key=lambda t: title_search_rank_key(t, "market", edition=edition),
        reverse=True,
    )
    recent = list(recent_titles or [])

    def _ok(clipped: str) -> bool:
        if len(clipped) < 10 or len(clipped) > TITLE_MAX:
            return False
        if not re.search(r"[？?！!]", clipped):
            return False
        if peer_title and too_similar_fn(clipped, peer_title):
            return False
        if any(too_similar_fn(clipped, old) for old in recent):
            return False
        return True

    for text in ordered:
        clipped = clip_fn(text)
        if _ok(clipped):
            return clipped

    # 放宽：仅避开 peer
    for text in ordered:
        clipped = clip_fn(text)
        if peer_title and too_similar_fn(clipped, peer_title):
            continue
        if 10 <= len(clipped) <= TITLE_MAX:
            return clipped

    ranked = sorted(
        options,
        key=lambda t: (
            ("？" in t or "?" in t or "！" in t),
            "必读" in t or "先看" in t,
            -len(t),
        ),
        reverse=True,
    )
    return clip_fn(ranked[0] if ranked else options[0])


def list_all_market_title_templates(*, wd: str = "周三", tags: str = "油价+半导体") -> str:
    """人工选标题时打印全表。"""
    lines = ["# market 标题轮换表（占位 {tags} / {wd} 成稿时自动替换）", ""]
    labels = {"pre": "盘前 pre", "midday": "午间 midday", "close": "盘后 close"}
    for ed in ("pre", "midday", "close"):
        lines.append(f"## {labels[ed]}（{len(MARKET_TITLE_TEMPLATES[ed])} 条）")
        lines.append("")
        for i, tpl in enumerate(MARKET_TITLE_TEMPLATES[ed], 1):
            sample = format_market_title(tpl, wd=wd, tags=tags)
            lines.append(f"{i:2}. {tpl}")
            lines.append(f"    → 示例：{sample}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    import argparse
    from pathlib import Path

    from scripts._bootstrap import ensure_repo_root_on_path

    ensure_repo_root_on_path()

    parser = argparse.ArgumentParser(description="market 标题模板轮换表")
    parser.add_argument("--wd", default="周三", help="示例周几")
    parser.add_argument("--tags", default="油价+半导体", help="示例钩子")
    parser.add_argument(
        "--edition",
        choices=("pre", "midday", "close", "all"),
        default="all",
    )
    args = parser.parse_args()

    if args.edition == "all":
        print(list_all_market_title_templates(wd=args.wd, tags=args.tags))
        return 0

    opts = build_market_title_options(args.edition, wd=args.wd, tags=args.tags)
    print(f"=== {args.edition}（{len(opts)} 条）===")
    for i, t in enumerate(opts, 1):
        print(f"{i:2}. {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
