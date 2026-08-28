#!/usr/bin/env python3
"""Two-gate CLI for writing WeChat drafts through a bound DeepSeek tab."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_browser_prompt import build_browser_prompt
from scripts.tools.wechat_mp_browser_workflow import (
    BrowserWritingWorkflow,
    WorkflowTransitionError,
    WorkflowStatus,
    confirm_prompt,
    confirm_push,
    create_workflow,
    load_workflow,
    mark_blocked,
    mark_drafted,
    record_response,
    require_deepseek_browser_response,
    require_hotspot_agent_edit,
    resume_after_login,
    stage_edited_article,
)
from scripts.tools.wechat_mp_deepseek_browser import (
    DeepSeekBrowserClient,
    DeepSeekBrowserError,
    DeepSeekLoginRequired,
)


def make_browser_client() -> DeepSeekBrowserClient:
    return DeepSeekBrowserClient()


def _root(value: str) -> Path | None:
    return Path(value).resolve() if value else None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DeepSeek 浏览器写稿双确认流程")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="研究完成后创建待确认提示词")
    prepare.add_argument("--kind", choices=("hotspot", "literary"), required=True)
    prepare.add_argument("--topic", required=True)
    prepare.add_argument("--thesis", required=True)
    prepare.add_argument("--fact", action="append", default=[])
    prepare.add_argument("--research-url", action="append", default=[])
    prepare.add_argument("--root", default="")

    for name in ("confirm-prompt", "write", "resume-login", "show", "confirm-push", "push"):
        command = sub.add_parser(name)
        command.add_argument("workflow_id")
        command.add_argument("--root", default="")
    sub.choices["write"].add_argument("--timeout", type=float, default=240.0)
    stage = sub.add_parser("stage")
    stage.add_argument("workflow_id")
    stage.add_argument("--article", type=Path, required=True)
    stage.add_argument("--edit-note", action="append", default=[])
    stage.add_argument("--root", default="")
    return parser


def _show(workflow_id: str, root: Path | None) -> None:
    workflow = load_workflow(workflow_id, root=root)
    print(f"workflow_id: {workflow.workflow_id}")
    print(f"kind: {workflow.kind}")
    print(f"topic: {workflow.topic}")
    print(f"status: {workflow.status.value}")
    print(f"response_chars: {len(workflow.raw_response)}")
    if workflow.error_code:
        print(f"error_code: {workflow.error_code}")


def _validate_staged_article(
    workflow: BrowserWritingWorkflow,
    article_path: Path,
    *,
    edit_notes: tuple[str, ...] = (),
) -> str:
    if workflow.kind == "literary":
        from scripts.tools.wechat_mp_literary import load_literary_draft
        from scripts.tools.wechat_mp_literary_cache import save_literary_body_cache

        draft = load_literary_draft(article_path)
        save_literary_body_cache(draft)
        return "\n".join(
            (
                f"标题: {draft.title}",
                f"摘要: {draft.digest}",
                f"正文字符数: {len(''.join(draft.body.split()))}",
                f"来源数: {len(draft.research_urls)}",
            )
        )

    from scripts.tools.wechat_mp_codex_hotspot import (
        load_codex_hotspot_draft,
        validate_codex_hotspot_originality,
    )
    from scripts.tools.wechat_mp_virtual_ledger import load_virtual_history
    from scripts.tools.wechat_mp_codex_images import prepare_hotspot_topic_images

    draft = load_codex_hotspot_draft(article_path)
    if not any(note.strip() for note in edit_notes):
        raise WorkflowTransitionError("热点深评缺少 Agent 核实编辑记录")
    validate_codex_hotspot_originality(
        draft,
        history_posts=load_virtual_history().get("posts", []),
    )
    prepared = prepare_hotspot_topic_images(
        draft.as_discussion_topic(),
        body_count=3,
        image_policy="verified_only",
    )
    if prepared is None:
        raise RuntimeError("热点真实图片校验未返回结果")
    notes = tuple(note.strip() for note in edit_notes if note.strip())
    return "\n".join(
        (
            "成稿来源: DeepSeek 固定浏览器会话",
            f"Agent 核实编辑: {'；'.join(notes) if notes else '缺失'}",
            f"标题: {draft.title}",
            f"摘要: {draft.digest}",
            f"正文字符数: {len(''.join(draft.body.split()))}",
            f"来源数: {len(draft.research_urls)}",
            f"配图: 封面 1 张，正文 {len(prepared.body_figures)} 张",
            "配图策略: 抖音优先，仅使用可追溯真实图片",
            "本稿未自动生成图片",
        )
    )


def push_staged_workflow(
    workflow: BrowserWritingWorkflow, *, root: Path | None = None
) -> str:
    del root
    if workflow.status != WorkflowStatus.PUSH_CONFIRMED:
        raise WorkflowTransitionError(
            f"workflow 当前为 {workflow.status.value}，需要 push_confirmed"
        )
    article_path = Path(workflow.article_path)
    if workflow.kind == "literary":
        from scripts.tools.wechat_mp_literary import (
            build_literary_article,
            load_literary_draft,
        )
        from scripts.tools.wechat_mp_tv_cover import pick_discussion_draft_thumb

        draft = load_literary_draft(article_path)
        article = build_literary_article(draft, upload_figures=True)
        topic = {
            "content_mode": "discussion",
            "cover_slug": draft.topic_slug or workflow.topic,
            "title_zh": draft.topic,
            "trend_title": draft.title,
            "from_trend": True,
            "research_urls": list(draft.research_urls),
        }
        thumb, cover_error = pick_discussion_draft_thumb(topic)
        slot_key = draft.slot_key
    else:
        require_deepseek_browser_response(workflow)
        require_hotspot_agent_edit(workflow)
        from scripts.tools.wechat_mp_codex_hotspot import load_codex_hotspot_draft
        from scripts.tools.wechat_mp_content import build_hotspot_article
        from scripts.tools.wechat_mp_draft import _pick_cover_for_kind

        draft = load_codex_hotspot_draft(article_path)
        article = build_hotspot_article(
            codex_draft=draft,
            upload_figures=True,
            image_policy="verified_only",
        )
        _, thumb, cover_error = _pick_cover_for_kind(
            kind="hotspot",
            cover_kind="hotspot",
            article=article,
        )
        slot_key = draft.slot_key or "hotspot"

    content = str(article.get("content") or "")
    if any(marker in content for marker in ("[[hl:", "[[fig:", "[[cta:")):
        raise RuntimeError("最终富文本仍含未转换控制符，已拒绝推送")
    if cover_error or not thumb:
        detail = str((cover_error or {}).get("errmsg") or "未取得封面 media_id")
        raise RuntimeError(f"封面准备失败: {detail}")

    from scripts.tools.wechat_mp_codex_client import (
        generation_scope,
        record_browser_deepseek_draft,
    )
    from scripts.tools.wechat_mp_draft_slots import upsert_draft_article
    from scripts.tools.wechat_mp_short_drama import assert_longform_promotion_safe

    with generation_scope(workflow.kind):
        record_browser_deepseek_draft(workflow.kind)
        assert_longform_promotion_safe(article, kind=workflow.kind)
        media_id, _action, error = upsert_draft_article(
            workflow.kind,
            article,
            thumb_media_id=thumb,
            slot_key=slot_key,
        )
    if error or not media_id:
        raise RuntimeError(str((error or {}).get("errmsg") or "微信草稿写入失败"))
    return media_id


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    root = _root(args.root)
    try:
        if args.command == "prepare":
            prompt = build_browser_prompt(
                kind=args.kind,
                topic=args.topic,
                thesis=args.thesis,
                fact_lines=args.fact,
                research_urls=args.research_url,
            )
            workflow = create_workflow(
                kind=args.kind,
                topic=args.topic,
                prompt=prompt,
                research_urls=tuple(args.research_url),
                root=root,
            )
            print(f"workflow_id: {workflow.workflow_id}")
            print("--- prompt ---")
            print(workflow.prompt)
            return 0
        if args.command == "confirm-prompt":
            workflow = confirm_prompt(args.workflow_id, root=root)
            print(f"OK 提示词已确认: {workflow.workflow_id}")
            return 0
        if args.command == "resume-login":
            workflow = resume_after_login(args.workflow_id, root=root)
            print(f"OK 已恢复待写稿状态: {workflow.workflow_id}")
            return 0
        if args.command == "show":
            _show(args.workflow_id, root)
            return 0
        if args.command == "stage":
            workflow = load_workflow(args.workflow_id, root=root)
            if workflow.status != WorkflowStatus.RESPONSE_RECEIVED:
                raise WorkflowTransitionError(
                    f"workflow 当前为 {workflow.status.value}，需要 response_received"
                )
            summary = _validate_staged_article(
                workflow,
                args.article,
                edit_notes=tuple(args.edit_note),
            )
            saved = stage_edited_article(
                workflow.workflow_id,
                args.article,
                edit_notes=tuple(args.edit_note),
                root=root,
            )
            if summary:
                print(summary)
            print(f"OK 编辑稿已暂存，等待第二次确认: {saved.workflow_id}")
            return 0
        if args.command == "confirm-push":
            workflow = confirm_push(args.workflow_id, root=root)
            print(f"OK 推草稿已确认: {workflow.workflow_id}")
            return 0
        if args.command == "push":
            workflow = load_workflow(args.workflow_id, root=root)
            if workflow.status != WorkflowStatus.PUSH_CONFIRMED:
                raise WorkflowTransitionError(
                    f"workflow 当前为 {workflow.status.value}，需要 push_confirmed"
                )
            media_id = push_staged_workflow(workflow, root=root)
            mark_drafted(workflow.workflow_id, media_id, root=root)
            print(f"OK 已写入公众号草稿箱 media_id={media_id}")
            return 0

        workflow = load_workflow(args.workflow_id, root=root)
        if workflow.status.value != "prompt_confirmed":
            raise WorkflowTransitionError(
                f"workflow 当前为 {workflow.status.value}，需要 prompt_confirmed"
            )
        try:
            response = make_browser_client().send_and_receive(
                workflow.prompt,
                timeout_seconds=args.timeout,
            )
        except DeepSeekLoginRequired as exc:
            mark_blocked(workflow.workflow_id, "login_required", root=root)
            print(str(exc), file=sys.stderr)
            return 3
        except DeepSeekBrowserError as exc:
            mark_blocked(workflow.workflow_id, exc.__class__.__name__, root=root)
            print(f"DeepSeek 浏览器写稿失败：{exc}", file=sys.stderr)
            return 3
        saved = record_response(workflow.workflow_id, response.text, root=root)
        print(f"OK 已提取本轮 DeepSeek 回复: {saved.workflow_id}")
        print(f"正文字符数: {len(saved.raw_response)}")
        return 0
    except (ValueError, FileNotFoundError, WorkflowTransitionError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
