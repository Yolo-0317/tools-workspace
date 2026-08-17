"""公众号 Codex CLI 客户端。"""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.tools import wechat_mp_codex_client as client


def _write_fake_codex(tmp_path: Path, *, exit_code: int = 0, output: str = "成稿") -> Path:
    command = tmp_path / "fake-codex"
    command.write_text(
        """#!/usr/bin/env python3
import json
import os
import pathlib
import sys

if sys.argv[1:] == ["--version"]:
    print("codex-cli test")
    raise SystemExit(0)

record_path = pathlib.Path(os.environ["FAKE_CODEX_RECORD"])
record_path.write_text(json.dumps({
    "argv": sys.argv[1:],
    "stdin": sys.stdin.read(),
}, ensure_ascii=False), encoding="utf-8")

exit_code = int(os.environ.get("FAKE_CODEX_EXIT", "0"))
if exit_code:
    print("not logged in", file=sys.stderr)
    raise SystemExit(exit_code)

output_index = sys.argv.index("--output-last-message") + 1
pathlib.Path(sys.argv[output_index]).write_text(
    os.environ.get("FAKE_CODEX_OUTPUT", "成稿"),
    encoding="utf-8",
)
""",
        encoding="utf-8",
    )
    command.chmod(command.stat().st_mode | stat.S_IXUSR)
    return command


@pytest.fixture(autouse=True)
def _clear_codex_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in (
        "WECHAT_MP_CODEX_COMMAND",
        "WECHAT_MP_CODEX_MODEL",
        "WECHAT_MP_CODEX_TIMEOUT_SECONDS",
        "WECHAT_MP_CODEX_MAX_RETRIES",
        "WECHAT_MP_CODEX_WORKSPACE",
        "FAKE_CODEX_RECORD",
        "FAKE_CODEX_EXIT",
        "FAKE_CODEX_OUTPUT",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("WECHAT_MP_CODEX_WORKSPACE", str(tmp_path))


def test_call_wechat_mp_codex_runs_read_only_ephemeral_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _write_fake_codex(tmp_path)
    record = tmp_path / "record.json"
    monkeypatch.setenv("WECHAT_MP_CODEX_COMMAND", str(command))
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    monkeypatch.setenv("FAKE_CODEX_OUTPUT", "最终正文")

    result = client.call_wechat_mp_codex(
        [{"role": "system", "content": "只输出正文"}, {"role": "user", "content": "写稿"}]
    )

    invocation = json.loads(record.read_text(encoding="utf-8"))
    assert result == "最终正文"
    assert invocation["argv"][:2] == ["exec", "--ephemeral"]
    assert invocation["argv"][invocation["argv"].index("--sandbox") + 1] == "read-only"
    assert invocation["argv"][-1] == "-"
    assert "只输出正文" in invocation["stdin"]
    assert "写稿" in invocation["stdin"]


def test_codex_failure_raises_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _write_fake_codex(tmp_path, exit_code=1)
    monkeypatch.setenv("WECHAT_MP_CODEX_COMMAND", str(command))
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(tmp_path / "record.json"))
    monkeypatch.setenv("FAKE_CODEX_EXIT", "1")

    with pytest.raises(RuntimeError, match="Codex.*not logged in"):
        client.call_wechat_mp_codex(
            [{"role": "user", "content": "写稿"}],
            max_retries=1,
        )


def test_sensitive_prompt_is_rejected_before_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _write_fake_codex(tmp_path)
    record = tmp_path / "record.json"
    monkeypatch.setenv("WECHAT_MP_CODEX_COMMAND", str(command))
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))

    with pytest.raises(ValueError, match="敏感"):
        client.call_wechat_mp_codex(
            [{"role": "user", "content": "wxTicket=secret-value"}]
        )

    assert not record.exists()


def test_generation_scope_records_codex_and_resets_between_articles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _write_fake_codex(tmp_path)
    monkeypatch.setenv("WECHAT_MP_CODEX_COMMAND", str(command))
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(tmp_path / "record.json"))

    with client.generation_scope("tv_review"):
        client.call_wechat_mp_codex([{"role": "user", "content": "写影视稿"}])
        events = client.generation_events()
        assert [(event.provider, event.mode, event.kind) for event in events] == [
            ("codex", "codex_exec", "tv_review")
        ]
        client.assert_codex_only_generation(allow_empty=False)

    assert client.generation_events() == ()


def test_interactive_codex_draft_records_provenance() -> None:
    with client.generation_scope("silver"):
        client.record_interactive_codex_draft("silver")
        events = client.generation_events()
        assert [(event.provider, event.mode, event.kind) for event in events] == [
            ("codex", "interactive_draft", "silver")
        ]
