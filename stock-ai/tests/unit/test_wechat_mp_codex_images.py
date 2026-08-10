from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from scripts.tools import wechat_mp_codex_images as images_mod
from scripts.tools.wechat_mp_codex_images import (
    CodexImageGenerationRequired,
    prepare_hotspot_topic_images,
    prepare_newspic_topic_images,
)


def _valid_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.effect_noise((800, 600), 100).convert("RGB").save(path, quality=94)


def _patch_report_fetch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    root: Path,
    report_names: tuple[str, ...],
) -> None:
    monkeypatch.setattr(images_mod.figures_mod, "INLINE_DISCUSSION_ROOT", root)

    def fake_ensure(topic: dict[str, object], *, max_images: int) -> list[dict[str, str]]:
        slug = str(topic["cover_slug"])
        return [
            {
                "rel": f"discussion/{slug}/{name}",
                "cap": "图源：公开报道（引用）",
            }
            for name in report_names[:max_images]
        ]

    monkeypatch.setattr(images_mod.figures_mod, "ensure_discussion_figures", fake_ensure)
    monkeypatch.setattr(
        images_mod.figures_mod,
        "_load_figure_sources",
        lambda _out_dir: {
            name: {
                "page_url": f"https://example.com/{index}",
                "page_title": f"同题报道 {index}",
            }
            for index, name in enumerate(report_names, 1)
        },
    )


def test_prepare_newspic_requests_only_missing_original_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _valid_image(tmp_path / "topic" / "still-01.jpg")
    _patch_report_fetch(monkeypatch, root=tmp_path, report_names=("still-01.jpg",))

    with pytest.raises(CodexImageGenerationRequired) as caught:
        prepare_newspic_topic_images(topic="事件", target_count=3, slug="topic")

    request = json.loads(caught.value.request_path.read_text(encoding="utf-8"))
    assert request["article_type"] == "newspic"
    assert request["report_image_count"] == 1
    assert request["missing_count"] == 2
    assert [Path(slot["output_path"]).name for slot in request["slots"]] == [
        "manual-01.jpg",
        "manual-02.jpg",
    ]
    assert all(Path(slot["output_path"]).is_absolute() for slot in request["slots"])


def test_prepare_newspic_combines_reports_and_generated_images(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_dir = tmp_path / "topic"
    _valid_image(out_dir / "still-01.jpg")
    _valid_image(out_dir / "manual-01.jpg")
    _patch_report_fetch(monkeypatch, root=tmp_path, report_names=("still-01.jpg",))

    prepared = prepare_newspic_topic_images(topic="事件", target_count=2, slug="topic")

    assert [path.name for path in prepared.image_paths] == [
        "still-01.jpg",
        "manual-01.jpg",
    ]
    sources = json.loads(prepared.sources_path.read_text(encoding="utf-8"))
    assert sources["still-01.jpg"] == {
        "source_type": "report",
        "page_url": "https://example.com/1",
        "page_title": "同题报道 1",
    }
    assert sources["manual-01.jpg"]["source_type"] == "original"
    assert "公开报道图不足" in sources["manual-01.jpg"]["fallback_reason"]


def test_prepare_newspic_re_requests_invalid_generated_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_dir = tmp_path / "topic"
    _valid_image(out_dir / "still-01.jpg")
    (out_dir / "manual-01.jpg").write_bytes(b"not-an-image" * 1000)
    _patch_report_fetch(monkeypatch, root=tmp_path, report_names=("still-01.jpg",))

    with pytest.raises(CodexImageGenerationRequired) as caught:
        prepare_newspic_topic_images(topic="事件", target_count=2, slug="topic")

    request = json.loads(caught.value.request_path.read_text(encoding="utf-8"))
    assert caught.value.missing_count == 1
    assert Path(request["slots"][0]["output_path"]).name == "manual-01.jpg"


def test_prepare_hotspot_requests_cover_and_missing_body_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_report_fetch(monkeypatch, root=tmp_path, report_names=())
    monkeypatch.setattr(
        images_mod.figures_mod,
        "ensure_discussion_body_figures",
        lambda _topic, *, max_images: [],
    )

    with pytest.raises(CodexImageGenerationRequired) as caught:
        prepare_hotspot_topic_images(
            {"cover_slug": "topic", "trend_title": "事件"},
            body_count=3,
        )

    request = json.loads(caught.value.request_path.read_text(encoding="utf-8"))
    assert request["article_type"] == "hotspot"
    assert [Path(slot["output_path"]).name for slot in request["slots"]] == [
        "cover.jpg",
        "manual-01.jpg",
        "manual-02.jpg",
        "manual-03.jpg",
    ]


def test_prepare_hotspot_accepts_generated_cover_and_body_images(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_dir = tmp_path / "topic"
    _valid_image(out_dir / "cover.jpg")
    for index in range(1, 4):
        _valid_image(out_dir / f"manual-{index:02d}.jpg")
    _patch_report_fetch(monkeypatch, root=tmp_path, report_names=())
    monkeypatch.setattr(
        images_mod.figures_mod,
        "ensure_discussion_body_figures",
        lambda _topic, *, max_images: [
            {
                "rel": f"discussion/topic/manual-{index:02d}.jpg",
                "cap": "原创新闻插画",
            }
            for index in range(1, max_images + 1)
        ],
    )

    prepare_hotspot_topic_images(
        {"cover_slug": "topic", "trend_title": "事件"},
        body_count=3,
    )

    assert not (out_dir / "codex-image-request.json").exists()


def test_prepare_hotspot_resume_skips_completed_network_fetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_dir = tmp_path / "topic"
    _patch_report_fetch(monkeypatch, root=tmp_path, report_names=())
    monkeypatch.setattr(
        images_mod.figures_mod,
        "ensure_discussion_body_figures",
        lambda _topic, *, max_images: [],
    )
    topic = {"cover_slug": "topic", "trend_title": "事件"}
    with pytest.raises(CodexImageGenerationRequired):
        prepare_hotspot_topic_images(topic, body_count=3)
    _valid_image(out_dir / "cover.jpg")
    for index in range(1, 4):
        _valid_image(out_dir / f"manual-{index:02d}.jpg")

    monkeypatch.setattr(
        images_mod.figures_mod,
        "ensure_discussion_figures",
        lambda _topic, *, max_images: pytest.fail("补图完成后不应再次联网抓图"),
    )
    monkeypatch.setattr(
        images_mod.figures_mod,
        "ensure_discussion_body_figures",
        lambda _topic, *, max_images: [
            {
                "rel": f"discussion/topic/manual-{index:02d}.jpg",
                "cap": "原创新闻插画",
            }
            for index in range(1, max_images + 1)
        ],
    )

    prepare_hotspot_topic_images(topic, body_count=3)

    assert (out_dir / "codex-images-ready.json").is_file()
