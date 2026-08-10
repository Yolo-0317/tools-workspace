"""公众号贴图（图片消息 / newspic）草稿的可复用发布链路。"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import ROOT, add_permanent_image, draft_add, draft_update
from scripts.tools.wechat_mp_draft_slots import get_slot_media_id, set_slot_media_id

TZ = ZoneInfo("Asia/Shanghai")
IMAGE_CACHE_PATH = ROOT / "data" / "wechat_mp_newspic_image_cache.json"
MAX_IMAGES = 9
MAX_TITLE_CHARS = 64
MAX_CONTENT_CHARS = 1000
TARGET_CONTENT_MIN = 300
TARGET_CONTENT_MAX = 700
WATERMARK_FONT_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def validate_newspic_input(*, title: str, content: str, image_paths: Iterable[Path]) -> list[Path]:
    paths = [Path(path) for path in image_paths]
    if not title.strip() or len(title.strip()) > MAX_TITLE_CHARS:
        raise ValueError(f"贴图标题须为 1-{MAX_TITLE_CHARS} 字")
    if not content.strip() or len(content.strip()) > MAX_CONTENT_CHARS:
        raise ValueError(f"贴图说明须为 1-{MAX_CONTENT_CHARS} 字")
    if not 1 <= len(paths) <= MAX_IMAGES:
        raise ValueError(f"贴图须有 1-{MAX_IMAGES} 张图片")
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"贴图图片不存在: {', '.join(missing)}")
    return paths


def validate_newspic_image_sources(*, image_paths: Iterable[Path], sources_path: Path) -> None:
    """要求每张贴图保留报道图或原创补位的来源记录。"""
    try:
        sources = json.loads(Path(sources_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"贴图来源清单无效: {sources_path}") from exc
    if not isinstance(sources, dict):
        raise ValueError("贴图来源清单必须是 JSON 对象")
    for image_path in image_paths:
        source = sources.get(image_path.name)
        if not isinstance(source, dict):
            raise ValueError(f"图片缺少来源记录: {image_path.name}")
        source_type = str(source.get("source_type") or "").strip()
        page_url = str(source.get("page_url") or "").strip()
        if source_type == "report" and page_url.startswith(("http://", "https://")):
            continue
        if source_type == "original" and str(source.get("fallback_reason") or "").strip():
            continue
        raise ValueError(f"图片来源记录不完整: {image_path.name}")


def build_newspic_article(*, title: str, content: str, image_media_ids: Iterable[str], author: str = "") -> dict[str, Any]:
    media_ids = [str(media_id).strip() for media_id in image_media_ids if str(media_id).strip()]
    normalized_title = title.strip()
    normalized_content = content.strip()
    if not normalized_title or len(normalized_title) > MAX_TITLE_CHARS:
        raise ValueError(f"贴图标题须为 1-{MAX_TITLE_CHARS} 字")
    if not normalized_content or len(normalized_content) > MAX_CONTENT_CHARS:
        raise ValueError(f"贴图说明须为 1-{MAX_CONTENT_CHARS} 字")
    if not 1 <= len(media_ids) <= MAX_IMAGES:
        raise ValueError(f"贴图须有 1-{MAX_IMAGES} 张图片")
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


def prepare_newspic_images(*, image_paths: Iterable[Path], watermark: str, output_dir: Path) -> list[Path]:
    paths = [Path(path) for path in image_paths]
    if not watermark.strip():
        return paths
    prepared_paths: list[Path] = []
    for image_path in paths:
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
) -> tuple[str, str]:
    paths = validate_newspic_input(title=title, content=content, image_paths=image_paths)
    if image_sources_path is not None:
        validate_newspic_image_sources(image_paths=paths, sources_path=image_sources_path)
    with tempfile.TemporaryDirectory(prefix="wechat-mp-newspic-") as temp_dir:
        upload_paths = prepare_newspic_images(image_paths=paths, watermark=watermark, output_dir=Path(temp_dir))
        image_media_ids = upload_newspic_images(upload_paths, force_reupload=force_reupload)
    article = build_newspic_article(title=title, content=content, image_media_ids=image_media_ids, author=author)
    old_id = get_slot_media_id(slot_key)
    if old_id:
        error = draft_update(media_id=old_id, article=article)
        if not error:
            set_slot_media_id(slot_key, old_id, title=title)
            return old_id, "updated"
    media_id, error = draft_add(articles=[article])
    if error or not media_id:
        raise RuntimeError(f"贴图草稿创建失败: {error}")
    set_slot_media_id(slot_key, media_id, title=title)
    return media_id, "created"
