"""Persistent state gates for DeepSeek-browser authored WeChat drafts."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import ROOT

TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_WORKFLOW_DIR = ROOT / "output" / "wechat_mp_browser_workflows"
FIXED_CONVERSATION_ID = "f0cc031d-233f-4648-807d-354275738e61"
WorkflowKind = Literal["hotspot", "literary"]


class WorkflowStatus(StrEnum):
    RESEARCHED = "researched"
    PROMPT_CONFIRMED = "prompt_confirmed"
    RESPONSE_RECEIVED = "response_received"
    EDITED = "edited"
    PUSH_CONFIRMED = "push_confirmed"
    DRAFTED = "drafted"
    BLOCKED = "blocked"


class WorkflowTransitionError(ValueError):
    """Raised when a workflow attempts to skip a confirmation gate."""


@dataclass(frozen=True)
class BrowserWritingWorkflow:
    workflow_id: str
    kind: WorkflowKind
    topic: str
    prompt: str
    prompt_sha256: str
    conversation_id: str
    status: WorkflowStatus
    research_urls: tuple[str, ...] = ()
    raw_response: str = ""
    response_provider: str = ""
    response_confirmation_text: str = ""
    response_confirmation_at: str = ""
    response_sha256: str = ""
    handoff_required: bool = False
    handoff_path: str = ""
    article_sha256: str = ""
    edit_notes: tuple[str, ...] = ()
    article_path: str = ""
    created_at: str = ""
    sent_at: str = ""
    response_received_at: str = ""
    first_confirmation_at: str = ""
    second_confirmation_at: str = ""
    media_id: str = ""
    error_code: str = ""
    push_egress_failures: int = 0


def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _workflow_dir(root: Path | None) -> Path:
    return Path(root) if root is not None else DEFAULT_WORKFLOW_DIR


def _workflow_path(workflow_id: str, *, root: Path | None) -> Path:
    clean_id = (workflow_id or "").strip()
    if not clean_id or any(ch not in "0123456789abcdef-" for ch in clean_id.lower()):
        raise ValueError("workflow_id 无效")
    return _workflow_dir(root) / f"{clean_id}.json"


def _save(workflow: BrowserWritingWorkflow, *, root: Path | None) -> BrowserWritingWorkflow:
    path = _workflow_path(workflow.workflow_id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(workflow)
    payload["status"] = workflow.status.value
    payload["research_urls"] = list(workflow.research_urls)
    payload["edit_notes"] = list(workflow.edit_notes)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return workflow


def load_workflow(
    workflow_id: str, *, root: Path | None = None
) -> BrowserWritingWorkflow:
    path = _workflow_path(workflow_id, root=root)
    if not path.is_file():
        raise FileNotFoundError(f"未找到浏览器写稿 workflow: {workflow_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = WorkflowStatus(str(data["status"]))
    data["research_urls"] = tuple(data.get("research_urls") or ())
    data["edit_notes"] = tuple(data.get("edit_notes") or ())
    return BrowserWritingWorkflow(**data)


def create_workflow(
    *,
    kind: WorkflowKind,
    topic: str,
    prompt: str,
    research_urls: tuple[str, ...] = (),
    handoff_required: bool = False,
    root: Path | None = None,
) -> BrowserWritingWorkflow:
    if kind not in {"hotspot", "literary"}:
        raise ValueError("kind 只允许 hotspot 或 literary")
    clean_topic = (topic or "").strip()
    clean_prompt = (prompt or "").strip()
    if not clean_topic or not clean_prompt:
        raise ValueError("topic 和 prompt 必须非空")
    workflow = BrowserWritingWorkflow(
        workflow_id=str(uuid.uuid4()),
        kind=kind,
        topic=clean_topic,
        prompt=clean_prompt,
        prompt_sha256=hashlib.sha256(clean_prompt.encode("utf-8")).hexdigest(),
        conversation_id=FIXED_CONVERSATION_ID,
        status=WorkflowStatus.RESEARCHED,
        research_urls=tuple(url.strip() for url in research_urls if url.strip()),
        handoff_required=handoff_required if kind == "hotspot" else False,
        created_at=_now(),
    )
    return _save(workflow, root=root)


def _require(workflow: BrowserWritingWorkflow, expected: WorkflowStatus) -> None:
    if workflow.status != expected:
        raise WorkflowTransitionError(
            f"workflow 当前为 {workflow.status.value}，需要 {expected.value}"
        )


def require_hotspot_body_provenance(workflow: BrowserWritingWorkflow) -> None:
    """用户主动热点必须保留可追溯的完整正文来源。"""

    if workflow.kind != "hotspot":
        return
    if workflow.conversation_id != FIXED_CONVERSATION_ID:
        raise WorkflowTransitionError("热点深评必须来自指定 DeepSeek 固定会话")
    if workflow.response_provider not in {
        "deepseek_browser",
        "deepseek_user_paste",
        "thread_confirmed_body",
    } or not workflow.raw_response.strip():
        raise WorkflowTransitionError("热点深评缺少 DeepSeek 初稿来源")
    if workflow.response_provider == "thread_confirmed_body" and (
        not workflow.response_confirmation_text.strip()
        or not workflow.response_confirmation_at.strip()
    ):
        raise WorkflowTransitionError("热点深评缺少当前任务正文确认记录")


def require_deepseek_browser_response(workflow: BrowserWritingWorkflow) -> None:
    """兼容旧调用名；实际校验所有允许的热点正文来源。"""

    require_hotspot_body_provenance(workflow)


def require_hotspot_agent_edit(workflow: BrowserWritingWorkflow) -> None:
    if workflow.kind == "hotspot" and not any(
        note.strip() for note in workflow.edit_notes
    ):
        raise WorkflowTransitionError("热点深评缺少 Agent 核实编辑记录")


def confirm_prompt(workflow_id: str, *, root: Path | None = None) -> BrowserWritingWorkflow:
    workflow = load_workflow(workflow_id, root=root)
    _require(workflow, WorkflowStatus.RESEARCHED)
    return _save(
        replace(
            workflow,
            status=WorkflowStatus.PROMPT_CONFIRMED,
            first_confirmation_at=_now(),
        ),
        root=root,
    )


def _record_response_with_provider(
    workflow_id: str,
    raw_response: str,
    *,
    provider: str,
    sent_at: str = "",
    root: Path | None = None,
) -> BrowserWritingWorkflow:
    workflow = load_workflow(workflow_id, root=root)
    _require(workflow, WorkflowStatus.PROMPT_CONFIRMED)
    response = (raw_response or "").strip()
    if not response:
        raise ValueError("DeepSeek 回复不能为空")
    now = _now()
    return _save(
        replace(
            workflow,
            status=WorkflowStatus.RESPONSE_RECEIVED,
            raw_response=response,
            response_provider=provider,
            response_sha256=hashlib.sha256(response.encode("utf-8")).hexdigest(),
            sent_at=sent_at or now,
            response_received_at=now,
        ),
        root=root,
    )


def record_response(
    workflow_id: str,
    raw_response: str,
    *,
    sent_at: str = "",
    root: Path | None = None,
) -> BrowserWritingWorkflow:
    return _record_response_with_provider(
        workflow_id,
        raw_response,
        provider="deepseek_browser",
        sent_at=sent_at,
        root=root,
    )


def record_pasted_response(
    workflow_id: str,
    raw_response: str,
    *,
    sent_at: str = "",
    root: Path | None = None,
) -> BrowserWritingWorkflow:
    """记录由用户从 DeepSeek 会话粘贴回来的初稿。"""

    return _record_response_with_provider(
        workflow_id,
        raw_response,
        provider="deepseek_user_paste",
        sent_at=sent_at,
        root=root,
    )


def _looks_like_complete_article(text: str) -> bool:
    compact = "".join(text.split())
    paragraphs = tuple(part.strip() for part in text.split("\n\n") if part.strip())
    review_prefixes = (
        "这版通过",
        "这篇稿子已经",
        "核对要点",
        "诊断结论",
        "可以直接进入排版流程",
    )
    return (
        len(compact) >= 500
        and len(paragraphs) >= 4
        and not paragraphs[0].startswith(review_prefixes)
    )


def record_confirmed_body(
    workflow_id: str,
    raw_response: str,
    *,
    confirmation_text: str,
    sent_at: str = "",
    root: Path | None = None,
) -> BrowserWritingWorkflow:
    """记录已在当前任务完整展示并由用户明确确认的热点正文。"""

    workflow = load_workflow(workflow_id, root=root)
    if workflow.status not in {WorkflowStatus.RESEARCHED, WorkflowStatus.PROMPT_CONFIRMED}:
        raise WorkflowTransitionError(
            f"workflow 当前为 {workflow.status.value}，需要 researched 或 prompt_confirmed"
        )
    if workflow.kind != "hotspot":
        raise WorkflowTransitionError("当前任务确认正文来源仅适用于热点深评")
    response = (raw_response or "").strip()
    confirmation = (confirmation_text or "").strip()
    if not confirmation:
        raise ValueError("用户确认原话不能为空")
    if not _looks_like_complete_article(response):
        raise ValueError("当前任务确认来源必须包含完整正文，不能只有审核结论或摘要")
    now = _now()
    return _save(
        replace(
            workflow,
            status=WorkflowStatus.RESPONSE_RECEIVED,
            raw_response=response,
            response_provider="thread_confirmed_body",
            response_confirmation_text=confirmation,
            response_confirmation_at=now,
            response_sha256=hashlib.sha256(response.encode("utf-8")).hexdigest(),
            sent_at=sent_at or now,
            response_received_at=now,
        ),
        root=root,
    )


def stage_edited_article(
    workflow_id: str,
    article_path: Path,
    *,
    edit_notes: tuple[str, ...] = (),
    handoff_path: Path | None = None,
    root: Path | None = None,
) -> BrowserWritingWorkflow:
    workflow = load_workflow(workflow_id, root=root)
    _require(workflow, WorkflowStatus.RESPONSE_RECEIVED)
    require_hotspot_body_provenance(workflow)
    source = Path(article_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"未找到编辑后稿件: {source}")
    notes = tuple(note.strip() for note in edit_notes if note.strip())
    if workflow.kind == "hotspot" and not notes:
        raise WorkflowTransitionError("热点深评缺少 Agent 核实编辑记录")
    if workflow.handoff_required and handoff_path is None:
        raise WorkflowTransitionError("新热点流程缺少交付记录")
    handoff = Path(handoff_path).resolve() if handoff_path is not None else None
    if handoff is not None and not handoff.is_file():
        raise FileNotFoundError(f"未找到交付记录: {handoff}")
    return _save(
        replace(
            workflow,
            status=WorkflowStatus.EDITED,
            article_path=str(source),
            article_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            handoff_path=str(handoff) if handoff is not None else "",
            edit_notes=notes,
        ),
        root=root,
    )


def require_staged_article_unchanged(workflow: BrowserWritingWorkflow) -> None:
    if not workflow.article_sha256 or not workflow.article_path:
        if workflow.handoff_required:
            raise WorkflowTransitionError("新热点流程缺少暂存文章摘要")
        return
    actual = hashlib.sha256(Path(workflow.article_path).read_bytes()).hexdigest()
    if actual != workflow.article_sha256:
        raise WorkflowTransitionError("文章在暂存后发生变化，需要重新核验并确认")


def confirm_push(workflow_id: str, *, root: Path | None = None) -> BrowserWritingWorkflow:
    workflow = load_workflow(workflow_id, root=root)
    _require(workflow, WorkflowStatus.EDITED)
    require_hotspot_body_provenance(workflow)
    require_hotspot_agent_edit(workflow)
    return _save(
        replace(
            workflow,
            status=WorkflowStatus.PUSH_CONFIRMED,
            second_confirmation_at=_now(),
        ),
        root=root,
    )


def mark_drafted(
    workflow_id: str,
    media_id: str,
    *,
    root: Path | None = None,
) -> BrowserWritingWorkflow:
    workflow = load_workflow(workflow_id, root=root)
    _require(workflow, WorkflowStatus.PUSH_CONFIRMED)
    clean_id = (media_id or "").strip()
    if not clean_id:
        raise ValueError("media_id 不能为空")
    return _save(
        replace(workflow, status=WorkflowStatus.DRAFTED, media_id=clean_id, error_code=""),
        root=root,
    )


def record_push_environment_failure(
    workflow_id: str, error_code: str, *, root: Path | None = None
) -> BrowserWritingWorkflow:
    """保留推送确认与稿件，供环境恢复后人工重试。"""
    workflow = load_workflow(workflow_id, root=root)
    _require(workflow, WorkflowStatus.PUSH_CONFIRMED)
    clean_code = (error_code or "push_environment_failure").strip()[:80]
    return _save(
        replace(
            workflow,
            error_code=clean_code,
            push_egress_failures=workflow.push_egress_failures + 1,
        ),
        root=root,
    )


def mark_blocked(
    workflow_id: str,
    error_code: str,
    *,
    root: Path | None = None,
) -> BrowserWritingWorkflow:
    workflow = load_workflow(workflow_id, root=root)
    if workflow.status in {WorkflowStatus.DRAFTED, WorkflowStatus.BLOCKED}:
        raise WorkflowTransitionError(f"workflow 已是终态 {workflow.status.value}")
    clean_code = (error_code or "unknown_error").strip()[:80]
    return _save(
        replace(workflow, status=WorkflowStatus.BLOCKED, error_code=clean_code),
        root=root,
    )


def resume_after_login(
    workflow_id: str, *, root: Path | None = None
) -> BrowserWritingWorkflow:
    """Resume only a login-blocked write without reusing either confirmation."""
    workflow = load_workflow(workflow_id, root=root)
    _require(workflow, WorkflowStatus.BLOCKED)
    if workflow.error_code != "login_required":
        raise WorkflowTransitionError(
            "只有 error_code=login_required 的 workflow 可以在登录后恢复"
        )
    if not workflow.first_confirmation_at or workflow.second_confirmation_at:
        raise WorkflowTransitionError("登录恢复所需的确认状态无效")
    return _save(
        replace(
            workflow,
            status=WorkflowStatus.PROMPT_CONFIRMED,
            error_code="",
        ),
        root=root,
    )
