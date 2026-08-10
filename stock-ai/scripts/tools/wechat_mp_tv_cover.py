#!/usr/bin/env python3
"""影视试跑封面：本地原创 HBO 霓虹风（无剧照/无官方 Logo，降低版权风险）。"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import requests

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
COVER_DIR = ROOT / "assets" / "wechat_mp" / "cover-tv"
COVER_CACHE = ROOT / "data" / "wechat_mp_thumb_tv_review.json"
DISCUSSION_COVER_CACHE = ROOT / "data" / "wechat_mp_thumb_discussion.json"

# 公众号首图常用 2.35:1
COVER_W, COVER_H = 900, 383

_SLUG_FILES: dict[str, str] = {
    "euphoria": "euphoria-hbo-neon.jpg",
}


def cover_path_for_slug(slug: str) -> Path:
    name = _SLUG_FILES.get(slug) or f"{slug}.jpg"
    return COVER_DIR / name


def generate_tmdb_poster_cover(
    path: Path,
    poster_file: str,
    *,
    size: str = "w780",
) -> Path:
    """公众号首图：官方竖版海报裁切为 2.35:1，保留海报原有标题。"""
    from PIL import Image

    from scripts.tools.wechat_mp_douban_stills import download_tmdb_image

    path.parent.mkdir(parents=True, exist_ok=True)
    src_path = path.parent / "_poster_src.jpg"
    download_tmdb_image(poster_file, src_path, size=size)
    src = Image.open(src_path).convert("RGB")
    sw, sh = src.size
    target_ratio = COVER_W / COVER_H
    crop_h = int(sw / target_ratio)
    top = max(0, int(sh * 0.06))
    if top + crop_h > sh:
        top = max(0, sh - crop_h)
    img = src.crop((0, top, sw, min(sh, top + crop_h))).resize(
        (COVER_W, COVER_H), Image.Resampling.LANCZOS
    )
    img.save(path, format="JPEG", quality=93, optimize=True)
    src_path.unlink(missing_ok=True)
    return path


def generate_tmdb_backdrop_cover(
    path: Path,
    backdrop_file: str,
    *,
    title_zh: str,
    title_en: str = "",
    platform: str = "Netflix",
    accent: tuple[int, int, int] = (229, 45, 55),
) -> Path:
    """通用影视封面：TMDB backdrop + 剧评叠字。"""
    from PIL import Image, ImageDraw, ImageFont

    from scripts.tools.wechat_mp_douban_stills import download_tmdb_image

    path.parent.mkdir(parents=True, exist_ok=True)
    src_path = path.parent / "_cover_src.jpg"
    download_tmdb_image(backdrop_file, src_path, size="w1280")

    src = Image.open(src_path).convert("RGB")
    sw, sh = src.size
    target_ratio = COVER_W / COVER_H
    src_ratio = sw / sh
    if src_ratio > target_ratio:
        new_w = int(sh * target_ratio)
        left = (sw - new_w) // 2
        src = src.crop((left, 0, left + new_w, sh))
    else:
        new_h = int(sw / target_ratio)
        top = max(0, (sh - new_h) // 4)
        src = src.crop((0, top, sw, top + new_h))

    img = src.resize((COVER_W, COVER_H), Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", (COVER_W, COVER_H), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for y in range(COVER_H // 3, COVER_H):
        t = (y - COVER_H // 3) / max(COVER_H - COVER_H // 3, 1)
        odraw.line((0, y, COVER_W, y), fill=(0, 0, 0, int(210 * t)))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    draw.rectangle((0, COVER_H - 5, COVER_W, COVER_H), fill=accent)
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 42)
        sub_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 20)
        badge_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 16)
    except OSError:
        title_font = ImageFont.load_default()
        sub_font = title_font
        badge_font = title_font

    draw.text((44, COVER_H - 148), (title_zh or "")[:14], fill=(255, 252, 252), font=title_font)
    if title_en:
        draw.text((44, COVER_H - 92), title_en[:36], fill=(235, 210, 214), font=sub_font)
    draw.text((44, COVER_H - 56), f"{platform} · 剧评", fill=accent, font=sub_font)
    draw.text((44, 28), "剧评引用 · TMDB 宣传剧照", fill=(220, 220, 225), font=badge_font)
    img.save(path, format="JPEG", quality=93, optimize=True)
    src_path.unlink(missing_ok=True)
    return path


def generate_teach_you_a_lesson_cover(path: Path | None = None) -> Path:
    """Netflix《铁拳教育》封面。"""
    return generate_tmdb_backdrop_cover(
        path or cover_path_for_slug("teach-you-a-lesson"),
        "vyG93jhmPL7tBIhRtCLa5mdBKob.jpg",
        title_zh="铁拳教育",
        title_en="Teach You a Lesson",
        platform="Netflix",
    )


def generate_tv_scene_card(
    path: Path,
    *,
    headline: str,
    show_title: str = "",
    palette: tuple[tuple[int, int, int], tuple[int, int, int]] | None = None,
) -> Path:
    """剧评场景卡：渐变横幅 + 桥段描述（非剧照截图）。"""
    from PIL import Image, ImageDraw, ImageFont

    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = 900, 360
    c0, c1 = palette or ((26, 39, 68), (74, 32, 48))
    img = Image.new("RGB", (w, h), c0)
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(c0[0] + (c1[0] - c0[0]) * t)
        g = int(c0[1] + (c1[1] - c0[1]) * t)
        b = int(c0[2] + (c1[2] - c0[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    draw = ImageDraw.Draw(img)
    draw.line((36, h - 8, w - 36, h - 8), fill=(229, 45, 55), width=3)
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 24)
        head_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 30)
    except OSError:
        title_font = ImageFont.load_default()
        head_font = title_font
    if show_title:
        draw.text((40, 36), show_title, fill=(200, 210, 230), font=title_font)
    # 简单换行
    lines: list[str] = []
    buf = ""
    for ch in headline:
        buf += ch
        if len(buf) >= 16:
            lines.append(buf)
            buf = ""
    if buf:
        lines.append(buf)
    y0 = 110 if show_title else 80
    for i, line in enumerate(lines[:3]):
        draw.text((40, y0 + i * 44), line, fill=(248, 250, 252), font=head_font)
    img.save(path, format="JPEG", quality=90, optimize=True)
    return path


def generate_euphoria_cover(path: Path | None = None) -> Path:
    """原创紫粉霓虹封面，致敬《亢奋》色调，不含演员剧照与 HBO 官方 Logo。"""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    out = path or cover_path_for_slug("euphoria")
    out.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (COVER_W, COVER_H), (12, 8, 28))
    px = img.load()
    for y in range(COVER_H):
        t = y / max(COVER_H - 1, 1)
        r = int(18 + 40 * t)
        g = int(6 + 12 * t)
        b = int(36 + 70 * t)
        for x in range(COVER_W):
            px[x, y] = (r, g, b)

    overlay = Image.new("RGBA", (COVER_W, COVER_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for cx, color, w in (
        (220, (255, 45, 120, 90), 260),
        (520, (120, 210, 255, 70), 220),
        (720, (180, 80, 255, 55), 180),
    ):
        draw.ellipse(
            (cx - w, 40 - w // 2, cx + w, COVER_H - 40 + w // 2),
            fill=color,
        )
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=38))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    draw.line((0, COVER_H - 2, COVER_W, COVER_H - 2), fill=(255, 80, 150), width=2)

    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 52)
        sub_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
        badge_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 18)
    except OSError:
        title_font = ImageFont.load_default()
        sub_font = title_font
        badge_font = title_font

    draw.text((48, 118), "EUPHORIA", fill=(245, 230, 255), font=title_font)
    draw.text((48, 188), "亢奋 · 第三季", fill=(200, 180, 230), font=sub_font)
    draw.text((48, 228), "HBO 青春剧 · 剧评", fill=(255, 120, 180), font=badge_font)
    draw.text(
        (48, 318),
        "原创封面 · 无官方剧照",
        fill=(140, 130, 170),
        font=badge_font,
    )

    img.save(out, format="JPEG", quality=92, optimize=True)
    return out


def generate_generic_tv_cover(
    path: Path,
    *,
    title_zh: str,
    platform: str = "",
    accent: tuple[int, int, int] = (180, 60, 90),
) -> Path:
    """无剧照时的纯色叠字封面（国产剧/热搜片）。"""
    from PIL import Image, ImageDraw, ImageFont

    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (COVER_W, COVER_H), (18, 16, 28))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, COVER_H - 4, COVER_W, COVER_H), fill=accent)
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 46)
        sub_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 22)
    except OSError:
        title_font = ImageFont.load_default()
        sub_font = title_font
    label = (title_zh or "剧评")[:10]
    draw.text((48, 120), f"《{label}》", fill=(245, 238, 250), font=title_font)
    if platform:
        draw.text((48, 200), f"{platform} · 剧评", fill=(200, 180, 210), font=sub_font)
    draw.text((48, 300), "原创封面 · 无官方剧照", fill=(130, 120, 150), font=sub_font)
    img.save(path, format="JPEG", quality=92, optimize=True)
    return path


def ensure_tv_cover_from_douban(slug: str, subject_id: str) -> Path:
    """从豆瓣条目海报生成公众号封面。"""
    inline = ROOT / "assets" / "wechat_mp" / "inline-tv" / slug
    inline.mkdir(parents=True, exist_ok=True)
    poster_path = inline / "poster.jpg"
    if not poster_path.is_file() or poster_path.stat().st_size < 5000:
        from scripts.tools.wechat_mp_douban_stills import DOUBAN_HEADERS

        url = f"https://movie.douban.com/subject/{subject_id}/"
        resp = requests.get(url, headers=DOUBAN_HEADERS, timeout=25)
        resp.raise_for_status()
        m = re.search(r'property="v:image"\s+content="([^"]+)"', resp.text)
        if not m:
            m = re.search(r'<img[^>]+src="(https://img[^"]+doubanio.com/view/photo[^"]+)"', resp.text)
        if not m:
            raise FileNotFoundError(f"豆瓣条目无海报: subject={subject_id}")
        img_url = m.group(1).replace("/s_ratio_poster/", "/l_ratio_poster/")
        img_resp = requests.get(img_url, headers=DOUBAN_HEADERS, timeout=60)
        img_resp.raise_for_status()
        poster_path.write_bytes(img_resp.content)
    path = cover_path_for_slug(slug)
    from PIL import Image

    src = Image.open(poster_path).convert("RGB")
    sw, sh = src.size
    target_ratio = COVER_W / COVER_H
    crop_h = int(sw / target_ratio)
    top = max(0, int(sh * 0.05))
    if top + crop_h > sh:
        top = max(0, sh - crop_h)
    img = src.crop((0, top, sw, min(sh, top + crop_h))).resize(
        (COVER_W, COVER_H), Image.Resampling.LANCZOS
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="JPEG", quality=93, optimize=True)
    img.save(inline / "cover.jpg", format="JPEG", quality=93, optimize=True)
    return path


def ensure_tv_cover(slug: str, *, topic: dict[str, Any] | None = None) -> Path:
    path = cover_path_for_slug(slug)
    if slug == "michael-jackson-the-verdict":
        from scripts.tools.wechat_mp_douban_stills import download_tmdb_image

        poster = "8R40yI5AJ931Hd3P4Yf8pdFgwJ1.jpg"
        inline = ROOT / "assets" / "wechat_mp" / "inline-tv" / slug
        inline.mkdir(parents=True, exist_ok=True)
        download_tmdb_image(poster, inline / "poster.jpg", size="w780")
        generate_tmdb_poster_cover(inline / "cover.jpg", poster)
        generate_tmdb_poster_cover(path, poster)
        return path
    if slug == "teach-you-a-lesson":
        generate_teach_you_a_lesson_cover(path)
        inline_cover = ROOT / "assets" / "wechat_mp" / "inline-tv" / slug / "cover.jpg"
        generate_teach_you_a_lesson_cover(inline_cover)
        return path
    movie_id = int((topic or {}).get("tmdb_movie_id") or 0)
    if slug == "spider-man-brand-new-day" or movie_id:
        from scripts.tools.wechat_mp_douban_stills import ensure_tmdb_movie_stills

        spec = {"tmdb_id": movie_id or 969681, "files": {}}
        ensure_tmdb_movie_stills(topic or {}, spec)
        inline_cover = ROOT / "assets" / "wechat_mp" / "inline-tv" / slug / "cover.jpg"
        if inline_cover.is_file() and inline_cover.stat().st_size > 15000:
            return inline_cover
        if path.is_file() and path.stat().st_size > 15000:
            return path
    if not path.is_file() or path.stat().st_size < 15000:
        if slug == "euphoria":
            generate_euphoria_cover(path)
        elif topic:
            zh = str(topic.get("title_zh") or "").strip()
            plat = str(topic.get("platform") or "剧评").strip()
            if zh:
                generate_generic_tv_cover(path, title_zh=zh, platform=plat)
                inline = ROOT / "assets" / "wechat_mp" / "inline-tv" / slug
                inline.mkdir(parents=True, exist_ok=True)
                generate_generic_tv_cover(inline / "cover.jpg", title_zh=zh, platform=plat)
            elif str(topic.get("douban_subject_id") or "").strip():
                try:
                    ensure_tv_cover_from_douban(slug, str(topic["douban_subject_id"]).strip())
                except Exception:
                    generate_generic_tv_cover(path, title_zh=slug.replace("-", " "), platform=plat)
            else:
                label = zh or slug.replace("-", " ") or "话题"
                generate_generic_tv_cover(path, title_zh=label, platform=plat or "话题")
                inline = ROOT / "assets" / "wechat_mp" / "inline-tv" / slug
                inline.mkdir(parents=True, exist_ok=True)
                generate_generic_tv_cover(inline / "cover.jpg", title_zh=label, platform=plat or "话题")
        else:
            label = slug.replace("-", " ") or "话题"
            generate_generic_tv_cover(path, title_zh=label, platform="话题")
    return path


def resolve_tv_cover_slug(topic: dict[str, Any] | None = None) -> str:
    if topic:
        slug = str(topic.get("cover_slug") or "").strip().lower()
        if slug:
            return slug
        en = str(topic.get("title_en") or "").strip().lower()
        if en:
            return en.replace(" ", "_").replace("&", "and")
    return "euphoria"


def pick_tv_review_thumb(
    topic: dict[str, Any] | None = None,
    *,
    force_reupload: bool = False,
) -> tuple[str | None, dict[str, Any] | None]:
    from scripts.tools.wechat_mp_client import add_permanent_image

    slug = resolve_tv_cover_slug(topic)
    inline_tv = ROOT / "assets" / "wechat_mp" / "inline-tv"
    cover_candidates = [
        inline_tv / slug / "cover.jpg",
        cover_path_for_slug(slug),
        inline_tv / slug / "douban-still-01.jpg",
    ]
    path: Path | None = None
    for cand in cover_candidates:
        if cand.is_file() and cand.stat().st_size > 15000:
            path = cand
            break
    if path is None or (path.is_file() and path.stat().st_size < 15000):
        path = ensure_tv_cover(slug, topic=topic)
    cache_key = hashlib.md5(path.read_bytes()).hexdigest()[:16]

    if not force_reupload and COVER_CACHE.is_file():
        try:
            import json

            cached = json.loads(COVER_CACHE.read_text(encoding="utf-8"))
            if (
                cached.get("slug") == slug
                and cached.get("cache_key") == cache_key
                and cached.get("media_id")
            ):
                return str(cached["media_id"]), None
        except Exception:
            pass

    media_id, err = add_permanent_image(path)
    if err or not media_id:
        return None, err or {"errcode": -1, "errmsg": f"上传影视封面失败: {path}"}

    import json
    from datetime import datetime
    from zoneinfo import ZoneInfo

    COVER_CACHE.parent.mkdir(parents=True, exist_ok=True)
    COVER_CACHE.write_text(
        json.dumps(
            {
                "slug": slug,
                "media_id": media_id,
                "cache_key": cache_key,
                "source": str(path),
                "updated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return media_id, None


def is_discussion_topic(topic: dict[str, Any] | None) -> bool:
    """社会话题讨论稿：封面须用同题报道事件图，禁止牛马/行情默认图。"""
    if not topic:
        return False
    if str(topic.get("content_mode") or "").strip().lower() == "discussion":
        return True
    if topic.get("from_discussion_trend"):
        return True
    if str(topic.get("type") or "").strip().lower() == "discussion":
        return True
    plat = str(topic.get("platform") or "").strip()
    if plat == "话题":
        return True
    return False


def tv_topic_uses_brand_cover(topic: dict[str, Any] | None) -> bool:
    """兼容旧名；语义同 is_discussion_topic。"""
    return is_discussion_topic(topic)


def _load_discussion_cover_cache(slug: str) -> dict[str, Any] | None:
    if not DISCUSSION_COVER_CACHE.is_file():
        return None
    try:
        import json

        data = json.loads(DISCUSSION_COVER_CACHE.read_text(encoding="utf-8"))
        entry = (data.get("by_slug") or {}).get(slug)
        return entry if isinstance(entry, dict) else None
    except Exception:
        return None


def _save_discussion_cover_cache(slug: str, *, media_id: str, cache_key: str, source: str) -> None:
    import json
    from datetime import datetime
    from zoneinfo import ZoneInfo

    DISCUSSION_COVER_CACHE.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(DISCUSSION_COVER_CACHE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    by_slug = dict(data.get("by_slug") or {})
    by_slug[slug] = {
        "media_id": media_id,
        "cache_key": cache_key,
        "source": source,
        "updated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    }
    data["by_slug"] = by_slug
    DISCUSSION_COVER_CACHE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def pick_discussion_draft_thumb(
    topic: dict[str, Any],
    *,
    force_reupload: bool = False,
) -> tuple[str | None, dict[str, Any] | None]:
    """话题讨论封面：同题报道 still 裁 2.35:1；失败则报错，不回退股票图。"""
    from scripts.tools.wechat_mp_client import add_permanent_image
    from scripts.tools.wechat_mp_discussion_figures import ensure_discussion_cover

    slug = resolve_tv_cover_slug(topic)
    cover_path = ensure_discussion_cover(topic)
    cache_key = hashlib.md5(cover_path.read_bytes()).hexdigest()[:16]
    if not force_reupload:
        cached = _load_discussion_cover_cache(slug)
        if (
            cached
            and cached.get("cache_key") == cache_key
            and cached.get("media_id")
        ):
            return str(cached["media_id"]), None
    media_id, err = add_permanent_image(cover_path)
    if err or not media_id:
        return None, err or {
            "errcode": -1,
            "errmsg": f"上传话题讨论封面失败: {cover_path}",
        }
    _save_discussion_cover_cache(
        slug, media_id=media_id, cache_key=cache_key, source=str(cover_path)
    )
    return media_id, None


def pick_tv_draft_thumb(
    topic: dict[str, Any] | None = None,
    *,
    batch: str = "tv_trial",
    force_reupload: bool = False,
) -> tuple[str, str | None, dict[str, Any] | None]:
    """返回 (cover_kind, thumb_media_id, err)。话题讨论必须用同题事件图。"""
    from scripts.tools.wechat_mp_tv_topics import pick_tv_topic

    topic = topic or pick_tv_topic()
    if is_discussion_topic(topic):
        thumb, err = pick_discussion_draft_thumb(topic, force_reupload=force_reupload)
        return "discussion", thumb, err
    tv_thumb, err = pick_tv_review_thumb(topic, force_reupload=force_reupload)
    if tv_thumb:
        return "tv_review", tv_thumb, None
    return "tv_review", None, err


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="影视试跑封面")
    parser.add_argument("--generate", default="", help="生成封面 slug，如 euphoria")
    args = parser.parse_args()
    slug = (args.generate or "").strip().lower()
    if slug == "euphoria":
        path = generate_euphoria_cover()
        print(f"OK {path}")
        return 0
    if slug == "teach-you-a-lesson":
        path = generate_teach_you_a_lesson_cover()
        print(f"OK {path}")
        return 0
    if slug:
        ensure_tv_cover(slug)
        print(f"OK {cover_path_for_slug(slug)}")
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
