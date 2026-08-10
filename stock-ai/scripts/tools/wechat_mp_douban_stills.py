#!/usr/bin/env python3
"""从豆瓣条目拉取剧照（photo id + Referer，非 TMDB）。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import requests

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
INLINE_TV_ROOT = ROOT / "assets" / "wechat_mp" / "inline-tv"


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if env_path.is_file():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_path)
        except Exception:
            pass


_load_dotenv()

DOUBAN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://movie.douban.com/",
}

# 人工筛过：豆瓣《亢奋》剧照 photo id（安全、无裸露帧）
EUPHORIA_DOUBAN_PHOTOS: dict[str, str] = {
    "douban-still-01.jpg": "2560512988",
    "douban-still-02.jpg": "2560326143",
    "douban-still-03.jpg": "2560512989",
}

# 豆瓣《怒呛人生》S1 剧照（剧评引用；S2 条目剧照较少，沿用系列安全帧）
BEEF_DOUBAN_PHOTOS: dict[str, str] = {
    "douban-still-01.jpg": "2890856178",
    "douban-still-02.jpg": "2890495381",
    "douban-still-03.jpg": "2890862607",
}


def douban_photo_url(photo_id: str, *, size: str = "l") -> str:
    pid = str(photo_id).strip().lstrip("p")
    return f"https://img3.doubanio.com/view/photo/{size}/public/p{pid}.jpg"


def download_douban_photo(photo_id: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(douban_photo_url(photo_id), headers=DOUBAN_HEADERS, timeout=60)
    resp.raise_for_status()
    if "image" not in (resp.headers.get("content-type") or ""):
        raise RuntimeError(f"豆瓣返回非图片: photo_id={photo_id}")
    if len(resp.content) < 5000:
        raise RuntimeError(f"豆瓣图片过小，可能被拦截: photo_id={photo_id}")
    dest.write_bytes(resp.content)
    return dest


def download_tmdb_image(file_path: str, dest: Path, *, size: str = "w780") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fp = str(file_path).strip().lstrip("/")
    url = f"https://image.tmdb.org/t/p/{size}/{fp}"
    resp = requests.get(url, headers=DOUBAN_HEADERS, timeout=60)
    resp.raise_for_status()
    if len(resp.content) < 3000:
        raise RuntimeError(f"TMDB 图片过小: {file_path}")
    dest.write_bytes(resp.content)
    return dest


TEACH_YOU_LESSON_TMDB_ID = 276161

# 海报 + 背景剧照（w780，剧评引用；路径来自 TMDB 公开图库页抓取）
TEACH_YOU_LESSON_TMDB_STILLS: dict[str, str] = {
    "still-01.jpg": "7KEA6GYQ81Lcmu3KHee2eYKjccP.jpg",
    "still-02.jpg": "fMECSPrTmRClSViMsXFYmiYIcWP.jpg",
    "still-03.jpg": "fOV6dJGG6EghbeXkU7RVQpDhFyp.jpg",
    "still-04.jpg": "vAlyMWbVUWImy0SFsDdROjy23mK.jpg",
    "still-05.jpg": "7I5o1pauNbi9fpp6Bq4OzRjaQfC.jpg",
    "still-06.jpg": "vyG93jhmPL7tBIhRtCLa5mdBKob.jpg",
    "still-07.jpg": "ueCAMPHlTcEkuSSxGBHX85zfvV9.jpg",
    "still-08.jpg": "jkKoS3YtjdQbzNOWPmxY2bPLHlr.jpg",
    "still-09.jpg": "mZAWkzC0oopXP9JzkzOlwLoSbgs.jpg",
    "still-10.jpg": "wzJuniw680wrUB2ttjwyaherOzk.jpg",
}

TMDB_SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


def tv_stills_force_refresh() -> bool:
    return os.getenv("WECHAT_MP_TV_STILLS_FORCE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def scrape_tmdb_image_paths(tv_id: int, *, kind: str = "backdrops") -> list[str]:
    """无需 API Token：抓取 TMDB 条目图片页的 file_path 列表。"""
    url = f"https://www.themoviedb.org/tv/{int(tv_id)}/images/{kind}"
    resp = requests.get(url, headers=TMDB_SCRAPE_HEADERS, timeout=45)
    resp.raise_for_status()
    found = re.findall(r"/t/p/(?:w\d+|original)/([A-Za-z0-9]+\.jpg)", resp.text)
    return list(dict.fromkeys(found))


def fetch_tmdb_stills_via_api(tv_id: int, *, limit: int = 8) -> list[str]:
    """有 TMDB_READ_ACCESS_TOKEN 或 TMDB_API_KEY 时走官方 API。"""
    read_token = os.getenv("TMDB_READ_ACCESS_TOKEN", "").strip()
    api_key = os.getenv("TMDB_API_KEY", "").strip()
    if read_token:
        resp = requests.get(
            f"https://api.themoviedb.org/3/tv/{int(tv_id)}/images",
            headers={"Authorization": f"Bearer {read_token}"},
            timeout=45,
        )
    elif api_key:
        resp = requests.get(
            f"https://api.themoviedb.org/3/tv/{int(tv_id)}/images",
            params={"api_key": api_key},
            timeout=45,
        )
    else:
        return []
    resp.raise_for_status()
    data = resp.json()
    paths: list[str] = []
    for row in data.get("backdrops") or []:
        fp = str(row.get("file_path") or "").strip().lstrip("/")
        if fp:
            paths.append(fp)
    for row in data.get("posters") or []:
        fp = str(row.get("file_path") or "").strip().lstrip("/")
        if fp and fp not in paths:
            paths.append(fp)
    return paths[:limit]


def resolve_teach_you_a_lesson_stills() -> dict[str, str]:
    """合并硬编码优选路径 + API/抓取补充（仍以 6 槽位映射为准）。"""
    return dict(TEACH_YOU_LESSON_TMDB_STILLS)


def resolve_tmdb_still_files(spec: dict[str, Any], *, slug: str) -> dict[str, str]:
    files = spec.get("files") if isinstance(spec.get("files"), dict) else {}
    if files:
        return {str(k): str(v) for k, v in files.items()}
    if slug == "teach-you-a-lesson":
        return dict(TEACH_YOU_LESSON_TMDB_STILLS)
    return {}


def ensure_tmdb_tv_stills(topic: dict[str, Any], spec: dict[str, Any]) -> None:
    """从 TMDB 下载真实剧照（spec.files 映射；有 Token 可 FORCE 刷新）。"""
    from scripts.tools.wechat_mp_tv_cover import generate_tmdb_backdrop_cover

    slug = _slug(topic)
    out_dir = INLINE_TV_ROOT / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    force = tv_stills_force_refresh()
    photos = resolve_tmdb_still_files(spec, slug=slug)
    tmdb_id = int(spec.get("tmdb_id") or topic.get("tmdb_id") or 0)
    if force and tmdb_id:
        api_paths = fetch_tmdb_stills_via_api(tmdb_id, limit=12)
        if len(api_paths) >= len(photos):
            keys = list(photos.keys()) or [f"still-{i+1:02d}.jpg" for i in range(len(api_paths))]
            photos = {
                keys[i]: api_paths[i] for i in range(min(len(keys), len(api_paths)))
            }
    for fname, file_path in photos.items():
        dest = out_dir / fname
        if dest.is_file() and dest.stat().st_size > 30000 and not force:
            continue
        download_tmdb_image(file_path, dest)
    backdrop = next(iter(photos.values()), "")
    if backdrop:
        generate_tmdb_backdrop_cover(
            out_dir / "cover.jpg",
            backdrop,
            title_zh=str(topic.get("title_zh") or ""),
            title_en=str(topic.get("title_en") or ""),
            platform=str(topic.get("platform") or "Netflix"),
        )


def ensure_douban_stills(topic: dict[str, Any]) -> None:
    slug = _slug(topic)
    photos = _photo_map(topic, slug)
    if not photos:
        return
    out_dir = INLINE_TV_ROOT / slug
    for fname, photo_id in photos.items():
        dest = out_dir / fname
        if dest.is_file() and dest.stat().st_size > 5000:
            continue
        download_douban_photo(photo_id, dest)


def fetch_tmdb_movie_images(movie_id: int, *, limit: int = 8) -> tuple[str, list[str]]:
    """返回 (poster_path, backdrop_paths)。"""
    read_token = os.getenv("TMDB_READ_ACCESS_TOKEN", "").strip()
    api_key = os.getenv("TMDB_API_KEY", "").strip()
    if read_token:
        resp = requests.get(
            f"https://api.themoviedb.org/3/movie/{int(movie_id)}/images",
            headers={"Authorization": f"Bearer {read_token}"},
            timeout=45,
        )
    elif api_key:
        resp = requests.get(
            f"https://api.themoviedb.org/3/movie/{int(movie_id)}/images",
            params={"api_key": api_key},
            timeout=45,
        )
    else:
        return "", []
    resp.raise_for_status()
    data = resp.json()
    poster = ""
    for row in data.get("posters") or []:
        fp = str(row.get("file_path") or "").strip().lstrip("/")
        if fp:
            poster = fp
            break
    backdrops: list[str] = []
    for row in data.get("backdrops") or []:
        fp = str(row.get("file_path") or "").strip().lstrip("/")
        if fp:
            backdrops.append(fp)
        if len(backdrops) >= limit:
            break
    return poster, backdrops


def ensure_tmdb_movie_stills(topic: dict[str, Any], spec: dict[str, Any]) -> None:
    """TMDB 电影：下载剧照 + 横版封面（inline-tv/{slug}/）。"""
    from scripts.tools.wechat_mp_tv_cover import (
        cover_path_for_slug,
        generate_tmdb_backdrop_cover,
        generate_tmdb_poster_cover,
    )

    slug = _slug(topic)
    out_dir = INLINE_TV_ROOT / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    force = tv_stills_force_refresh()
    photos = resolve_tmdb_still_files(spec, slug=slug)
    movie_id = int(spec.get("tmdb_id") or topic.get("tmdb_movie_id") or 0)
    if not photos and movie_id:
        _, api_paths = fetch_tmdb_movie_images(movie_id, limit=6)
        photos = {f"still-{i+1:02d}.jpg": p for i, p in enumerate(api_paths)}
    if force and movie_id:
        poster_fp, api_paths = fetch_tmdb_movie_images(movie_id, limit=12)
        if api_paths and len(api_paths) >= len(photos):
            keys = list(photos.keys()) or [f"still-{i+1:02d}.jpg" for i in range(len(api_paths))]
            photos = {keys[i]: api_paths[i] for i in range(min(len(keys), len(api_paths)))}
        if poster_fp:
            download_tmdb_image(poster_fp, out_dir / "poster.jpg", size="w780")
    for fname, file_path in photos.items():
        dest = out_dir / fname
        if dest.is_file() and dest.stat().st_size > 30000 and not force:
            continue
        download_tmdb_image(file_path, dest)
    backdrop = next(iter(photos.values()), "")
    if backdrop:
        generate_tmdb_backdrop_cover(
            out_dir / "cover.jpg",
            backdrop,
            title_zh=str(topic.get("title_zh") or ""),
            title_en=str(topic.get("title_en") or ""),
            platform=str(topic.get("platform") or "院线"),
        )
        generate_tmdb_backdrop_cover(
            cover_path_for_slug(slug),
            backdrop,
            title_zh=str(topic.get("title_zh") or ""),
            title_en=str(topic.get("title_en") or ""),
            platform=str(topic.get("platform") or "院线"),
        )
    elif movie_id:
        poster_fp, api_paths = fetch_tmdb_movie_images(movie_id, limit=4)
        if poster_fp:
            download_tmdb_image(poster_fp, out_dir / "poster.jpg", size="w780")
            generate_tmdb_poster_cover(out_dir / "cover.jpg", poster_fp)
            generate_tmdb_poster_cover(cover_path_for_slug(slug), poster_fp)


def scrape_douban_photo_ids(seed_photo_id: str, *, max_ids: int = 12) -> list[str]:
    """从一张剧照页向外扩 photo id（维护用）。"""
    seen: set[str] = {str(seed_photo_id).strip()}
    queue = [str(seed_photo_id).strip()]
    while queue and len(seen) < max_ids:
        pid = queue.pop(0)
        html = requests.get(
            f"https://movie.douban.com/photos/photo/{pid}/",
            headers=DOUBAN_HEADERS,
            timeout=45,
        ).text
        for found in re.findall(r"photos/photo/(\d+)", html):
            if found not in seen:
                seen.add(found)
                queue.append(found)
    return sorted(seen)


def _slug(topic: dict[str, Any]) -> str:
    slug = str(topic.get("cover_slug") or "").strip().lower()
    en = str(topic.get("title_en") or "").strip().lower()
    if slug == "euphoria" or en == "euphoria":
        return "euphoria"
    if slug == "beef" or en == "beef":
        return "beef"
    if slug in {"teach-you-a-lesson", "teach_you_a_lesson"} or en in {
        "teach you a lesson",
        "get schooled",
    }:
        return "teach-you-a-lesson"
    if slug == "spider-man-brand-new-day" or "spider-man" in en:
        return "spider-man-brand-new-day"
    return slug or "tv"


def _photo_map(topic: dict[str, Any], slug: str) -> dict[str, str]:
    custom = topic.get("douban_photos")
    if isinstance(custom, dict) and custom:
        return {str(k): str(v) for k, v in custom.items()}
    if slug == "euphoria":
        return dict(EUPHORIA_DOUBAN_PHOTOS)
    if slug == "beef":
        return dict(BEEF_DOUBAN_PHOTOS)
    return {}
