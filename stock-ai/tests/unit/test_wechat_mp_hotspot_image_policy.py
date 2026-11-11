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


def _write_cover_source(
    out_dir: Path,
    *,
    source_filename: str = "still-01.jpg",
    reuse_in_body: object = False,
) -> None:
    (out_dir / "cover_source.json").write_text(
        json.dumps(
            {
                "source_filename": source_filename,
                "reuse_in_body": reuse_in_body,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _prepare_verified_images(out_dir: Path, image_count: int = 4) -> None:
    _write_douyin_state(
        out_dir,
        topic="测试热点",
        candidates=[_douyin_candidate()],
    )
    for index in range(1, image_count + 1):
        _write_verified_image(
            out_dir,
            f"still-{index:02d}.jpg",
            source_type=(
                "douyin_cover"
                if index == 1
                else "official_media_webpage_screenshot"
            ),
            page_url=(
                "https://www.douyin.com/video/123"
                if index == 1
                else f"https://example.com/report-{index}"
            ),
        )


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
    assert [figure.path.name for figure in result.body_figures] == ["still-01.jpg"]


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
    ("image_count", "expected_body_names"),
    [
        (1, ["still-01.jpg"]),
        (2, ["still-01.jpg", "still-02.jpg"]),
        (3, ["still-01.jpg", "still-02.jpg", "still-03.jpg"]),
        (4, ["still-02.jpg", "still-03.jpg", "still-04.jpg"]),
        (6, ["still-02.jpg", "still-03.jpg", "still-04.jpg"]),
    ],
)
def test_up_to_three_verified_images_all_appear_in_body(
    tmp_path: Path,
    image_count: int,
    expected_body_names: list[str],
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
    assert [figure.path.name for figure in result.body_figures] == expected_body_names


def test_explicit_cover_reuse_places_cover_first_in_body(tmp_path: Path) -> None:
    validate_verified_hotspot_images = _load_api()
    _prepare_verified_images(tmp_path)
    _write_cover_source(tmp_path, reuse_in_body=True)

    result = validate_verified_hotspot_images(
        tmp_path,
        expected_topic="测试热点",
    )

    assert [figure.path.name for figure in result.body_figures] == [
        "still-01.jpg",
        "still-02.jpg",
        "still-03.jpg",
    ]


def test_cover_reuse_obeys_requested_body_limit(tmp_path: Path) -> None:
    validate_verified_hotspot_images = _load_api()
    _prepare_verified_images(tmp_path)
    _write_cover_source(tmp_path, reuse_in_body=True)

    result = validate_verified_hotspot_images(
        tmp_path,
        expected_topic="测试热点",
        max_body=2,
    )

    assert [figure.path.name for figure in result.body_figures] == [
        "still-01.jpg",
        "still-02.jpg",
    ]


def test_cover_reuse_with_zero_body_limit_returns_no_body_images(
    tmp_path: Path,
) -> None:
    validate_verified_hotspot_images = _load_api()
    _prepare_verified_images(tmp_path)
    _write_cover_source(tmp_path, reuse_in_body=True)

    result = validate_verified_hotspot_images(
        tmp_path,
        expected_topic="测试热点",
        max_body=0,
    )

    assert result.body_figures == ()


@pytest.mark.parametrize("invalid_value", ["true", 1, None, [], {}])
def test_non_boolean_cover_reuse_value_does_not_drop_cover_when_only_two_images(
    tmp_path: Path,
    invalid_value: object,
) -> None:
    validate_verified_hotspot_images = _load_api()
    _prepare_verified_images(tmp_path, image_count=2)
    _write_cover_source(tmp_path, reuse_in_body=invalid_value)

    result = validate_verified_hotspot_images(
        tmp_path,
        expected_topic="测试热点",
    )

    assert [figure.path.name for figure in result.body_figures] == [
        "still-01.jpg",
        "still-02.jpg",
    ]


def test_malformed_cover_source_does_not_drop_cover_when_only_two_images(
    tmp_path: Path,
) -> None:
    validate_verified_hotspot_images = _load_api()
    _prepare_verified_images(tmp_path, image_count=2)
    (tmp_path / "cover_source.json").write_text("{", encoding="utf-8")

    result = validate_verified_hotspot_images(
        tmp_path,
        expected_topic="测试热点",
    )

    assert [figure.path.name for figure in result.body_figures] == [
        "still-01.jpg",
        "still-02.jpg",
    ]


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


def test_new_hotspot_images_require_visual_check_metadata(tmp_path: Path) -> None:
    validate_verified_hotspot_images = _load_api()
    _write_douyin_state(
        tmp_path, topic="测试热点", candidates=[], fallback_reason="搜索卡片没有证据图"
    )
    _write_verified_image(
        tmp_path, "still-01.jpg", source_type="official_media_webpage_screenshot"
    )

    with pytest.raises(ValueError, match="视觉核对"):
        validate_verified_hotspot_images(
            tmp_path, expected_topic="测试热点", require_visual_check=True
        )


def test_new_hotspot_visual_check_keeps_cover_in_body(tmp_path: Path) -> None:
    validate_verified_hotspot_images = _load_api()
    _write_douyin_state(
        tmp_path, topic="测试热点", candidates=[], fallback_reason="搜索卡片没有证据图"
    )
    for index in (1, 2):
        path = _write_verified_image(
            tmp_path, f"still-{index:02d}.jpg",
            source_type="official_media_webpage_screenshot",
        )
        sources_path = tmp_path / "figure_sources.json"
        sources = json.loads(sources_path.read_text(encoding="utf-8"))
        sources[path.name].update(
            visual_description="上海松江公寓房源页面，月租1500元起",
            visual_checked_at="2026-09-23T17:00:00+08:00",
            evidence_role="price_snapshot",
        )
        sources_path.write_text(json.dumps(sources, ensure_ascii=False), encoding="utf-8")

    result = validate_verified_hotspot_images(
        tmp_path, expected_topic="测试热点", require_visual_check=True
    )

    assert len(result.body_figures) == 2
    assert result.cover_source in [figure.path for figure in result.body_figures]


def _write_video_still_state(out_dir: Path) -> None:
    import hashlib
    out_dir.mkdir(parents=True, exist_ok=True)
    video = out_dir / 'report.mp4'
    video.write_bytes(b'locally-verified-test-video')
    image = _write_verified_image(out_dir, 'still-01.jpg', source_type='news_video_still')
    manifest = out_dir / 'figure_sources.json'
    data = json.loads(manifest.read_text())
    data[image.name].update(source_video=str(video), timecode_seconds=2,
                            sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                            visual_description='报道中的门店', visual_checked_at='2026-10-12', evidence_role='scene')
    manifest.write_text(json.dumps(data))
    (out_dir / 'video-research.json').write_text(json.dumps({
        'schema_version': 1, 'topic': '测试热点', 'completed_at': '2026-10-12',
        'viewed_range': '抽帧和所用图片已人工核对',
        'video': {'page_url': data[image.name]['page_url'], 'source_name': data[image.name]['source_name'],
                  'published_at': '2026-08-27', 'local_path': str(video),
                  'sha256': hashlib.sha256(video.read_bytes()).hexdigest(), 'duration_seconds': 10}}))


def test_verified_video_still_does_not_require_douyin(tmp_path: Path) -> None:
    _write_video_still_state(tmp_path)
    result = _load_api()(tmp_path, expected_topic='测试热点', require_visual_check=True)
    assert result.cover_source.name == 'still-01.jpg'
    assert len(result.body_figures) == 1


@pytest.mark.parametrize('corruption', ['video_hash', 'image_hash', 'timecode', 'topic'])
def test_video_still_provenance_corruption_is_rejected(tmp_path: Path, corruption: str) -> None:
    _write_video_still_state(tmp_path)
    if corruption == 'video_hash':
        (tmp_path / 'report.mp4').write_bytes(b'changed')
    elif corruption == 'topic':
        p=tmp_path / 'video-research.json'; data=json.loads(p.read_text()); data['topic']='other'; p.write_text(json.dumps(data))
    else:
        p=tmp_path / 'figure_sources.json'; data=json.loads(p.read_text())
        data['still-01.jpg']['sha256' if corruption == 'image_hash' else 'timecode_seconds'] = 'bad' if corruption == 'image_hash' else 12
        p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='视频|截图'):
        _load_api()(tmp_path, expected_topic='测试热点', require_visual_check=True)


def _write_report_image_state(out_dir: Path) -> None:
    import hashlib
    image = _write_verified_image(out_dir, 'manual-01.jpg', source_type='news_report_image')
    manifest = out_dir / 'figure_sources.json'
    data = json.loads(manifest.read_text())
    data[image.name].update(sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                            visual_description='校服款式设计示意图', visual_checked_at='2026-10-15', evidence_role='document')
    manifest.write_text(json.dumps(data))
    page = out_dir / 'source.html'
    page.write_text('<img src="https://example.com/image.jpg">')
    (out_dir / 'report-image-research.json').write_text(json.dumps({
        'schema_version': 1, 'topic': '测试热点', 'completed_at': '2026-10-15',
        'reviewed_scope': '已读原报道并实际查看所用设计图',
        'sources': [{'page_url': data[image.name]['page_url'], 'source_name': '浙江在线',
                     'published_at': '2026-08-27', 'local_page': str(page),
                     'sha256': hashlib.sha256(page.read_bytes()).hexdigest()}]}))


def test_verified_original_report_images_do_not_require_douyin(tmp_path: Path) -> None:
    _write_report_image_state(tmp_path)
    result = _load_api()(tmp_path, expected_topic='测试热点', require_visual_check=True)
    assert result.cover_source.name == 'manual-01.jpg'
    assert len(result.body_figures) == 1


@pytest.mark.parametrize('corruption', ['page_hash', 'image_hash', 'image_url', 'topic'])
def test_report_image_provenance_corruption_is_rejected(tmp_path: Path, corruption: str) -> None:
    _write_report_image_state(tmp_path)
    if corruption == 'page_hash':
        (tmp_path / 'source.html').write_text('changed')
    elif corruption == 'topic':
        path = tmp_path / 'report-image-research.json'
        data = json.loads(path.read_text()); data['topic'] = 'other'; path.write_text(json.dumps(data))
    else:
        path = tmp_path / 'figure_sources.json'
        data = json.loads(path.read_text())
        data['manual-01.jpg']['sha256' if corruption == 'image_hash' else 'image_url'] = 'bad'
        path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='原报道'):
        _load_api()(tmp_path, expected_topic='测试热点', require_visual_check=True)
