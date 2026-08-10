from pathlib import Path

import pytest

from scripts.tools import wechat_mp_newspic
from PIL import Image

from scripts.tools.wechat_mp_newspic import add_image_watermark, build_newspic_article, upsert_newspic_draft, validate_newspic_image_sources, validate_newspic_input


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
