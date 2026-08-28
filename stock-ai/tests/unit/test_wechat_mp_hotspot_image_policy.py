from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image


def _load_api():
    from scripts.tools.wechat_mp_hotspot_image_policy import (
        validate_verified_hotspot_images,
    )

    return validate_verified_hotspot_images


def _write_douyin_state(
    out_dir: Path,
    *,
    topic: str,
    candidates: list[dict[str, object]],
    fallback_reason: str = "",
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "douyin-search.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "topic": topic,
                "query": topic,
                "completed_at": "2026-08-28T12:00:00+08:00",
                "fallback_reason": fallback_reason,
                "candidates": candidates,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _douyin_candidate(*, selected: bool = True) -> dict[str, object]:
    return {
        "account": "浙江日报",
        "display_time": "1天前",
        "video_url": "https://www.douyin.com/video/123",
        "cover_url": "https://example.com/douyin-cover.jpg",
        "selected": selected,
    }


def _write_verified_image(
    out_dir: Path,
    filename: str,
    *,
    source_type: str,
    page_url: str | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    Image.effect_noise((800, 600), 80).convert("RGB").save(path, quality=94)
    sources_path = out_dir / "figure_sources.json"
    sources = (
        json.loads(sources_path.read_text(encoding="utf-8"))
        if sources_path.is_file()
        else {}
    )
    sources[filename] = {
        "page_url": page_url or f"https://example.com/{filename}",
        "image_url": "https://example.com/image.jpg",
        "source_name": "浙江日报" if source_type == "douyin_cover" else "浙江在线",
        "published_at": "2026-08-27",
        "source_type": source_type,
        "verified": True,
        "page_title": f"测试报道 {filename}",
        "caption": f"图源：测试来源 {filename}",
    }
    sources_path.write_text(
        json.dumps(sources, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def test_missing_douyin_search_state_is_rejected(tmp_path: Path) -> None:
    validate_verified_hotspot_images = _load_api()

    with pytest.raises(ValueError, match="必须先完成抖音搜索"):
        validate_verified_hotspot_images(tmp_path, expected_topic="测试热点")


def test_zero_douyin_candidates_requires_fallback_reason(tmp_path: Path) -> None:
    validate_verified_hotspot_images = _load_api()
    _write_douyin_state(tmp_path, topic="测试热点", candidates=[])
    _write_verified_image(
        tmp_path,
        "still-01.jpg",
        source_type="official_media_webpage_screenshot",
    )

    with pytest.raises(ValueError, match="必须记录原因"):
        validate_verified_hotspot_images(tmp_path, expected_topic="测试热点")


def test_zero_douyin_candidates_can_use_official_cover(tmp_path: Path) -> None:
    validate_verified_hotspot_images = _load_api()
    _write_douyin_state(
        tmp_path,
        topic="测试热点",
        candidates=[],
        fallback_reason="搜索结果无政务或正规媒体同题封面",
    )
    _write_verified_image(
        tmp_path,
        "still-01.jpg",
        source_type="official_media_webpage_screenshot",
    )

    result = validate_verified_hotspot_images(tmp_path, expected_topic="测试热点")

    assert result.cover_source.name == "still-01.jpg"
    assert result.body_figures == ()


def test_selected_douyin_candidate_must_match_figure_source(tmp_path: Path) -> None:
    validate_verified_hotspot_images = _load_api()
    _write_douyin_state(
        tmp_path,
        topic="测试热点",
        candidates=[_douyin_candidate()],
    )
    _write_verified_image(
        tmp_path,
        "still-01.jpg",
        source_type="official_media_webpage_screenshot",
    )

    with pytest.raises(ValueError, match="所选抖音封面未写入 figure_sources"):
        validate_verified_hotspot_images(tmp_path, expected_topic="测试热点")


@pytest.mark.parametrize(
    ("image_count", "expected_body_count"),
    [(1, 0), (2, 1), (4, 3), (6, 3)],
)
def test_verified_images_use_one_cover_and_up_to_three_body_images(
    tmp_path: Path,
    image_count: int,
    expected_body_count: int,
) -> None:
    validate_verified_hotspot_images = _load_api()
    _write_douyin_state(
        tmp_path,
        topic="测试热点",
        candidates=[_douyin_candidate()],
    )
    for index in range(1, image_count + 1):
        _write_verified_image(
            tmp_path,
            f"still-{index:02d}.jpg",
            source_type=(
                "douyin_cover" if index == 1 else "official_media_webpage_screenshot"
            ),
            page_url=(
                "https://www.douyin.com/video/123"
                if index == 1
                else f"https://example.com/report-{index}"
            ),
        )

    result = validate_verified_hotspot_images(tmp_path, expected_topic="测试热点")

    assert result.cover_source.name == "still-01.jpg"
    assert len(result.body_figures) == expected_body_count
    assert all(figure.path.name != "still-01.jpg" for figure in result.body_figures)


def test_zero_verified_images_are_rejected(tmp_path: Path) -> None:
    validate_verified_hotspot_images = _load_api()
    _write_douyin_state(
        tmp_path,
        topic="测试热点",
        candidates=[],
        fallback_reason="搜索结果没有合格同题封面",
    )

    with pytest.raises(ValueError, match="缺少可追溯封面"):
        validate_verified_hotspot_images(tmp_path, expected_topic="测试热点")


def test_topic_mismatch_is_rejected(tmp_path: Path) -> None:
    validate_verified_hotspot_images = _load_api()
    _write_douyin_state(
        tmp_path,
        topic="另一个热点",
        candidates=[],
        fallback_reason="没有合格候选",
    )

    with pytest.raises(ValueError, match="主题不一致"):
        validate_verified_hotspot_images(tmp_path, expected_topic="测试热点")
