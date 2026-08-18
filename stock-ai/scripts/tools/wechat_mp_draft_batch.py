#!/usr/bin/env python3
"""按日历批次推送公众号草稿（交易日 19:00 两篇 / 周日休市 19:00 要闻 1 篇）。

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
# evening 群发：内容顺序 news → hotspot；封面槽位 1 牛马 → 2 多屏
EVENING_PUBLISH_ORDER: tuple[str, ...] = ("news", "hotspot")
EVENING_COVER_SLOT_KINDS: tuple[str, ...] = ("sector", "hotspot")

# (群发位置, 内容 kind, 封面资源 kind, 说明)
EVENING_PUBLISH_ROWS: tuple[tuple[str, str, str, str], ...] = (
    ("头条", "news", "sector", "牛马品牌"),
    ("次条", "hotspot", "hotspot", "牛马品牌"),
)


def cover_kind_for_content(*, content_kind: str, batch: str) -> str:
    """内容 kind → 封面资源 kind。封面槽位 1/2/3 固定，与正文 kind 解耦。"""
    k = (content_kind or "").strip().lower()
    if batch == "evening":
        evening_kinds = resolve_evening_kinds()
        # hotspot_only：唯一一篇用槽 1 牛马主图（sector/banner）
        if evening_kinds == ("hotspot",) and k == "hotspot":
            return EVENING_COVER_SLOT_KINDS[0]
        try:
            idx = EVENING_PUBLISH_ORDER.index(k)
            return EVENING_COVER_SLOT_KINDS[idx]
        except ValueError:
            return k
    if batch == "tv_trial" and k == "tv_review":
        return "tv_review"
    if batch in HOTSPOT_SCHEDULE_BATCHES and k in {"hotspot", "tv_review"}:
        if k == "tv_review":
            return "tv_review"
        return EVENING_COVER_SLOT_KINDS[0]
    if batch == "weekend" and k in {"news", "hotspot"}:
        return EVENING_COVER_SLOT_KINDS[0]
    return k


def resolve_evening_kinds() -> tuple[str, ...]:
    """返回当前固定的晚间两篇（news + hotspot）。"""
    return EVENING_PUBLISH_ORDER


HOTSPOT_SCHEDULE_BATCHES: frozenset[str] = frozenset(
    {"hotspot_early", "hotspot_morning", "hotspot_afternoon", "hotspot_evening"}
)

SCHEDULE_BATCHES: dict[str, dict[str, Any]] = {
    "evening": {
        "kinds": EVENING_PUBLISH_ORDER,
        "edition": "close",
        "dragon_slot": None,
    },
    "weekend": {
        "kinds": ("hotspot",),
        "edition": "close",
        "dragon_slot": None,
    },
    "weekend_skip": {
        "kinds": (),
        "edition": None,
        "dragon_slot": None,
    },
    "tv_trial": {
        "kinds": ("tv_review",),
        "edition": None,
        "dragon_slot": None,
    },
    "hotspot_early": {
        "kinds": ("hotspot",),
        "edition": "pre",
        "dragon_slot": None,
        "slot_key": "hotspot_early",
    },
    "hotspot_morning": {
        "kinds": ("hotspot",),
        "edition": "pre",
        "dragon_slot": None,
        "slot_key": "hotspot_morning",
    },
    "hotspot_afternoon": {
        "kinds": ("hotspot",),
        "edition": "midday",
        "dragon_slot": None,
        "slot_key": "hotspot_afternoon",
    },
    "hotspot_evening": {
        "kinds": ("hotspot",),
        "edition": "close",
        "dragon_slot": None,
        "slot_key": "hotspot_evening",
    },
}


def resolve_scheduled_batch(*, now: datetime | None = None) -> str:
    """交易日 → evening；休市日 → weekend(news)，仅周六跳过；若开启影视试跑，休市日 → tv_trial。"""
    from stock_ai.trading_calendar import is_off_market_day

    dt = now or datetime.now(_TZ)
    is_off = is_off_market_day(dt.date())

    if is_off:
        try:
            from scripts.tools.wechat_mp_tv_review_article import tv_trial_active

            if tv_trial_active(when=dt):
                return "tv_trial"
        except Exception:
            pass

        if dt.weekday() == 5:
            return "weekend_skip"
        return "weekend"

    return "evening"


def _apply_batch_env(batch: str) -> None:
    os.environ.setdefault("CURSOR_AGENT_MODEL", "composer-2.5")
    os.environ.setdefault("WECHAT_MP_CURSOR_MAX_RETRIES", "1")
    os.environ.setdefault("WECHAT_MP_CURSOR_TIMEOUT_SECONDS", "420")
    spec = SCHEDULE_BATCHES[batch]
    slot = spec.get("dragon_slot")
    if slot:
        os.environ["WECHAT_MP_DRAGON_SLOT"] = str(slot)
    elif "WECHAT_MP_DRAGON_SLOT" in os.environ:
        os.environ.pop("WECHAT_MP_DRAGON_SLOT", None)

    for key in (
        "WECHAT_MP_WEEKEND_NEWS",
        "WECHAT_MP_HOT_STOCK_NEWS",
        "WECHAT_MP_NEWS_BATCH",
        "WECHAT_MP_HOT_STOCK_NEWS_HOURS",
    ):
        os.environ.pop(key, None)

    if batch == "evening":
        os.environ["WECHAT_MP_HOT_STOCK_NEWS"] = "1"
        os.environ["WECHAT_MP_WEEKEND_NEWS"] = "1"  # 兼容旧 env 读取
    if batch == "weekend":
        os.environ["WECHAT_MP_WEEKEND_NEWS"] = "1"  # 批次标记；休市日写 hotspot 非热股 news
    if batch == "evening":
        os.environ["WECHAT_MP_SECTOR_EVENING_DEDUP"] = "1"
        os.environ["WECHAT_MP_SECTOR_HOT_WATCH_TOP_N"] = "0"
        os.environ.setdefault("WECHAT_MP_PUSH_QUALITY_GATE", "1")
    else:
        os.environ.pop("WECHAT_MP_SECTOR_EVENING_DEDUP", None)
        if "WECHAT_MP_SECTOR_HOT_WATCH_TOP_N" in os.environ:
            os.environ.pop("WECHAT_MP_SECTOR_HOT_WATCH_TOP_N", None)
    if batch in HOTSPOT_SCHEDULE_BATCHES:
        os.environ.setdefault("WECHAT_MP_HOTSPOT_SOURCE", "trends")
        os.environ.setdefault("WECHAT_MP_PUSH_QUALITY_GATE", "1")
        os.environ["WECHAT_MP_HOTSPOT_TREND_ENRICH"] = "0"
        os.environ["WECHAT_MP_STOCK_AI_CTA"] = "0"
        os.environ.setdefault("WECHAT_MP_DISCUSSION_FIGURES", "1")
        os.environ.setdefault("WECHAT_MP_DISCUSSION_BODY_FIGURES", "3")
        os.environ.setdefault("WECHAT_MP_HOTSPOT_SOCIAL_FIGURES", "1")
        os.environ.setdefault("WECHAT_MP_HOTSPOT_IMITATE_REWRITE", "0")
        os.environ.setdefault("WECHAT_MP_HOTSPOT_MAX_ATTEMPTS", "1")
    if batch == "tv_trial":
        os.environ.setdefault("WECHAT_MP_DISCUSSION_IMITATE_REWRITE", "0")
        os.environ["WECHAT_MP_STOCK_AI_CTA"] = "0"
        os.environ.setdefault("WECHAT_MP_TV_PICK_MODE", "discussion")
        os.environ.setdefault("WECHAT_MP_TV_RESEARCH", "1")
    if batch == "hotspot_afternoon":
        pass  # 兼容旧名；env 已在 HOTSPOT_SCHEDULE_BATCHES 块设置
    os.environ["WECHAT_MP_NEWS_BATCH"] = batch if batch != "tv_trial" else "tv_trial"

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
    kinds: tuple[str, ...]
    if batch == "evening":
        kinds = resolve_evening_kinds()
    else:
        kinds = tuple(spec["kinds"])
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
            elif kind in {"market", "sector", "hotspot"}:
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

        from scripts.tools.wechat_mp_push_quality_gate import (
            assess_article_for_push,
            format_quality_gate_report,
            quality_gate_enabled,
            quality_gate_strict,
        )

        gate_ok = True
        if quality_gate_enabled():
            gate = assess_article_for_push(
                article,
                kind,
                edition=edition if kind in {"market", "sector", "hotspot"} else None,
            )
            print(format_quality_gate_report(gate))
            gate_ok = gate.ok
            if not gate_ok and quality_gate_strict() and not dry_run:
                failed.append(kind)
                results.append(
                    DraftPushResult(
                        kind=kind,
                        title=article.get("title", ""),
                        action="",
                        ok=False,
                        error=gate.block_reason or "质量门禁未过",
                    )
                )
                print(
                    f"FAIL [{kind}] 质量门禁: {gate.block_reason}",
                    file=sys.stderr,
                )
                continue

        if dry_run:
            print(f"=== {kind} ({BATCH_LABELS.get(batch)}) ===")
            if edition and kind in {"market", "sector", "hotspot"}:
                print(f"edition: {edition}")
            print(f"标题: {article['title']}")
            print(f"摘要: {article['digest'][:100]}")
            from scripts.tools.wechat_mp_seo import print_publish_hints

            print_publish_hints(
                kind,
                article,
                edition=edition if kind in {"market", "sector", "hotspot"} else None,
            )
            tags = tuple(article.get("recommended_hashtags") or ())
            results.append(
                DraftPushResult(
                    kind=kind,
                    title=article["title"],
                    action="dry-run",
                    ok=gate_ok,
                    hashtags=tags,
                )
            )
            continue

        from scripts.tools.wechat_mp_public import audit_recommendation_safety

        compliance = audit_recommendation_safety(
            title=str(article.get("title") or ""),
            digest=str(article.get("digest") or ""),
            body=str(article.get("body_text") or ""),
        )
        if compliance:
            failed.append(kind)
            msg = "、".join(compliance)
            results.append(
                DraftPushResult(kind=kind, title=article.get("title", ""), action="", ok=False, error=msg)
            )
            print(f"❌ [{kind}] 推荐安全/合规未过: {msg}", file=sys.stderr)
            strict = os.getenv("WECHAT_MP_STRICT_COMPLIANCE", "1").strip().lower()
            if strict not in ("0", "false", "no", "off"):
                continue

        cover_kind = cover_kind_for_content(content_kind=kind, batch=batch)
        thumb: str | None = None
        terr: dict[str, Any] | None = None
        if kind == "tv_review":
            from scripts.tools.wechat_mp_tv_cover import pick_tv_draft_thumb
            from scripts.tools.wechat_mp_tv_review_article import get_last_built_tv_topic

            topic = get_last_built_tv_topic()
            if not topic:
                from scripts.tools.wechat_mp_tv_topics import pick_tv_topic

                topic = pick_tv_topic()
            cover_kind, thumb, terr = pick_tv_draft_thumb(topic, batch=batch)
        elif kind == "hotspot" and batch in HOTSPOT_SCHEDULE_BATCHES:
            from scripts.tools.wechat_mp_hotspot_article import (
                get_last_built_hotspot_topic,
                hotspot_social_layout_enabled,
            )
            from scripts.tools.wechat_mp_tv_cover import pick_discussion_draft_thumb

            topic = get_last_built_hotspot_topic()
            if hotspot_social_layout_enabled() and topic:
                cover_kind = "discussion"
                thumb, terr = pick_discussion_draft_thumb(topic)
            else:
                thumb, terr = pick_thumb_for_draft_kind(cover_kind)
        else:
            thumb, terr = pick_thumb_for_draft_kind(cover_kind)
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
            print(f"❌ [{kind}] 封面失败({cover_kind})", file=sys.stderr)
            continue

        meta, _ = get_material_image_meta(thumb or "")
        slot_key = str(spec.get("slot_key") or kind)
        media_id, action, err = upsert_draft_article(
            kind, article, thumb_media_id=thumb or "", slot_key=slot_key
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
            f"OK [{kind}] {verb} · {article['title']} · 封面={cover}({cover_kind}) · slot={get_slot_media_id(slot_key) or media_id}"
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
        help="evening=交易日 news+hotspot；weekend=周日休市 hotspot；weekend_skip=周六跳过",
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
