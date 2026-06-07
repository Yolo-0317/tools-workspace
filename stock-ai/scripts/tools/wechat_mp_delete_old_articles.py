#!/usr/bin/env python3
"""批量删除公众号 2022-05 之前的已发布文章与图文永久素材（API 可达部分）。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import (
    ROOT,
    del_permanent_material,
    freepublish_delete,
    freepublish_first_title,
    get_material_count,
    list_all_freepublish,
    list_all_material_news,
    material_news_first_title,
    mp_configured,
)
from scripts.tools.wechat_mp_content import DRAFT_KINDS
from scripts.tools.wechat_mp_draft_slots import SLOTS_PATH, get_slot_media_id

TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_CUTOFF = datetime(2022, 5, 1, 0, 0, 0, tzinfo=TZ)


@dataclass
class DeleteTarget:
    kind: str  # freepublish | material_news
    key: str  # article_id or media_id
    title: str
    update_time: int
    update_at: str


def _parse_cutoff(raw: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.replace(tzinfo=TZ)
        except ValueError:
            continue
    raise ValueError(f"无法解析日期: {raw!r}，示例 2022-05-01")


def _fmt_ts(ts: int) -> str:
    if not ts:
        return "未知时间"
    return datetime.fromtimestamp(ts, tz=TZ).strftime("%Y-%m-%d %H:%M:%S")


def _protected_media_ids() -> set[str]:
    keep: set[str] = set()
    for kind in DRAFT_KINDS:
        mid = get_slot_media_id(kind)
        if mid:
            keep.add(mid)
    if SLOTS_PATH.is_file():
        try:
            data = json.loads(SLOTS_PATH.read_text(encoding="utf-8"))
            for row in data.values() if isinstance(data, dict) else []:
                if isinstance(row, dict) and row.get("media_id"):
                    keep.add(str(row["media_id"]))
        except Exception:
            pass
    import os

    for key in os.environ:
        if key.startswith("WECHAT_MP_THUMB_MEDIA_ID"):
            val = os.environ.get(key, "").strip()
            if val:
                keep.add(val)
    return keep


def _collect_targets(*, cutoff: datetime) -> tuple[list[DeleteTarget], dict[str, int]]:
    cutoff_ts = int(cutoff.timestamp())
    protected = _protected_media_ids()
    targets: list[DeleteTarget] = []
    stats = {"freepublish_total": 0, "material_news_total": 0, "skipped_protected": 0}

    pub_items, pub_err = list_all_freepublish()
    if pub_err:
        print(f"⚠️ freepublish 列表失败: {pub_err}", file=sys.stderr)
    else:
        stats["freepublish_total"] = len(pub_items)
        for it in pub_items:
            ts = int(it.get("update_time") or 0)
            if ts >= cutoff_ts:
                continue
            article_id = str(it.get("article_id") or "")
            if not article_id:
                continue
            targets.append(
                DeleteTarget(
                    kind="freepublish",
                    key=article_id,
                    title=freepublish_first_title(it) or "(无标题)",
                    update_time=ts,
                    update_at=_fmt_ts(ts),
                )
            )

    news_items, news_err = list_all_material_news()
    if news_err:
        print(f"⚠️ 图文素材列表失败: {news_err}", file=sys.stderr)
    else:
        stats["material_news_total"] = len(news_items)
        for it in news_items:
            media_id = str(it.get("media_id") or "")
            if not media_id:
                continue
            if media_id in protected:
                stats["skipped_protected"] += 1
                continue
            ts = int(it.get("update_time") or 0)
            if ts >= cutoff_ts:
                continue
            targets.append(
                DeleteTarget(
                    kind="material_news",
                    key=media_id,
                    title=material_news_first_title(it) or "(无标题)",
                    update_time=ts,
                    update_at=_fmt_ts(ts),
                )
            )

    targets.sort(key=lambda x: (x.update_time, x.kind, x.key))
    return targets, stats


def _delete_one(target: DeleteTarget) -> dict | None:
    if target.kind == "freepublish":
        return freepublish_delete(article_id=target.key, index=0)
    if target.kind == "material_news":
        return del_permanent_material(target.key)
    return {"errcode": -1, "errmsg": f"未知类型 {target.kind}"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="删除公众号 cutoff 之前的文章（freepublish + 图文永久素材）"
    )
    parser.add_argument(
        "--before",
        default="2022-05-01",
        help="删除此日期之前的内容（Asia/Shanghai，默认 2022-05-01）",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅列出，不删除")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="实际删除（与 --dry-run 互斥，必须显式指定）",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.35,
        help="每条删除间隔秒数（默认 0.35）",
    )
    args = parser.parse_args()

    if not mp_configured():
        print("❌ 未配置 WECHAT_MP_APPID / WECHAT_MP_SECRET", file=sys.stderr)
        return 1

    if args.execute and args.dry_run:
        print("❌ 不能同时 --execute 与 --dry-run", file=sys.stderr)
        return 1
    if not args.execute:
        args.dry_run = True

    try:
        cutoff = _parse_cutoff(args.before)
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    counts, count_err = get_material_count()
    if count_err:
        print(f"⚠️ 素材统计失败: {count_err}", file=sys.stderr)
    elif counts:
        news_n = counts.get("news_count", 0)
        img_n = counts.get("image_count", 0)
        print(f"素材库统计: news={news_n} image={img_n}")

    targets, stats = _collect_targets(cutoff=cutoff)
    pub_n = sum(1 for t in targets if t.kind == "freepublish")
    mat_n = sum(1 for t in targets if t.kind == "material_news")

    print(f"截止 {cutoff.strftime('%Y-%m-%d')}（不含）")
    print(
        f"扫描: freepublish={stats['freepublish_total']} "
        f"material_news={stats['material_news_total']} "
        f"保护跳过={stats['skipped_protected']}"
    )
    print(f"待删: 共 {len(targets)}（freepublish={pub_n} material_news={mat_n}）")

    if not targets:
        print("OK 无符合条件的文章")
        return 0

    report_path = ROOT / "output" / f"wechat_mp_delete_before_{cutoff.strftime('%Y%m%d')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            [
                {
                    "kind": t.kind,
                    "id": t.key,
                    "title": t.title,
                    "update_at": t.update_at,
                    "update_time": t.update_time,
                }
                for t in targets
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"清单已写入 {report_path}")

    for t in targets[:30]:
        print(f"  · [{t.kind}] {t.update_at} {t.title}")
        print(f"    id={t.key}")
    if len(targets) > 30:
        print(f"  … 另有 {len(targets) - 30} 条，见 {report_path}")

    if args.dry_run:
        print("（dry-run 未删除；确认后加 --execute）")
        print(
            "说明: API 无法列出「已群发通知」的历史消息，"
            "2022 年前若多为后台群发，可能需在 mp.weixin.qq.com 手工清理发表记录。"
        )
        return 0

    ok = 0
    fail = 0
    for i, t in enumerate(targets, 1):
        err = _delete_one(t)
        if err:
            fail += 1
            print(f"❌ [{i}/{len(targets)}] {t.title}: {err}", file=sys.stderr)
        else:
            ok += 1
            if i <= 10 or i == len(targets):
                print(f"✓ [{i}/{len(targets)}] {t.update_at} {t.title}")
        if i < len(targets):
            time.sleep(max(0.0, args.sleep))

    print(f"完成: 成功 {ok} 失败 {fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
