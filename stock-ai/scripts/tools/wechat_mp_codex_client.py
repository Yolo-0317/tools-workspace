"""Codex-only client and provenance trace for WeChat writing."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Literal, Sequence

from scripts.tools.cursor_agent_client import messages_to_prompt


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACE = ROOT / "agent-workspaces" / "wechat-writer"
DEFAULT_APP_COMMAND = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(?:cookie|wxticket|slave_sid|data_ticket|(?:access_)?token|"
    r"deepseek_api_key|wechat_mp_secret)\s*[:=]\s*[\"']?[^\s\"']{8,}"
)


@dataclass(frozen=True)
class CodexGenerationEvent:
    provider: str
    mode: Literal["codex_exec", "interactive_draft"]
    cli_version: str
    generated_at: str
    kind: str


_CURRENT_KIND: ContextVar[str] = ContextVar("wechat_mp_codex_kind", default="")
_EVENTS: ContextVar[tuple[CodexGenerationEvent, ...]] = ContextVar(
    "wechat_mp_codex_events",
    default=(),
)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name) or default)
    except ValueError:
        return default


def _command() -> str:
    configured = os.getenv("WECHAT_MP_CODEX_COMMAND", "").strip()
    candidate = configured or shutil.which("codex") or ""
    if not candidate and DEFAULT_APP_COMMAND.is_file():
        candidate = str(DEFAULT_APP_COMMAND)
    path = Path(candidate).expanduser() if candidate else None
    if path is None or not path.is_file() or not os.access(path, os.X_OK):
        raise RuntimeError("公众号写稿需要已安装并登录的 Codex CLI")
    return str(path.resolve())


def _workspace() -> Path:
    configured = os.getenv("WECHAT_MP_CODEX_WORKSPACE", "").strip()
    path = Path(configured).expanduser().resolve() if configured else DEFAULT_WORKSPACE
    if not path.is_dir():
        raise RuntimeError(f"公众号 Codex 工作目录不存在: {path}")
    return path


def wechat_mp_codex_model() -> str | None:
    return os.getenv("WECHAT_MP_CODEX_MODEL", "").strip() or None


def codex_available() -> bool:
    try:
        _command()
        _workspace()
        return True
    except RuntimeError:
        return False


def _assert_prompt_safe(prompt: str) -> None:
    if _SENSITIVE_ASSIGNMENT.search(prompt):
        raise ValueError("公众号 Codex 提示中包含敏感凭据，已拒绝执行")


def _codex_version(command: str | None = None) -> str:
    try:
        proc = subprocess.run(
            [command or _command(), "--version"],
            capture_output=True,
            text=True,
            shell=False,
            timeout=10,
            check=False,
        )
    except Exception:  # noqa: BLE001
        return "codex-cli unknown"
    text = (proc.stdout or proc.stderr or "").strip()
    return text[:120] or "codex-cli unknown"


def _record_event(*, mode: Literal["codex_exec", "interactive_draft"], command: str | None = None) -> None:
    event = CodexGenerationEvent(
        provider="codex",
        mode=mode,
        cli_version=_codex_version(command),
        generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        kind=_CURRENT_KIND.get(),
    )
    _EVENTS.set((*_EVENTS.get(), event))


@contextmanager
def generation_scope(kind: str) -> Iterator[None]:
    kind_token = _CURRENT_KIND.set(kind.strip())
    _EVENTS.set(())
    try:
        yield
    finally:
        _EVENTS.set(())
        _CURRENT_KIND.reset(kind_token)


def generation_events() -> tuple[CodexGenerationEvent, ...]:
    return _EVENTS.get()


def record_interactive_codex_draft(kind: str) -> None:
    expected = _CURRENT_KIND.get()
    if expected and expected != kind:
        raise ValueError(f"Codex 草稿 kind 不一致: {kind} != {expected}")
    _record_event(mode="interactive_draft")


def assert_codex_only_generation(*, allow_empty: bool = True) -> None:
    events: Sequence[CodexGenerationEvent] = generation_events()
    if not events and not allow_empty:
        raise RuntimeError("公众号 AI 稿缺少 Codex 生成来源")
    if any(event.provider != "codex" for event in events):
        raise RuntimeError("公众号 AI 写稿只允许 Codex")


def call_wechat_mp_codex(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    max_retries: int | None = None,
    timeout_seconds: float | None = None,
    output_schema: Path | None = None,
) -> str:
    prompt = messages_to_prompt(messages)
    _assert_prompt_safe(prompt)
    command = _command()
    workspace = _workspace()
    retries = max_retries if max_retries is not None else _env_int(
        "WECHAT_MP_CODEX_MAX_RETRIES",
        1,
    )
    retries = max(1, retries)
    timeout_value = timeout_seconds if timeout_seconds is not None else _env_float(
        "WECHAT_MP_CODEX_TIMEOUT_SECONDS",
        420,
    )
    selected_model = model or wechat_mp_codex_model()
    last_error = "Codex 未返回结果"

    for attempt in range(1, retries + 1):
        with tempfile.TemporaryDirectory(prefix="wechat-codex-") as temp_dir:
            output_path = Path(temp_dir) / "last-message.txt"
            argv = [
                command,
                "exec",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "-C",
                str(workspace),
            ]
            if selected_model:
                argv.extend(["--model", selected_model])
            if output_schema is not None:
                argv.extend(["--output-schema", str(output_schema.resolve())])
            argv.extend(["--output-last-message", str(output_path), "-"])
            try:
                proc = subprocess.run(
                    argv,
                    input=prompt,
                    text=True,
                    shell=False,
                    capture_output=True,
                    timeout=timeout_value,
                    check=False,
                    cwd=str(workspace),
                )
                if proc.returncode != 0:
                    detail = (proc.stderr or proc.stdout or "退出非零").strip()[:500]
                    raise RuntimeError(detail)
                content = (
                    output_path.read_text(encoding="utf-8").strip()
                    if output_path.is_file()
                    else ""
                )
                if not content:
                    raise RuntimeError("返回空正文")
                _record_event(mode="codex_exec", command=command)
                return content
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if attempt < retries:
                    time.sleep(min(3.0, float(attempt)))

    raise RuntimeError(f"Codex 公众号写稿失败（已重试 {retries} 次）: {last_error}")
