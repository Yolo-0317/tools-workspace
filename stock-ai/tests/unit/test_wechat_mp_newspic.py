from argparse import Namespace
from pathlib import Path

import pytest

from scripts.tools import wechat_mp_newspic
from PIL import Image

from scripts.tools.wechat_mp_newspic import add_image_watermark, build_newspic_article, upsert_newspic_draft, validate_newspic_image_sources, validate_newspic_input
from scripts.tools.wechat_mp_codex_images import (
    CodexImageGenerationRequired,
    PreparedTopicImages,
)


def test_build_newspic_article_uses_image_message_shape() -> None:
    article = build_newspic_article(title="材料从哪来？", content="一段说明", image_media_ids=["image-1", "image-2"])
    assert article["article_type"] == "newspic"
    assert article["image_info"]["image_list"] == [{"image_media_id": "image-1"}, {"image_media_id": "image-2"}]
    assert "thumb_media_id" not in article


def test_validate_newspic_input_rejects_more_than_nine_images(tmp_path: Path) -> None:
    image = tmp_path / "image.jpg"
    image.write_bytes(b"x")
    with pytest.raises(ValueError, match="1-9"):
        validate_newspic_input(title="标题", content="说明", image_paths=[image] * 10)


def test_validate_newspic_image_sources_requires_original_fallback_reason(tmp_path: Path) -> None:
    image = tmp_path / "image.jpg"
    image.write_bytes(b"x")
    sources = tmp_path / "sources.json"
    sources.write_text('{"image.jpg": {"source_type": "original"}}', encoding="utf-8")

    with pytest.raises(ValueError, match="来源记录不完整"):
        validate_newspic_image_sources(image_paths=[image], sources_path=sources)


def test_add_image_watermark_creates_modified_copy(tmp_path: Path) -> None:
    image = tmp_path / "image.png"
    output = tmp_path / "watermarked.png"
    Image.new("RGB", (320, 480), color=(30, 60, 90)).save(image)

    add_image_watermark(image_path=image, output_path=output, text="栀夏 · ZHI XIA")

    assert output.is_file()
    assert output.read_bytes() != image.read_bytes()
    with Image.open(output) as result:
        assert result.size == (320, 480)


def test_upsert_newspic_draft_creates_slot_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image = tmp_path / "image.jpg"
    image.write_bytes(b"x")
    captured: dict[str, object] = {}
    monkeypatch.setattr(wechat_mp_newspic, "upload_newspic_images", lambda *_args, **_kwargs: ["image-media-id"])
    monkeypatch.setattr(wechat_mp_newspic, "get_slot_media_id", lambda _slot: "")
    monkeypatch.setattr(wechat_mp_newspic, "draft_add", lambda *, articles: (captured.setdefault("article", articles[0]) and "draft-media-id", None))
    monkeypatch.setattr(wechat_mp_newspic, "set_slot_media_id", lambda slot, media_id, *, title: captured.update(slot=slot, media_id=media_id, title=title))

    media_id, action = upsert_newspic_draft(slot_key="newspic_test", title="标题", content="说明", image_paths=[image])

    assert (media_id, action) == ("draft-media-id", "created")
    assert captured["article"]["article_type"] == "newspic"
    assert captured["slot"] == "newspic_test"


def test_resolve_newspic_images_uses_topic_preparer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.tools import wechat_mp_newspic_draft as draft_cli

    first = tmp_path / "still-01.jpg"
    second = tmp_path / "manual-01.jpg"
    sources = tmp_path / "image-sources.json"
    captured: dict[str, object] = {}

    def fake_prepare(**kwargs) -> PreparedTopicImages:
        captured.update(kwargs)
        return PreparedTopicImages((first, second), sources)

    monkeypatch.setattr(draft_cli, "prepare_newspic_topic_images", fake_prepare)
    args = Namespace(
        topic="具体事件",
        research_url=["https://example.com/report"],
        image_count=6,
        images=None,
        image_sources=None,
    )

    image_paths, sources_path = draft_cli._resolve_newspic_images(args)

    assert image_paths == [first, second]
    assert sources_path == sources
    assert captured == {
        "topic": "具体事件",
        "research_urls": ["https://example.com/report"],
        "target_count": 6,
    }


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            Namespace(
                topic="具体事件",
                research_url=[],
                image_count=6,
                images=[Path("a.jpg")],
                image_sources=None,
            ),
            "不能同时",
        ),
        (
            Namespace(
                topic="",
                research_url=[],
                image_count=6,
                images=[Path("a.jpg")],
                image_sources=None,
            ),
            "必须同时",
        ),
        (
            Namespace(
                topic="",
                research_url=[],
                image_count=6,
                images=None,
                image_sources=Path("sources.json"),
            ),
            "必须同时",
        ),
    ],
)
def test_resolve_newspic_images_rejects_invalid_mode_combinations(
    args: Namespace,
    message: str,
) -> None:
    from scripts.tools import wechat_mp_newspic_draft as draft_cli

    with pytest.raises(ValueError, match=message):
        draft_cli._resolve_newspic_images(args)


def test_newspic_main_returns_recoverable_status_for_codex_image_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts.tools import wechat_mp_newspic_draft as draft_cli

    request_path = tmp_path / "codex-image-request.json"
    request_path.write_text("{}", encoding="utf-8")

    def require_generation(**_kwargs) -> PreparedTopicImages:
        raise CodexImageGenerationRequired(
            request_path=request_path,
            missing_count=2,
        )

    monkeypatch.setattr(draft_cli, "prepare_newspic_topic_images", require_generation)
    monkeypatch.setattr(
        draft_cli,
        "upsert_newspic_draft",
        lambda **_kwargs: pytest.fail("缺图时不应调用微信公众号草稿 API"),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "wechat_mp_newspic_draft",
            "--title",
            "具体事件为什么引发争议？",
            "--content",
            "这是贴图说明。",
            "--topic",
            "具体事件",
        ],
    )

    assert draft_cli.main() == 2
    error = capsys.readouterr().err
    assert "需要 Codex 原创补图" in error
    assert str(request_path) in error


def test_newspic_main_dry_run_never_calls_wechat_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts.tools import wechat_mp_newspic_draft as draft_cli

    image = tmp_path / "image.jpg"
    sources = tmp_path / "image-sources.json"
    Image.new("RGB", (640, 960), color=(30, 60, 90)).save(image)
    sources.write_text(
        '{"image.jpg":{"source_type":"report","page_url":"https://example.com/a"}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        draft_cli,
        "upsert_newspic_draft",
        lambda **_kwargs: pytest.fail("dry-run 不应调用微信公众号草稿 API"),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "wechat_mp_newspic_draft",
            "--title",
            "标题",
            "--content",
            "说明",
            "--images",
            str(image),
            "--image-sources",
            str(sources),
            "--dry-run",
        ],
    )

    assert draft_cli.main() == 0
    output = capsys.readouterr().out
    assert "DRY-RUN" in output
    assert str(image) in output
