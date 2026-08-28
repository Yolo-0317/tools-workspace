#!/usr/bin/env python3
"""每日公众号草稿：固定五槽位（优先更新旧稿，并清理重复）。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import (
    get_material_image_meta,
    mp_configured,
    pick_thumb_for_draft_kind,
)
from scripts.tools.wechat_mp_content import DRAFT_KINDS, build_article
from scripts.tools.wechat_mp_codex_hotspot import (
    CodexHotspotDraft,
    load_codex_hotspot_draft,
    validate_codex_hotspot_originality,
)
from scripts.tools.wechat_mp_codex_hot_business import (
    CodexHotBusinessDraft,
    load_codex_hot_business_draft,
    validate_codex_hot_business_originality,
)
from scripts.tools.wechat_mp_codex_silver import (
    CodexSilverDraft,
    load_codex_silver_draft,
    validate_codex_silver_originality,
)
from scripts.tools.wechat_mp_codex_short_drama import (
    CodexShortDramaDraft,
    load_codex_short_drama_draft,
)
from scripts.tools.wechat_mp_codex_client import (
    CodexGenerationEvent,
    assert_codex_only_generation,
    generation_events,
    generation_scope,
    record_interactive_codex_draft,
)
from scripts.tools.wechat_mp_draft_slots import upsert_draft_article
from scripts.tools.wechat_mp_short_drama import (
    assert_longform_promotion_safe,
    promotion_summary,
    record_drama_usage,
    verify_saved_short_drama,
)


SHORT_DRAMA_REQUEST_PATH = Path(__file__).resolve().parents[2] / "output" / "short_drama_feature_request.json"


def _resolve_cover_kind(content_kind: str) -> str:
    """内容 kind → 封面资源 kind（evening 批次 news 用牛马 sector 封面）。"""
    if content_kind == "silver":
        return "hot_business"
    if content_kind == "short_drama_feature":
        return "tv_review"
    if content_kind == "literary":
        return "tv_review"
    from scripts.tools.wechat_mp_draft_batch import (
        cover_kind_for_content,
        resolve_scheduled_batch,
    )

    batch = os.getenv("WECHAT_MP_NEWS_BATCH", "").strip() or resolve_scheduled_batch()
    return cover_kind_for_content(content_kind=content_kind, batch=batch)


def _resolve_kinds(raw: str) -> list[str]:
    from scripts.tools.wechat_mp_content import DAILY_DRAFT_KINDS

    text = (raw or "all").strip().lower()
    if text == "all":
        return list(DAILY_DRAFT_KINDS)
    kinds = [k.strip() for k in text.split(",") if k.strip()]
    bad = [k for k in kinds if k not in DRAFT_KINDS]
    if bad:
        raise ValueError(f"未知 kind: {', '.join(bad)}；可选: {', '.join(DRAFT_KINDS)}, all")
    return kinds


def _build_for_kind(
    kind: str,
    *,
    edition: str | None,
    market_title: str | None,
    variant: str | None,
    codex_draft: CodexHotspotDraft | CodexHotBusinessDraft | CodexSilverDraft | CodexShortDramaDraft | None = None,
    topic_hint: str = "",
    silver_lane: str | None = None,
    upload_figures: bool = True,
) -> dict[str, object]:
    if kind == "news" and market_title:
        return build_article(kind, peer_market_title=market_title)
    if kind in {"market", "sector", "hotspot"}:
        return build_article(
            kind,
            edition=edition,
            codex_draft=codex_draft if kind == "hotspot" else None,
            upload_figures=upload_figures,
        )
    if kind == "hot_business":
        return build_article(
            kind,
            topic_hint=topic_hint,
            codex_draft=codex_draft,
            upload_figures=upload_figures,
        )
    if kind == "silver":
        return build_article(
            kind,
            topic_hint=topic_hint,
            silver_lane=silver_lane,
            codex_draft=codex_draft,
            upload_figures=upload_figures,
        )
    if kind == "short_drama_feature":
        return build_article(
            kind,
            codex_draft=codex_draft,
            upload_figures=upload_figures,
        )
    if kind == "temp":
        return build_article(kind, variant=variant)
    if kind == "workspace":
        return build_article(kind, variant=variant)
    if kind == "guba":
        return build_article(kind, edition=edition or "close")
    return build_article(kind)


def _build_with_codex_provenance(
    kind: str,
    *,
    edition: str | None,
    market_title: str | None,
    variant: str | None,
    codex_draft: CodexHotspotDraft | CodexHotBusinessDraft | CodexSilverDraft | CodexShortDramaDraft | object | None,
    topic_hint: str,
    silver_lane: str | None,
    upload_figures: bool,
) -> tuple[dict[str, object], tuple[CodexGenerationEvent, ...]]:
    with generation_scope(kind):
        if codex_draft is not None:
            record_interactive_codex_draft(kind)
        article = _build_for_kind(
            kind,
            edition=edition,
            market_title=market_title,
            variant=variant,
            codex_draft=codex_draft,
            topic_hint=topic_hint,
            silver_lane=silver_lane,
            upload_figures=upload_figures,
        )
        events = generation_events()
        assert_codex_only_generation(allow_empty=codex_draft is None)
        return article, events


def _assert_article_provenance(
    events: tuple[CodexGenerationEvent, ...],
    *,
    codex_draft_supplied: bool,
) -> None:
    if codex_draft_supplied and not events:
        raise RuntimeError("Codex 草稿缺少生成来源")
    if any(event.provider != "codex" for event in events):
        raise RuntimeError("公众号 AI 写稿只允许 Codex")


def _validate_codex_draft_kinds(kinds: list[str], path: Path | None) -> None:
    if path is not None and kinds == ["hotspot"]:
        raise ValueError(
            "用户主动热点必须使用 scripts.tools.wechat_mp_browser_write 的 DeepSeek 双确认流程"
        )
    if path is not None and kinds not in (
        ["hot_business"],
        ["silver"],
        ["short_drama_feature"],
    ):
        raise ValueError(
            "--codex-draft 仅允许与单篇 hotspot 一起使用，"
            "或与单篇 hot_business、silver、short_drama_feature 一起使用"
        )


def _validate_topic_kinds(kinds: list[str], topic: str) -> None:
    if topic.strip() and kinds not in (["hot_business"], ["silver"]):
        raise ValueError("--topic 仅允许与单篇 hot_business 或 silver 一起使用")


def _validate_silver_lane_kinds(kinds: list[str], silver_lane: str | None) -> None:
    if silver_lane and kinds != ["silver"]:
        raise ValueError("--silver-lane 仅允许与单篇 silver 一起使用")


def _resolve_codex_slot_key(draft: CodexHotspotDraft | None) -> str | None:
    if draft is None:
        return None
    return (
        os.getenv("WECHAT_MP_HOTSPOT_SLOT_KEY", "").strip()
        or draft.slot_key
        or None
    )


def _resolve_draft_slot_key(
    kind: str,
    draft: CodexHotspotDraft | CodexHotBusinessDraft | CodexSilverDraft | CodexShortDramaDraft | None,
) -> str | None:
    if kind == "hot_business":
        return "hot_business"
    if kind == "silver":
        return "silver"
    if kind == "short_drama_feature":
        return "short_drama_feature"
    if kind == "literary":
        return "literary"
    if kind == "hotspot" and isinstance(draft, CodexHotspotDraft):
        return _resolve_codex_slot_key(draft)
    return None


def _pick_cover_for_kind(
    *,
    kind: str,
    cover_kind: str,
    article: dict[str, object] | None = None,
) -> tuple[str, str | None, dict[str, object] | None]:
    if kind == "short_drama_feature":
        from scripts.tools.wechat_mp_tv_cover import pick_tv_review_thumb

        short_meta = (article or {}).get("short_drama") or {}
        drama_id = str(short_meta.get("drama_id") or "").strip()
        drama_name = str(short_meta.get("drama_name") or "").strip()
        if not drama_id or not drama_name:
            return "tv_review", None, {
                "errcode": -1,
                "errmsg": "单剧推广稿缺少封面所需的剧目身份",
            }
        thumb, error = pick_tv_review_thumb(
            {
                "title_zh": drama_name,
                "platform": "短剧推荐",
                "cover_slug": f"short-drama-{drama_id}",
            }
        )
        return "tv_review", thumb, error
    if kind == "silver":
        from scripts.tools.wechat_mp_silver_article import (
            get_last_built_silver_topic,
        )
        from scripts.tools.wechat_mp_tv_cover import pick_discussion_draft_thumb

        topic = get_last_built_silver_topic()
        if topic:
            thumb, error = pick_discussion_draft_thumb(topic)
            return "discussion", thumb, error
    if kind in {"hotspot", "hot_business"}:
        from scripts.tools.wechat_mp_hotspot_article import (
            get_last_built_hotspot_topic,
            hotspot_social_layout_enabled,
        )
        from scripts.tools.wechat_mp_tv_cover import pick_discussion_draft_thumb

        topic = get_last_built_hotspot_topic()
        if hotspot_social_layout_enabled() and topic:
            thumb, error = pick_discussion_draft_thumb(topic)
            return "discussion", thumb, error
    thumb, error = pick_thumb_for_draft_kind(cover_kind)
    return cover_kind, thumb, error


def _record_silver_topic_from_article(article: dict[str, object]) -> None:
    topic_id = str(article.get("silver_topic_id") or "").strip()
    if not topic_id or topic_id == "manual":
        return
    from scripts.tools.wechat_mp_silver_topics import (
        load_silver_topics,
        record_silver_topic_usage,
    )

    topic = next((item for item in load_silver_topics() if item.topic_id == topic_id), None)
    if topic is None:
        raise RuntimeError(f"银发选题记录失败，选题库中不存在: {topic_id}")
    record_silver_topic_usage(topic)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成/更新公众号图文草稿（五槽日更 + temp 临时槽）")
    parser.add_argument(
        "--kind",
        default="all",
        help="单篇或逗号组合，如 market,temp；all=日更五篇（不含 temp）",
    )
    parser.add_argument(
        "--variant",
        default=None,
        metavar="NAME",
        help="稿变体：temp 默认 lark_cli；workspace 可选 english_buddy（见 wechat_mp_temp_article.list_temp_variants）",
    )
    parser.add_argument(
        "--codex-draft",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "读取 Codex 准备的 hotspot、hot_business、silver 或 "
            "short_drama_feature JSON；单剧稿由当前 Codex 浏览并写作"
        ),
    )
    parser.add_argument(
        "--topic",
        default="",
        metavar="TEXT",
        help="仅 hot_business 或 silver：手动指定题目；仍执行研究与质量门槛",
    )
    parser.add_argument(
        "--silver-lane",
        choices=("relation", "health", "money"),
        default=None,
        help="仅 silver：关系生活、健康习惯或钱财防骗方向",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印标题与正文预览")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="草稿后 freepublish（需 WECHAT_MP_AUTO_PUBLISH=1 或显式传参）",
    )
    parser.add_argument(
        "--edition",
        choices=("pre", "midday", "close"),
        default=None,
        help="A股评论时段：pre 盘前 / midday 午间 / close 盘后（market、hotspot、sector）；"
        "选择稿件适用的盘前、午间或收盘版本",
    )
    parser.add_argument("--list-materials", action="store_true", help="列出素材库图片后退出")
    parser.add_argument(
        "--prune-only",
        action="store_true",
        help="只清理多余草稿，不写入内容",
    )
    parser.add_argument(
        "--force-new",
        action="store_true",
        help="忽略槽位，强制新建（仍会清理多余旧稿）",
    )
    parser.add_argument(
        "--preview-html",
        type=Path,
        default=None,
        metavar="PATH",
        help="仅 market：写出本地手机预览 HTML（含插图 file://）",
    )
    args = parser.parse_args()

    try:
        kinds = _resolve_kinds(args.kind)
        _validate_codex_draft_kinds(kinds, args.codex_draft)
        _validate_topic_kinds(kinds, args.topic)
        _validate_silver_lane_kinds(kinds, args.silver_lane)
        if args.codex_draft is None:
            codex_draft = None
        elif kinds == ["hot_business"]:
            codex_draft = load_codex_hot_business_draft(args.codex_draft)
        elif kinds == ["silver"]:
            codex_draft = load_codex_silver_draft(args.codex_draft)
        elif kinds == ["short_drama_feature"]:
            codex_draft = load_codex_short_drama_draft(args.codex_draft)
        else:
            codex_draft = load_codex_hotspot_draft(args.codex_draft)
    except ValueError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"错误: 无法读取 Codex 草稿: {exc}", file=sys.stderr)
        return 1

    codex_slot_key = _resolve_draft_slot_key(kinds[0], codex_draft) if len(kinds) == 1 else None

    if args.list_materials:
        from scripts.tools.wechat_mp_list_materials import main as list_main

        _argv = sys.argv
        sys.argv = [_argv[0]]
        try:
            return list_main()
        finally:
            sys.argv = _argv

    if args.preview_html:
        if "market" not in kinds or len(kinds) != 1:
            print("❌ --preview-html 仅用于 --kind market", file=sys.stderr)
            return 1
        from scripts.tools.wechat_mp_content import build_market_article
        from scripts.tools.wechat_mp_figures import write_market_preview_html

        article = build_market_article(edition=args.edition)
        out = write_market_preview_html(article, out_path=args.preview_html)
        print(f"✅ 预览 HTML: {out}")
        print(f"标题: {article['title']}")
        print(f"摘要: {article['digest']}")
        return 0

    if args.prune_only:
        from scripts.tools.wechat_mp_prune_drafts import prune_obsolete_drafts

        return prune_obsolete_drafts(dry_run=args.dry_run)

    if kinds == ["short_drama_feature"] and codex_draft is None:
        from scripts.tools.wechat_mp_short_drama_feature_article import (
            prepare_short_drama_feature_request,
        )

        try:
            request = prepare_short_drama_feature_request()
            SHORT_DRAMA_REQUEST_PATH.parent.mkdir(parents=True, exist_ok=True)
            SHORT_DRAMA_REQUEST_PATH.write_text(
                json.dumps(request, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"错误 [short_drama_feature]: {exc}", file=sys.stderr)
            return 1
        print(f"已生成 Codex 写稿请求: {SHORT_DRAMA_REQUEST_PATH}")
        for candidate in request.get("candidates") or []:
            print(
                f"候选: {candidate.get('drama_name') or candidate.get('drama_id')} "
                f"(drama_id={candidate.get('drama_id') or ''})"
            )
        print("请由当前 Codex 查找公开资料并生成结构化稿件，再通过 --codex-draft 写入草稿。")
        return 0

    if not mp_configured() and not args.dry_run:
        print("错误: 未配置 WECHAT_MP_APPID / WECHAT_MP_SECRET", file=sys.stderr)
        return 1

    if args.dry_run:
        ok = True
        market_title: str | None = None
        for kind in kinds:
            try:
                edition = args.edition if kind in {"market", "sector", "hotspot"} else None
                article, provenance_events = _build_with_codex_provenance(
                    kind,
                    edition=edition,
                    market_title=market_title,
                    variant=args.variant,
                    codex_draft=codex_draft,
                    topic_hint=args.topic,
                    silver_lane=args.silver_lane,
                    upload_figures=False,
                )
                _assert_article_provenance(
                    provenance_events,
                    codex_draft_supplied=codex_draft is not None,
                )
                if codex_draft is not None and kind == "hotspot":
                    from scripts.tools.wechat_mp_originality import (
                        format_originality_report,
                    )
                    from scripts.tools.wechat_mp_virtual_ledger import (
                        load_virtual_history,
                    )

                    report = validate_codex_hotspot_originality(
                        codex_draft,
                        history_posts=load_virtual_history().get("posts", []),
                    )
                    print(format_originality_report(report))
                if codex_draft is not None and kind == "hot_business":
                    from scripts.tools.wechat_mp_originality import format_originality_report
                    from scripts.tools.wechat_mp_virtual_ledger import load_virtual_history

                    report = validate_codex_hot_business_originality(
                        codex_draft,
                        history_posts=load_virtual_history().get("posts", []),
                    )
                    print(format_originality_report(report))
                if codex_draft is not None and kind == "silver":
                    from scripts.tools.wechat_mp_originality import format_originality_report
                    from scripts.tools.wechat_mp_virtual_ledger import load_virtual_history

                    report = validate_codex_silver_originality(
                        codex_draft,
                        history_posts=load_virtual_history().get("posts", []),
                    )
                    print(format_originality_report(report))
                assert_longform_promotion_safe(article, kind=kind)
            except Exception as exc:
                if codex_draft is not None:
                    print(f"错误 [{kind}]: {exc}", file=sys.stderr)
                else:
                    print(f"❌ [{kind}] {exc}", file=sys.stderr)
                ok = False
                continue
            if kind == "market":
                market_title = article.get("title") or None
            print(f"=== {kind} ===")
            if kind == "temp" and args.variant:
                print(f"variant: {args.variant}")
            if kind == "market" and args.edition:
                print(f"edition: {args.edition}")
            if kind == "hot_business":
                business_report = article.get("hot_business_report") or {}
                score = business_report.get("candidate_score")
                print(f"候选评分: {score if score is not None else '手动指定'}")
                print(f"来源域: {business_report.get('source_domains', 0)}")
                print(f"事实条数: {business_report.get('fact_count', 0)}")
            if kind == "silver":
                silver_report = article.get("silver_report") or {}
                print(f"方向: {silver_report.get('lane', '')}")
                print(f"选题: {silver_report.get('topic', '')}")
                print(f"来源域: {silver_report.get('source_domains', 0)}")
                print(f"事实条数: {silver_report.get('fact_count', 0)}")
                print(f"权威来源: {silver_report.get('authority_source_count', 0)}")
            if kind == "short_drama_feature":
                report = article.get("short_drama_feature_report") or {}
                attempts = report.get("attempts") or []
                for attempt in attempts:
                    if attempt.get("status") == "rejected":
                        print(
                            f"{attempt.get('drama_name') or attempt.get('drama_id')}: "
                            f"已拒绝 · {attempt.get('reason') or '未通过门禁'}"
                        )
                sources = report.get("sources") or []
                official_count = sum(1 for source in sources if source.get("official"))
                print(f"来源: {len(sources)}（官方 {official_count}）")
                for source in sources:
                    print(f"来源链接: {source.get('url') or ''}")
                print(f"剧情事实: {len(report.get('facts') or [])}")
                print(f"正文去空白字符: {report.get('body_chars', 0)}")
                print(
                    f"事实门禁: {report.get('fact_gate', '')} · "
                    f"审计: {report.get('claim_audit', '')}"
                )
            print(f"标题: {article['title']}")
            print(f"摘要: {article['digest']}")
            if article.get("short_drama"):
                print(promotion_summary(article))
            short_drama_skipped = article.get("short_drama_skipped") or {}
            if kind in {"hot_business", "silver"} and short_drama_skipped:
                print(
                    "短剧推广: 已跳过 · "
                    f"{short_drama_skipped.get('reason') or '无可用候选'}"
                )
            from scripts.tools.wechat_mp_seo import print_publish_hints

            print_publish_hints(
                kind,
                article,
                edition=args.edition if kind in {"market", "sector", "hotspot"} else None,
            )
            from scripts.tools.wechat_mp_traffic_checklist import print_traffic_checklist

            print_traffic_checklist(
                kind,
                article,
                edition=args.edition if kind in {"market", "sector", "hotspot"} else None,
            )
            from scripts.tools.wechat_mp_publish_checklist import print_manual_publish_checklist

            print_manual_publish_checklist()
            pi = article.get("product_info") or {}
            fk = (pi.get("footer_product_info") or {}).get("product_key")
            if fk:
                print(f"文末商品: product_key={fk[:24]}…")
            preview_text = (
                article.get("body_text")
                if kind == "short_drama_feature"
                else article.get("content")
            )
            print(str(preview_text or "")[:1200])
            print()
        return 0 if ok else 1

    if args.force_new:
        from scripts.tools.wechat_mp_draft_slots import SLOTS_PATH

        if SLOTS_PATH.is_file():
            SLOTS_PATH.unlink()
            print("已清空槽位缓存，将全部新建", file=sys.stderr)

    ok_count = 0
    market_title: str | None = None
    for kind in kinds:
        try:
            edition = args.edition if kind in {"market", "sector", "hotspot"} else None
            article, provenance_events = _build_with_codex_provenance(
                kind,
                edition=edition,
                market_title=market_title,
                variant=args.variant,
                codex_draft=codex_draft,
                topic_hint=args.topic,
                silver_lane=args.silver_lane,
                upload_figures=True,
            )
            if codex_draft is not None and kind == "hotspot":
                from scripts.tools.wechat_mp_originality import (
                    format_originality_report,
                )
                from scripts.tools.wechat_mp_virtual_ledger import load_virtual_history

                report = validate_codex_hotspot_originality(
                    codex_draft,
                    history_posts=load_virtual_history().get("posts", []),
                )
                print(format_originality_report(report))
            if codex_draft is not None and kind == "hot_business":
                from scripts.tools.wechat_mp_originality import format_originality_report
                from scripts.tools.wechat_mp_virtual_ledger import load_virtual_history

                report = validate_codex_hot_business_originality(
                    codex_draft,
                    history_posts=load_virtual_history().get("posts", []),
                )
                print(format_originality_report(report))
            if codex_draft is not None and kind == "silver":
                from scripts.tools.wechat_mp_originality import format_originality_report
                from scripts.tools.wechat_mp_virtual_ledger import load_virtual_history

                report = validate_codex_silver_originality(
                    codex_draft,
                    history_posts=load_virtual_history().get("posts", []),
                )
                print(format_originality_report(report))
            assert_longform_promotion_safe(article, kind=kind)
        except Exception as exc:
            if codex_draft is not None:
                print(f"错误 [{kind}]: {exc}", file=sys.stderr)
            else:
                print(f"❌ [{kind}] 跳过: {exc}", file=sys.stderr)
            continue

        if kind == "market":
            market_title = article.get("title") or None

        from scripts.tools.wechat_mp_public import check_public_compliance

        compliance = check_public_compliance(
            article.get("body_text") or "",
            title=str(article.get("title") or ""),
        )
        if compliance:
            print(
                f"❌ [{kind}] 合规检查未通过: {'、'.join(compliance)}",
                file=sys.stderr,
            )
            strict = os.getenv("WECHAT_MP_STRICT_COMPLIANCE", "1").strip().lower()
            if strict not in ("0", "false", "no", "off"):
                continue

        _assert_article_provenance(
            provenance_events,
            codex_draft_supplied=codex_draft is not None,
        )

        cover_kind = _resolve_cover_kind(kind)
        cover_kind, thumb, terr = _pick_cover_for_kind(
            kind=kind,
            cover_kind=cover_kind,
            article=article,
        )
        if kind == "workspace" and (args.variant or "").strip().lower() == "english_buddy":
            from scripts.tools.wechat_mp_english_buddy_article import (
                pick_english_buddy_workspace_thumb,
            )

            thumb, terr = pick_english_buddy_workspace_thumb()
            if not thumb:
                thumb, terr = pick_thumb_for_draft_kind(kind)
        if kind == "temp" and (args.variant or "").strip().lower() == "harryputter":
            from scripts.tools.wechat_mp_harryputter_article import pick_harryputter_thumb

            thumb, terr = pick_harryputter_thumb()
            if not thumb:
                thumb, terr = pick_thumb_for_draft_kind(kind)
        if kind == "tv_review":
            from scripts.tools.wechat_mp_tv_cover import pick_tv_review_thumb
            from scripts.tools.wechat_mp_tv_topics import pick_tv_topic

            topic = pick_tv_topic()
            thumb, terr = pick_tv_review_thumb(topic)
            if not thumb:
                thumb, terr = pick_thumb_for_draft_kind(cover_kind)
        if terr:
            print(f"❌ [{kind}] 封面: {terr.get('errmsg')}", file=sys.stderr)
            continue
        meta, _ = get_material_image_meta(thumb or "")
        if meta:
            cover_note = f"({cover_kind})" if cover_kind != kind else ""
            print(
                f"封面 [{kind}]{cover_note}: {meta.get('name')} {meta.get('width')}x{meta.get('height')}",
                file=sys.stderr,
            )

        media_id, action, err = upsert_draft_article(
            kind,
            article,
            thumb_media_id=thumb or "",
            slot_key=(
                codex_slot_key
                if kind == "hotspot"
                else _resolve_draft_slot_key(kind, codex_draft)
            ),
        )
        if err:
            print(f"❌ [{kind}] 失败: {err}", file=sys.stderr)
            continue
        short_meta = article.get("short_drama") or {}
        if short_meta:
            expected_drama_id = str(short_meta.get("drama_id") or "")
            try:
                verify_saved_short_drama(
                    media_id=media_id or "",
                    expected_drama_id=expected_drama_id,
                    kind=kind,
                )
                record_drama_usage(
                    short_meta,
                    article_title=str(article.get("title") or ""),
                )
            except Exception as exc:
                print(
                    f"错误 [{kind}] 短剧草稿回读未通过: {exc}；草稿已保留，请勿发表",
                    file=sys.stderr,
                )
                continue
        if kind == "silver":
            try:
                _record_silver_topic_from_article(article)
            except Exception as exc:
                print(f"错误 [{kind}] 选题使用记录失败: {exc}；草稿已保留", file=sys.stderr)
                continue
        ok_count += 1
        verb = "已更新" if action == "updated" else "已新建"
        cover_hint = meta.get("name") if meta else ""
        print(f"OK [{kind}] {verb} media_id={media_id} · {article['title']} · 封面={cover_hint}")
        from scripts.tools.wechat_mp_seo import format_hashtag_line

        tags = article.get("recommended_hashtags") or []
        if tags:
            print(f"  {format_hashtag_line(list(tags))}")

        if args.publish or os.getenv("WECHAT_MP_AUTO_PUBLISH", "").lower() in {
            "1",
            "true",
            "yes",
        }:
            from scripts.tools.wechat_mp_client import freepublish_submit

            pub_id, pub_err = freepublish_submit(media_id=media_id or "")
            if pub_err:
                print(f"⚠️ [{kind}] 发布失败: {pub_err}", file=sys.stderr)
            else:
                print(f"OK [{kind}] publish_id={pub_id}")

    if ok_count == 0:
        return 1

    from scripts.tools.wechat_mp_prune_drafts import prune_obsolete_drafts

    prune_obsolete_drafts(dry_run=False)
    print(
        "提示: 请在 mp.weixin.qq.com 草稿箱审阅当前稿件"
    )
    print(
        "提示: 推稿前已做合规扫描；可用 wechat_mp_eval --kind all --traffic 查看评分与阅读量清单",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
