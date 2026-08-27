from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path

from scripts.tools import wechat_mp_browser_write as browser_cli
from scripts.tools.wechat_mp_browser_workflow import (
    BrowserWritingWorkflow,
    WorkflowStatus,
    confirm_prompt,
    create_workflow,
    load_workflow,
    record_response,
)


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
