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
    for key in ("LLM_BACKEND", "SOP_LLM_BACKEND", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(key, raising=False)


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
