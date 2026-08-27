from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from scripts.tools.wechat_mp_chatgpt_image_browser import (
    ChatGPTGenerationTimeout,
    ChatGPTImageBrowser,
    ChatGPTLoginRequired,
    ChatGPTWrongTab,
    CommandResult,
    copy_validated_image,
    parse_composer_refs,
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
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return CommandResult(0, text, "")


def _page(**overrides: object) -> dict[str, object]:
    page: dict[str, object] = {
        "url": "https://chatgpt.com/c/example",
        "logged_in": True,
        "has_composer": True,
        "generating": False,
        "generated_image_count": 1,
    }
    page.update(overrides)
    return page


def test_validate_requires_chatgpt_tab() -> None:
    runner = FakeRunner([_ok({"bound": True}), _ok(_page(url="https://example.com"))])
    with pytest.raises(ChatGPTWrongTab):
        ChatGPTImageBrowser(runner).inspect()


def test_validate_reports_login_required_without_touching_storage() -> None:
    runner = FakeRunner(
        [_ok({"bound": True}), _ok(_page(logged_in=False, has_composer=False))]
    )
    with pytest.raises(ChatGPTLoginRequired, match="登录 ChatGPT"):
        ChatGPTImageBrowser(runner).inspect()
    flattened = " ".join(part for call in runner.calls for part in call)
    assert "cookie" not in flattened.lower()
    assert "localStorage" not in flattened
    assert "sessionStorage" not in flattened


def test_parse_composer_refs_finds_input_file_and_send() -> None:
    state = """
      [20]<textarea placeholder=询问任何问题 />
      [21]<input type=file accept=image/* />
      [22]<button aria-label=发送提示 />
    """
    assert parse_composer_refs(state) == ("20", "21", "22")


def test_generate_types_prompt_uploads_reference_and_clicks_send(tmp_path: Path) -> None:
    reference = tmp_path / "cover.png"
    Image.new("RGB", (1200, 800), "white").save(reference)
    runner = FakeRunner(
        [
            _ok({"bound": True}),
            _ok(_page()),
            _ok(
                "[20]<textarea placeholder=询问任何问题 />\n"
                "[21]<input type=file accept=image/* />\n"
                "[22]<button aria-label=发送提示 />"
            ),
            _ok({"uploaded": True}),
            _ok({"typed": True}),
            _ok({"clicked": True}),
            _ok(_page()),
            _ok({"unbound": True}),
        ]
    )
    with pytest.raises(ChatGPTGenerationTimeout):
        ChatGPTImageBrowser(runner, poll_seconds=0).generate(
            prompt="画一张图",
            download_dir=tmp_path,
            reference_paths=[reference],
            timeout_seconds=0,
        )
    assert ("browser", "chatgpt_image_writer", "upload", "21", str(reference)) in runner.calls
    assert ("browser", "chatgpt_image_writer", "type", "20", "画一张图") in runner.calls
    assert ("browser", "chatgpt_image_writer", "click", "22") in runner.calls
    assert runner.calls[-1][-1] == "unbind"
    assert not any("close" in call for call in runner.calls)


def test_copy_validated_image_is_atomic_and_preserves_target_on_failure(
    tmp_path: Path,
) -> None:
    source = tmp_path / "download.png"
    target = tmp_path / "final.jpg"
    target.write_bytes(b"existing")
    source.write_bytes(b"bad")
    with pytest.raises(ValueError):
        copy_validated_image(source, target, expected_ratio=2.35)
    assert target.read_bytes() == b"existing"

    Image.effect_noise((1410, 600), 80).convert("RGB").save(source)
    result = copy_validated_image(source, target, expected_ratio=2.35)
    assert result.path == target
    assert result.width == 1410
    assert result.height == 600
    with Image.open(target) as image:
        assert image.size == (1410, 600)
