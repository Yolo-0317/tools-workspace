from __future__ import annotations

from pathlib import Path

import pytest

from scripts.tools.wechat_mp_browser_workflow import (
    WorkflowStatus,
    WorkflowTransitionError,
    confirm_prompt,
    confirm_push,
    create_workflow,
    load_workflow,
    mark_drafted,
    mark_blocked,
    record_response,
    resume_after_login,
    stage_edited_article,
)


def test_workflow_requires_prompt_confirmation_before_response(tmp_path: Path) -> None:
    workflow = create_workflow(
        kind="hotspot",
        topic="测试热点",
        prompt="写一篇热点深评",
        research_urls=("https://a.example/x",),
        root=tmp_path,
    )

    with pytest.raises(WorkflowTransitionError, match="prompt_confirmed"):
        record_response(workflow.workflow_id, "标题\n\n正文", root=tmp_path)

    assert load_workflow(workflow.workflow_id, root=tmp_path).status == WorkflowStatus.RESEARCHED


def test_workflow_requires_second_confirmation_before_drafted(tmp_path: Path) -> None:
    workflow = create_workflow(
        kind="literary",
        topic="《史记》",
        prompt="写一篇文学讨论稿",
        root=tmp_path,
    )
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    record_response(workflow.workflow_id, "标题\n\n正文", root=tmp_path)
    article_path = tmp_path / "literary.json"
    article_path.write_text("{}", encoding="utf-8")
    stage_edited_article(workflow.workflow_id, article_path, root=tmp_path)

    with pytest.raises(WorkflowTransitionError, match="push_confirmed"):
        mark_drafted(workflow.workflow_id, "media-id", root=tmp_path)

    confirm_push(workflow.workflow_id, root=tmp_path)
    drafted = mark_drafted(workflow.workflow_id, "media-id", root=tmp_path)
    assert drafted.status == WorkflowStatus.DRAFTED
    assert drafted.media_id == "media-id"


def test_confirmation_cannot_be_reused_by_another_workflow(tmp_path: Path) -> None:
    first = create_workflow(kind="hotspot", topic="甲", prompt="甲提示", root=tmp_path)
    second = create_workflow(kind="hotspot", topic="乙", prompt="乙提示", root=tmp_path)

    confirm_prompt(first.workflow_id, root=tmp_path)

    assert load_workflow(first.workflow_id, root=tmp_path).status == WorkflowStatus.PROMPT_CONFIRMED
    assert load_workflow(second.workflow_id, root=tmp_path).status == WorkflowStatus.RESEARCHED
    assert load_workflow(second.workflow_id, root=tmp_path).first_confirmation_at == ""


def test_login_block_can_resume_without_reusing_or_skipping_confirmation(tmp_path: Path) -> None:
    workflow = create_workflow(kind="hotspot", topic="甲", prompt="甲提示", root=tmp_path)
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    mark_blocked(workflow.workflow_id, "login_required", root=tmp_path)

    resumed = resume_after_login(workflow.workflow_id, root=tmp_path)

    assert resumed.status == WorkflowStatus.PROMPT_CONFIRMED
    assert resumed.first_confirmation_at
    assert resumed.second_confirmation_at == ""
    assert resumed.error_code == ""


def test_non_login_block_cannot_resume_as_login(tmp_path: Path) -> None:
    workflow = create_workflow(kind="hotspot", topic="甲", prompt="甲提示", root=tmp_path)
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    mark_blocked(workflow.workflow_id, "response_timeout", root=tmp_path)

    with pytest.raises(WorkflowTransitionError, match="login_required"):
        resume_after_login(workflow.workflow_id, root=tmp_path)
