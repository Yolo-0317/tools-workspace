from __future__ import annotations

import json
import hashlib
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
    record_confirmed_body,
    record_pasted_response,
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


def test_hotspot_response_records_deepseek_browser_provider(tmp_path: Path) -> None:
    workflow = create_workflow(
        kind="hotspot",
        topic="测试热点",
        prompt="写一篇热点深评",
        root=tmp_path,
    )
    confirm_prompt(workflow.workflow_id, root=tmp_path)

    saved = record_response(workflow.workflow_id, "标题\n\n正文", root=tmp_path)

    assert saved.response_provider == "deepseek_browser"


def test_hotspot_user_pasted_deepseek_response_can_be_staged(tmp_path: Path) -> None:
    """Catch regressions that force Codex to operate the DeepSeek browser itself."""
    workflow = create_workflow(
        kind="hotspot",
        topic="测试热点",
        prompt="写一篇热点深评",
        root=tmp_path,
    )
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    pasted = record_pasted_response(
        workflow.workflow_id,
        "DeepSeek 初稿标题\n\nDeepSeek 初稿正文",
        root=tmp_path,
    )
    article_path = tmp_path / "hotspot.json"
    article_path.write_text("{}", encoding="utf-8")

    staged = stage_edited_article(
        pasted.workflow_id,
        article_path,
        edit_notes=("核对关键事实",),
        root=tmp_path,
    )

    assert pasted.response_provider == "deepseek_user_paste"
    assert staged.status == WorkflowStatus.EDITED


def test_hotspot_thread_confirmed_body_can_be_staged(tmp_path: Path) -> None:
    workflow = create_workflow(
        kind="hotspot",
        topic="测试热点",
        prompt="写一篇热点深评",
        root=tmp_path,
    )
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    body = "\n\n".join(
        (
            "测试标题",
            "第一段交代事件发生的时间、地点和当事人，并把读者真正关心的问题说清楚。" * 4,
            "第二段补充公开规则、当事方回应和仍需等待的信息，不把推断写成已经发生的事实。" * 4,
            "第三段说明这件事对普通人的具体影响，也保留已有安排和适用范围。" * 4,
            "最后一段回到付款、选择和责任边界，给读者留下一个可以继续讨论的问题。" * 4,
        )
    )

    recorded = record_confirmed_body(
        workflow.workflow_id,
        body,
        confirmation_text="就按照刚刚的正文发布",
        root=tmp_path,
    )
    article_path = tmp_path / "hotspot.json"
    article_path.write_text("{}", encoding="utf-8")
    staged = stage_edited_article(
        recorded.workflow_id,
        article_path,
        edit_notes=("核对关键事实",),
        root=tmp_path,
    )

    assert recorded.status == WorkflowStatus.RESPONSE_RECEIVED
    assert recorded.response_provider == "thread_confirmed_body"
    assert recorded.response_confirmation_text == "就按照刚刚的正文发布"
    assert recorded.response_confirmation_at
    assert staged.status == WorkflowStatus.EDITED


def test_thread_confirmed_body_directly_records_researched_workflow(tmp_path: Path) -> None:
    workflow = create_workflow(
        kind="hotspot", topic="测试热点", prompt="提示词", root=tmp_path
    )
    body = "标题\n\n" + ("这是完整正文，说明事实和读者关切。\n\n" * 35)

    recorded = record_confirmed_body(
        workflow.workflow_id,
        body,
        confirmation_text="核对后按这篇推草稿",
        root=tmp_path,
    )

    assert recorded.status == WorkflowStatus.RESPONSE_RECEIVED
    assert recorded.first_confirmation_at == ""
    assert recorded.response_sha256 == hashlib.sha256(body.strip().encode("utf-8")).hexdigest()


def test_thread_confirmed_body_rejects_empty_confirmation(tmp_path: Path) -> None:
    workflow = create_workflow(
        kind="hotspot", topic="测试热点", prompt="提示词", root=tmp_path
    )
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    body = ("完整正文内容。" * 100) + "\n\n" + ("继续解释事情。" * 100)

    with pytest.raises(ValueError, match="确认原话不能为空"):
        record_confirmed_body(
            workflow.workflow_id,
            body,
            confirmation_text=" ",
            root=tmp_path,
        )


def test_thread_confirmed_body_rejects_review_conclusion(tmp_path: Path) -> None:
    workflow = create_workflow(
        kind="hotspot", topic="测试热点", prompt="提示词", root=tmp_path
    )
    confirm_prompt(workflow.workflow_id, root=tmp_path)

    with pytest.raises(ValueError, match="完整正文"):
        record_confirmed_body(
            workflow.workflow_id,
            "这版通过，可以直接进入排版流程。\n\n核对要点：标题合规，事实边界清楚。",
            confirmation_text="确认发布",
            root=tmp_path,
        )


def test_hotspot_stage_rejects_missing_deepseek_provider(tmp_path: Path) -> None:
    workflow = create_workflow(
        kind="hotspot",
        topic="测试热点",
        prompt="写一篇热点深评",
        root=tmp_path,
    )
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    responded = record_response(workflow.workflow_id, "标题\n\n正文", root=tmp_path)
    state_path = tmp_path / f"{responded.workflow_id}.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["response_provider"] = ""
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    article_path = tmp_path / "hotspot.json"
    article_path.write_text("{}", encoding="utf-8")

    with pytest.raises(WorkflowTransitionError, match="DeepSeek 初稿来源"):
        stage_edited_article(responded.workflow_id, article_path, root=tmp_path)


def test_hotspot_stage_requires_agent_edit_notes(tmp_path: Path) -> None:
    workflow = create_workflow(
        kind="hotspot",
        topic="测试热点",
        prompt="写一篇热点深评",
        root=tmp_path,
    )
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    record_response(workflow.workflow_id, "标题\n\n正文", root=tmp_path)
    article_path = tmp_path / "hotspot.json"
    article_path.write_text("{}", encoding="utf-8")

    with pytest.raises(WorkflowTransitionError, match="Agent 核实编辑记录"):
        stage_edited_article(workflow.workflow_id, article_path, root=tmp_path)


def test_hotspot_stage_records_agent_edit_notes(tmp_path: Path) -> None:
    workflow = create_workflow(
        kind="hotspot",
        topic="测试热点",
        prompt="写一篇热点深评",
        root=tmp_path,
    )
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    record_response(workflow.workflow_id, "标题\n\n正文", root=tmp_path)
    article_path = tmp_path / "hotspot.json"
    article_path.write_text("{}", encoding="utf-8")

    saved = stage_edited_article(
        workflow.workflow_id,
        article_path,
        edit_notes=("核对法院案号与裁判要点", "删去无法回源的推断"),
        root=tmp_path,
    )

    assert saved.edit_notes == (
        "核对法院案号与裁判要点",
        "删去无法回源的推断",
    )


def test_new_hotspot_workflow_requires_handoff_before_staging(tmp_path: Path) -> None:
    workflow = create_workflow(
        kind="hotspot", topic="测试热点", prompt="提示词", handoff_required=True,
        root=tmp_path,
    )
    body = "标题\n\n" + ("完整正文说明事件和影响。\n\n" * 60)
    record_confirmed_body(
        workflow.workflow_id, body, confirmation_text="按这篇推草稿", root=tmp_path
    )
    article = tmp_path / "article.json"
    article.write_text("{}", encoding="utf-8")

    with pytest.raises(WorkflowTransitionError, match="交付记录"):
        stage_edited_article(
            workflow.workflow_id, article, edit_notes=("核对关键事实",),
            root=tmp_path,
        )


def test_new_hotspot_staging_detects_later_article_replacement(tmp_path: Path) -> None:
    from scripts.tools.wechat_mp_browser_workflow import require_staged_article_unchanged

    workflow = create_workflow(
        kind="hotspot", topic="测试热点", prompt="提示词", handoff_required=True,
        root=tmp_path,
    )
    body = "标题\n\n" + ("完整正文说明事件和影响。\n\n" * 60)
    record_confirmed_body(
        workflow.workflow_id, body, confirmation_text="按这篇推草稿", root=tmp_path
    )
    article = tmp_path / "article.json"
    article.write_text("{}", encoding="utf-8")
    handoff = tmp_path / "editorial_handoff.json"
    handoff.write_text("{}", encoding="utf-8")
    staged = stage_edited_article(
        workflow.workflow_id, article, handoff_path=handoff,
        edit_notes=("核对关键事实",), root=tmp_path,
    )
    article.write_text('{"changed":true}', encoding="utf-8")

    with pytest.raises(WorkflowTransitionError, match="暂存后发生变化"):
        require_staged_article_unchanged(staged)


def test_hotspot_confirm_push_rechecks_agent_edit_notes(tmp_path: Path) -> None:
    workflow = create_workflow(
        kind="hotspot",
        topic="测试热点",
        prompt="写一篇热点深评",
        root=tmp_path,
    )
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    responded = record_response(workflow.workflow_id, "标题\n\n正文", root=tmp_path)
    article_path = tmp_path / "hotspot.json"
    article_path.write_text("{}", encoding="utf-8")
    staged = stage_edited_article(
        responded.workflow_id,
        article_path,
        edit_notes=("核对关键事实",),
        root=tmp_path,
    )
    state_path = tmp_path / f"{staged.workflow_id}.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["edit_notes"] = []
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(WorkflowTransitionError, match="Agent 核实编辑记录"):
        confirm_push(staged.workflow_id, root=tmp_path)


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
