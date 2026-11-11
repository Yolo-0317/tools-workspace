#!/usr/bin/env python3
"""参考文语料库：读前清单、提炼笔记路径、链接登记。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = ROOT / "data" / "wechat_mp_reference_corpus"


def _load_series(series: str) -> dict:
    path = CORPUS_ROOT / series / "sources.json"
    if not path.is_file():
        raise FileNotFoundError(f"无语料库: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _episode_by_ep(data: dict, ep: int) -> tuple[str, dict] | None:
    for slug, row in (data.get("episodes") or {}).items():
        if int(row.get("ep") or 0) == ep:
            return slug, row
    return None


def cmd_list(args: argparse.Namespace) -> int:
    data = _load_series(args.series)
    print(f"系列: {data.get('series') or args.series}")
    for slug, row in sorted(
        (data.get("episodes") or {}).items(),
        key=lambda x: int(x[1].get("ep") or 0),
    ):
        links = row.get("links") or []
        a = sum(1 for x in links if x.get("tier") == "A_fact")
        c = sum(1 for x in links if x.get("tier") == "C_anti")
        print(
            f"  E{row.get('ep')} {row.get('classic')} · {slug} · "
            f"links A={a} C={c} · nail={row.get('nail') or '-'}"
        )
    return 0


def cmd_checklist(args: argparse.Namespace) -> int:
    data = _load_series(args.series)
    hit = _episode_by_ep(data, args.ep)
    if not hit:
        print(f"无 E{args.ep}", file=sys.stderr)
        return 1
    slug, row = hit
    print(f"# E{args.ep} {row.get('classic')} ({slug})")
    print(f"钉子: {row.get('nail') or '-'}")
    print(f"笔记: {row.get('notes_file') or '-'}\n")
    tiers = data.get("reading_tiers") or {}
    links = row.get("links") or []
    for tier in ("A_fact", "B_voice", "C_anti"):
        label = tiers.get(tier) or tier
        bucket = [x for x in links if x.get("tier") == tier]
        print(f"## {tier} — {label}")
        if not bucket:
            print("  （待补充链接）")
        for item in bucket:
            print(f"  - [{item.get('source') or '?'}] {item.get('title') or ''}")
            print(f"    {item.get('url') or item.get('local') or ''}")
            if item.get("take"):
                print(f"    取: {item['take']}")
        print()
    for item in data.get("cross_series_voice") or []:
        print(f"## 跨题范本: {item.get('title')}")
        print(f"  {item.get('local') or item.get('url') or ''}")
        print(f"  用于: {item.get('use_for') or ''}\n")
    print("写前: 填 notes → 开头仿写 80 字确认 → body_cache → repush")
    print(f"提炼规律: data/wechat_mp_reference_corpus/{args.series}/distilled-patterns.md")
    return 0


def cmd_notes_path(args: argparse.Namespace) -> int:
    data = _load_series(args.series)
    row = (data.get("episodes") or {}).get(args.slug)
    if not row:
        print(f"无 slug={args.slug}", file=sys.stderr)
        return 1
    path = ROOT / str(row.get("notes_file") or "")
    print(path)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="公众号参考文语料库")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list", help="列出各集链接概况")
    p_list.add_argument("--series", default="dianji-zhongguo")
    p_list.set_defaults(func=cmd_list)

    p_chk = sub.add_parser("checklist", help="打印单集读前清单")
    p_chk.add_argument("--series", default="dianji-zhongguo")
    p_chk.add_argument("--ep", type=int, required=True)
    p_chk.set_defaults(func=cmd_checklist)

    p_notes = sub.add_parser("notes-path", help="返回提炼笔记路径")
    p_notes.add_argument("--series", default="dianji-zhongguo")
    p_notes.add_argument("--slug", required=True)
    p_notes.set_defaults(func=cmd_notes_path)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
