from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from scripts.tools.wechat_mp_chatgpt_image_browser import ChatGPTGeneratedImage
from scripts.tools.wechat_mp_chatgpt_images import RequestExecutionError, execute_request


def _image(path: Path, size: tuple[int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.effect_noise(size, 80).convert("RGB").save(path)


class FakeBrowser:
    def __init__(self, downloads: list[Path | Exception]) -> None:
        self.downloads = list(downloads)
        self.calls: list[dict[str, object]] = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        result = self.downloads.pop(0)
        if isinstance(result, Exception):
            raise result
        return ChatGPTGeneratedImage("https://chatgpt.com/c/test", result)


def _request(path: Path, slots: list[dict[str, str]]) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "generator": "chatgpt_web",
                "failure_policy": "stop_and_prompt",
                "article_type": "hotspot",
                "topic": "测试故事",
                "slots": slots,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_runs_cover_before_dependent_body_slots(tmp_path: Path) -> None:
    cover_download = tmp_path / "downloads" / "cover.png"
    body_download = tmp_path / "downloads" / "body.png"
    _image(cover_download, (1410, 600))
    _image(body_download, (1200, 900))
    request = _request(
        tmp_path / "request.json",
        [
            {
                "slot_id": "body-01",
                "reference_slot_id": "cover",
                "output_path": str(tmp_path / "manual-01.jpg"),
                "prompt": "正文",
            },
            {
                "slot_id": "cover",
                "output_path": str(tmp_path / "cover.jpg"),
                "prompt": "封面",
            },
        ],
    )
    browser = FakeBrowser([cover_download, body_download])
    report = execute_request(request, browser=browser, download_dir=tmp_path / "downloads")
    assert report.completed_slot_ids == ("cover", "body-01")
    assert browser.calls[0]["prompt"] == "封面"
    assert browser.calls[1]["reference_paths"] == [tmp_path / "cover.jpg"]


def test_resume_skips_existing_valid_slots(tmp_path: Path) -> None:
    _image(tmp_path / "cover.jpg", (1410, 600))
    body_download = tmp_path / "downloads" / "body.png"
    _image(body_download, (1200, 900))
    request = _request(
        tmp_path / "request.json",
        [
            {"slot_id": "cover", "output_path": str(tmp_path / "cover.jpg"), "prompt": "封面"},
            {
                "slot_id": "body-01",
                "reference_slot_id": "cover",
                "output_path": str(tmp_path / "manual-01.jpg"),
                "prompt": "正文",
            },
        ],
    )
    browser = FakeBrowser([body_download])
    report = execute_request(request, browser=browser, download_dir=tmp_path / "downloads")
    assert report.skipped_slot_ids == ("cover",)
    assert len(browser.calls) == 1


def test_failure_stops_before_next_slot_and_records_reason(tmp_path: Path) -> None:
    request = _request(
        tmp_path / "request.json",
        [
            {"slot_id": "cover", "output_path": str(tmp_path / "cover.jpg"), "prompt": "封面"},
            {"slot_id": "body-01", "output_path": str(tmp_path / "body.jpg"), "prompt": "正文"},
        ],
    )
    browser = FakeBrowser([RuntimeError("网页失败")])
    with pytest.raises(RequestExecutionError, match="已停止"):
        execute_request(request, browser=browser, download_dir=tmp_path / "downloads")
    progress = json.loads((tmp_path / "chatgpt-image-progress.json").read_text())
    assert progress["status"] == "stopped"
    assert progress["failed_slot_id"] == "cover"
    assert len(browser.calls) == 1


def test_rejects_output_path_outside_request_directory(tmp_path: Path) -> None:
    request = _request(
        tmp_path / "request.json",
        [{"slot_id": "cover", "output_path": "/tmp/outside.jpg", "prompt": "封面"}],
    )
    with pytest.raises(ValueError, match="输出路径"):
        execute_request(request, browser=FakeBrowser([]), download_dir=tmp_path)
