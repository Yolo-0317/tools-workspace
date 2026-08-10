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
    ):
        monkeypatch.delenv(key, raising=False)


def test_wechat_mp_backend_always_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.tools.deepseek_client import wechat_mp_llm_backend

    monkeypatch.setenv("LLM_BACKEND", "deepseek")
    assert wechat_mp_llm_backend() == "cursor"


def test_wechat_mp_model_defaults_composer(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.tools.deepseek_client import wechat_mp_llm_model

    monkeypatch.setenv("CURSOR_AGENT_MODEL", "composer-2.5")
    assert wechat_mp_llm_model() == "composer-2.5"
    monkeypatch.setenv("WECHAT_MP_LLM_MODEL", "composer-2.5-fast")
    assert wechat_mp_llm_model() == "composer-2.5-fast"


def test_call_wechat_mp_llm_uses_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.tools import deepseek_client

    monkeypatch.setattr(
        deepseek_client,
        "call_deepseek",
        lambda messages, **kwargs: kwargs,
    )
    out = deepseek_client.call_wechat_mp_llm([{"role": "user", "content": "hi"}])
    assert out["backend"] == "cursor"
    assert out["max_retries"] == 1
    assert out["model"] == "composer-2.5"


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
