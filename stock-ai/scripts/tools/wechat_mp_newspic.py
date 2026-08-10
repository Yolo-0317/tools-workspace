"""公众号贴图（图片消息 / newspic）草稿的可复用发布链路。"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import (
    ROOT,
    add_permanent_image,
    draft_add,
    draft_update,
    fetch_draft_news_item,
)
from scripts.tools.wechat_mp_draft_slots import get_slot_media_id, set_slot_media_id
from scripts.tools.wechat_mp_virtual_film import FILM_LANES, FILM_RULES

TZ = ZoneInfo("Asia/Shanghai")
IMAGE_CACHE_PATH = ROOT / "data" / "wechat_mp_newspic_image_cache.json"
MAX_IMAGES = 9
MIN_IMAGES = 6
MIN_TITLE_CHARS = 8
MAX_TITLE_CHARS = 20
SIX_IMAGE_CONTENT_RANGE = (600, 800)
MULTI_IMAGE_CONTENT_RANGE = (800, 1000)
VIRTUAL_MIN_IMAGES = 2
VIRTUAL_MAX_IMAGES = 6
VIRTUAL_MAX_TITLE_CHARS = 32
VIRTUAL_CONTENT_RANGES = {
    2: (150, 300),
    3: (150, 500),
    4: (300, 500),
    5: (600, 800),
    6: (600, 800),
}
WATERMARK_FONT_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _is_virtual_lifestyle(draft_profile: str) -> bool:
    return draft_profile.strip() == "virtual_lifestyle"


def _validate_newspic_text(
    *,
    title: str,
    content: str,
    image_count: int,
    draft_profile: str = "newspic",
    content_lane: str = "",
) -> None:
    normalized_title = title.strip()
    normalized_content = content.strip()
    max_title_chars = (
        VIRTUAL_MAX_TITLE_CHARS
        if _is_virtual_lifestyle(draft_profile)
        else MAX_TITLE_CHARS
    )
    if not MIN_TITLE_CHARS <= len(normalized_title) <= max_title_chars:
        raise ValueError(
            f"贴图标题须为 {MIN_TITLE_CHARS}-{max_title_chars} 字"
        )
    if _is_virtual_lifestyle(draft_profile) and content_lane in FILM_RULES:
        minimum_images, maximum_images = FILM_RULES[content_lane]["images"]
        if not minimum_images <= image_count <= maximum_images:
            raise ValueError(
                f"{content_lane} 须使用 {minimum_images}-{maximum_images} 张图片"
            )
        content_min, content_max = FILM_RULES[content_lane]["copy"]
    elif _is_virtual_lifestyle(draft_profile):
        if not VIRTUAL_MIN_IMAGES <= image_count <= VIRTUAL_MAX_IMAGES:
            raise ValueError(
                f"栀夏贴图须有 {VIRTUAL_MIN_IMAGES}-{VIRTUAL_MAX_IMAGES} 张图片"
            )
        content_min, content_max = VIRTUAL_CONTENT_RANGES[image_count]
    else:
        if not MIN_IMAGES <= image_count <= MAX_IMAGES:
            raise ValueError(f"贴图须有 {MIN_IMAGES}-{MAX_IMAGES} 张图片")
        content_min, content_max = (
            SIX_IMAGE_CONTENT_RANGE if image_count == 6 else MULTI_IMAGE_CONTENT_RANGE
        )
    if not content_min <= len(normalized_content) <= content_max:
        raise ValueError(f"{image_count} 图贴图说明须为 {content_min}-{content_max} 字")


def validate_newspic_input(
    *,
    title: str,
    content: str,
    image_paths: Iterable[Path],
    draft_profile: str = "newspic",
    content_lane: str = "",
) -> list[Path]:
    paths = [Path(path) for path in image_paths]
    _validate_newspic_text(
        title=title,
        content=content,
        image_count=len(paths),
        draft_profile=draft_profile,
        content_lane=content_lane,
    )
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"贴图图片不存在: {', '.join(missing)}")
    return paths


def validate_newspic_image_sources(
    *,
    image_paths: Iterable[Path],
    sources_path: Path,
    content: str | None = None,
    draft_profile: str = "newspic",
    content_type: str = "",
    content_lane: str = "",
    character_image_policy: str = "default_one",
    visual_exception: str = "",
) -> dict[str, dict[str, Any]]:
    """要求每张贴图保留报道图或原创补位的来源记录。"""
    sources = load_newspic_image_sources(sources_path)
    has_original = False
    has_virtual_character = False
    virtual_character_count = 0
    virtual_topic_count = 0
    for image_path in image_paths:
        source = sources.get(image_path.name)
        if not isinstance(source, dict):
            raise ValueError(f"图片缺少来源记录: {image_path.name}")
        source_type = str(source.get("source_type") or "").strip()
        page_url = str(source.get("page_url") or "").strip()
        page_title = str(source.get("page_title") or "").strip()
        if _is_virtual_lifestyle(draft_profile):
            visual_role = str(source.get("visual_role") or "").strip()
            position_role = str(source.get("position_role") or "").strip()
            allow_watermark = source.get("allow_zhixia_watermark")
            if visual_role not in {"character", "topic"}:
                raise ValueError(
                    f"栀夏贴图须标注 visual_role=character/topic: {image_path.name}"
                )
            if position_role not in {"hook", "evidence", "author"}:
                raise ValueError(
                    f"栀夏贴图须标注 position_role=hook/evidence/author: {image_path.name}"
                )
            if not isinstance(allow_watermark, bool):
                raise ValueError(
                    f"栀夏贴图须标注布尔值 allow_zhixia_watermark: {image_path.name}"
                )
            if visual_role == "character":
                capture_mode = str(source.get("capture_mode") or "").strip()
                if capture_mode not in {
                    "mirror_selfie",
                    "handheld_selfie",
                    "timer",
                    "author_card",
                }:
                    raise ValueError(
                        f"栀夏角色图须标注有效 capture_mode: {image_path.name}"
                    )
                has_virtual_character = True
                virtual_character_count += 1
            else:
                virtual_topic_count += 1
            if source_type == "report" and allow_watermark:
                raise ValueError(f"报道图不得添加栀夏水印: {image_path.name}")
            if source_type in {"film_official", "film_media"}:
                if allow_watermark:
                    raise ValueError(f"影视图不得添加栀夏水印: {image_path.name}")
                film_title = str(source.get("film_title") or "").strip()
                source_name = str(source.get("source_name") or "").strip()
                if (
                    not film_title
                    or not source_name
                    or not page_url.startswith("https://")
                    or not page_title
                ):
                    raise ValueError(
                        "影视图来源记录须包含 film_title、source_name、"
                        f"page_title 与 HTTPS page_url: {image_path.name}"
                    )
                continue
        if (
            source_type == "report"
            and page_url.startswith(("http://", "https://"))
            and page_title
            and (
                not _is_virtual_lifestyle(draft_profile)
                or str(source.get("source_name") or "").strip()
            )
        ):
            continue
        if source_type == "original" and str(source.get("fallback_reason") or "").strip():
            has_original = True
            continue
        raise ValueError(f"图片来源记录不完整: {image_path.name}")
    if _is_virtual_lifestyle(draft_profile) and character_image_policy == "optional_one":
        if content_lane not in FILM_LANES:
            raise ValueError("optional_one 角色图片策略只适用于影视内容")
        if virtual_character_count > 1 or virtual_topic_count < 1:
            raise ValueError("影视贴图须有主题图，栀夏角色图最多一张")
    elif _is_virtual_lifestyle(draft_profile) and not has_virtual_character:
        raise ValueError("栀夏贴图须至少一张栀夏角色图")
    if _is_virtual_lifestyle(draft_profile) and content_type in {"A", "A+C", "C"}:
        if character_image_policy == "default_one":
            if virtual_character_count != 1 or virtual_topic_count < 1:
                raise ValueError("观点型栀夏贴图默认须恰好一张角色图并至少一张主题图")
        elif character_image_policy == "story_multiple":
            if not 2 <= virtual_character_count <= 4 or not visual_exception.strip():
                raise ValueError("多角色图例外须有 2-4 张角色图并填写 visual_exception")
        elif character_image_policy == "optional_one":
            if content_lane not in FILM_LANES:
                raise ValueError("optional_one 角色图片策略只适用于影视内容")
        else:
            raise ValueError("未知的栀夏角色图片策略")
    if has_original and content is not None:
        if _is_virtual_lifestyle(draft_profile):
            if "AI 虚拟角色" not in content or "AI 生成示意图" not in content:
                raise ValueError(
                    "栀夏贴图正文须同时标注“AI 虚拟角色 / AI 生成示意图”"
                )
        elif "原创新闻插画" not in content:
            raise ValueError("贴图包含原创补图时，正文须标注“原创新闻插画”")
    return sources


def load_newspic_image_sources(sources_path: Path) -> dict[str, dict[str, Any]]:
    try:
        sources = json.loads(Path(sources_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"贴图来源清单无效: {sources_path}") from exc
    if not isinstance(sources, dict):
        raise ValueError("贴图来源清单必须是 JSON 对象")
    return {
        str(name): dict(source)
        for name, source in sources.items()
        if isinstance(source, dict)
    }


def build_newspic_article(
    *,
    title: str,
    content: str,
    image_media_ids: Iterable[str],
    author: str = "",
    draft_profile: str = "newspic",
    content_lane: str = "",
) -> dict[str, Any]:
    media_ids = [str(media_id).strip() for media_id in image_media_ids if str(media_id).strip()]
    normalized_title = title.strip()
    normalized_content = content.strip()
    _validate_newspic_text(
        title=normalized_title,
        content=normalized_content,
        image_count=len(media_ids),
        draft_profile=draft_profile,
        content_lane=content_lane,
    )
    article: dict[str, Any] = {
        "article_type": "newspic",
        "title": normalized_title,
        "content": normalized_content,
        "need_open_comment": 1,
        "only_fans_can_comment": 0,
        "image_info": {"image_list": [{"image_media_id": media_id} for media_id in media_ids]},
    }
    if author.strip():
        article["author"] = author.strip()
    return article


def verify_newspic_draft(
    *,
    media_id: str,
    expected_title: str,
    expected_content: str,
    expected_image_count: int,
) -> None:
    item, error = fetch_draft_news_item(media_id=media_id)
    if error or item is None:
        raise RuntimeError(f"贴图草稿回读失败: {error}")
    if str(item.get("article_type") or "") != "newspic":
        raise RuntimeError("贴图草稿回读稿型不符")
    if str(item.get("title") or "").strip() != expected_title.strip():
        raise RuntimeError("贴图草稿回读标题不符")
    remote_content = str(item.get("content") or "").strip()
    if len(remote_content) != len(expected_content.strip()):
        raise RuntimeError("贴图草稿回读正文长度不符")
    image_list = (item.get("image_info") or {}).get("image_list") or []
    if len(image_list) != expected_image_count:
        raise RuntimeError("贴图草稿回读图片数量不符")


def _load_image_cache() -> dict[str, Any]:
    if not IMAGE_CACHE_PATH.is_file():
        return {}
    try:
        return json.loads(IMAGE_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_image_cache(cache: dict[str, Any]) -> None:
    IMAGE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    IMAGE_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def upload_newspic_images(image_paths: Iterable[Path], *, force_reupload: bool = False) -> list[str]:
    paths = [Path(path) for path in image_paths]
    cache = _load_image_cache()
    media_ids: list[str] = []
    dirty = False
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        cached = cache.get(digest) or {}
        media_id = "" if force_reupload else str(cached.get("media_id") or "")
        if not media_id:
            media_id, error = add_permanent_image(path)
            if error or not media_id:
                raise RuntimeError(f"贴图素材上传失败 {path}: {error}")
            cache[digest] = {
                "media_id": media_id,
                "source": str(path),
                "updated_at": datetime.now(TZ).isoformat(timespec="seconds"),
            }
            dirty = True
        media_ids.append(media_id)
    if dirty:
        _save_image_cache(cache)
    return media_ids


def _watermark_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in WATERMARK_FONT_CANDIDATES:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, font_size)
    return ImageFont.load_default()


def add_image_watermark(*, image_path: Path, output_path: Path, text: str) -> None:
    """写入右下角署名，不修改原始素材。"""
    with Image.open(image_path) as source:
        image = source.convert("RGBA")
    width, height = image.size
    font = _watermark_font(max(20, round(min(width, height) * 0.028)))
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font, stroke_width=1)
    text_width, text_height = right - left, bottom - top
    margin = max(20, round(min(width, height) * 0.035))
    position = (width - text_width - margin, height - text_height - margin)
    draw.text(position, text, font=font, fill=(255, 255, 255, 185), stroke_width=1, stroke_fill=(0, 0, 0, 135))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output_path, quality=95)


def prepare_newspic_images(
    *,
    image_paths: Iterable[Path],
    watermark: str,
    output_dir: Path,
    image_sources: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[Path]:
    paths = [Path(path) for path in image_paths]
    if not watermark.strip():
        return paths
    prepared_paths: list[Path] = []
    for image_path in paths:
        source = (image_sources or {}).get(image_path.name)
        if source is not None and not bool(source.get("allow_zhixia_watermark")):
            prepared_paths.append(image_path)
            continue
        prepared_path = output_dir / image_path.name
        add_image_watermark(image_path=image_path, output_path=prepared_path, text=watermark.strip())
        prepared_paths.append(prepared_path)
    return prepared_paths


def upsert_newspic_draft(
    *,
    slot_key: str,
    title: str,
    content: str,
    image_paths: Iterable[Path],
    image_sources_path: Path | None = None,
    author: str = "",
    force_reupload: bool = False,
    watermark: str = "",
    content_type: str = "",
    content_lane: str = "",
    character_image_policy: str = "default_one",
    visual_exception: str = "",
) -> tuple[str, str]:
    paths = validate_newspic_input(
        title=title,
        content=content,
        image_paths=image_paths,
        draft_profile=slot_key,
        content_lane=content_lane,
    )
    image_sources: dict[str, dict[str, Any]] = {}
    if image_sources_path is not None:
        image_sources = validate_newspic_image_sources(
            image_paths=paths,
            sources_path=image_sources_path,
            content=content,
            draft_profile=slot_key,
            content_type=content_type,
            content_lane=content_lane,
            character_image_policy=character_image_policy,
            visual_exception=visual_exception,
        )
    with tempfile.TemporaryDirectory(prefix="wechat-mp-newspic-") as temp_dir:
        upload_paths = prepare_newspic_images(
            image_paths=paths,
            image_sources=image_sources or None,
            watermark=watermark,
            output_dir=Path(temp_dir),
        )
        image_media_ids = upload_newspic_images(upload_paths, force_reupload=force_reupload)
    article = build_newspic_article(
        title=title,
        content=content,
        image_media_ids=image_media_ids,
        author=author,
        draft_profile=slot_key,
        content_lane=content_lane,
    )
    old_id = get_slot_media_id(slot_key)
    if old_id:
        error = draft_update(media_id=old_id, article=article)
        if not error:
            verify_newspic_draft(
                media_id=old_id,
                expected_title=title,
                expected_content=content,
                expected_image_count=len(paths),
            )
            set_slot_media_id(slot_key, old_id, title=title)
            return old_id, "updated"
    media_id, error = draft_add(articles=[article])
    if error or not media_id:
        raise RuntimeError(f"贴图草稿创建失败: {error}")
    verify_newspic_draft(
        media_id=media_id,
        expected_title=title,
        expected_content=content,
        expected_image_count=len(paths),
    )
    set_slot_media_id(slot_key, media_id, title=title)
    return media_id, "created"
