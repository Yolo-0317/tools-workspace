from __future__ import annotations

import json

import pytest

from scripts.tools.wechat_mp_deepseek_browser import (
    FIXED_CONVERSATION_ID,
    CommandResult,
    DeepSeekBrowserClient,
    DeepSeekLoginRequired,
    DeepSeekSendFailed,
    DeepSeekWrongConversation,
    parse_opencli_refs,
)


class FakeRunner:
    def __init__(self, results: list[CommandResult]) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, ...]] = []

    def run(self, args):
        self.calls.append(tuple(args))
        if not self.results:
            raise AssertionError(f"unexpected command: {args}")
        return self.results.pop(0)


def _ok(payload: object) -> CommandResult:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return CommandResult(returncode=0, stdout=text, stderr="")


def _client_for_page(**overrides) -> DeepSeekBrowserClient:
    page = {
        "url": f"https://chat.deepseek.com/a/chat/s/{FIXED_CONVERSATION_ID}",
        "title": "公众号爆文秘诀 - DeepSeek",
        "has_textarea": True,
        "has_login_form": False,
        "is_generating": False,
        "assistant_count": 3,
    }
    page.update(overrides)
    return DeepSeekBrowserClient(FakeRunner([_ok({"session": "test"}), _ok(page)]))


def test_validate_current_tab_accepts_fixed_logged_in_conversation() -> None:
    state = _client_for_page().validate_current_tab()
    assert state.conversation_id == FIXED_CONVERSATION_ID
    assert state.assistant_count == 3


def test_validate_current_tab_reports_login_instruction_when_logged_out() -> None:
    client = _client_for_page(
        url="https://chat.deepseek.com/sign_in",
        has_textarea=False,
        has_login_form=True,
    )
    with pytest.raises(DeepSeekLoginRequired, match="请在 Chrome 登录 DeepSeek"):
        client.validate_current_tab()


def test_validate_current_tab_rejects_other_conversation() -> None:
    client = _client_for_page(url="https://chat.deepseek.com/a/chat/s/other")
    with pytest.raises(DeepSeekWrongConversation):
        client.validate_current_tab()


def test_validate_current_tab_reports_wrong_tab_before_login_required() -> None:
    client = _client_for_page(
        url="https://example.com/",
        has_textarea=False,
        has_login_form=False,
    )
    with pytest.raises(DeepSeekWrongConversation):
        client.validate_current_tab()


def test_parse_opencli_refs_finds_textarea_and_send_button() -> None:
    state = """
      [450]<textarea placeholder=给 DeepSeek 发送消息 autocomplete=off />
      [466]<div role=button tabindex=0 />
      [467]<input type=file accept=.txt,.md />
      <div />
        [468]<div role=button />
    """
    assert parse_opencli_refs(state) == ("450", "468")


def test_send_and_receive_returns_only_new_assistant_message() -> None:
    before = {
        "messages": [
            {"role": "user", "text": "旧问题"},
            {"role": "assistant", "text": "旧长文"},
        ],
        "is_generating": False,
    }
    after = {
        "messages": [
            {"role": "user", "text": "旧问题"},
            {"role": "assistant", "text": "旧长文"},
            {"role": "user", "text": "新提示词"},
            {"role": "assistant", "text": "新标题\n\n新正文"},
        ],
        "is_generating": False,
    }
    runner = FakeRunner(
        [
            _ok({"session": "test"}),
            _ok(
                {
                    "url": f"https://chat.deepseek.com/a/chat/s/{FIXED_CONVERSATION_ID}",
                    "title": "公众号爆文秘诀 - DeepSeek",
                    "has_textarea": True,
                    "has_login_form": False,
                    "is_generating": False,
                    "assistant_count": 1,
                }
            ),
            _ok(before),
            _ok("[450]<textarea placeholder=给 DeepSeek 发送消息 />\n[468]<div role=button />"),
            _ok({"typed": True}),
            _ok({"clicked": True}),
            _ok(after),
            _ok({"unbound": True}),
        ]
    )

    result = DeepSeekBrowserClient(runner).send_and_receive("新提示词", timeout_seconds=1)

    assert result.text == "新标题\n\n新正文"
    assert result.assistant_index == 1
    assert runner.calls[-1][-1] == "unbind"


def test_send_and_receive_rejects_unpersisted_prompt() -> None:
    before = {
        "messages": [{"role": "assistant", "text": "旧长文"}],
        "is_generating": False,
    }
    runner = FakeRunner(
        [
            _ok({"session": "test"}),
            _ok(
                {
                    "url": f"https://chat.deepseek.com/a/chat/s/{FIXED_CONVERSATION_ID}",
                    "title": "公众号爆文秘诀 - DeepSeek",
                    "has_textarea": True,
                    "has_login_form": False,
                    "is_generating": False,
                    "assistant_count": 1,
                }
            ),
            _ok(before),
            _ok("[450]<textarea placeholder=给 DeepSeek 发送消息 />\n[468]<div role=button />"),
            _ok({"typed": True}),
            _ok({"clicked": True}),
            _ok(before),
            _ok({"unbound": True}),
        ]
    )

    with pytest.raises(DeepSeekSendFailed, match="未持久化"):
        DeepSeekBrowserClient(runner).send_and_receive("新提示词", timeout_seconds=0)


def test_send_and_receive_waits_through_quiet_transition_before_reply() -> None:
    before = {
        "messages": [{"role": "assistant", "text": "旧长文"}],
        "is_generating": False,
    }
    transition = {
        "messages": [{"role": "assistant", "text": "旧长文"}],
        "body_text": "新提示词",
        "is_generating": False,
    }
    after = {
        "messages": [
            {"role": "assistant", "text": "旧长文"},
            {"role": "assistant", "text": "新回复"},
        ],
        "body_text": "新提示词\n新回复",
        "is_generating": False,
    }
    runner = FakeRunner(
        [
            _ok({"session": "test"}),
            _ok(
                {
                    "url": f"https://chat.deepseek.com/a/chat/s/{FIXED_CONVERSATION_ID}",
                    "title": "公众号爆文秘诀 - DeepSeek",
                    "has_textarea": True,
                    "has_login_form": False,
                    "is_generating": False,
                    "assistant_count": 1,
                }
            ),
            _ok(before),
            _ok("[450]<textarea placeholder=给 DeepSeek 发送消息 />\n[468]<div role=button />"),
            _ok({"typed": True}),
            _ok({"clicked": True}),
            _ok(transition),
            _ok(after),
            _ok({"unbound": True}),
        ]
    )

    result = DeepSeekBrowserClient(runner, poll_seconds=0).send_and_receive(
        "新提示词", timeout_seconds=1
    )

    assert result.text == "新回复"
