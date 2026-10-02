from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.tools import wechat_mp_browser_write as browser_cli
from scripts.tools.wechat_mp_browser_workflow import (
    WorkflowStatus,
    confirm_prompt,
    create_workflow,
    load_workflow,
    record_response,
)
from scripts.tools.wechat_mp_deepseek_browser import (
    DeepSeekLoginRequired,
    DeepSeekResponse,
    LOGIN_INSTRUCTION,
)


class RecordingClient:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def send_and_receive(self, prompt: str, timeout_seconds: float):
        self.calls.append(prompt)
        return DeepSeekResponse(text="测试标题\n\n测试正文", assistant_index=4)


class LoginRequiredClient:
    def send_and_receive(self, prompt: str, timeout_seconds: float):
        raise DeepSeekLoginRequired(LOGIN_INSTRUCTION)


def _complete_hotspot_body() -> str:
    return "\n\n".join(
        (
            "平台月付还能用吗？9月30日后付款页面会怎么变",
            "第一段把新规实施时间、支付页面变化和普通人的疑问交代清楚。" * 8,
            "第二段解释余额、银行卡和月付背后的资金性质并不相同。" * 8,
            "第三段引用公开规定，也说明平台页面最终怎样调整还要看实际设计。" * 8,
            "第四段回到付款前的选择，让读者看清借款主体、费用和还款时间。" * 8,
        )
    )


def test_prepare_new_hotspot_requires_editorial_handoff(tmp_path: Path, capsys) -> None:
    result = browser_cli.main(
        [
            "prepare", "--kind", "hotspot", "--topic", "月租房",
            "--thesis", "酒店月租房是否划算，取决于具体房源的租期、通勤和全部费用，不能只看页面起价。",
            "--fact", "报道时上海松江一处房源页面显示月租1500元起。",
            "--research-url", "https://a.example/report",
            "--research-url", "https://b.example/report",
            "--research-url", "https://c.example/report",
            "--root", str(tmp_path),
        ]
    )
    output = capsys.readouterr().out
    workflow_id = output.split("workflow_id: ", 1)[1].splitlines()[0]

    assert result == 0
    assert load_workflow(workflow_id, root=tmp_path).handoff_required is True


def test_stage_new_hotspot_rejects_missing_handoff_before_image_work(
    tmp_path: Path, monkeypatch
) -> None:
    workflow = create_workflow(
        kind="hotspot", topic="月租房", prompt="提示词", handoff_required=True,
        root=tmp_path,
    )
    browser_cli.record_confirmed_body(
        workflow.workflow_id, _complete_hotspot_body(),
        confirmation_text="按此稿推草稿", root=tmp_path,
    )
    article = tmp_path / "article.json"
    article.write_text("{}", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(
        browser_cli, "_validate_staged_article",
        lambda *_a, **_k: calls.append("validated"),
    )

    result = browser_cli.main(
        ["stage", workflow.workflow_id, "--article", str(article),
         "--edit-note", "核对来源", "--root", str(tmp_path)]
    )

    assert result == 2
    assert calls == []


def test_write_refuses_unconfirmed_prompt(tmp_path: Path, monkeypatch) -> None:
    workflow = create_workflow(kind="hotspot", topic="题目", prompt="提示词", root=tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(browser_cli, "make_browser_client", lambda: RecordingClient(calls))

    result = browser_cli.main(["write", workflow.workflow_id, "--root", str(tmp_path)])

    assert result == 2
    assert calls == []
    assert load_workflow(workflow.workflow_id, root=tmp_path).status == WorkflowStatus.RESEARCHED


def test_login_failure_marks_workflow_blocked_and_can_resume(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    workflow = create_workflow(kind="hotspot", topic="题目", prompt="提示词", root=tmp_path)
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    monkeypatch.setattr(browser_cli, "make_browser_client", lambda: LoginRequiredClient())

    result = browser_cli.main(["write", workflow.workflow_id, "--root", str(tmp_path)])

    assert result == 3
    assert LOGIN_INSTRUCTION in capsys.readouterr().err
    blocked = load_workflow(workflow.workflow_id, root=tmp_path)
    assert blocked.status == WorkflowStatus.BLOCKED
    assert blocked.error_code == "login_required"

    assert browser_cli.main(["resume-login", workflow.workflow_id, "--root", str(tmp_path)]) == 0
    assert load_workflow(workflow.workflow_id, root=tmp_path).status == WorkflowStatus.PROMPT_CONFIRMED


def test_write_records_only_browser_response(tmp_path: Path, monkeypatch) -> None:
    workflow = create_workflow(kind="literary", topic="史记", prompt="提示词", root=tmp_path)
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(browser_cli, "make_browser_client", lambda: RecordingClient(calls))

    result = browser_cli.main(["write", workflow.workflow_id, "--root", str(tmp_path)])

    saved = load_workflow(workflow.workflow_id, root=tmp_path)
    assert result == 0
    assert calls == ["提示词"]
    assert saved.status == WorkflowStatus.RESPONSE_RECEIVED
    assert saved.raw_response == "测试标题\n\n测试正文"


def test_record_pasted_response_cli_preserves_user_supplied_deepseek_draft(
    tmp_path: Path,
) -> None:
    workflow = create_workflow(kind="hotspot", topic="题目", prompt="提示词", root=tmp_path)
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    response_file = tmp_path / "deepseek-response.txt"
    response_file.write_text("初稿标题\n\n初稿正文", encoding="utf-8")

    result = browser_cli.main(
        [
            "record-pasted",
            workflow.workflow_id,
            "--response-file",
            str(response_file),
            "--root",
            str(tmp_path),
        ]
    )

    saved = load_workflow(workflow.workflow_id, root=tmp_path)
    assert result == 0
    assert saved.status == WorkflowStatus.RESPONSE_RECEIVED
    assert saved.response_provider == "deepseek_user_paste"
    assert saved.raw_response == "初稿标题\n\n初稿正文"


def test_record_confirmed_body_cli_preserves_thread_confirmation(
    tmp_path: Path,
) -> None:
    workflow = create_workflow(kind="hotspot", topic="题目", prompt="提示词", root=tmp_path)
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    response_file = tmp_path / "confirmed-body.txt"
    response_file.write_text(_complete_hotspot_body(), encoding="utf-8")

    result = browser_cli.main(
        [
            "record-confirmed-body",
            workflow.workflow_id,
            "--response-file",
            str(response_file),
            "--confirmation-text",
            "就按照刚刚的正文发布",
            "--root",
            str(tmp_path),
        ]
    )

    saved = load_workflow(workflow.workflow_id, root=tmp_path)
    assert result == 0
    assert saved.status == WorkflowStatus.RESPONSE_RECEIVED
    assert saved.response_provider == "thread_confirmed_body"
    assert saved.response_confirmation_text == "就按照刚刚的正文发布"


def test_hotspot_stage_cli_records_repeated_agent_edit_notes(
    tmp_path: Path, monkeypatch
) -> None:
    workflow = create_workflow(kind="hotspot", topic="题目", prompt="提示词", root=tmp_path)
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    record_response(workflow.workflow_id, "标题\n\n正文", root=tmp_path)
    article = tmp_path / "hotspot.json"
    article.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        browser_cli,
        "_validate_staged_article",
        lambda *_args, **_kwargs: "第二次确认摘要",
    )

    result = browser_cli.main(
        [
            "stage",
            workflow.workflow_id,
            "--article",
            str(article),
            "--edit-note",
            "核对关键事实",
            "--edit-note",
            "删除无来源判断",
            "--root",
            str(tmp_path),
        ]
    )

    saved = load_workflow(workflow.workflow_id, root=tmp_path)
    assert result == 0
    assert saved.edit_notes == ("核对关键事实", "删除无来源判断")


def test_hotspot_second_confirmation_summary_discloses_sources_and_no_generation(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts.tools import wechat_mp_codex_hotspot as hotspot_mod
    from scripts.tools import wechat_mp_codex_images as images_mod
    from scripts.tools import wechat_mp_hotspot_quality_gate as quality_mod
    from scripts.tools.wechat_mp_hotspot_image_policy import VerifiedHotspotImages

    article = tmp_path / "hotspot.json"
    article.write_text(
        json.dumps(
            {
                "title": "热点标题",
                "digest": "热点摘要",
                "body": "第一段。\n\n第二段。",
                "topic": "热点主题",
                "research_urls": ["https://example.com/report"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    workflow = create_workflow(kind="hotspot", topic="热点主题", prompt="提示词", root=tmp_path)
    monkeypatch.setattr(hotspot_mod, "validate_codex_hotspot_originality", lambda *_a, **_k: None)
    monkeypatch.setattr(quality_mod, "require_hotspot_public_copy", lambda **_kwargs: None)
    monkeypatch.setattr(
        quality_mod,
        "require_hotspot_editorial_quality",
        lambda **_kwargs: quality_mod.HotspotEditorialScore(7, 7, True, ()),
    )
    monkeypatch.setattr(
        images_mod,
        "prepare_hotspot_topic_images",
        lambda *_a, **_k: VerifiedHotspotImages(
            cover_source=tmp_path / "cover-source.jpg",
            body_figures=(),
            source_meta={},
        ),
    )

    summary = browser_cli._validate_staged_article(
        workflow,
        article,
        edit_notes=("核对公开回应",),
    )

    assert "成稿来源: DeepSeek 固定浏览器会话" in summary
    assert "Agent 核实编辑: 核对公开回应" in summary
    assert "编辑质量: 7/7" in summary
    assert "配图: 封面 1 张，正文 0 张" in summary
    assert "本稿未自动生成图片" in summary


def test_hotspot_second_confirmation_summary_names_user_pasted_source(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts.tools import wechat_mp_codex_hotspot as hotspot_mod
    from scripts.tools import wechat_mp_codex_images as images_mod
    from scripts.tools import wechat_mp_hotspot_quality_gate as quality_mod
    from scripts.tools.wechat_mp_hotspot_image_policy import VerifiedHotspotImages

    article = tmp_path / "hotspot.json"
    article.write_text(
        json.dumps(
            {
                "title": "热点标题",
                "digest": "热点摘要",
                "body": "第一段。\n\n第二段。",
                "topic": "热点主题",
                "research_urls": ["https://example.com/report"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    workflow = create_workflow(kind="hotspot", topic="热点主题", prompt="提示词", root=tmp_path)
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    workflow = browser_cli.record_pasted_response(
        workflow.workflow_id,
        "DeepSeek 初稿",
        root=tmp_path,
    )
    monkeypatch.setattr(hotspot_mod, "validate_codex_hotspot_originality", lambda *_a, **_k: None)
    monkeypatch.setattr(quality_mod, "require_hotspot_public_copy", lambda **_kwargs: None)
    monkeypatch.setattr(
        quality_mod,
        "require_hotspot_editorial_quality",
        lambda **_kwargs: quality_mod.HotspotEditorialScore(7, 7, True, ()),
    )
    monkeypatch.setattr(
        images_mod,
        "prepare_hotspot_topic_images",
        lambda *_a, **_k: VerifiedHotspotImages(
            cover_source=tmp_path / "cover-source.jpg",
            body_figures=(),
            source_meta={},
        ),
    )

    summary = browser_cli._validate_staged_article(
        workflow,
        article,
        edit_notes=("核对公开回应",),
    )

    assert "成稿来源: 用户粘贴的 DeepSeek 初稿" in summary


def test_hotspot_second_confirmation_summary_names_thread_confirmed_source(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts.tools import wechat_mp_codex_hotspot as hotspot_mod
    from scripts.tools import wechat_mp_codex_images as images_mod
    from scripts.tools import wechat_mp_hotspot_quality_gate as quality_mod
    from scripts.tools.wechat_mp_hotspot_image_policy import VerifiedHotspotImages

    article = tmp_path / "hotspot.json"
    article.write_text(
        json.dumps(
            {
                "title": "热点标题",
                "digest": "热点摘要",
                "body": "第一段。\n\n第二段。",
                "topic": "热点主题",
                "research_urls": ["https://example.com/report"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    workflow = create_workflow(kind="hotspot", topic="热点主题", prompt="提示词", root=tmp_path)
    confirm_prompt(workflow.workflow_id, root=tmp_path)
    workflow = browser_cli.record_confirmed_body(
        workflow.workflow_id,
        _complete_hotspot_body(),
        confirmation_text="就按照刚刚的正文发布",
        root=tmp_path,
    )
    monkeypatch.setattr(hotspot_mod, "validate_codex_hotspot_originality", lambda *_a, **_k: None)
    monkeypatch.setattr(quality_mod, "require_hotspot_public_copy", lambda **_kwargs: None)
    monkeypatch.setattr(
        quality_mod,
        "require_hotspot_editorial_quality",
        lambda **_kwargs: quality_mod.HotspotEditorialScore(7, 7, True, ()),
    )
    monkeypatch.setattr(
        images_mod,
        "prepare_hotspot_topic_images",
        lambda *_a, **_k: VerifiedHotspotImages(
            cover_source=tmp_path / "cover-source.jpg",
            body_figures=(),
            source_meta={},
        ),
    )

    summary = browser_cli._validate_staged_article(
        workflow,
        article,
        edit_notes=("核对公开回应",),
    )

    assert "成稿来源: 当前任务已确认正文" in summary


def test_hotspot_stage_rejects_editorial_leak_before_images(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts.tools import wechat_mp_codex_hotspot as hotspot_mod
    from scripts.tools import wechat_mp_codex_images as images_mod

    article = tmp_path / "hotspot-editorial-leak.json"
    article.write_text(
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
    workflow = create_workflow(
        kind="hotspot",
        topic="辽宁中考科目调整",
        prompt="提示词",
        root=tmp_path,
    )
    monkeypatch.setattr(
        hotspot_mod,
        "validate_codex_hotspot_originality",
        lambda *_args, **_kwargs: None,
    )
    image_calls: list[int] = []
    monkeypatch.setattr(
        images_mod,
        "prepare_hotspot_topic_images",
        lambda *_args, **_kwargs: image_calls.append(1),
    )

    with pytest.raises(ValueError, match="editorial_instruction_leak"):
        browser_cli._validate_staged_article(
            workflow,
            article,
            edit_notes=("已核实",),
        )

    assert image_calls == []
