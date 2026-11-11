"""通过 OpenCLI 操作已登录的 ChatGPT 网页生成并保存公众号配图。"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from PIL import Image

DEFAULT_SESSION = "chatgpt_image_writer"


class ChatGPTImageBrowserError(RuntimeError):
    pass


class ChatGPTLoginRequired(ChatGPTImageBrowserError):
    pass


class ChatGPTWrongTab(ChatGPTImageBrowserError):
    pass


class ChatGPTGenerationTimeout(ChatGPTImageBrowserError):
    pass


class ChatGPTDownloadFailed(ChatGPTImageBrowserError):
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
            [self.binary, *args], check=False, capture_output=True, text=True
        )
        return CommandResult(proc.returncode, proc.stdout, proc.stderr)


@dataclass(frozen=True)
class ChatGPTImagePageState:
    url: str
    logged_in: bool
    generating: bool
    generated_image_count: int


@dataclass(frozen=True)
class ChatGPTGeneratedImage:
    source_conversation_url: str
    downloaded_path: Path


@dataclass(frozen=True)
class ValidatedImage:
    path: Path
    width: int
    height: int
    image_format: str


_PAGE_JS = r'''(()=>{
  const url=location.href;
  const composer=document.querySelector('textarea, #prompt-textarea, [contenteditable=true]');
  const body=(document.body.innerText||'').slice(0,4000);
  const login=/登录|注册|Log in|Sign up/i.test(body) && !composer;
  const stopping=Array.from(document.querySelectorAll('button,[role=button]')).some(e=>
    /停止生成|Stop generating/i.test((e.innerText||'')+' '+(e.getAttribute('aria-label')||'')));
  const images=Array.from(document.querySelectorAll('img')).filter(e=>
    /generated|已生成|生成的图片/i.test((e.alt||'')+' '+(e.getAttribute('aria-label')||'')));
  return JSON.stringify({url,logged_in:!login && !!composer,has_composer:!!composer,
    generating:stopping,generated_image_count:images.length});
})()'''


def _decode_json(stdout: str) -> dict:
    raw = (stdout or "").strip()
    try:
        value = json.loads(raw)
        if isinstance(value, str):
            value = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ChatGPTImageBrowserError("OpenCLI 未返回有效页面状态") from exc
    if not isinstance(value, dict):
        raise ChatGPTImageBrowserError("OpenCLI 页面状态格式错误")
    return value


def parse_composer_refs(state_text: str) -> tuple[str, str | None, str]:
    text = state_text or ""
    input_match = re.search(
        r"\[(\d+)\]<(?:textarea|div)\b[^\n]*(?:placeholder=|contenteditable=true)",
        text,
        flags=re.I,
    )
    if not input_match:
        raise ChatGPTImageBrowserError("找不到 ChatGPT 输入框")
    file_match = re.search(r"\[(\d+)\]<input\b[^\n]*type=file", text, flags=re.I)
    send_match = re.search(
        r"\[(\d+)\]<(?:button|div)\b[^\n]*(?:发送|Send prompt|aria-label=发送)",
        text,
        flags=re.I,
    )
    if not send_match:
        buttons = re.findall(r"\[(\d+)\]<(?:button|div)\b[^\n]*(?:role=button)", text)
        if not buttons:
            raise ChatGPTImageBrowserError("找不到 ChatGPT 发送按钮")
        send_ref = buttons[-1]
    else:
        send_ref = send_match.group(1)
    return input_match.group(1), file_match.group(1) if file_match else None, send_ref


def _last_generated_image_ref(state_text: str) -> str:
    matches = re.findall(
        r"\[(\d+)\]<(?:img|button|div)\b[^\n]*(?:generated|已生成|生成的图片)",
        state_text or "",
        flags=re.I,
    )
    if not matches:
        raise ChatGPTDownloadFailed("找不到本轮生成的图片")
    return matches[-1]


def _save_ref(state_text: str) -> str:
    match = re.search(
        r"\[(\d+)\]<(?:button|a|div)\b[^\n]*(?:保存|下载|Save|Download)",
        state_text or "",
        flags=re.I,
    )
    if not match:
        raise ChatGPTDownloadFailed("图片已生成，但找不到页面保存按钮")
    return match.group(1)


def _download_snapshot(directory: Path) -> dict[Path, tuple[int, int]]:
    directory.mkdir(parents=True, exist_ok=True)
    result: dict[Path, tuple[int, int]] = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            stat = path.stat()
            result[path.resolve()] = (stat.st_size, stat.st_mtime_ns)
    return result


def _wait_for_download(
    directory: Path,
    before: dict[Path, tuple[int, int]],
    *,
    timeout_seconds: float,
    poll_seconds: float,
) -> Path:
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    last: tuple[Path, int] | None = None
    while time.monotonic() <= deadline:
        candidates: list[Path] = []
        for path in directory.iterdir():
            if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            stat = path.stat()
            if before.get(path.resolve()) != (stat.st_size, stat.st_mtime_ns):
                candidates.append(path.resolve())
        if candidates:
            newest = max(candidates, key=lambda item: item.stat().st_mtime_ns)
            size = newest.stat().st_size
            if size > 0 and last == (newest, size):
                return newest
            last = (newest, size)
        if poll_seconds:
            time.sleep(poll_seconds)
    raise ChatGPTDownloadFailed("等待 ChatGPT 图片下载完成超时")


def copy_validated_image(
    source: Path,
    target: Path,
    *,
    expected_ratio: float | None = None,
    ratio_tolerance: float = 0.18,
) -> ValidatedImage:
    source = Path(source)
    target = Path(target)
    try:
        with Image.open(source) as image:
            image.verify()
        with Image.open(source) as image:
            width, height = image.size
            image_format = str(image.format or source.suffix.lstrip(".")).upper()
    except (OSError, ValueError) as exc:
        raise ValueError("下载文件不是有效图片") from exc
    if source.stat().st_size < 8000 or width < 600 or height < 400:
        raise ValueError("图片尺寸或文件大小不足")
    ratio = width / height
    if expected_ratio and abs(ratio - expected_ratio) / expected_ratio > ratio_tolerance:
        raise ValueError("图片比例不符合当前槽位要求")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.chatgpt.tmp{source.suffix.lower()}")
    try:
        shutil.copyfile(source, temp)
        with Image.open(temp) as image:
            image.verify()
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    return ValidatedImage(target, width, height, image_format)


class ChatGPTImageBrowser:
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

    def _browser(self, *args: str) -> CommandResult:
        result = self.runner.run(("browser", self.session, *args))
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "OpenCLI 命令失败").strip()
            raise ChatGPTImageBrowserError(detail[:500])
        return result

    def inspect(self) -> ChatGPTImagePageState:
        if not self._bound:
            self._browser("bind")
            self._bound = True
        data = _decode_json(self._browser("eval", _PAGE_JS).stdout)
        url = str(data.get("url") or "")
        if "chatgpt.com" not in url:
            raise ChatGPTWrongTab("请在 Chrome 切换到 ChatGPT 图片会话后重试")
        logged_in = bool(data.get("logged_in")) and bool(data.get("has_composer"))
        if not logged_in:
            raise ChatGPTLoginRequired("请在 Chrome 登录 ChatGPT 并保持目标会话为当前标签")
        return ChatGPTImagePageState(
            url=url,
            logged_in=True,
            generating=bool(data.get("generating")),
            generated_image_count=int(data.get("generated_image_count") or 0),
        )

    def generate(
        self,
        *,
        prompt: str,
        download_dir: Path,
        reference_paths: Sequence[Path] = (),
        timeout_seconds: float = 240.0,
    ) -> ChatGPTGeneratedImage:
        clean_prompt = (prompt or "").strip()
        if not clean_prompt:
            raise ValueError("图片提示词不能为空")
        try:
            initial = self.inspect()
            before_count = initial.generated_image_count
            state_text = self._browser("state").stdout
            composer_ref, file_ref, send_ref = parse_composer_refs(state_text)
            references = [Path(path).resolve() for path in reference_paths]
            if references and not file_ref:
                raise ChatGPTImageBrowserError("当前页面找不到参考图上传入口")
            for reference in references:
                if not reference.is_file():
                    raise ValueError(f"参考图不存在：{reference.name}")
                self._browser("upload", str(file_ref), str(reference))
            self._browser("type", composer_ref, clean_prompt)
            self._browser("click", send_ref)

            deadline = time.monotonic() + max(0.0, timeout_seconds)
            latest = self.inspect()
            while (
                latest.generating or latest.generated_image_count <= before_count
            ) and time.monotonic() < deadline:
                if self.poll_seconds:
                    time.sleep(self.poll_seconds)
                latest = self.inspect()
            if latest.generating or latest.generated_image_count <= before_count:
                raise ChatGPTGenerationTimeout("等待 ChatGPT 网页生成图片超时，请检查页面后重试")

            generated_ref = _last_generated_image_ref(self._browser("state").stdout)
            self._browser("click", generated_ref)
            detail_state = self._browser("state").stdout
            save_ref = _save_ref(detail_state)
            before_download = _download_snapshot(Path(download_dir))
            self._browser("click", save_ref)
            downloaded = _wait_for_download(
                Path(download_dir),
                before_download,
                timeout_seconds=min(60.0, timeout_seconds),
                poll_seconds=max(0.05, self.poll_seconds),
            )
            return ChatGPTGeneratedImage(latest.url, downloaded)
        finally:
            self.unbind()

    def unbind(self) -> None:
        if not self._bound:
            return
        try:
            self._browser("unbind")
        finally:
            self._bound = False
