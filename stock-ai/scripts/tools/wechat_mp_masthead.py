"""公众号正文品牌头：banner 图 + 赛博风 slogan 条。"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import _escape_html

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BANNER_PATH = ROOT / "assets" / "wechat_mp" / "banner.png"
UPLOAD_CACHE_PATH = ROOT / "data" / "wechat_mp_figure_upload_cache.json"
TZ = ZoneInfo("Asia/Shanghai")

DEFAULT_ACCOUNT_NAME = "牛马也智能"

# 与 banner 一致的 FinTech 配色
_COLOR_PANEL_BG = "#061528"
_COLOR_PANEL_BORDER = "#1a6b9a"
_COLOR_CYAN = "#00e5ff"
_COLOR_NAME = "#7dd3fc"
_COLOR_SLOGAN_BG = "#0b2340"
_COLOR_SLOGAN_BORDER = "#1565a8"
_COLOR_SLOGAN_TEXT = "#e8f4fc"

KIND_SLOGANS: dict[str, str] = {
    "hotspot": "网下吵什么，盘上怎么走",
    "hot_business": "热点背后的生意，先把账算清楚",
    "silver": "退休不是退场，把日子重新安排好",
    "sector": "今天资金盯哪条链？先拆行业再盯票",
    "market": "牛马下班别躺平，先看一眼大盘魂",
    "news": "消息比外卖还快，筛十条够你吹",
    "workspace": "代码和 K 线之间，还隔着一个 launchd",
    "temp": "官方 CLI 一条链路，飞书也能脚本化",
    "harryputter": "HarryPutter：哈利波特朗读和文本对到句，播到哪亮哪句",
}

_DEFAULT_SLOGAN = "打工人的智能复盘手记"


def masthead_enabled() -> bool:
    raw = os.environ.get("WECHAT_MP_MASTHEAD", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def account_name(*, kind: str | None = None) -> str:
    return (os.environ.get("WECHAT_MP_ACCOUNT_NAME") or DEFAULT_ACCOUNT_NAME).strip()[:16]


def resolve_banner_path(*, kind: str | None = None) -> Path:
    override = os.environ.get("WECHAT_MP_BANNER_PATH", "").strip()
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return path
    if DEFAULT_BANNER_PATH.is_file():
        return DEFAULT_BANNER_PATH
    raise FileNotFoundError(f"banner 不存在: {DEFAULT_BANNER_PATH}")


def banner_cache_key(path: Path) -> str:
    digest = hashlib.md5(path.read_bytes()).hexdigest()[:16]
    return f"banner:{path.name}#{digest}"


def slogan_for_kind(kind: str | None) -> str:
    k = (kind or "").strip().lower()
    env_key = f"WECHAT_MP_MASTHEAD_SLOGAN_{k.upper()}" if k else ""
    if env_key:
        override = os.environ.get(env_key, "").strip()
        if override:
            return override[:48]
    global_slogan = os.environ.get("WECHAT_MP_MASTHEAD_SLOGAN", "").strip()
    if global_slogan:
        return global_slogan[:48]
    return KIND_SLOGANS.get(k, _DEFAULT_SLOGAN)


def _load_upload_cache() -> dict[str, str]:
    if not UPLOAD_CACHE_PATH.is_file():
        return {}
    try:
        data = json.loads(UPLOAD_CACHE_PATH.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in (data.get("urls") or {}).items() if v}
    except Exception:
        return {}


def _save_upload_cache(urls: dict[str, str]) -> None:
    UPLOAD_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": datetime.now(TZ).isoformat(), "urls": urls}
    UPLOAD_CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def upload_banner_image(*, kind: str | None = None) -> tuple[str | None, dict | None]:
    from scripts.tools.wechat_mp_client import upload_article_image

    path = resolve_banner_path(kind=kind)
    key = banner_cache_key(path)
    cache = _load_upload_cache()
    if key in cache:
        return cache[key], None
    url, err = upload_article_image(path)
    if url:
        cache[key] = url
        _save_upload_cache(cache)
    return url, err


def _banner_src(
    *,
    kind: str | None,
    upload_images: bool,
    local_preview: bool,
) -> str | None:
    path = resolve_banner_path(kind=kind)
    if local_preview:
        return path.resolve().as_uri()
    key = banner_cache_key(path)
    cache = _load_upload_cache()
    if key in cache:
        return cache[key]
    if not upload_images:
        return None
    from scripts.tools.wechat_mp_client import mp_configured

    if not mp_configured():
        return None
    url, err = upload_banner_image(kind=kind)
    if err:
        from scripts.tools.wechat_mp_client import append_alert

        append_alert(f"BANNER upload fail: {err}")
    return url


def _banner_img_html(src: str, *, kind: str | None = None) -> str:
    return (
        '<div style="margin:0;padding:0;line-height:0;font-size:0;">'
        f'<img src="{_escape_html(src)}" alt="{_escape_html(account_name(kind=kind))}" '
        'style="width:100%;height:auto;display:block;margin:0;padding:0;'
        'border-radius:10px 10px 0 0;"/>'
        "</div>"
    )


def _slogan_panel_html(*, name: str, slogan: str, kind: str | None = None) -> str:
    name_text = _escape_html(name)
    slogan_text = _escape_html(slogan)
    panel_bg, border_top, name_color = _COLOR_PANEL_BG, f"2px solid {_COLOR_CYAN}", _COLOR_NAME
    slogan_bg, slogan_border, slogan_color = (
        _COLOR_SLOGAN_BG,
        _COLOR_SLOGAN_BORDER,
        _COLOR_SLOGAN_TEXT,
    )
    name_shadow = "text-shadow:0 0 8px rgba(0,229,255,0.35);"
    return (
        f'<div style="margin:0;padding:10px 12px;text-align:center;'
        f"background-color:{panel_bg};"
        f"border-top:{border_top};"
        f'border-radius:0 0 10px 10px;">'
        f'<p style="margin:0;padding:0;font-size:16px;font-weight:700;'
        f"color:{name_color};letter-spacing:0.12em;line-height:1.35;"
        f'{name_shadow}">{name_text}</p>'
        f'<p style="margin:8px 0 0;padding:8px 10px;'
        f"background-color:{slogan_bg};"
        f"border:1px solid {slogan_border};border-radius:8px;"
        f"font-size:13px;color:{slogan_color};line-height:1.55;"
        f'letter-spacing:0.05em;">{slogan_text}</p>'
        "</div>"
    )


def masthead_html(
    kind: str | None = None,
    *,
    upload_images: bool = True,
    local_preview: bool = False,
) -> str:
    """banner 全宽图 + 深色 cyan 风 slogan 条。"""
    if not masthead_enabled():
        return ""
    k = (kind or "").strip().lower()
    if k in {"guba", "hotspot", "hot_business", "tv_review", "tv", "film", "movie"}:
        return ""
    name = account_name(kind=kind)
    slogan = slogan_for_kind(kind)
    src = _banner_src(kind=kind, upload_images=upload_images, local_preview=local_preview)
    img_part = _banner_img_html(src, kind=kind) if src else ""
    panel = _slogan_panel_html(name=name, slogan=slogan, kind=kind)
    return (
        f'<section style="margin:0 0 14px;padding:0;text-align:center;overflow:hidden;'
        f"border:1px solid {_COLOR_PANEL_BORDER};border-radius:10px;"
        f'line-height:0;font-size:0;">'
        f"{img_part}{panel}"
        "</section>"
    )
