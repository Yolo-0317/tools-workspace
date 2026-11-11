"""OpenCLI adapter for one fixed, logged-in DeepSeek Chrome conversation."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Protocol, Sequence

FIXED_CONVERSATION_ID = "f0cc031d-233f-4648-807d-354275738e61"
FIXED_CONVERSATION_URL = (
    "https://chat.deepseek.com/a/chat/s/" + FIXED_CONVERSATION_ID
)
LOGIN_INSTRUCTION = (
    "DeepSeek 当前未登录。请在 Chrome 登录 DeepSeek，打开固定的“公众号爆文秘诀”会话"
    "并保持为当前标签，然后回复“已登录”。"
)
DEFAULT_SESSION = "deepseek_writer"


class DeepSeekBrowserError(RuntimeError):
    pass


class DeepSeekLoginRequired(DeepSeekBrowserError):
    pass


class DeepSeekWrongConversation(DeepSeekBrowserError):
    pass


class DeepSeekBusy(DeepSeekBrowserError):
    pass


class DeepSeekResponseTimeout(DeepSeekBrowserError):
    pass


class DeepSeekSendFailed(DeepSeekBrowserError):
    pass


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class OpenCliRunner(Protocol):
    def run(self, args: Sequence[str]) -> CommandResult: ...


class SubprocessOpenCliRunner:
    def __init__(self, binary: str | None = None) -> None:
        self.binary = binary or os.getenv("OPENCLI_BIN", "opencli")

    def run(self, args: Sequence[str]) -> CommandResult:
        proc = subprocess.run(
            [self.binary, *args],
            check=False,
            capture_output=True,
            text=True,
        )
        return CommandResult(proc.returncode, proc.stdout, proc.stderr)


@dataclass(frozen=True)
class DeepSeekPageState:
    conversation_id: str
    url: str
    title: str
    assistant_count: int


@dataclass(frozen=True)
class DeepSeekResponse:
    text: str
    assistant_index: int


_VALIDATE_JS = r'''(()=>{
  const url=location.href;
  const textareas=Array.from(document.querySelectorAll('textarea'));
  const hasTextarea=textareas.some(e=>/DeepSeek|发送消息/.test(e.placeholder||''));
  const bodyText=(document.body.innerText||'').slice(0,2000);
  const hasLoginForm=!!document.querySelector('input[type=password]') ||
    /登录|注册/.test(bodyText) && !hasTextarea;
  const stopButtons=Array.from(document.querySelectorAll('[role=button],button'))
    .filter(e=>/停止|Stop generating/i.test((e.innerText||'')+' '+(e.getAttribute('aria-label')||'')));
  const assistantCount=document.querySelectorAll('.ds-markdown').length;
  return JSON.stringify({url,title:document.title,has_textarea:hasTextarea,
    has_login_form:hasLoginForm,is_generating:stopButtons.length>0,
    assistant_count:assistantCount});
})()'''

_SNAPSHOT_JS = r'''(()=>{
  const clean=s=>(s||'').replace(/\s+$/,'').trim();
  const assistants=Array.from(document.querySelectorAll('.ds-markdown'))
    .map(e=>({role:'assistant',text:clean(e.innerText)})).filter(x=>x.text);
  const area=document.querySelector('textarea');
  const bodyText=document.body.innerText||'';
  const stopButtons=Array.from(document.querySelectorAll('[role=button],button'))
    .filter(e=>/停止|Stop generating/i.test((e.innerText||'')+' '+(e.getAttribute('aria-label')||'')));
  return JSON.stringify({messages:assistants,is_generating:stopButtons.length>0,
    body_text:bodyText.slice(-12000),input_value:area?area.value:''});
})()'''


def _decode_json(stdout: str) -> dict:
    text = (stdout or "").strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DeepSeekBrowserError(f"OpenCLI 返回非 JSON: {text[:160]}") from exc
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise DeepSeekBrowserError("OpenCLI eval 返回字符串但内容不是 JSON") from exc
    if not isinstance(value, dict):
        raise DeepSeekBrowserError("OpenCLI 返回结构不是对象")
    return value


def parse_opencli_refs(state_text: str) -> tuple[str, str]:
    text = state_text or ""
    textarea = re.search(r"\[(\d+)\]<textarea\b[^\n]*placeholder=给 DeepSeek 发送消息", text)
    if not textarea:
        raise DeepSeekSendFailed("找不到 DeepSeek 输入框引用")
    tail = text[textarea.end() :]
    file_match = re.search(r"\[\d+\]<input\b[^\n]*type=file", tail)
    send_area = tail[file_match.end() :] if file_match else tail
    buttons = re.findall(r"\[(\d+)\]<(?:div|button)\b[^\n]*role=button", send_area)
    if not buttons:
        buttons = re.findall(r"\[(\d+)\]<(?:div|button)\b[^\n]*role=button", tail)
    if not buttons:
        raise DeepSeekSendFailed("找不到 DeepSeek 发送按钮引用")
    return textarea.group(1), buttons[0] if file_match else buttons[-1]


class DeepSeekBrowserClient:
    def __init__(
        self,
        runner: OpenCliRunner | None = None,
        *,
        session: str = DEFAULT_SESSION,
        poll_seconds: float = 1.0,
    ) -> None:
        self.runner = runner or SubprocessOpenCliRunner()
        self.session = session
        self.poll_seconds = max(0.0, poll_seconds)
        self._bound = False

    def _run(self, *args: str) -> CommandResult:
        result = self.runner.run(args)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "OpenCLI 命令失败").strip()
            raise DeepSeekBrowserError(detail[:500])
        return result

    def _browser(self, *args: str) -> CommandResult:
        return self._run("browser", self.session, *args)

    def validate_current_tab(self) -> DeepSeekPageState:
        if not self._bound:
            self._browser("bind")
            self._bound = True
        data = _decode_json(self._browser("eval", _VALIDATE_JS).stdout)
        url = str(data.get("url") or "")
        has_textarea = bool(data.get("has_textarea"))
        has_login = bool(data.get("has_login_form"))
        if "chat.deepseek.com" not in url:
            raise DeepSeekWrongConversation(
                "当前 Chrome 标签不是固定的“公众号爆文秘诀”DeepSeek 会话。"
            )
        if has_login or "sign_in" in url or "login" in url or not has_textarea:
            raise DeepSeekLoginRequired(LOGIN_INSTRUCTION)
        match = re.search(r"/a/chat/s/([0-9a-f-]+)", url, flags=re.I)
        conversation_id = match.group(1) if match else ""
        if conversation_id != FIXED_CONVERSATION_ID:
            raise DeepSeekWrongConversation(
                "当前 Chrome 标签不是固定的“公众号爆文秘诀”DeepSeek 会话。"
            )
        if bool(data.get("is_generating")):
            raise DeepSeekBusy("DeepSeek 当前仍在生成另一条回复，请等待完成后重试。")
        return DeepSeekPageState(
            conversation_id=conversation_id,
            url=url,
            title=str(data.get("title") or ""),
            assistant_count=int(data.get("assistant_count") or 0),
        )

    def _snapshot(self) -> dict:
        return _decode_json(self._browser("eval", _SNAPSHOT_JS).stdout)

    @staticmethod
    def _assistant_texts(snapshot: dict) -> list[str]:
        messages = snapshot.get("messages") or []
        return [
            str(row.get("text") or "").strip()
            for row in messages
            if isinstance(row, dict)
            and str(row.get("role") or "") == "assistant"
            and str(row.get("text") or "").strip()
        ]

    def send_and_receive(
        self, prompt: str, timeout_seconds: float = 180.0
    ) -> DeepSeekResponse:
        clean_prompt = (prompt or "").strip()
        if not clean_prompt:
            raise ValueError("DeepSeek 提示词不能为空")
        try:
            self.validate_current_tab()
            before = self._snapshot()
            before_assistants = self._assistant_texts(before)
            state_text = self._browser("state").stdout
            textarea_ref, send_ref = parse_opencli_refs(state_text)
            self._browser("type", textarea_ref, clean_prompt)
            self._browser("click", send_ref)

            deadline = time.monotonic() + max(0.0, timeout_seconds)
            latest = self._snapshot()
            assistants = self._assistant_texts(latest)
            while len(assistants) <= len(before_assistants) and time.monotonic() < deadline:
                if self.poll_seconds:
                    time.sleep(self.poll_seconds)
                latest = self._snapshot()
                assistants = self._assistant_texts(latest)

            body_text = str(latest.get("body_text") or "")
            messages = latest.get("messages") or []
            prompt_persisted = clean_prompt in body_text or any(
                isinstance(row, dict)
                and str(row.get("role") or "") == "user"
                and str(row.get("text") or "").strip() == clean_prompt
                for row in messages
            )
            if not prompt_persisted:
                raise DeepSeekSendFailed("本次提示词未持久化到 DeepSeek 会话")

            if len(assistants) <= len(before_assistants):
                raise DeepSeekResponseTimeout("等待 DeepSeek 新回复超时")
            response = assistants[len(before_assistants)].strip()
            if not response:
                raise DeepSeekSendFailed("DeepSeek 本轮回复为空")
            return DeepSeekResponse(
                text=response,
                assistant_index=len(before_assistants),
            )
        finally:
            self.unbind()

    def unbind(self) -> None:
        if not self._bound:
            return
        try:
            self._browser("unbind")
        finally:
            self._bound = False
