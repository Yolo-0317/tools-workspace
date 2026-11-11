"""用户主动热点深评的抖音优先与真实图片门禁。"""

from __future__ import annotations

import hashlib
import math
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

DOUYIN_RESEARCH_FILENAME = "douyin-search.json"
FIGURE_SOURCES_FILENAME = "figure_sources.json"
COVER_SOURCE_FILENAME = "cover_source.json"
_ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
_DISALLOWED_SOURCE_TYPES = {"generated", "original", "ai_generated"}


@dataclass(frozen=True)
class DouyinCandidate:
    account: str
    display_time: str
    video_url: str
    cover_url: str
    selected: bool = False


@dataclass(frozen=True)
class DouyinSearchRecord:
    topic: str
    query: str
    completed_at: str
    fallback_reason: str
    candidates: tuple[DouyinCandidate, ...]


@dataclass(frozen=True)
class VerifiedFigure:
    path: Path
    rel: str
    caption: str
    page_url: str
    source_name: str
    source_type: str


@dataclass(frozen=True)
class VerifiedHotspotImages:
    cover_source: Path
    body_figures: tuple[VerifiedFigure, ...]
    source_meta: dict[str, dict[str, str]]


def _read_json_object(path: Path, *, missing_message: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(missing_message)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} 不是有效 JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} 顶层必须是 JSON 对象")
    return payload


def _required_text(payload: dict[str, Any], field: str, *, owner: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{owner} 字段 {field} 必须是非空字符串")
    return value.strip()


def load_douyin_search(
    out_dir: Path,
    *,
    expected_topic: str,
) -> DouyinSearchRecord:
    payload = _read_json_object(
        Path(out_dir) / DOUYIN_RESEARCH_FILENAME,
        missing_message="用户主动热点必须先完成抖音搜索并保存 douyin-search.json",
    )
    if payload.get("schema_version") != 1:
        raise ValueError("抖音搜索状态 schema_version 必须为 1")
    topic = _required_text(payload, "topic", owner="抖音搜索状态")
    if topic != expected_topic.strip():
        raise ValueError("抖音搜索状态与热点主题不一致")
    query = _required_text(payload, "query", owner="抖音搜索状态")
    completed_at = _required_text(payload, "completed_at", owner="抖音搜索状态")
    fallback_reason = str(payload.get("fallback_reason") or "").strip()
    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        raise ValueError("抖音搜索状态 candidates 必须是数组")

    candidates: list[DouyinCandidate] = []
    for index, raw in enumerate(raw_candidates, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"抖音候选 {index} 必须是 JSON 对象")
        candidate = DouyinCandidate(
            account=_required_text(raw, "account", owner=f"抖音候选 {index}"),
            display_time=_required_text(
                raw, "display_time", owner=f"抖音候选 {index}"
            ),
            video_url=_required_text(raw, "video_url", owner=f"抖音候选 {index}"),
            cover_url=_required_text(raw, "cover_url", owner=f"抖音候选 {index}"),
            selected=raw.get("selected") is True,
        )
        if not candidate.video_url.startswith("https://www.douyin.com/"):
            raise ValueError(f"抖音候选 {index} 缺少稳定原视频链接")
        candidates.append(candidate)

    if not any(candidate.selected for candidate in candidates) and not fallback_reason:
        raise ValueError("抖音无可用候选时必须记录原因")
    return DouyinSearchRecord(
        topic=topic,
        query=query,
        completed_at=completed_at,
        fallback_reason=fallback_reason,
        candidates=tuple(candidates),
    )


def _verified(value: object) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _valid_image(path: Path) -> bool:
    if (
        not path.is_file()
        or path.suffix.lower() not in _ALLOWED_SUFFIXES
        or path.stat().st_size < 8000
    ):
        return False
    try:
        with Image.open(path) as image:
            width, height = image.size
            image.verify()
    except Exception:
        return False
    return width >= 300 and height >= 240


def _load_verified_figures(
    out_dir: Path,
) -> tuple[list[VerifiedFigure], dict[str, dict[str, str]]]:
    manifest = out_dir / FIGURE_SOURCES_FILENAME
    if not manifest.is_file():
        return [], {}
    payload = _read_json_object(
        manifest,
        missing_message="缺少图片来源清单 figure_sources.json",
    )
    figures: list[VerifiedFigure] = []
    normalized_meta: dict[str, dict[str, str]] = {}
    for filename in sorted(payload):
        raw = payload.get(filename)
        if not isinstance(raw, dict) or not _verified(raw.get("verified")):
            continue
        source_type = str(raw.get("source_type") or "").strip()
        if not source_type or source_type.lower() in _DISALLOWED_SOURCE_TYPES:
            continue
        page_url = str(raw.get("page_url") or "").strip()
        source_name = str(raw.get("source_name") or "").strip()
        published_at = str(raw.get("published_at") or "").strip()
        page_title = str(raw.get("page_title") or "").strip()
        caption = str(raw.get("caption") or "").strip()
        if not all((page_url.startswith(("http://", "https://")), source_name, published_at, page_title, caption)):
            continue
        path = out_dir / Path(filename).name
        if not _valid_image(path):
            continue
        meta = {
            "page_url": page_url,
            "source_name": source_name,
            "published_at": published_at,
            "source_type": source_type,
            "page_title": page_title,
            "caption": caption,
            "verified": "true",
            "visual_description": str(raw.get("visual_description") or "").strip(),
            "visual_checked_at": str(raw.get("visual_checked_at") or "").strip(),
            "evidence_role": str(raw.get("evidence_role") or "").strip(),
        }
        normalized_meta[path.name] = meta
        figures.append(
            VerifiedFigure(
                path=path,
                rel=f"discussion/{out_dir.name}/{path.name}",
                caption=caption,
                page_url=page_url,
                source_name=source_name,
                source_type=source_type,
            )
        )
    return figures, normalized_meta


def _load_cover_preferences(out_dir: Path) -> tuple[str, bool]:
    path = out_dir / COVER_SOURCE_FILENAME
    if not path.is_file():
        return "", False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "", False
    if not isinstance(payload, dict):
        return "", False
    requested = str(payload.get("source_filename") or "").strip()
    reuse_in_body = payload.get("reuse_in_body") is True
    return requested, reuse_in_body


def _validate_video_stills(root: Path, *, expected_topic: str, figures: list[VerifiedFigure]) -> None:
    record = _read_json_object(root / "video-research.json", missing_message="缺少真实视频取证记录")
    if record.get("schema_version") != 1 or record.get("topic") != expected_topic.strip():
        raise ValueError("视频取证版本或主题不一致")
    for key in ("completed_at", "viewed_range"):
        _required_text(record, key, owner="视频取证")
    video = record.get("video")
    if not isinstance(video, dict):
        raise ValueError("视频取证缺少原视频")
    for key in ("page_url", "source_name", "published_at", "local_path", "sha256"):
        _required_text(video, key, owner="视频取证")
    path = Path(video["local_path"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != video["sha256"]:
        raise ValueError("视频文件不存在或摘要不一致")
    duration = video.get("duration_seconds")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        raise ValueError("视频时长无效")
    manifest = _read_json_object(root / FIGURE_SOURCES_FILENAME, missing_message="缺少视频截图来源")
    for figure in figures:
        raw = manifest[figure.path.name]
        if (figure.source_type != "news_video_still" or figure.page_url != video["page_url"]
                or figure.source_name != video["source_name"] or raw.get("published_at") != video["published_at"]
                or Path(str(raw.get("source_video") or "")).resolve() != path.resolve()):
            raise ValueError("视频截图与原报道来源不一致")
        seconds = raw.get("timecode_seconds")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 <= seconds <= duration:
            raise ValueError("视频截图时间超出原视频")
        if hashlib.sha256(figure.path.read_bytes()).hexdigest() != raw.get("sha256"):
            raise ValueError("视频截图摘要不一致")
        for key in ("visual_description", "visual_checked_at", "evidence_role"):
            _required_text(raw, key, owner="视频截图")


def _validate_report_images(root: Path, *, expected_topic: str, figures: list[VerifiedFigure]) -> None:
    record = _read_json_object(root / "report-image-research.json", missing_message="缺少原报道配图取证记录")
    if record.get("schema_version") != 1 or record.get("topic") != expected_topic.strip():
        raise ValueError("原报道配图取证版本或主题不一致")
    for key in ("completed_at", "reviewed_scope"):
        _required_text(record, key, owner="原报道配图取证")
    sources = record.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("原报道配图缺少来源页面")
    pages = {}
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("原报道页面记录必须是对象")
        for key in ("page_url", "source_name", "published_at", "local_page", "sha256"):
            _required_text(source, key, owner="原报道页面")
        path = Path(source["local_page"])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("原报道页面不存在或摘要不一致")
        pages[source["page_url"]] = (source, path.read_text(encoding="utf-8"))
    manifest = _read_json_object(root / FIGURE_SOURCES_FILENAME, missing_message="缺少原报道图片来源")
    for figure in figures:
        source, html = pages.get(figure.page_url, ({}, ""))
        raw = manifest[figure.path.name]
        image_url = str(raw.get("image_url") or "")
        if (figure.source_type != "news_report_image" or figure.source_name != source.get("source_name")
                or raw.get("published_at") != source.get("published_at")
                or not image_url.startswith(("https://", "http://")) or image_url not in html):
            raise ValueError("原报道图片与来源页面不一致")
        if hashlib.sha256(figure.path.read_bytes()).hexdigest() != raw.get("sha256"):
            raise ValueError("原报道图片摘要不一致")
        for key in ("visual_description", "visual_checked_at", "evidence_role"):
            _required_text(raw, key, owner="原报道图片")


def validate_verified_hotspot_images(
    out_dir: Path,
    *,
    expected_topic: str,
    max_body: int = 3,
    require_visual_check: bool = False,
) -> VerifiedHotspotImages:
    if not 0 <= max_body <= 3:
        raise ValueError("热点正文真实图片数量必须为 0—3")
    root = Path(out_dir)
    figures, source_meta = _load_verified_figures(root)
    if (root / "video-research.json").is_file():
        _validate_video_stills(root, expected_topic=expected_topic, figures=figures)
        selected_urls: set[str] = set()
    elif (root / "report-image-research.json").is_file():
        _validate_report_images(root, expected_topic=expected_topic, figures=figures)
        selected_urls = set()
    else:
        search = load_douyin_search(root, expected_topic=expected_topic)
        selected_urls = {candidate.video_url for candidate in search.candidates if candidate.selected}
    figure_douyin_urls = {
        figure.page_url
        for figure in figures
        if figure.source_type == "douyin_cover"
    }
    if selected_urls - figure_douyin_urls:
        raise ValueError("所选抖音封面未写入 figure_sources")
    if not figures:
        raise ValueError("缺少可追溯封面")

    by_name = {figure.path.name: figure for figure in figures}
    requested, reuse_in_body = _load_cover_preferences(root)
    cover = by_name.get(requested)
    if cover is None and selected_urls:
        cover = next(
            (figure for figure in figures if figure.page_url in selected_urls),
            None,
        )
    if cover is None:
        cover = figures[0]
    if max_body > 0 and len(figures) <= max_body:
        body_candidates = figures
    else:
        body_candidates = (
            [cover, *(figure for figure in figures if figure.path != cover.path)]
            if reuse_in_body
            else [figure for figure in figures if figure.path != cover.path]
        )
    body = tuple(body_candidates[:max_body])
    if require_visual_check:
        for figure in (cover, *body):
            meta = source_meta[figure.path.name]
            if not all(
                meta.get(key)
                for key in ("visual_description", "visual_checked_at", "evidence_role")
            ):
                raise ValueError(f"图片 {figure.path.name} 缺少人工视觉核对记录")
    return VerifiedHotspotImages(
        cover_source=cover.path,
        body_figures=body,
        source_meta=source_meta,
    )
