from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path

from scripts.tools import wechat_mp_browser_write as browser_cli
from scripts.tools.wechat_mp_browser_workflow import (
    BrowserWritingWorkflow,
    FIXED_CONVERSATION_ID,
    WorkflowStatus,
    WorkflowTransitionError,
    confirm_prompt,
    create_workflow,
    load_workflow,
    record_response,
)
import pytest


@pytest.fixture(autouse=True)
def _allow_wechat_egress_preflight(monkeypatch) -> None:
    from scripts.tools import wechat_mp_client

    monkeypatch.setattr(
        wechat_mp_client,
        "verify_required_wechat_egress",
        lambda: {"ok": True, "required_ip": None, "observed_ip": None},
    )


def test_push_provenance_uses_user_pasted_deepseek_source(monkeypatch) -> None:
    from scripts.tools import wechat_mp_codex_client

    workflow = BrowserWritingWorkflow(
        workflow_id="00000000-0000-0000-0000-000000000004",
        kind="hotspot",
        topic="热点主题",
        prompt="提示词",
        prompt_sha256="hash",
        conversation_id=FIXED_CONVERSATION_ID,
        status=WorkflowStatus.PUSH_CONFIRMED,
        raw_response="DeepSeek 初稿",
        response_provider="deepseek_user_paste",
        edit_notes=("核对公开回应",),
    )
    calls: list[str] = []
    monkeypatch.setattr(
        wechat_mp_codex_client,
        "record_browser_deepseek_draft",
        lambda kind: calls.append(f"browser:{kind}"),
    )
    monkeypatch.setattr(
        wechat_mp_codex_client,
        "record_user_pasted_deepseek_draft",
        lambda kind: calls.append(f"pasted:{kind}"),
    )

    browser_cli._record_workflow_deepseek_provenance(workflow)

    assert calls == ["pasted:hotspot"]


def test_push_provenance_uses_thread_confirmed_source(monkeypatch) -> None:
    from scripts.tools import wechat_mp_codex_client

    workflow = BrowserWritingWorkflow(
        workflow_id="00000000-0000-0000-0000-000000000104",
        kind="hotspot",
        topic="热点主题",
        prompt="提示词",
        prompt_sha256="hash",
        conversation_id=FIXED_CONVERSATION_ID,
        status=WorkflowStatus.PUSH_CONFIRMED,
        raw_response="完整正文" * 200,
        response_provider="thread_confirmed_body",
        response_confirmation_text="就按照刚刚的正文发布",
        response_confirmation_at="2026-09-16T12:00:00+08:00",
        edit_notes=("核对公开回应",),
    )
    calls: list[str] = []
    monkeypatch.setattr(
        wechat_mp_codex_client,
        "record_browser_deepseek_draft",
        lambda kind: calls.append(f"browser:{kind}"),
    )
    monkeypatch.setattr(
        wechat_mp_codex_client,
        "record_user_pasted_deepseek_draft",
        lambda kind: calls.append(f"pasted:{kind}"),
    )
    monkeypatch.setattr(
        wechat_mp_codex_client,
        "record_thread_confirmed_body",
        lambda kind: calls.append(f"thread:{kind}"),
    )

    browser_cli._record_workflow_deepseek_provenance(workflow)

    assert calls == ["thread:hotspot"]


def test_push_preflights_wechat_egress_before_reading_article(monkeypatch) -> None:
    from scripts.tools import wechat_mp_client

    workflow = BrowserWritingWorkflow(
        workflow_id="00000000-0000-0000-0000-000000000005",
        kind="literary",
        topic="史记",
        prompt="提示词",
        prompt_sha256="hash",
        conversation_id="conversation",
        status=WorkflowStatus.PUSH_CONFIRMED,
        article_path="/path/that/must/not/be/read.json",
    )
    monkeypatch.setattr(
        wechat_mp_client,
        "verify_required_wechat_egress",
        lambda: (_ for _ in ()).throw(RuntimeError("微信 API 出口未通过预检")),
    )

    with pytest.raises(RuntimeError, match="出口未通过预检"):
        browser_cli.push_staged_workflow(workflow)


def test_egress_failure_preserves_confirmed_workflow_for_retry(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts.tools import wechat_mp_client
    from scripts.tools.wechat_mp_browser_workflow import (
        confirm_push, record_confirmed_body, stage_edited_article,
    )

    workflow = create_workflow(
        kind="hotspot", topic="测试热点", prompt="提示词", root=tmp_path
    )
    body = "标题\n\n" + ("这是已经确认的完整文章正文。\n\n" * 50)
    record_confirmed_body(
        workflow.workflow_id, body, confirmation_text="按这篇推草稿", root=tmp_path
    )
    article = tmp_path / "article.json"
    article.write_text("{}", encoding="utf-8")
    stage_edited_article(
        workflow.workflow_id, article, edit_notes=("核对来源",), root=tmp_path
    )
    confirm_push(workflow.workflow_id, root=tmp_path)
    preflight_calls: list[int] = []

    def failed_preflight() -> None:
        preflight_calls.append(1)
        raise RuntimeError("微信 API 出口预检失败: -2")

    monkeypatch.setattr(
        wechat_mp_client, "verify_required_wechat_egress", failed_preflight
    )

    result = browser_cli.main(
        ["push", workflow.workflow_id, "--root", str(tmp_path)]
    )

    saved = load_workflow(workflow.workflow_id, root=tmp_path)
    assert result == 3
    assert saved.status == WorkflowStatus.PUSH_CONFIRMED
    assert saved.error_code == "wechat_egress_unavailable"
    assert saved.article_path == str(article.resolve())
    assert saved.second_confirmation_at
    assert saved.push_egress_failures == 1

    assert browser_cli.main(["push", workflow.workflow_id, "--root", str(tmp_path)]) == 3
    assert load_workflow(workflow.workflow_id, root=tmp_path).push_egress_failures == 2
    assert browser_cli.main(["push", workflow.workflow_id, "--root", str(tmp_path)]) == 3
    assert preflight_calls == [1, 1]


def test_literary_next_push_uses_article_slot(tmp_path: Path, monkeypatch) -> None:
    from scripts.tools import wechat_mp_codex_client
    from scripts.tools import wechat_mp_draft_slots
    from scripts.tools import wechat_mp_literary
    from scripts.tools import wechat_mp_short_drama
    from scripts.tools import wechat_mp_tv_cover

    payload = _literary_payload()
    payload["slot_key"] = "literary_next"
    article_path = tmp_path / "literary-next.json"
    article_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    workflow = BrowserWritingWorkflow(
        workflow_id="00000000-0000-0000-0000-000000000001",
        kind="literary",
        topic="史记",
        prompt="提示词",
        prompt_sha256="hash",
        conversation_id="conversation",
        status=WorkflowStatus.PUSH_CONFIRMED,
        article_path=str(article_path),
    )
    used_slots: list[str] = []

    monkeypatch.setattr(
        wechat_mp_literary,
        "build_literary_article",
        lambda draft, upload_figures=True: {
            "title": draft.title,
            "content": "<p>正文</p>",
            "slot_key": draft.slot_key,
        },
    )
    monkeypatch.setattr(
        wechat_mp_tv_cover,
        "pick_discussion_draft_thumb",
        lambda topic: ("thumb", None),
    )
    monkeypatch.setattr(wechat_mp_codex_client, "generation_scope", lambda kind: nullcontext())
    monkeypatch.setattr(wechat_mp_codex_client, "record_browser_deepseek_draft", lambda kind: None)
    monkeypatch.setattr(wechat_mp_short_drama, "assert_longform_promotion_safe", lambda *a, **k: None)
    monkeypatch.setattr(
        wechat_mp_draft_slots,
        "upsert_draft_article",
        lambda kind, article, thumb_media_id, slot_key: (
            used_slots.append(slot_key) or "new-media",
            "created",
            None,
        ),
    )

    media_id = browser_cli.push_staged_workflow(workflow, root=tmp_path)

    assert media_id == "new-media"
    assert used_slots == ["literary_next"]


def _literary_payload() -> dict:
    return {
        "title": "司马迁真正难的，不只是活下来",
        "digest": "从《史记》的写作选择，看一个人怎样处理评价与目标。",
        "body": "司马迁站在未写完的竹简前，他需要决定这部书还能不能写完。" * 58,
        "topic": "典籍里的中国 史记",
        "research_urls": [
            "https://www.chnmuseum.cn/a",
            "https://tv.cctv.com/b",
            "https://www.nlc.cn/c",
        ],
        "original_thesis": "司马迁真正重要的选择，是让写作目标压过同时代人对个人尊严的评价。",
        "slot_key": "literary",
        "topic_slug": "dianji-shiji",
    }


def _response_workflow(tmp_path: Path):
    workflow = create_workflow(kind="literary", topic="史记", prompt="提示词", root=tmp_path)
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    return record_response(workflow.workflow_id, "标题\n\n正文", root=tmp_path)


def test_stage_validates_article_and_push_refuses_without_second_confirmation(
    tmp_path: Path, monkeypatch
) -> None:
    workflow = _response_workflow(tmp_path)
    article_path = tmp_path / "literary.json"
    article_path.write_text(json.dumps(_literary_payload(), ensure_ascii=False), encoding="utf-8")
    assert browser_cli.main(
        ["stage", workflow.workflow_id, "--article", str(article_path), "--root", str(tmp_path)]
    ) == 0
    calls: list[str] = []
    monkeypatch.setattr(browser_cli, "push_staged_workflow", lambda *a, **k: calls.append("push"))

    result = browser_cli.main(["push", workflow.workflow_id, "--root", str(tmp_path)])

    assert result == 2
    assert calls == []


def test_confirmed_literary_push_uses_independent_slot_and_marks_drafted(
    tmp_path: Path, monkeypatch
) -> None:
    workflow = _response_workflow(tmp_path)
    article_path = tmp_path / "literary.json"
    article_path.write_text(json.dumps(_literary_payload(), ensure_ascii=False), encoding="utf-8")
    browser_cli.main(
        ["stage", workflow.workflow_id, "--article", str(article_path), "--root", str(tmp_path)]
    )
    browser_cli.main(["confirm-push", workflow.workflow_id, "--root", str(tmp_path)])
    slots: list[str] = []

    def fake_push(workflow, *, root):
        slots.append("literary")
        return "new-literary-media"

    monkeypatch.setattr(browser_cli, "push_staged_workflow", fake_push)

    result = browser_cli.main(["push", workflow.workflow_id, "--root", str(tmp_path)])

    saved = load_workflow(workflow.workflow_id, root=tmp_path)
    assert result == 0
    assert slots == ["literary"]
    assert saved.status == WorkflowStatus.DRAFTED
    assert saved.media_id == "new-literary-media"


def test_stage_rejects_article_kind_mismatch(tmp_path: Path) -> None:
    workflow = _response_workflow(tmp_path)
    article_path = tmp_path / "hotspot-shaped.json"
    payload = _literary_payload()
    payload["slot_key"] = "hotspot_afternoon"
    article_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = browser_cli.main(
        ["stage", workflow.workflow_id, "--article", str(article_path), "--root", str(tmp_path)]
    )

    assert result == 2
    assert load_workflow(workflow.workflow_id, root=tmp_path).status == WorkflowStatus.RESPONSE_RECEIVED


def test_hotspot_push_rechecks_deepseek_browser_provider(tmp_path: Path) -> None:
    article_path = tmp_path / "hotspot.json"
    article_path.write_text(
        json.dumps(
            {
                "title": "热点标题",
                "digest": "热点摘要",
                "body": "热点正文",
                "topic": "热点主题",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    workflow = BrowserWritingWorkflow(
        workflow_id="00000000-0000-0000-0000-000000000002",
        kind="hotspot",
        topic="热点主题",
        prompt="提示词",
        prompt_sha256="hash",
        conversation_id="bad-conversation",
        status=WorkflowStatus.PUSH_CONFIRMED,
        article_path=str(article_path),
    )

    with pytest.raises(WorkflowTransitionError, match="DeepSeek 固定会话"):
        browser_cli.push_staged_workflow(workflow, root=tmp_path)


def test_hotspot_push_forces_verified_only_image_policy(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts.tools import wechat_mp_codex_client
    from scripts.tools import wechat_mp_content
    from scripts.tools import wechat_mp_draft
    from scripts.tools import wechat_mp_draft_slots
    from scripts.tools import wechat_mp_hotspot_quality_gate as quality_mod
    from scripts.tools import wechat_mp_short_drama

    article_path = tmp_path / "hotspot.json"
    article_path.write_text(
        json.dumps(
            {
                "title": "热点标题",
                "digest": "热点摘要",
                "body": "热点正文",
                "topic": "热点主题",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    workflow = BrowserWritingWorkflow(
        workflow_id="00000000-0000-0000-0000-000000000003",
        kind="hotspot",
        topic="热点主题",
        prompt="提示词",
        prompt_sha256="hash",
        conversation_id=FIXED_CONVERSATION_ID,
        status=WorkflowStatus.PUSH_CONFIRMED,
        raw_response="DeepSeek 初稿",
        response_provider="deepseek_browser",
        edit_notes=("核对公开回应",),
        article_path=str(article_path),
    )
    policies: list[str] = []

    def build(*, codex_draft, upload_figures, image_policy):
        policies.append(image_policy)
        return {"title": codex_draft.title, "content": "<p>正文</p>"}

    monkeypatch.setattr(wechat_mp_content, "build_hotspot_article", build)
    monkeypatch.setattr(quality_mod, "require_hotspot_public_copy", lambda **_kwargs: None)
    monkeypatch.setattr(
        quality_mod,
        "require_hotspot_editorial_quality",
        lambda **_kwargs: quality_mod.HotspotEditorialScore(7, 7, True, ()),
    )
    monkeypatch.setattr(
        wechat_mp_draft,
        "_pick_cover_for_kind",
        lambda **_kwargs: ("cover", "thumb", None),
    )
    monkeypatch.setattr(wechat_mp_codex_client, "generation_scope", lambda kind: nullcontext())
    monkeypatch.setattr(wechat_mp_codex_client, "record_browser_deepseek_draft", lambda kind: None)
    monkeypatch.setattr(wechat_mp_short_drama, "assert_longform_promotion_safe", lambda *a, **k: None)
    monkeypatch.setattr(
        wechat_mp_draft_slots,
        "upsert_draft_article",
        lambda *a, **k: ("media-id", "created", None),
    )

    media_id = browser_cli.push_staged_workflow(workflow, root=tmp_path)

    assert media_id == "media-id"
    assert policies == ["verified_only"]


def test_hotspot_push_rechecks_public_copy_before_build(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts.tools import wechat_mp_content

    article_path = tmp_path / "hotspot-editorial-leak.json"
    article_path.write_text(
        json.dumps(
            {
                "title": "辽宁中考3科不再计分",
                "digest": "辽宁调整中考计分科目。",
                "body": "辽宁发布调整。\n\n这是地方政策，更不能写成全国统一取消三科计分。",
                "topic": "辽宁中考科目调整",
                "original_thesis": "减少计分科目能否减负，取决于课时、等级和录取配套。",
                "research_urls": [
                    "https://a.gov.cn/1",
                    "https://b.cn/2",
                    "https://c.cn/3",
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    workflow = BrowserWritingWorkflow(
        workflow_id="00000000-0000-0000-0000-000000000099",
        kind="hotspot",
        topic="辽宁中考科目调整",
        prompt="提示词",
        prompt_sha256="hash",
        conversation_id=FIXED_CONVERSATION_ID,
        status=WorkflowStatus.PUSH_CONFIRMED,
        raw_response="DeepSeek 初稿",
        response_provider="deepseek_user_paste",
        edit_notes=("核对政策原文",),
        article_path=str(article_path),
    )
    build_calls: list[dict] = []
    monkeypatch.setattr(
        wechat_mp_content,
        "build_hotspot_article",
        lambda **kwargs: build_calls.append(kwargs),
    )

    with pytest.raises(ValueError, match="热点公开文案未通过门禁"):
        browser_cli.push_staged_workflow(workflow, root=tmp_path)

    assert build_calls == []


def test_push_rejects_article_changed_after_stage_before_upload(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts.tools import wechat_mp_draft_slots

    article_path = tmp_path / "article.json"
    article_path.write_text("{}", encoding="utf-8")
    workflow = BrowserWritingWorkflow(
        workflow_id="00000000-0000-0000-0000-000000000199",
        kind="hotspot",
        topic="热点主题",
        prompt="提示词",
        prompt_sha256="hash",
        conversation_id=FIXED_CONVERSATION_ID,
        status=WorkflowStatus.PUSH_CONFIRMED,
        raw_response="完整正文" * 200,
        response_provider="thread_confirmed_body",
        response_confirmation_text="确认发布",
        response_confirmation_at="2026-09-23T17:00:00+08:00",
        edit_notes=("核对事实",),
        article_path=str(article_path),
        article_sha256="old-hash",
        handoff_required=True,
    )
    uploads: list[object] = []
    monkeypatch.setattr(
        wechat_mp_draft_slots,
        "upsert_draft_article",
        lambda *args, **kwargs: uploads.append((args, kwargs)),
    )

    with pytest.raises(WorkflowTransitionError, match="暂存后发生变化"):
        browser_cli.push_staged_workflow(workflow)

    assert uploads == []
