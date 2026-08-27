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
    article_path: str = ""
    created_at: str = ""
    sent_at: str = ""
    response_received_at: str = ""
    first_confirmation_at: str = ""
    second_confirmation_at: str = ""
    media_id: str = ""
    error_code: str = ""


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
    return BrowserWritingWorkflow(**data)


def create_workflow(
    *,
    kind: WorkflowKind,
    topic: str,
    prompt: str,
    research_urls: tuple[str, ...] = (),
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
        created_at=_now(),
    )
    return _save(workflow, root=root)


def _require(workflow: BrowserWritingWorkflow, expected: WorkflowStatus) -> None:
    if workflow.status != expected:
        raise WorkflowTransitionError(
            f"workflow 当前为 {workflow.status.value}，需要 {expected.value}"
        )


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


def record_response(
    workflow_id: str,
    raw_response: str,
    *,
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
            sent_at=sent_at or now,
            response_received_at=now,
        ),
        root=root,
    )


def stage_edited_article(
    workflow_id: str,
    article_path: Path,
    *,
    root: Path | None = None,
) -> BrowserWritingWorkflow:
    workflow = load_workflow(workflow_id, root=root)
    _require(workflow, WorkflowStatus.RESPONSE_RECEIVED)
    source = Path(article_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"未找到编辑后稿件: {source}")
    return _save(
        replace(workflow, status=WorkflowStatus.EDITED, article_path=str(source)),
        root=root,
    )


def confirm_push(workflow_id: str, *, root: Path | None = None) -> BrowserWritingWorkflow:
    workflow = load_workflow(workflow_id, root=root)
    _require(workflow, WorkflowStatus.EDITED)
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
        replace(workflow, status=WorkflowStatus.DRAFTED, media_id=clean_id),
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
