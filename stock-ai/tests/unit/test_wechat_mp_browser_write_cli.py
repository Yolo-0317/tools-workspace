from __future__ import annotations

from pathlib import Path

from scripts.tools import wechat_mp_browser_write as browser_cli
from scripts.tools.wechat_mp_browser_workflow import (
    WorkflowStatus,
    confirm_prompt,
    create_workflow,
    load_workflow,
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
