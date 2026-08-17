"""LLM 后端分流：写稿 LLM_BACKEND vs SOP_LLM_BACKEND。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "LLM_BACKEND",
        "SOP_LLM_BACKEND",
        "DEEPSEEK_API_KEY",
        "WECHAT_MP_LLM_MODEL",
        "WECHAT_MP_CURSOR_MAX_RETRIES",
        "WECHAT_MP_CODEX_MODEL",
        "WECHAT_MP_CODEX_MAX_RETRIES",
    ):
        monkeypatch.delenv(key, raising=False)


def test_wechat_mp_backend_always_codex(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.tools.deepseek_client import wechat_mp_llm_backend

    monkeypatch.setenv("LLM_BACKEND", "deepseek")
    assert wechat_mp_llm_backend() == "codex"


def test_wechat_mp_model_uses_only_codex_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.tools.deepseek_client import wechat_mp_llm_model

    monkeypatch.setenv("CURSOR_AGENT_MODEL", "composer-2.5")
    monkeypatch.setenv("WECHAT_MP_LLM_MODEL", "composer-2.5-fast")
    assert wechat_mp_llm_model() is None
    monkeypatch.setenv("WECHAT_MP_CODEX_MODEL", "gpt-5.6")
    assert wechat_mp_llm_model() == "gpt-5.6"


def test_call_wechat_mp_llm_uses_codex_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.tools import deepseek_client

    captured: dict[str, object] = {}

    def fake_codex(messages: list[dict[str, str]], **kwargs: object) -> str:
        captured["messages"] = messages
        captured.update(kwargs)
        return "正文"

    monkeypatch.setattr(
        deepseek_client,
        "call_wechat_mp_codex",
        fake_codex,
    )
    out = deepseek_client.call_wechat_mp_llm([{"role": "user", "content": "hi"}])
    assert out == "正文"
    assert captured["max_retries"] is None
    assert captured["model"] is None
    assert captured["messages"] == [{"role": "user", "content": "hi"}]


def test_call_wechat_mp_llm_rejects_non_codex_backend() -> None:
    from scripts.tools.deepseek_client import call_wechat_mp_llm

    with pytest.raises(ValueError, match="只允许 codex"):
        call_wechat_mp_llm(
            [{"role": "user", "content": "hi"}],
            backend="deepseek",
        )


def test_sop_backend_defaults_deepseek(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.tools.deepseek_client import sop_llm_backend

    monkeypatch.setenv("LLM_BACKEND", "cursor")
    assert sop_llm_backend() == "deepseek"


def test_sop_backend_override(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.tools.deepseek_client import sop_llm_backend

    monkeypatch.setenv("SOP_LLM_BACKEND", "deepseek")
    monkeypatch.setenv("LLM_BACKEND", "cursor")
    assert sop_llm_backend() == "deepseek"


def test_is_sop_llm_requires_api_key_when_deepseek(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.tools.deepseek_client import is_sop_llm_configured

    monkeypatch.setenv("SOP_LLM_BACKEND", "deepseek")
    assert is_sop_llm_configured() is False
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    assert is_sop_llm_configured() is True
