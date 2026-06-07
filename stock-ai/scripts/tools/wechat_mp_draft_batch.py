#!/usr/bin/env python3
"""按日历批次推送公众号草稿（交易日 19:00 三篇 / 周日休市 19:00 要闻 1 篇）。

批次表真源见 SCHEDULE_BATCHES；文档 stock-ai/docs/WECHAT_MP_SCHEDULING.md。
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

_TZ = ZoneInfo("Asia/Shanghai")

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import (
    get_material_image_meta,
    mp_configured,
    pick_thumb_for_draft_kind,
)
from scripts.tools.wechat_mp_content import build_article
from scripts.tools.wechat_mp_draft_notify import (
    BATCH_LABELS,
    DraftPushResult,
    send_batch_notifications,
)
from scripts.tools.wechat_mp_draft_slots import get_slot_media_id, upsert_draft_article

# launchd 每日 19:00 触发；shell 按交易日/休市日解析 batch（见 resolve_scheduled_batch）
SCHEDULE_BATCHES: dict[str, dict[str, Any]] = {
    "evening": {
        "kinds": ("sector", "dragons", "top5"),
        "edition": "close",
        "dragon_slot": "eod",
    },
    "weekend": {
        "kinds": ("news",),
        "edition": None,
        "dragon_slot": None,
    },
    "weekend_skip": {
        "kinds": (),
        "edition": None,
        "dragon_slot": None,
    },
}


def resolve_scheduled_batch(*, now: datetime | None = None) -> str:
    """交易日 → evening；休市日 → weekend(news)，仅周六跳过（周日/法定节假日仍发）。"""
    from stock_ai.trading_calendar import is_off_market_day

    dt = now or datetime.now(_TZ)
    if is_off_market_day(dt.date()):
        if dt.weekday() == 5:
            return "weekend_skip"
        return "weekend"
    return "evening"


def _apply_batch_env(batch: str) -> None:
    spec = SCHEDULE_BATCHES[batch]
    slot = spec.get("dragon_slot")
    if slot:
        os.environ["WECHAT_MP_DRAGON_SLOT"] = str(slot)
    elif "WECHAT_MP_DRAGON_SLOT" in os.environ:
        os.environ.pop("WECHAT_MP_DRAGON_SLOT", None)
    if batch == "weekend":
        os.environ["WECHAT_MP_WEEKEND_NEWS"] = "1"
    else:
        os.environ.pop("WECHAT_MP_WEEKEND_NEWS", None)


def _peer_market_title() -> str | None:
    from scripts.tools.wechat_mp_draft_slots import _load_slots

    entry = (_load_slots().get("slots") or {}).get("market") or {}
    title = str(entry.get("title") or "").strip()
    return title or None


def run_batch(
    batch: str,
    *,
    dry_run: bool = False,
    notify: bool = True,
) -> int:
    if batch not in SCHEDULE_BATCHES:
        raise ValueError(f"未知 batch={batch!r}，可选: {', '.join(SCHEDULE_BATCHES)}")

    spec = SCHEDULE_BATCHES[batch]
    kinds: tuple[str, ...] = tuple(spec["kinds"])
    edition = spec.get("edition")

    _apply_batch_env(batch)

    if not kinds:
        label = BATCH_LABELS.get(batch, batch)
        print(f"SKIP {label}（本日不推草稿）", file=sys.stderr)
        return 0

    if not mp_configured() and not dry_run:
        print("❌ 未配置 WECHAT_MP_APPID / WECHAT_MP_SECRET", file=sys.stderr)
        return 1

    results: list[DraftPushResult] = []
    failed: list[str] = []
    for kind in kinds:
        try:
            if kind == "news":
                article = build_article(
                    kind,
                    peer_market_title=_peer_market_title(),
                )
            elif kind in {"market", "sector"}:
                article = build_article(kind, edition=edition)
            else:
                article = build_article(kind)
        except Exception as exc:  # noqa: BLE001
            failed.append(kind)
            results.append(
                DraftPushResult(kind=kind, title="", action="", ok=False, error=str(exc))
            )
            print(f"❌ [{kind}] 构建失败: {exc}", file=sys.stderr)
            continue

        if dry_run:
            print(f"=== {kind} ({BATCH_LABELS.get(batch)}) ===")
            if edition and kind in {"market", "sector"}:
                print(f"edition: {edition}")
            print(f"标题: {article['title']}")
            print(f"摘要: {article['digest'][:100]}")
            from scripts.tools.wechat_mp_seo import print_publish_hints

            print_publish_hints(
                kind,
                article,
                edition=edition if kind in {"market", "sector"} else None,
            )
            tags = tuple(article.get("recommended_hashtags") or ())
            results.append(
                DraftPushResult(
                    kind=kind,
                    title=article["title"],
                    action="dry-run",
                    ok=True,
                    hashtags=tags,
                )
            )
            continue

        from scripts.tools.wechat_mp_public import check_public_compliance

        compliance = check_public_compliance(
            article.get("body_text") or "",
            title=str(article.get("title") or ""),
        )
        if compliance:
            failed.append(kind)
            msg = "、".join(compliance)
            results.append(
                DraftPushResult(kind=kind, title=article.get("title", ""), action="", ok=False, error=msg)
            )
            print(f"❌ [{kind}] 合规未过: {msg}", file=sys.stderr)
            strict = os.getenv("WECHAT_MP_STRICT_COMPLIANCE", "1").strip().lower()
            if strict not in ("0", "false", "no", "off"):
                continue

        thumb, terr = pick_thumb_for_draft_kind(kind)
        if terr:
            failed.append(kind)
            results.append(
                DraftPushResult(
                    kind=kind,
                    title=article.get("title", ""),
                    action="",
                    ok=False,
                    error=str(terr.get("errmsg") or terr),
                )
            )
            print(f"❌ [{kind}] 封面失败", file=sys.stderr)
            continue

        meta, _ = get_material_image_meta(thumb or "")
        media_id, action, err = upsert_draft_article(
            kind, article, thumb_media_id=thumb or ""
        )
        if err:
            failed.append(kind)
            results.append(
                DraftPushResult(
                    kind=kind,
                    title=article.get("title", ""),
                    action="",
                    ok=False,
                    error=str(err),
                )
            )
            print(f"❌ [{kind}] 推送失败: {err}", file=sys.stderr)
            continue

        verb = "updated" if action == "updated" else "created"
        cover = meta.get("name") if meta else ""
        print(
            f"OK [{kind}] {verb} · {article['title']} · 封面={cover} · slot={get_slot_media_id(kind) or media_id}"
        )
        tags = tuple(article.get("recommended_hashtags") or ())
        results.append(
            DraftPushResult(
                kind=kind,
                title=article["title"],
                action=action or verb,
                ok=True,
                hashtags=tags,
            )
        )

    ok_count = sum(1 for r in results if r.ok and r.action != "dry-run")
    if not dry_run and ok_count > 0:
        from scripts.tools.wechat_mp_prune_drafts import prune_obsolete_drafts

        prune_obsolete_drafts(dry_run=False)

    if notify and not dry_run:
        send_batch_notifications(
            batch,
            results,
            failed_kinds=failed,
            is_error=ok_count == 0,
        )

    return 0 if ok_count > 0 or dry_run else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="按时段批次推送公众号草稿")
    parser.add_argument(
        "--batch",
        choices=tuple(SCHEDULE_BATCHES),
        default=None,
        help="evening=交易日3篇；weekend=周日休市news(72h个股优先)；weekend_skip=周六休市跳过",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="不发送微信/飞书通知",
    )
    args = parser.parse_args()
    batch = args.batch or resolve_scheduled_batch()
    return run_batch(
        batch,
        dry_run=args.dry_run,
        notify=not args.no_notify,
    )


if __name__ == "__main__":
    raise SystemExit(main())
