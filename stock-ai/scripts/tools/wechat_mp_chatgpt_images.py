"""执行公众号原创配图请求，失败时停止且不切换生成渠道。"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from PIL import Image

from scripts.tools.wechat_mp_chatgpt_image_browser import (
    DEFAULT_SESSION,
    ChatGPTImageBrowser,
    copy_validated_image,
)

PROGRESS_FILENAME = "chatgpt-image-progress.json"


class RequestExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExecutionReport:
    completed_slot_ids: tuple[str, ...]
    skipped_slot_ids: tuple[str, ...]
    progress_path: Path


def _read_request(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("原创配图请求文件无效") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 2:
        raise ValueError("只支持 schema_version=2 的原创配图请求")
    if payload.get("generator") != "chatgpt_web":
        raise ValueError("请求未指定 ChatGPT 网页生成")
    if payload.get("failure_policy") != "stop_and_prompt":
        raise ValueError("请求必须使用失败即停策略")
    slots = payload.get("slots")
    if not isinstance(slots, list) or not slots:
        raise ValueError("原创配图请求没有图片槽位")
    return payload


def _valid_image(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size < 8000:
            return False
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, ValueError):
        return False


def _ratio_for(slot_id: str, article_type: str) -> float:
    if slot_id == "cover":
        return 2.35
    if article_type == "newspic":
        return 0.75
    return 4 / 3


def _write_progress(path: Path, payload: dict[str, Any]) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _ordered_slots(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(slot.get("slot_id") or ""): slot for slot in slots if isinstance(slot, dict)}
    if "" in by_id or len(by_id) != len(slots):
        raise ValueError("图片槽位 ID 缺失或重复")
    for slot_id, slot in by_id.items():
        dependency = str(slot.get("reference_slot_id") or "")
        if dependency and dependency not in by_id:
            raise ValueError(f"槽位 {slot_id} 引用了不存在的参考槽位")
    return sorted(slots, key=lambda slot: (str(slot.get("slot_id")) != "cover", str(slot.get("slot_id"))))


def execute_request(
    request_path: Path,
    *,
    browser: ChatGPTImageBrowser,
    download_dir: Path,
    timeout_seconds: float = 240.0,
) -> ExecutionReport:
    request_path = Path(request_path).resolve()
    payload = _read_request(request_path)
    root = request_path.parent.resolve()
    progress_path = root / PROGRESS_FILENAME
    article_type = str(payload.get("article_type") or "")
    slots = _ordered_slots(payload["slots"])
    targets: dict[str, Path] = {}
    for slot in slots:
        slot_id = str(slot["slot_id"])
        target = Path(str(slot.get("output_path") or "")).resolve()
        if target.parent != root:
            raise ValueError(f"槽位 {slot_id} 的输出路径不在请求目录内")
        targets[slot_id] = target

    completed: list[str] = []
    skipped: list[str] = []
    for slot in slots:
        slot_id = str(slot["slot_id"])
        target = targets[slot_id]
        if _valid_image(target):
            skipped.append(slot_id)
            continue
        dependency = str(slot.get("reference_slot_id") or "")
        references = [targets[dependency]] if dependency else []
        if dependency and not _valid_image(references[0]):
            raise ValueError(f"槽位 {slot_id} 的参考图尚未完成")
        try:
            generated = browser.generate(
                prompt=str(slot.get("prompt") or "").strip(),
                download_dir=Path(download_dir),
                reference_paths=references,
                timeout_seconds=timeout_seconds,
            )
            copy_validated_image(
                generated.downloaded_path,
                target,
                expected_ratio=_ratio_for(slot_id, article_type),
            )
            completed.append(slot_id)
            _write_progress(
                progress_path,
                {
                    "schema_version": 1,
                    "status": "running",
                    "completed_slot_ids": completed,
                    "skipped_slot_ids": skipped,
                },
            )
        except Exception as exc:
            _write_progress(
                progress_path,
                {
                    "schema_version": 1,
                    "status": "stopped",
                    "failed_slot_id": slot_id,
                    "completed_slot_ids": completed,
                    "skipped_slot_ids": skipped,
                    "action": "检查 ChatGPT 登录、当前标签、生成结果或下载后重试",
                },
            )
            raise RequestExecutionError(
                f"ChatGPT 网页配图在槽位 {slot_id} 失败，流程已停止：{exc}"
            ) from exc

    _write_progress(
        progress_path,
        {
            "schema_version": 1,
            "status": "complete",
            "completed_slot_ids": completed,
            "skipped_slot_ids": skipped,
        },
    )
    return ExecutionReport(tuple(completed), tuple(skipped), progress_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="使用已登录 ChatGPT 网页补齐公众号原创配图")
    parser.add_argument("--request", required=True, type=Path, help="原创配图请求 JSON")
    parser.add_argument("--download-dir", required=True, type=Path, help="浏览器下载目录")
    parser.add_argument("--session", default=DEFAULT_SESSION, help="OpenCLI 浏览器会话名")
    parser.add_argument("--timeout", type=float, default=240.0, help="单张图片等待秒数")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    browser = ChatGPTImageBrowser(session=args.session)
    try:
        report = execute_request(
            args.request,
            browser=browser,
            download_dir=args.download_dir,
            timeout_seconds=args.timeout,
        )
    except (ValueError, RequestExecutionError) as exc:
        print(str(exc))
        return 1
    print(str(report.progress_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
