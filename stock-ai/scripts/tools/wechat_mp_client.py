"""微信公众平台 API 客户端（草稿箱 / 发布；需 AppID + AppSecret + IP 白名单）。"""

from __future__ import annotations

import json
import os
import re
import struct
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except Exception:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


_load_dotenv()

TOKEN_CACHE = ROOT / "data" / "wechat_mp_token.json"
THUMB_CACHE = ROOT / "data" / "wechat_mp_thumb.json"
DEFAULT_COVER_PATH = ROOT / "assets" / "wechat_mp" / "default_cover.jpg"
ALERT_LOG = ROOT / "logs" / "wechat_mp_alerts.log"
API_BASE = "https://api.weixin.qq.com/cgi-bin"
TZ = ZoneInfo("Asia/Shanghai")

# 常见 IP 白名单相关 errcode
IP_WHITELIST_ERRCODES = frozenset({40164, 61004})


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _normalize_material_name(name: str) -> str:
    """修复素材 name 被误按 Latin-1 解码的中文（便于匹配「机器人图」等）。"""
    if not name:
        return name
    try:
        fixed = name.encode("latin-1").decode("utf-8")
        if fixed != name:
            return fixed
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    return name


def _material_display_name(item: dict[str, Any]) -> str:
    return _normalize_material_name(str(item.get("name") or ""))


def mp_configured() -> bool:
    return bool(_env("WECHAT_MP_APPID") and _env("WECHAT_MP_SECRET"))


def _mp_session() -> requests.Session:
    """微信 API 不走系统/Clash 代理，出口须为家用 WAN（白名单 IP）。"""
    session = requests.Session()
    session.trust_env = False
    return session


def _mp_post_json(url: str, *, params: dict[str, Any] | None, payload: Any) -> dict[str, Any]:
    """POST JSON 且 UTF-8 直传中文，避免 requests.json= 把中文变成 \\uXXXX 在草稿箱乱码。"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    resp = _mp_session().post(url, params=params, data=body, headers=headers, timeout=60)
    try:
        data = resp.json()
    except Exception:
        snippet = (resp.text or resp.content[:200].decode("utf-8", errors="replace"))[:200]
        return {"errcode": -1, "errmsg": f"非 JSON 响应 HTTP {resp.status_code}: {snippet}"}
    return data


def get_public_ip(*, timeout: float = 10.0) -> str:
    override = _env("WECHAT_MP_PUBLIC_IP")
    if override:
        return override
    resp = requests.get("https://api.ipify.org?format=text", timeout=timeout)
    resp.raise_for_status()
    return resp.text.strip()


def _load_token_cache() -> dict[str, Any] | None:
    if not TOKEN_CACHE.is_file():
        return None
    try:
        return json.loads(TOKEN_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_token_cache(payload: dict[str, Any]) -> None:
    TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_CACHE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_access_token(*, force_refresh: bool = False) -> tuple[str | None, dict[str, Any] | None]:
    """返回 (access_token, error_json)。error_json 含 errcode/errmsg。"""
    appid = _env("WECHAT_MP_APPID")
    secret = _env("WECHAT_MP_SECRET")
    if not appid or not secret:
        return None, {"errcode": -1, "errmsg": "未配置 WECHAT_MP_APPID / WECHAT_MP_SECRET"}

    if not force_refresh:
        cached = _load_token_cache()
        if cached and cached.get("appid") == appid:
            expires = float(cached.get("expires_at") or 0)
            if cached.get("access_token") and expires > time.time() + 60:
                return str(cached["access_token"]), None

    url = f"{API_BASE}/token"
    resp = _mp_session().get(
        url,
        params={"grant_type": "client_credential", "appid": appid, "secret": secret},
        timeout=20,
    )
    data = resp.json()
    if data.get("errcode"):
        return None, data
    token = str(data.get("access_token") or "")
    expires_in = int(data.get("expires_in") or 7200)
    _save_token_cache(
        {
            "appid": appid,
            "access_token": token,
            "expires_at": time.time() + expires_in,
            "fetched_at": datetime.now(TZ).isoformat(timespec="seconds"),
        }
    )
    return token, None


def is_ip_whitelist_error(err: dict[str, Any] | None) -> bool:
    if not err:
        return False
    code = err.get("errcode")
    try:
        return int(code) in IP_WHITELIST_ERRCODES
    except (TypeError, ValueError):
        return False


def check_api_reachable() -> dict[str, Any]:
    """检测公网 IP 与 token 是否可用（用于白名单监控）。"""
    expected_ip = _env("WECHAT_MP_WHITELIST_IP")
    current_ip = get_public_ip()
    out: dict[str, Any] = {
        "ok": False,
        "current_ip": current_ip,
        "expected_ip": expected_ip or None,
        "ip_match": (current_ip == expected_ip) if expected_ip else None,
        "token_ok": False,
        "errcode": None,
        "errmsg": None,
    }
    if expected_ip and current_ip != expected_ip:
        out["errmsg"] = f"当前公网 IP {current_ip} 与 WECHAT_MP_WHITELIST_IP={expected_ip} 不一致"
        return out

    token, err = get_access_token()
    if err:
        out["errcode"] = err.get("errcode")
        out["errmsg"] = err.get("errmsg")
        out["ip_whitelist_error"] = is_ip_whitelist_error(err)
        return out

    out["token_ok"] = True
    out["ok"] = True
    out["access_token_prefix"] = (token or "")[:8] + "…" if token else None
    return out


def append_alert(message: str) -> None:
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    with ALERT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {message}\n")


def _line_to_html(line: str) -> str:
    from scripts.tools.wechat_mp_rich_html import format_line_rich_html, rich_html_enabled

    if rich_html_enabled():
        return format_line_rich_html(line)
    return _escape_html(line)


def _append_body_lines(parts: list[str], lines: list[str]) -> None:
    if not lines:
        return
    if len(lines) == 1 and lines[0].startswith("·"):
        parts.append(f"<p>{_line_to_html(lines[0])}</p>")
    elif all(line.startswith("·") for line in lines):
        items = "".join(
            f"<li>{_line_to_html(line.lstrip('·').strip())}</li>" for line in lines
        )
        parts.append(f"<ul>{items}</ul>")
    else:
        parts.append(f"<p>{'<br/>'.join(_line_to_html(x) for x in lines)}</p>")


def text_to_html(text: str) -> str:
    parts: list[str] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        from scripts.tools.wechat_mp_rich_html import (
            blockquote_title_html,
            is_blockquote_title_line,
        )

        if lines and is_blockquote_title_line(lines[0]):
            parts.append(blockquote_title_html(lines[0]))
            _append_body_lines(parts, [ln for ln in lines[1:] if ln.strip()])
            continue
        _append_body_lines(parts, lines)
    return "\n".join(parts) or "<p>（空）</p>"


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _load_thumb_cache() -> dict[str, Any] | None:
    if not THUMB_CACHE.is_file():
        return None
    try:
        return json.loads(THUMB_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_thumb_cache(media_id: str, *, source: str) -> None:
    THUMB_CACHE.parent.mkdir(parents=True, exist_ok=True)
    THUMB_CACHE.write_text(
        json.dumps(
            {
                "media_id": media_id,
                "source": source,
                "updated_at": datetime.now(TZ).isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _resolve_cover_path() -> Path | None:
    explicit = _env("WECHAT_MP_THUMB_PATH")
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_file():
            return path
        raise FileNotFoundError(f"WECHAT_MP_THUMB_PATH 不存在: {path}")
    return None


def add_permanent_image(image_path: Path) -> tuple[str | None, dict[str, Any] | None]:
    """上传永久素材图片，返回 (thumb_media_id, error_json)。"""
    token, err = get_access_token()
    if err:
        return None, err
    path = Path(image_path)
    if not path.is_file():
        return None, {"errcode": -1, "errmsg": f"封面文件不存在: {path}"}

    url = f"{API_BASE}/material/add_material"
    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    with path.open("rb") as fh:
        resp = _mp_session().post(
            url,
            params={"access_token": token, "type": "image"},
            files={"media": (path.name, fh, mime)},
            timeout=60,
        )
    data = resp.json()
    if data.get("errcode"):
        return None, data
    media_id = str(data.get("media_id") or "")
    if not media_id:
        return None, {"errcode": -1, "errmsg": "上传封面未返回 media_id"}
    return media_id, None


def _image_size_from_bytes(data: bytes) -> tuple[int, int] | None:
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return int(w), int(h)
    if len(data) >= 2 and data[:2] == b"\xff\xd8":
        idx = 2
        while idx < len(data) - 8:
            if data[idx] != 0xFF:
                idx += 1
                continue
            marker = data[idx + 1]
            idx += 2
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                h, w = struct.unpack(">HH", data[idx + 3 : idx + 7])
                return int(w), int(h)
            if idx + 1 >= len(data):
                break
            seg_len = struct.unpack(">H", data[idx : idx + 2])[0]
            idx += seg_len
    return None


def _crop_box_for_ratio(img_w: int, img_h: int, target_ratio: float) -> str:
    """居中裁剪为 target_ratio（宽/高），返回 X1_Y1_X2_Y2。"""
    if img_w <= 0 or img_h <= 0:
        return "0_0_1_1"
    current = img_w / img_h
    if current >= target_ratio:
        crop_w = target_ratio / current
        x1 = (1.0 - crop_w) / 2.0
        x2 = x1 + crop_w
        return f"{x1:.6f}_0_{x2:.6f}_1"
    crop_h = current / target_ratio
    y1 = (1.0 - crop_h) / 2.0
    y2 = y1 + crop_h
    return f"0_{y1:.6f}_1_{y2:.6f}"


def compute_cover_crop_fields(*, width: int, height: int) -> dict[str, str]:
    return {
        "pic_crop_235_1": _crop_box_for_ratio(width, height, 2.35),
        "pic_crop_1_1": _crop_box_for_ratio(width, height, 1.0),
    }


def get_material_image_meta(media_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """从素材列表 + 图片 url 解析尺寸（图片类 get_material 可能直接返回二进制，不走该接口）。"""
    offset = 0
    while offset < 200:
        items, list_err = batchget_material_images(offset=offset, count=20)
        if list_err:
            return None, list_err
        if not items:
            break
        for it in items:
            if str(it.get("media_id") or "") == media_id:
                img_url = str(it.get("url") or "")
                width = height = None
                if img_url:
                    resp = _mp_session().get(img_url, timeout=30)
                    resp.raise_for_status()
                    size = _image_size_from_bytes(resp.content)
                    if size:
                        width, height = size
                return (
                    {
                        "media_id": media_id,
                        "name": it.get("name"),
                        "url": img_url,
                        "width": width,
                        "height": height,
                        "bytes": len(resp.content) if img_url else None,
                    },
                    None,
                )
        if len(items) < 20:
            break
        offset += 20
    return None, {"errcode": -1, "errmsg": f"未找到素材 media_id={media_id}"}


def attach_cover_crop_fields(article: dict[str, Any], *, thumb_media_id: str) -> dict[str, Any]:
    """为图文草稿补全封面裁剪坐标（缺省时微信草稿箱预览常显示黑块）。"""
    if article.get("pic_crop_235_1") and article.get("pic_crop_1_1"):
        return article

    preset_235 = _env("WECHAT_MP_PIC_CROP_235_1")
    preset_11 = _env("WECHAT_MP_PIC_CROP_1_1")
    if preset_235:
        article["pic_crop_235_1"] = preset_235
    if preset_11:
        article["pic_crop_1_1"] = preset_11
    if article.get("pic_crop_235_1") and article.get("pic_crop_1_1"):
        return article

    meta, err = get_material_image_meta(thumb_media_id)
    if err or not meta:
        article.setdefault("pic_crop_235_1", "0_0_1_1")
        article.setdefault("pic_crop_1_1", "0_0_1_1")
        return article

    w, h = meta.get("width"), meta.get("height")
    if w and h:
        article.update(compute_cover_crop_fields(width=int(w), height=int(h)))
    else:
        article.setdefault("pic_crop_235_1", "0_0_1_1")
        article.setdefault("pic_crop_1_1", "0_0_1_1")
    return article


def del_permanent_material(media_id: str) -> dict[str, Any] | None:
    token, err = get_access_token()
    if err:
        return err
    url = f"{API_BASE}/material/del_material"
    data = _mp_post_json(url, params={"access_token": token}, payload={"media_id": media_id})
    if data.get("errcode"):
        return data
    return None


def _list_all_material_images(*, max_items: int = 500) -> list[dict[str, Any]]:
    """分页拉取全部图片素材（默认最多 500 条）。"""
    all_items: list[dict[str, Any]] = []
    offset = 0
    while offset < max_items:
        chunk, err = batchget_material_images(offset=offset, count=20)
        if err:
            break
        if not chunk:
            break
        all_items.extend(chunk)
        offset += len(chunk)
        if len(chunk) < 20:
            break
    return all_items


def batchget_material_images(
    *,
    offset: int = 0,
    count: int = 20,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """拉取永久图片素材列表（含公众平台素材库上传的图）。"""
    token, err = get_access_token()
    if err:
        return [], err
    count = max(1, min(20, count))
    url = f"{API_BASE}/material/batchget_material"
    data = _mp_post_json(
        url,
        params={"access_token": token},
        payload={"type": "image", "offset": offset, "count": count},
    )
    if data.get("errcode"):
        return [], data
    items = list(data.get("item") or [])
    for it in items:
        raw = str(it.get("name") or "")
        it["name_raw"] = raw
        it["name"] = _normalize_material_name(raw)
    return items, None


# 四槽位默认封面（素材名子串，优先「双封面」竖版）
_DEFAULT_KIND_THUMB_NAMES: dict[str, str] = {
    "market": "封面-交易所屏-双封面",
    "top5": "封面-手机看盘-双封面",
    "dragons": "封面-K线暗色-双封面",
    "workspace": "封面-数据大屏-双封面",
}


def pick_thumb_from_material_library(
    *,
    name_sub: str | None = None,
    media_id_preset: str | None = None,
    use_global_preset: bool = True,
) -> tuple[str | None, dict[str, Any] | None]:
    """
    从素材库选封面 thumb_media_id。
    优先级：media_id_preset → 全局 WECHAT_MP_THUMB_MEDIA_ID（可选）
    → name_sub / WECHAT_MP_THUMB_NAME → WECHAT_MP_THUMB_INDEX → 最新一张图。
    """
    preset = (media_id_preset or "").strip()
    if not preset and use_global_preset:
        preset = _env("WECHAT_MP_THUMB_MEDIA_ID")
    if preset:
        return preset, None

    items = _list_all_material_images()
    if not items:
        return None, {
            "errcode": -1,
            "errmsg": "素材库无图片：请在 mp.weixin.qq.com 素材管理上传封面，或设置 WECHAT_MP_THUMB_MEDIA_ID",
        }

    if name_sub is None:
        name_sub = _env("WECHAT_MP_THUMB_NAME", "机器人图")
    if name_sub:
        for it in items:
            display = _material_display_name(it)
            if name_sub in display or name_sub in str(it.get("name_raw") or ""):
                return str(it["media_id"]), None

    idx_raw = _env("WECHAT_MP_THUMB_INDEX")
    if idx_raw:
        try:
            idx = int(idx_raw)
            if 0 <= idx < len(items):
                return str(items[idx]["media_id"]), None
        except ValueError:
            pass

    skip_default = _env("WECHAT_MP_THUMB_SKIP_DEFAULT", "1").lower() not in {"0", "false", "no"}
    pool = items
    if skip_default:
        filtered = [
            it
            for it in items
            if "default_cover" not in str(it.get("name") or "").lower()
        ]
        if filtered:
            pool = filtered

    deny = {"default_cover", "default_cover.jpg", "black", "placeholder"}
    pool = [it for it in pool if str(it.get("name") or "").lower() not in deny]
    if not pool:
        return None, {
            "errcode": -1,
            "errmsg": "素材库仅有黑底占位图，请上传真实封面并设置 WECHAT_MP_THUMB_MEDIA_ID",
        }

    sorted_items = sorted(pool, key=lambda x: int(x.get("update_time") or 0), reverse=True)
    return str(sorted_items[0]["media_id"]), None


def pick_thumb_for_draft_kind(kind: str) -> tuple[str | None, dict[str, Any] | None]:
    """
    按草稿槽位选封面（market / top5 / dragons / workspace）。
    环境变量：WECHAT_MP_THUMB_MEDIA_ID_{KIND}、WECHAT_MP_THUMB_NAME_{KIND}
    """
    k = (kind or "").strip().lower()
    env_suffix = k.upper()
    media_preset = _env(f"WECHAT_MP_THUMB_MEDIA_ID_{env_suffix}")
    name_sub = _env(f"WECHAT_MP_THUMB_NAME_{env_suffix}") or _DEFAULT_KIND_THUMB_NAMES.get(k, "")
    return pick_thumb_from_material_library(
        name_sub=name_sub,
        media_id_preset=media_preset or None,
        use_global_preset=False,
    )


def ensure_thumb_media_id(*, force_reupload: bool = False) -> tuple[str | None, dict[str, Any] | None]:
    """
    获取图文草稿封面 thumb_media_id。
    默认从公众平台素材库选图；仅当 WECHAT_MP_THUMB_UPLOAD=1 时才上传本地文件。
    """
    if not force_reupload:
        lib_id, lib_err = pick_thumb_from_material_library()
        if lib_id:
            return lib_id, None
        if lib_err and _env("WECHAT_MP_THUMB_UPLOAD") not in {"1", "true", "yes"}:
            return None, lib_err

    if _env("WECHAT_MP_THUMB_UPLOAD") not in {"1", "true", "yes"}:
        return None, {
            "errcode": -1,
            "errmsg": (
                "缺少封面：在素材库上传图片并设置 WECHAT_MP_THUMB_MEDIA_ID，"
                "或 WECHAT_MP_THUMB_NAME / WECHAT_MP_THUMB_INDEX 指定素材"
            ),
        }

    cover = _resolve_cover_path()
    if cover is None:
        return None, {
            "errcode": -1,
            "errmsg": "WECHAT_MP_THUMB_UPLOAD=1 但未找到 WECHAT_MP_THUMB_PATH 或默认封面文件",
        }

    media_id, err = add_permanent_image(cover)
    if err:
        return None, err
    _save_thumb_cache(media_id or "", source=str(cover))
    return media_id, None


def draft_batchget(
    *,
    offset: int = 0,
    count: int = 20,
    no_content: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """草稿箱列表，返回 item 列表（含 media_id、content.news_item）。"""
    token, err = get_access_token()
    if err:
        return [], err
    count = max(1, min(20, count))
    url = f"{API_BASE}/draft/batchget"
    data = _mp_post_json(
        url,
        params={"access_token": token},
        payload={
            "offset": offset,
            "count": count,
            "no_content": 1 if no_content else 0,
        },
    )
    if data.get("errcode"):
        return [], data
    return list(data.get("item") or []), None


def list_all_drafts(*, max_items: int = 100) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    all_items: list[dict[str, Any]] = []
    offset = 0
    while offset < max_items:
        chunk, err = draft_batchget(offset=offset, count=20, no_content=True)
        if err:
            return all_items, err
        if not chunk:
            break
        all_items.extend(chunk)
        offset += len(chunk)
        if len(chunk) < 20:
            break
    return all_items, None


def draft_delete(*, media_id: str) -> dict[str, Any] | None:
    """删除草稿（不可恢复）。"""
    token, err = get_access_token()
    if err:
        return err
    url = f"{API_BASE}/draft/delete"
    data = _mp_post_json(
        url,
        params={"access_token": token},
        payload={"media_id": media_id},
    )
    if data.get("errcode"):
        return data
    return None


def normalize_draft_text(text: str) -> str:
    """草稿标题/摘要等字段的中文编码修复。"""
    return _normalize_material_name(text)


def draft_first_title(item: dict[str, Any]) -> str:
    content = item.get("content") or {}
    news = content.get("news_item") or []
    if news and isinstance(news[0], dict):
        return normalize_draft_text(str(news[0].get("title") or ""))
    return ""


def draft_update(
    *,
    media_id: str,
    article: dict[str, Any],
    index: int = 0,
) -> dict[str, Any] | None:
    """更新已有草稿（单图文 index=0）。成功返回 None，失败返回 error_json。"""
    token, err = get_access_token()
    if err:
        return err

    item = dict(article)
    item.setdefault("article_type", "news")
    tid = str(item.get("thumb_media_id") or "")
    if tid:
        attach_cover_crop_fields(item, thumb_media_id=tid)

    url = f"{API_BASE}/draft/update"
    data = _mp_post_json(
        url,
        params={"access_token": token},
        payload={"media_id": media_id, "index": index, "articles": item},
    )
    if data.get("errcode"):
        return data
    return None


def draft_add(*, articles: list[dict[str, Any]]) -> tuple[str | None, dict[str, Any] | None]:
    """新增草稿，返回 (media_id, error_json)。"""
    token, err = get_access_token()
    if err:
        return None, err

    prepared: list[dict[str, Any]] = []
    need_thumb = False
    for raw in articles:
        item = dict(raw)
        article_type = item.get("article_type") or "news"
        item["article_type"] = article_type
        if article_type == "news" and not item.get("thumb_media_id"):
            need_thumb = True
        prepared.append(item)

    thumb: str | None = None
    if need_thumb:
        thumb, thumb_err = ensure_thumb_media_id()
        if thumb_err:
            return None, thumb_err

    for item in prepared:
        if (item.get("article_type") or "news") != "news":
            continue
        if need_thumb and not item.get("thumb_media_id"):
            item["thumb_media_id"] = thumb
        tid = str(item.get("thumb_media_id") or "")
        if tid:
            attach_cover_crop_fields(item, thumb_media_id=tid)

    url = f"{API_BASE}/draft/add"
    data = _mp_post_json(
        url,
        params={"access_token": token},
        payload={"articles": prepared},
    )
    if data.get("errcode"):
        return None, data
    return str(data.get("media_id") or ""), None


def freepublish_submit(*, media_id: str) -> tuple[str | None, dict[str, Any] | None]:
    """提交发布草稿，返回 (publish_id, error_json)。"""
    token, err = get_access_token()
    if err:
        return None, err
    url = f"{API_BASE}/freepublish/submit"
    data = _mp_post_json(
        url,
        params={"access_token": token},
        payload={"media_id": media_id},
    )
    if data.get("errcode"):
        return None, data
    return str(data.get("publish_id") or ""), None
