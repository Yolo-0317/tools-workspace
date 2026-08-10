import json
from argparse import Namespace
from pathlib import Path

import pytest

from scripts.tools import wechat_mp_newspic
from PIL import Image

from scripts.tools.wechat_mp_newspic import add_image_watermark, build_newspic_article, prepare_newspic_images, upsert_newspic_draft, validate_newspic_image_sources, validate_newspic_input, verify_newspic_draft
from scripts.tools.wechat_mp_codex_images import (
    CodexImageGenerationRequired,
    PreparedTopicImages,
)


def test_build_newspic_article_uses_image_message_shape() -> None:
    article = build_newspic_article(
        title="手机壳材料究竟从哪来",
        content="甲" * 600,
        image_media_ids=[f"image-{index}" for index in range(1, 7)],
    )
    assert article["article_type"] == "newspic"
    assert article["image_info"]["image_list"] == [
        {"image_media_id": f"image-{index}"} for index in range(1, 7)
    ]
    assert "thumb_media_id" not in article


def test_validate_newspic_input_rejects_more_than_nine_images(tmp_path: Path) -> None:
    image = tmp_path / "image.jpg"
    image.write_bytes(b"x")
    with pytest.raises(ValueError, match="6-9"):
        validate_newspic_input(title="这是一个合规贴图标题", content="甲" * 800, image_paths=[image] * 10)


@pytest.mark.parametrize("title", ["标题太短", "这是一个超过二十个字符限制而必须被拒绝掉的贴图标题"])
def test_validate_newspic_input_enforces_editorial_title_length(
    tmp_path: Path,
    title: str,
) -> None:
    images = []
    for index in range(6):
        image = tmp_path / f"image-{index}.jpg"
        image.write_bytes(b"x")
        images.append(image)

    with pytest.raises(ValueError, match="8-20"):
        validate_newspic_input(title=title, content="甲" * 600, image_paths=images)


@pytest.mark.parametrize(
    ("image_count", "content_length", "message"),
    [
        (5, 600, "6-9"),
        (6, 599, "600-800"),
        (6, 801, "600-800"),
        (7, 799, "800-1000"),
        (9, 1001, "800-1000"),
    ],
)
def test_validate_newspic_input_enforces_image_count_content_ranges(
    tmp_path: Path,
    image_count: int,
    content_length: int,
    message: str,
) -> None:
    images = []
    for index in range(image_count):
        image = tmp_path / f"image-{index}.jpg"
        image.write_bytes(b"x")
        images.append(image)

    with pytest.raises(ValueError, match=message):
        validate_newspic_input(
            title="这是一个合规贴图标题",
            content="甲" * content_length,
            image_paths=images,
        )


def test_validate_newspic_input_accepts_virtual_lifestyle_quick_post(
    tmp_path: Path,
) -> None:
    images = []
    for index in range(3):
        image = tmp_path / f"image-{index}.jpg"
        image.write_bytes(b"x")
        images.append(image)

    assert validate_newspic_input(
        title="下班前先做这一步",
        content="甲" * 220,
        image_paths=images,
        draft_profile="virtual_lifestyle",
    ) == images


def test_validate_newspic_input_rejects_short_virtual_lifestyle_copy(
    tmp_path: Path,
) -> None:
    images = []
    for index in range(3):
        image = tmp_path / f"image-{index}.jpg"
        image.write_bytes(b"x")
        images.append(image)

    with pytest.raises(ValueError, match="150-500"):
        validate_newspic_input(
            title="下班前先做这一步",
            content="甲" * 149,
            image_paths=images,
            draft_profile="virtual_lifestyle",
        )


def test_validate_newspic_image_sources_requires_original_fallback_reason(tmp_path: Path) -> None:
    image = tmp_path / "image.jpg"
    image.write_bytes(b"x")
    sources = tmp_path / "sources.json"
    sources.write_text('{"image.jpg": {"source_type": "original"}}', encoding="utf-8")

    with pytest.raises(ValueError, match="来源记录不完整"):
        validate_newspic_image_sources(image_paths=[image], sources_path=sources)


def test_validate_newspic_image_sources_requires_report_page_title(tmp_path: Path) -> None:
    image = tmp_path / "image.jpg"
    image.write_bytes(b"x")
    sources = tmp_path / "sources.json"
    sources.write_text(
        '{"image.jpg": {"source_type": "report", "page_url": "https://example.com/a"}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="来源记录不完整"):
        validate_newspic_image_sources(image_paths=[image], sources_path=sources)


def test_validate_newspic_image_sources_requires_original_label_in_content(tmp_path: Path) -> None:
    image = tmp_path / "image.jpg"
    image.write_bytes(b"x")
    sources = tmp_path / "sources.json"
    sources.write_text(
        '{"image.jpg": {"source_type": "original", "fallback_reason": "报道图不足"}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="原创新闻插画"):
        validate_newspic_image_sources(
            image_paths=[image],
            sources_path=sources,
            content="甲" * 600,
        )


def test_validate_newspic_image_sources_requires_virtual_role_disclosure(
    tmp_path: Path,
) -> None:
    image = tmp_path / "image.jpg"
    image.write_bytes(b"x")
    sources = tmp_path / "sources.json"
    sources.write_text(
        json.dumps({"image.jpg": {
            "source_type": "original",
            "fallback_reason": "AI角色场景",
            "visual_role": "character",
            "position_role": "author",
            "capture_mode": "mirror_selfie",
            "allow_zhixia_watermark": True,
        }}, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="AI 虚拟角色"):
        validate_newspic_image_sources(
            image_paths=[image],
            sources_path=sources,
            content="甲" * 220,
            draft_profile="virtual_lifestyle",
        )


def test_validate_virtual_lifestyle_sources_requires_character_image(
    tmp_path: Path,
) -> None:
    images = [tmp_path / "topic-1.jpg", tmp_path / "topic-2.jpg"]
    for image in images:
        image.write_bytes(b"x")
    sources = tmp_path / "sources.json"
    sources.write_text(
        json.dumps(
            {
                image.name: {
                    "source_type": "original",
                    "fallback_reason": "原创主题视觉",
                    "visual_role": "topic",
                    "position_role": "evidence",
                    "allow_zhixia_watermark": True,
                }
                for image in images
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="至少一张栀夏角色图"):
        validate_newspic_image_sources(
            image_paths=images,
            sources_path=sources,
            content="栀夏是 AI 虚拟角色；图片为 AI 生成示意图。" + "甲" * 180,
            draft_profile="virtual_lifestyle",
        )


def test_validate_virtual_lifestyle_sources_accepts_character_and_topic_mix(
    tmp_path: Path,
) -> None:
    character = tmp_path / "character.jpg"
    topic = tmp_path / "topic.jpg"
    character.write_bytes(b"x")
    topic.write_bytes(b"x")
    sources = tmp_path / "sources.json"
    sources.write_text(
        json.dumps(
            {
                character.name: {
                    "source_type": "original",
                    "fallback_reason": "栀夏角色场景",
                    "visual_role": "character",
                    "position_role": "author",
                    "capture_mode": "mirror_selfie",
                    "allow_zhixia_watermark": True,
                },
                topic.name: {
                    "source_type": "report",
                    "page_url": "https://example.com/topic",
                    "page_title": "话题来源",
                    "source_name": "示例媒体",
                    "visual_role": "topic",
                    "position_role": "hook",
                    "allow_zhixia_watermark": False,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    validate_newspic_image_sources(
        image_paths=[character, topic],
        sources_path=sources,
        content="栀夏是 AI 虚拟角色；图片为 AI 生成示意图。" + "甲" * 180,
        draft_profile="virtual_lifestyle",
    )


def test_virtual_report_image_cannot_receive_zhixia_watermark(tmp_path: Path) -> None:
    image = tmp_path / "report.jpg"
    image.write_bytes(b"x")
    sources = tmp_path / "sources.json"
    sources.write_text(
        json.dumps(
            {
                image.name: {
                    "source_type": "report",
                    "visual_role": "topic",
                    "position_role": "hook",
                    "page_url": "https://example.com/report",
                    "page_title": "相关报道",
                    "source_name": "示例媒体",
                    "allow_zhixia_watermark": True,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="报道图.*水印"):
        validate_newspic_image_sources(
            image_paths=[image],
            sources_path=sources,
            content="栀夏是 AI 虚拟角色；图片为 AI 生成示意图。" + "甲" * 180,
            draft_profile="virtual_lifestyle",
            content_type="A",
        )


def test_virtual_character_image_requires_capture_mode(tmp_path: Path) -> None:
    image = tmp_path / "character.jpg"
    image.write_bytes(b"x")
    sources = tmp_path / "sources.json"
    sources.write_text(
        json.dumps(
            {
                image.name: {
                    "source_type": "original",
                    "fallback_reason": "角色作者卡",
                    "visual_role": "character",
                    "position_role": "author",
                    "allow_zhixia_watermark": True,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="capture_mode"):
        validate_newspic_image_sources(
            image_paths=[image],
            sources_path=sources,
            content="栀夏是 AI 虚拟角色；图片为 AI 生成示意图。" + "甲" * 180,
            draft_profile="virtual_lifestyle",
            content_type="C",
        )


def test_prepare_images_watermarks_only_allowed_originals(tmp_path: Path) -> None:
    report = tmp_path / "report.png"
    topic = tmp_path / "topic.png"
    character = tmp_path / "character.png"
    for index, image in enumerate((report, topic, character), start=1):
        Image.new("RGB", (320, 480), color=(30 * index, 60, 90)).save(image)
    prepared = prepare_newspic_images(
        image_paths=[report, topic, character],
        image_sources={
            report.name: {"allow_zhixia_watermark": False},
            topic.name: {"allow_zhixia_watermark": True},
            character.name: {"allow_zhixia_watermark": True},
        },
        watermark="栀夏 · ZHI XIA",
        output_dir=tmp_path / "out",
    )

    assert prepared[0] == report
    assert prepared[1] != topic
    assert prepared[2] != character
    assert prepared[1].read_bytes() != topic.read_bytes()
    assert prepared[2].read_bytes() != character.read_bytes()


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
    images = []
    for index in range(6):
        image = tmp_path / f"image-{index}.jpg"
        image.write_bytes(b"x")
        images.append(image)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        wechat_mp_newspic,
        "upload_newspic_images",
        lambda *_args, **_kwargs: [f"image-media-{index}" for index in range(6)],
    )
    monkeypatch.setattr(wechat_mp_newspic, "get_slot_media_id", lambda _slot: "")
    monkeypatch.setattr(wechat_mp_newspic, "draft_add", lambda *, articles: (captured.setdefault("article", articles[0]) and "draft-media-id", None))
    monkeypatch.setattr(
        wechat_mp_newspic,
        "fetch_draft_news_item",
        lambda *, media_id: (
            {
                "article_type": "newspic",
                "title": "这是一个合规贴图标题",
                "content": "甲" * 600,
                "image_info": {
                    "image_list": [
                        {"image_media_id": f"image-media-{index}"}
                        for index in range(6)
                    ]
                },
            },
            None,
        ),
    )
    monkeypatch.setattr(wechat_mp_newspic, "set_slot_media_id", lambda slot, media_id, *, title: captured.update(slot=slot, media_id=media_id, title=title))

    media_id, action = upsert_newspic_draft(
        slot_key="newspic_test",
        title="这是一个合规贴图标题",
        content="甲" * 600,
        image_paths=images,
    )

    assert (media_id, action) == ("draft-media-id", "created")
    assert captured["article"]["article_type"] == "newspic"
    assert captured["slot"] == "newspic_test"


def test_verify_newspic_draft_accepts_matching_remote_item(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        wechat_mp_newspic,
        "fetch_draft_news_item",
        lambda *, media_id: (
            {
                "article_type": "newspic",
                "title": "这是一个合规贴图标题",
                "content": "甲" * 600,
                "image_info": {
                    "image_list": [
                        {"image_media_id": f"image-{index}"} for index in range(6)
                    ]
                },
            },
            None,
        ),
    )

    verify_newspic_draft(
        media_id="draft-media-id",
        expected_title="这是一个合规贴图标题",
        expected_content="甲" * 600,
        expected_image_count=6,
    )


def test_verify_newspic_draft_rejects_remote_read_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        wechat_mp_newspic,
        "fetch_draft_news_item",
        lambda *, media_id: (None, {"errcode": 123, "errmsg": "读取失败"}),
    )

    with pytest.raises(RuntimeError, match="回读失败"):
        verify_newspic_draft(
            media_id="draft-media-id",
            expected_title="这是一个合规贴图标题",
            expected_content="甲" * 600,
            expected_image_count=6,
        )


def test_verify_newspic_draft_rejects_remote_shape_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        wechat_mp_newspic,
        "fetch_draft_news_item",
        lambda *, media_id: (
            {
                "article_type": "news",
                "title": "这是一个合规贴图标题",
                "content": "甲" * 600,
                "image_info": {"image_list": []},
            },
            None,
        ),
    )

    with pytest.raises(RuntimeError, match="稿型不符"):
        verify_newspic_draft(
            media_id="draft-media-id",
            expected_title="这是一个合规贴图标题",
            expected_content="甲" * 600,
            expected_image_count=6,
        )


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

    images = [tmp_path / f"image-{index}.jpg" for index in range(6)]
    sources = tmp_path / "image-sources.json"
    for image in images:
        Image.new("RGB", (640, 960), color=(30, 60, 90)).save(image)
    sources.write_text(
        json.dumps(
            {
                image.name: {
                    "source_type": "report",
                    "page_url": f"https://example.com/{index}",
                    "page_title": f"同题报道 {index}",
                }
                for index, image in enumerate(images, 1)
            },
            ensure_ascii=False,
        ),
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
            "这是一个合规贴图标题",
            "--content",
            "甲" * 600,
            "--images",
            *[str(image) for image in images],
            "--image-sources",
            str(sources),
            "--dry-run",
        ],
    )

    assert draft_cli.main() == 0
    output = capsys.readouterr().out
    assert "DRY-RUN" in output
    assert str(images[0]) in output
