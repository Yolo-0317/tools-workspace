"""微信公众平台 API 客户端（草稿箱 / 发布；需 AppID + AppSecret + IP 白名单）。"""

from __future__ import annotations

import json
import os
import re
import struct
import time
from datetime import datetime
from ipaddress import AddressValueError, IPv4Address
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter

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
SECTOR_BANNER_THUMB_CACHE = ROOT / "data" / "wechat_mp_sector_banner_thumb.json"
_KIND_THUMB_ASSET_CACHE: dict[str, Path] = {
    "hotspot": ROOT / "data" / "wechat_mp_thumb_hotspot.json",
    "tv_review": ROOT / "data" / "wechat_mp_thumb_tv_review.json",
}
DEFAULT_COVER_PATH = ROOT / "assets" / "wechat_mp" / "default_cover.jpg"
ALERT_LOG = ROOT / "logs" / "wechat_mp_alerts.log"
API_BASE = "https://api.weixin.qq.com/cgi-bin"
TZ = ZoneInfo("Asia/Shanghai")

# 常见 IP 白名单相关 errcode
IP_WHITELIST_ERRCODES = frozenset({40164, 61004})
INVALID_IP_RE = re.compile(r"invalid ip\s+(\d{1,3}(?:\.\d{1,3}){3})", re.IGNORECASE)


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
    appid, secret = mp_credentials()
    return bool(appid and secret)


def mp_credentials() -> tuple[str, str]:
    return _env("WECHAT_MP_APPID"), _env("WECHAT_MP_SECRET")


class FixedWeChatAPIAdapter(HTTPAdapter):
    """连接固定 IPv4，同时保留微信域名的 Host、SNI 与证书校验。"""

    def __init__(self, *, resolve_ip: str) -> None:
        self.resolve_ip = str(IPv4Address(resolve_ip))
        super().__init__()

    def get_connection_with_tls_context(
        self,
        request: requests.PreparedRequest,
        verify: bool | str,
        proxies: dict[str, str] | None = None,
        cert: Any = None,
    ) -> Any:
        parsed = urlsplit(request.url)
        if parsed.hostname != "api.weixin.qq.com":
            return super().get_connection_with_tls_context(
                request,
                verify,
                proxies=proxies,
                cert=cert,
            )
        request.headers.setdefault("Host", "api.weixin.qq.com")
        return self.poolmanager.connection_from_host(
            host=self.resolve_ip,
            port=parsed.port or 443,
            scheme="https",
            pool_kwargs={
                "assert_hostname": "api.weixin.qq.com",
                "server_hostname": "api.weixin.qq.com",
            },
        )


def _configured_api_resolve_ip() -> str:
    value = _env("WECHAT_MP_API_RESOLVE_IP")
    if not value:
        return ""
    try:
        return str(IPv4Address(value))
    except AddressValueError as exc:
        raise ValueError("WECHAT_MP_API_RESOLVE_IP 须为 IPv4 地址") from exc


def _mp_session() -> requests.Session:
    """微信 API 不走普通代理；可选固定目标 IPv4 以稳定 SASE 出口。"""
    session = requests.Session()
    session.trust_env = False
    resolve_ip = _configured_api_resolve_ip()
    if resolve_ip:
        session.mount(
            "https://api.weixin.qq.com/",
            FixedWeChatAPIAdapter(resolve_ip=resolve_ip),
        )
    return session


def _mp_parse_json(resp: requests.Response) -> dict[str, Any]:
    """微信 API 常返回 Content-Type: text/plain，requests 会误用 ISO-8859-1 解码。"""
    try:
        return json.loads(resp.content.decode("utf-8"))
    except Exception:
        snippet = (resp.text or resp.content[:200].decode("utf-8", errors="replace"))[:200]
        return {"errcode": -1, "errmsg": f"非 JSON 响应 HTTP {resp.status_code}: {snippet}"}


def _mp_post_json(
    url: str,
    *,
    params: dict[str, Any] | None,
    payload: Any,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """POST JSON 且 UTF-8 直传中文，避免 requests.json= 把中文变成 \\uXXXX 在草稿箱乱码。"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req_headers = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        req_headers.update(headers)
    resp = _mp_session().post(url, params=params, data=body, headers=req_headers, timeout=60)
    return _mp_parse_json(resp)


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
    try:
        resp = _mp_session().get(
            url,
            params={"grant_type": "client_credential", "appid": appid, "secret": secret},
            timeout=20,
        )
        data = _mp_parse_json(resp)
    except requests.RequestException:
        return None, {"errcode": -2, "errmsg": "微信公众号 token 网络请求失败"}
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


def invalid_ip_from_error(error: dict[str, Any] | None) -> str:
    """从微信白名单错误中提取微信实际看到的 IPv4。"""
    if not is_ip_whitelist_error(error):
        return ""
    match = INVALID_IP_RE.search(str((error or {}).get("errmsg") or ""))
    if not match:
        return ""
    try:
        return str(IPv4Address(match.group(1)))
    except AddressValueError:
        return ""


def verify_required_wechat_egress() -> dict[str, Any]:
    """强刷 token 验证固定路由；无法证明符合要求时停止写操作。"""
    required = _env("WECHAT_MP_REQUIRED_EGRESS_IP")
    if not required:
        return {"ok": True, "required_ip": None, "observed_ip": None}
    try:
        required = str(IPv4Address(required))
    except AddressValueError as exc:
        raise RuntimeError("WECHAT_MP_REQUIRED_EGRESS_IP 须为 IPv4 地址") from exc

    token, error = get_access_token(force_refresh=True)
    if token and not error:
        return {"ok": True, "required_ip": required, "observed_ip": None}

    observed = invalid_ip_from_error(error)
    if observed and observed != required:
        raise RuntimeError(f"微信 API 出口 {observed} 与要求 {required} 不一致")
    if observed == required:
        raise RuntimeError(f"微信 API 已走目标出口 {required}，但该 IP 尚未被白名单放行")
    raise RuntimeError(f"微信 API 出口预检失败: {(error or {}).get('errcode')}")


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


def _body_paragraph_style(*, article_kind: str | None = None) -> str:
    from scripts.tools.wechat_mp_layout import active_layout

    k = (article_kind or "").strip().lower()
    if k == "discussion":
        return (
            "margin:0 0 14px;padding:0;"
            "line-height:1.88;font-size:16px;color:#333333;"
            "letter-spacing:0.02em;"
        )
    layout = active_layout()
    return (
        f"margin:{layout.para_margin};padding:0;"
        "line-height:1.72;font-size:16px;color:#333333;"
        "letter-spacing:0.01em;"
    )


def _body_list_style() -> str:
    from scripts.tools.wechat_mp_layout import active_layout

    layout = active_layout()
    return (
        f"margin:{layout.list_margin};padding-left:1.2em;"
        "line-height:1.65;color:#333333;"
    )


_SECTION_HEAD_RE = re.compile(r"^[一二三四五六七八九十]、")
_NEWS_HEAD_RE = re.compile(r"^\[(利好|利空|中性)\]")
_NEWS_ITEM_RE = re.compile(r"^\d+\.\s*(\[(利好|利空|中性)\]|(?:利好|利空|中性)｜)")
_NEWS_AI_RE = re.compile(r"^AI点评[：:]")
_NEWS_LABEL_RE = re.compile(r"^(地缘|国内)[：:]?\s*$")
_NEWS_SUMMARY_RE = re.compile(r"^\s{2,}\S")


def _is_news_content_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if _NEWS_HEAD_RE.match(s):
        return True
    if _NEWS_ITEM_RE.match(s):
        return True
    if _NEWS_AI_RE.match(s):
        return True
    if _NEWS_LABEL_RE.match(s):
        return True
    if _NEWS_SUMMARY_RE.match(line):
        return True
    return False


def _block_is_news_cluster(lines: list[str]) -> bool:
    non_empty = [ln for ln in lines if ln.strip()]
    if not non_empty:
        return False
    return all(_is_news_content_line(ln) for ln in non_empty)


def _next_nonempty_line(lines: list[str], start: int) -> tuple[int, str] | None:
    for j in range(start, len(lines)):
        if lines[j].strip():
            return j, lines[j]
    return None


_FIGURE_BODY_RE = re.compile(r"^\[\[fig:[^|\]]+\|[^\]]*\]\]\s*$")
_CTA_BODY_RE = re.compile(r"^\[\[cta:[^\]]+\]\]\s*$")


def _is_figure_line(line: str) -> bool:
    return bool(_FIGURE_BODY_RE.match(line.strip()))


def _is_cta_line(line: str) -> bool:
    return bool(_CTA_BODY_RE.match(line.strip()))


def split_wechat_body_blocks(text: str) -> list[str]:
    """
    分段落块。快讯区不把「空行」当成新段落，避免每条 [利好] 新闻各包一个 <p> 拉大留白。
    """
    from scripts.tools.wechat_mp_rich_html import is_blockquote_title_line

    lines = text.splitlines()
    blocks: list[list[str]] = []
    cur: list[str] = []

    def flush() -> None:
        if cur:
            blocks.append(cur[:])
            cur.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            nxt = _next_nonempty_line(lines, i + 1)
            if nxt is None:
                flush()
                break
            _, next_line = nxt
            ns = next_line.strip()
            if _SECTION_HEAD_RE.match(ns) or is_blockquote_title_line(ns):
                flush()
            elif _is_figure_line(next_line) or _is_cta_line(next_line):
                flush()
            elif cur and _block_is_news_cluster(cur) and _is_news_content_line(next_line):
                pass
            elif _is_news_content_line(next_line) and cur and not _block_is_news_cluster(cur):
                flush()
            elif cur and _block_is_news_cluster(cur) and not _is_news_content_line(next_line):
                flush()
            elif (
                cur
                and len(cur) == 1
                and _SECTION_HEAD_RE.match(cur[0].strip())
                and not _is_news_content_line(next_line)
            ):
                flush()
            elif cur and not _block_is_news_cluster(cur) and not _is_news_content_line(next_line):
                flush()
            i += 1
            continue

        if _is_figure_line(line) or _is_cta_line(line):
            flush()
            cur.append(line)
            flush()
            i += 1
            continue

        if is_blockquote_title_line(line.strip()):
            flush()
            cur.append(line)
            i += 1
            continue

        if _SECTION_HEAD_RE.match(line.strip()):
            flush()
            cur.append(line)
            i += 1
            continue

        if _is_news_content_line(line):
            if cur and not _block_is_news_cluster(cur):
                flush()
            cur.append(line)
            i += 1
            continue

        if cur and _block_is_news_cluster(cur):
            flush()
        cur.append(line)
        i += 1

    flush()
    return ["\n".join(b) for b in blocks]


def _body_news_paragraph_style(*, kind: str = "body") -> str:
    from scripts.tools.wechat_mp_layout import active_layout

    layout = active_layout()
    if kind == "title":
        return (
            f"margin:{layout.news_title_margin};padding:0;"
            f"line-height:{layout.news_line_height};font-size:{layout.news_title_size};"
            "color:#1a1a1a;letter-spacing:0.01em;"
        )
    if kind == "ai":
        return (
            f"margin:{layout.news_ai_margin};padding:0;"
            f"line-height:{layout.news_line_height};font-size:{layout.news_body_size};"
            "color:#333333;letter-spacing:0.01em;"
        )
    if kind == "summary":
        return (
            f"margin:{layout.news_summary_margin};padding:0;"
            f"line-height:{layout.news_line_height};font-size:{layout.news_body_size};"
            "color:#333333;letter-spacing:0.01em;"
        )
    return (
        f"margin:{layout.news_margin};padding:0;"
        f"line-height:{layout.news_line_height};font-size:{layout.news_body_size};"
        "color:#333333;"
    )


def _news_line_kind(line: str) -> str:
    s = line.strip()
    if _NEWS_ITEM_RE.match(s):
        return "title"
    if _NEWS_AI_RE.match(s):
        return "ai"
    if _NEWS_SUMMARY_RE.match(line):
        return "summary"
    return "body"


def _append_news_cluster(parts: list[str], lines: list[str]) -> None:
    for line in lines:
        kind = _news_line_kind(line)
        parts.append(
            f'<p style="{_body_news_paragraph_style(kind=kind)}">{_line_to_html(line)}</p>'
        )


def _append_body_lines(
    parts: list[str],
    lines: list[str],
    *,
    lede_first_para: bool = False,
    article_kind: str | None = None,
) -> bool:
    """追加正文段落；若 `lede_first_para` 则首段用开篇样式。返回是否已应用开篇样式。"""
    if not lines:
        return False
    if _block_is_news_cluster(lines):
        _append_news_cluster(parts, lines)
        return False
    if len(lines) == 1 and lines[0].startswith("·"):
        parts.append(
            f'<p style="{_body_paragraph_style(article_kind=article_kind)}">'
            f"{_line_to_html(lines[0])}</p>"
        )
        return False
    if all(line.startswith("·") for line in lines):
        items = "".join(
            f"<li>{_line_to_html(line.lstrip('·').strip())}</li>" for line in lines
        )
        parts.append(f'<ul style="{_body_list_style()}">{items}</ul>')
        return False
    if len(lines) == 1 and lines[0].strip().startswith("（配图"):
        parts.append(
            f'<p style="margin:6px 0 2px;font-size:10px;line-height:1.45;'
            f'color:#aaa;text-align:center;">{_line_to_html(lines[0].strip())}</p>'
        )
        return False
    stripped_lines = [ln for ln in lines if ln.strip()]
    if stripped_lines and all(ln.strip().startswith("> ") for ln in stripped_lines):
        from scripts.tools.wechat_mp_rich_html import blockquote_body_html

        bare = [ln.strip()[2:].strip() for ln in stripped_lines]
        parts.append(blockquote_body_html(bare))
        return lede_first_para
    from scripts.tools.wechat_mp_rich_html import opening_lede_paragraph_style

    style = (
        opening_lede_paragraph_style()
        if lede_first_para
        else _body_paragraph_style(article_kind=article_kind)
    )
    inner = "<br/>".join(_line_to_html(x) for x in lines)
    parts.append(f'<p style="{style}">{inner}</p>')
    return lede_first_para


def upload_article_image(image_path: Path) -> tuple[str | None, dict[str, Any] | None]:
    """上传图文消息正文图片，返回 (url, error_json)。草稿 content 仅接受此 URL。"""
    token, err = get_access_token()
    if err:
        return None, err
    path = Path(image_path)
    if not path.is_file():
        return None, {"errcode": -1, "errmsg": f"正文图片不存在: {path}"}

    url = f"{API_BASE}/media/uploadimg"
    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    with path.open("rb") as fh:
        resp = _mp_session().post(
            url,
            params={"access_token": token},
            files={"media": (path.name, fh, mime)},
            timeout=60,
        )
    try:
        data = resp.json()
    except Exception:
        snippet = (resp.text or "")[:200]
        return None, {"errcode": -1, "errmsg": f"uploadimg 非 JSON: {snippet}"}
    if data.get("errcode"):
        return None, data
    img_url = str(data.get("url") or "").strip()
    if not img_url:
        return None, {"errcode": -1, "errmsg": "uploadimg 未返回 url"}
    return img_url, None


def _text_prose_to_html(
    text: str,
    *,
    upload_figures: bool = True,
    local_figure_preview: bool = False,
    seen_section: bool = False,
    prev_was_figure: bool = False,
    lede_done: bool = False,
    article_kind: str | None = None,
) -> tuple[list[str], bool, bool, bool]:
    """将无 ``` 围栏的散文转为 HTML 片段。"""
    from scripts.tools.wechat_mp_rich_html import OPENING_LEDE_KINDS

    parts: list[str] = []
    kind = (article_kind or "").strip().lower()
    want_lede_kind = kind in OPENING_LEDE_KINDS

    def _want_opening_lede() -> bool:
        if not want_lede_kind or lede_done:
            return False
        if kind == "market":
            return not seen_section
        if kind == "discussion":
            return not seen_section
        return False

    for block in split_wechat_body_blocks(text):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        from scripts.tools.wechat_mp_figures import figure_to_html, parse_figure_line
        from scripts.tools.wechat_mp_rich_html import (
            blockquote_title_html,
            cta_box_html,
            is_blockquote_title_line,
            parse_cta_line,
        )

        if len(lines) == 1:
            cta_parts = parse_cta_line(lines[0])
            if cta_parts:
                parts.append(cta_box_html(cta_parts))
                prev_was_figure = True
                continue
            fig = parse_figure_line(lines[0])
            if fig:
                fname, caption = fig
                if prev_was_figure:
                    parts.append(
                        '<p style="margin:0;padding:0;height:12px;line-height:12px;'
                        'font-size:12px;">&nbsp;</p>'
                    )
                img_url: str | None = None
                if mp_configured():
                    from scripts.tools.wechat_mp_figures import (
                        inline_figure_url_from_cache,
                        upload_inline_figure,
                    )

                    if upload_figures:
                        img_url, up_err = upload_inline_figure(fname)
                        if up_err:
                            append_alert(f"FIGURE upload fail {fname}: {up_err}")
                    else:
                        img_url = inline_figure_url_from_cache(fname)
                parts.append(
                    figure_to_html(
                        fname,
                        caption,
                        image_url=img_url,
                        local_preview=local_figure_preview and not img_url,
                    )
                )
                prev_was_figure = True
                continue

        if lines and is_blockquote_title_line(lines[0]):
            parts.append(
                blockquote_title_html(
                    lines[0],
                    tight_top=prev_was_figure,
                    first_section=not seen_section,
                    article_kind=kind or None,
                )
            )
            seen_section = True
            prev_was_figure = False
            body_lines = [ln for ln in lines[1:] if ln.strip()]
            if body_lines:
                if _append_body_lines(
                    parts,
                    body_lines,
                    lede_first_para=_want_opening_lede(),
                    article_kind=kind or None,
                ):
                    lede_done = True
            continue
        prev_was_figure = False
        if _want_opening_lede():
            if _append_body_lines(
                parts, lines, lede_first_para=True, article_kind=kind or None
            ):
                lede_done = True
        else:
            _append_body_lines(parts, lines, article_kind=kind or None)
    return parts, seen_section, prev_was_figure, lede_done


def text_to_html(
    text: str,
    *,
    upload_figures: bool = True,
    local_figure_preview: bool = False,
    article_kind: str | None = None,
) -> str:
    from scripts.tools.wechat_format import split_body_code_fences
    from scripts.tools.wechat_mp_rich_html import code_block_html

    parts: list[str] = []
    seen_section = False
    prev_was_figure = False
    lede_done = False
    for fence_kind, lang, chunk in split_body_code_fences(text):
        if fence_kind == "code":
            if chunk.strip():
                parts.append(code_block_html(chunk, lang=lang))
            prev_was_figure = False
            continue
        prose = chunk.strip()
        if not prose:
            continue
        sub_parts, seen_section, prev_was_figure, lede_done = _text_prose_to_html(
            prose,
            upload_figures=upload_figures,
            local_figure_preview=local_figure_preview,
            seen_section=seen_section,
            prev_was_figure=prev_was_figure,
            lede_done=lede_done,
            article_kind=article_kind,
        )
        parts.extend(sub_parts)
    return "\n".join(parts) or "<p>（空）</p>"


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _escape_html_plain(text: str) -> str:
    """纯文本转 HTML：不转义 >，避免 -> 复制成 -&gt;。"""
    return text.replace("&", "&amp;").replace("<", "&lt;")


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


# 四槽位默认封面（素材名子串，须与公众平台素材库文件名一致）
_DEFAULT_KIND_THUMB_NAMES: dict[str, str] = {
    "sector": "封面-牛马品牌-双封面",
    "market": "封面-交易所屏-双封面",
    "news": "封面-显示器走势-双封面",
    "hotspot": "封面-牛马品牌-双封面",
    "hot_business": "封面-牛马品牌-双封面",
    "workspace": "封面-数据大屏-双封面",
    "temp": "封面-数据大屏-双封面",
    "guba": "封面-牛马品牌-双封面",
}

_DEFAULT_KIND_THUMB_ASSETS: dict[str, Path] = {
    "tv_review": ROOT / "assets" / "wechat_mp" / "cover-tv" / "euphoria-hbo-neon.jpg",
}

# 带货预览会上传 avatar 等到同一素材库；财经选封面须排除，禁止回退到「最新一张」
_FINANCE_THUMB_DENY_SUBSTR: tuple[str, ...] = ("avatar", "简选")

_KIND_THUMB_FALLBACKS: dict[str, tuple[str, ...]] = {
    "news": ("封面-多屏行情-双封面", "封面-平板分析-双封面", "多屏行情"),
    "hotspot": ("封面-牛马品牌-双封面", "牛马品牌", "banner"),
    "hot_business": ("封面-牛马品牌-双封面", "牛马品牌", "banner"),
}


def _material_name_blob(item: dict[str, Any]) -> str:
    return " ".join(
        (
            _material_display_name(item),
            str(item.get("name") or ""),
            str(item.get("name_raw") or ""),
        )
    ).lower()


def _is_finance_thumb_material(item: dict[str, Any]) -> bool:
    blob = _material_name_blob(item)
    return not any(d in blob for d in _FINANCE_THUMB_DENY_SUBSTR)


def pick_thumb_from_material_library(
    *,
    name_sub: str | None = None,
    media_id_preset: str | None = None,
    use_global_preset: bool = True,
    finance_only: bool = False,
    allow_latest_fallback: bool = True,
) -> tuple[str | None, dict[str, Any] | None]:
    """
    从素材库选封面 thumb_media_id。
    优先级：media_id_preset → 全局 WECHAT_MP_THUMB_MEDIA_ID（可选）
    → name_sub / WECHAT_MP_THUMB_NAME → WECHAT_MP_THUMB_INDEX → 最新一张图。
    finance_only=True 时排除带货 avatar/简选 素材；allow_latest_fallback=False 时不回退最新图。
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

    pool = [it for it in items if _is_finance_thumb_material(it)] if finance_only else items
    if finance_only and not pool:
        return None, {
            "errcode": -1,
            "errmsg": "素材库无可用财经封面（已排除带货 avatar/简选 图）；请上传「封面-*-双封面」或设置 WECHAT_MP_THUMB_NAME_NEWS 等",
        }

    if name_sub is None:
        name_sub = _env("WECHAT_MP_THUMB_NAME", "机器人图")
    if name_sub:
        for it in pool:
            display = _material_display_name(it)
            if name_sub in display or name_sub in str(it.get("name_raw") or ""):
                return str(it["media_id"]), None
        if finance_only and not allow_latest_fallback:
            return None, {
                "errcode": -1,
                "errmsg": (
                    f"未匹配财经封面「{name_sub}」（已排除带货 avatar）。"
                    f"请上传对应素材或设置 WECHAT_MP_THUMB_NAME_*"
                ),
            }

    if finance_only and not allow_latest_fallback:
        return None, {
            "errcode": -1,
            "errmsg": "财经封面未指定或未匹配，已禁止回退到素材库最新图（防误用带货 avatar）",
        }

    idx_raw = _env("WECHAT_MP_THUMB_INDEX")
    if idx_raw:
        try:
            idx = int(idx_raw)
            if 0 <= idx < len(items):
                return str(items[idx]["media_id"]), None
        except ValueError:
            pass

    skip_default = _env("WECHAT_MP_THUMB_SKIP_DEFAULT", "1").lower() not in {"0", "false", "no"}
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


def _sector_banner_thumb_path() -> Path:
    """行业稿封面 = 正文品牌头 banner（牛马图），与 masthead 同源。"""
    explicit = _env("WECHAT_MP_SECTOR_THUMB_PATH")
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_file():
            return path
        raise FileNotFoundError(f"WECHAT_MP_SECTOR_THUMB_PATH 不存在: {path}")
    from scripts.tools.wechat_mp_masthead import resolve_banner_path

    return resolve_banner_path(kind="sector")


def _load_sector_banner_thumb_cache() -> dict[str, Any] | None:
    if not SECTOR_BANNER_THUMB_CACHE.is_file():
        return None
    try:
        return json.loads(SECTOR_BANNER_THUMB_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_sector_banner_thumb_cache(media_id: str, *, source: str, cache_key: str) -> None:
    SECTOR_BANNER_THUMB_CACHE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "media_id": media_id,
        "source": source,
        "cache_key": cache_key,
        "updated_at": datetime.now(TZ).isoformat(),
    }
    SECTOR_BANNER_THUMB_CACHE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _kind_thumb_from_assets_enabled(kind: str) -> bool:
    k = (kind or "").strip().lower()
    if k not in _DEFAULT_KIND_THUMB_ASSETS:
        return False
    per = _env(f"WECHAT_MP_{k.upper()}_THUMB_FROM_ASSETS", "")
    if per:
        return per.lower() not in ("0", "false", "no", "off")
    return _env("WECHAT_MP_KIND_THUMB_FROM_ASSETS", "1").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _kind_thumb_asset_path(kind: str) -> Path | None:
    k = (kind or "").strip().lower()
    explicit = _env(f"WECHAT_MP_THUMB_PATH_{k.upper()}")
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_file():
            return path
        raise FileNotFoundError(f"WECHAT_MP_THUMB_PATH_{k.upper()} 不存在: {path}")
    path = _DEFAULT_KIND_THUMB_ASSETS.get(k)
    if path is not None and path.is_file():
        return path
    return None


def _load_kind_thumb_asset_cache(kind: str) -> dict[str, Any] | None:
    cache_path = _KIND_THUMB_ASSET_CACHE.get(kind)
    if not cache_path or not cache_path.is_file():
        return None
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_kind_thumb_asset_cache(
    kind: str,
    media_id: str,
    *,
    source: str,
    cache_key: str,
) -> None:
    cache_path = _KIND_THUMB_ASSET_CACHE.get(kind)
    if not cache_path:
        return
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "media_id": media_id,
        "source": source,
        "cache_key": cache_key,
        "updated_at": datetime.now(TZ).isoformat(),
    }
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def pick_kind_thumb_from_local_asset(
    kind: str,
    *,
    force_reupload: bool = False,
) -> tuple[str | None, dict[str, Any] | None]:
    """上传配置为本地文件的稿型封面。"""
    k = (kind or "").strip().lower()
    if not _kind_thumb_from_assets_enabled(k):
        return None, {
            "errcode": -1,
            "errmsg": (
                f"未启用本地封面（WECHAT_MP_{k.upper()}_THUMB_FROM_ASSETS=0）；"
                "或设置 WECHAT_MP_THUMB_PATH_{KIND}"
            ),
        }
    try:
        path = _kind_thumb_asset_path(k)
    except FileNotFoundError as exc:
        return None, {"errcode": -1, "errmsg": str(exc)}
    if path is None:
        return None, {
            "errcode": -1,
            "errmsg": f"未找到 {k} 默认封面文件（assets/wechat_mp/cover-*-dual.jpg）",
        }

    import hashlib

    cache_key = hashlib.md5(path.read_bytes()).hexdigest()[:16]
    if not force_reupload:
        cached = _load_kind_thumb_asset_cache(k)
        if (
            cached
            and str(cached.get("cache_key") or "") == cache_key
            and cached.get("media_id")
        ):
            return str(cached["media_id"]), None

    media_id, err = add_permanent_image(path)
    if err or not media_id:
        return None, err or {"errcode": -1, "errmsg": f"上传 {k} 本地封面失败"}
    _save_kind_thumb_asset_cache(k, media_id, source=str(path), cache_key=cache_key)
    return media_id, None


def pick_sector_thumb_from_banner(*, force_reupload: bool = False) -> tuple[str | None, dict[str, Any] | None]:
    """素材库无「封面-牛马品牌」时，上传 assets/wechat_mp/banner.png 作 sector 封面。"""
    if _env("WECHAT_MP_SECTOR_THUMB_FROM_BANNER", "1").lower() in ("0", "false", "no", "off"):
        return None, {
            "errcode": -1,
            "errmsg": "未匹配素材库封面；可在素材库上传「封面-牛马品牌-双封面」或保持 WECHAT_MP_SECTOR_THUMB_FROM_BANNER=1",
        }
    try:
        path = _sector_banner_thumb_path()
    except FileNotFoundError as exc:
        return None, {"errcode": -1, "errmsg": str(exc)}

    import hashlib

    cache_key = hashlib.md5(path.read_bytes()).hexdigest()[:16]
    if not force_reupload:
        cached = _load_sector_banner_thumb_cache()
        if (
            cached
            and str(cached.get("cache_key") or "") == cache_key
            and cached.get("media_id")
        ):
            return str(cached["media_id"]), None

    media_id, err = add_permanent_image(path)
    if err or not media_id:
        return None, err or {"errcode": -1, "errmsg": "上传 sector banner 封面失败"}
    _save_sector_banner_thumb_cache(media_id, source=str(path), cache_key=cache_key)
    return media_id, None


def pick_thumb_for_draft_kind(kind: str) -> tuple[str | None, dict[str, Any] | None]:
    """
    按封面资源 kind 选 thumb（sector / hotspot / tv_review 等素材或本地图）。
    环境变量：WECHAT_MP_THUMB_MEDIA_ID_{KIND}、WECHAT_MP_THUMB_NAME_{KIND}
    与带货隔离：排除 avatar/简选 素材，且禁止「最新一张」回退。
    sector：素材库「封面-牛马品牌」→ 否则上传 banner.png。
    注意：evening 批次「内容 kind」与「封面 kind」解耦，见 wechat_mp_draft_batch.cover_kind_for_content。
    """
    k = (kind or "").strip().lower()
    env_suffix = k.upper()
    media_preset = _env(f"WECHAT_MP_THUMB_MEDIA_ID_{env_suffix}")
    if media_preset:
        return media_preset, None
    if _kind_thumb_from_assets_enabled(k):
        mid, err = pick_kind_thumb_from_local_asset(k)
        if mid:
            return mid, None
    primary = _env(f"WECHAT_MP_THUMB_NAME_{env_suffix}") or _DEFAULT_KIND_THUMB_NAMES.get(k, "")
    candidates: list[str] = []
    for sub in (primary, *_KIND_THUMB_FALLBACKS.get(k, ())):
        if sub and sub not in candidates:
            candidates.append(sub)
    last_err: dict[str, Any] | None = None
    for name_sub in candidates:
        mid, err = pick_thumb_from_material_library(
            name_sub=name_sub,
            media_id_preset=media_preset if name_sub == primary else None,
            use_global_preset=False,
            finance_only=True,
            allow_latest_fallback=False,
        )
        if mid:
            return mid, None
        last_err = err
    if k in {"sector", "guba", "hotspot", "hot_business"}:
        mid, err = pick_sector_thumb_from_banner()
        if mid:
            return mid, None
        last_err = err or last_err
    return None, last_err or {
        "errcode": -1,
        "errmsg": f"财经槽位 {k} 未匹配任何封面候选: {', '.join(candidates)}",
    }


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


def fetch_draft_news_item(
    *,
    media_id: str,
    max_items: int = 100,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """按 media_id 拉取草稿首篇图文（含 content HTML）。"""
    target = (media_id or "").strip()
    if not target:
        return None, {"errcode": -1, "errmsg": "media_id 为空"}
    offset = 0
    while offset < max_items:
        chunk, err = draft_batchget(offset=offset, count=20, no_content=False)
        if err:
            return None, err
        if not chunk:
            break
        for item in chunk:
            if str(item.get("media_id") or "") != target:
                continue
            news = (item.get("content") or {}).get("news_item") or []
            if news and isinstance(news[0], dict):
                return news[0], None
            return None, {"errcode": -1, "errmsg": "草稿无 news_item"}
        offset += len(chunk)
        if len(chunk) < 20:
            break
    return None, {"errcode": -1, "errmsg": f"未找到 media_id={target}"}


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


def freepublish_batchget(
    *,
    offset: int = 0,
    count: int = 20,
    no_content: bool = True,
) -> tuple[list[dict[str, Any]], int, dict[str, Any] | None]:
    """已发布（未群发通知）列表；返回 (items, total_count, error_json)。"""
    token, err = get_access_token()
    if err:
        return [], 0, err
    count = max(1, min(20, count))
    url = f"{API_BASE}/freepublish/batchget"
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
        return [], 0, data
    items = list(data.get("item") or [])
    total = int(data.get("total_count") or 0)
    return items, total, None


def get_product_card_info(
    *,
    product_id: str,
    article_type: str = "news",
    card_type: int = 1,
    extra: dict[str, Any] | None = None,
    cookie: str = "",
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """返佣商品卡片：获取 product_key / DOM（文末 footer 用 product_key）。"""
    token, err = get_access_token()
    if err:
        return {}, err
    url = "https://api.weixin.qq.com/channels/ec/service/product/getcardinfo"
    payload: dict[str, Any] = {
        "product_id": str(product_id),
        "article_type": article_type,
        "card_type": card_type,
    }
    if extra:
        payload.update(extra)
    headers: dict[str, str] | None = None
    ck = (cookie or _env("WECHAT_MP_DAIHUO_COOKIE")).strip()
    if ck:
        headers = {"Cookie": ck}
    data = _mp_post_json(
        url,
        params={"access_token": token},
        payload=payload,
        headers=headers,
    )
    if data.get("errcode"):
        return {}, data
    return data, None


def list_all_freepublish(*, max_items: int = 5000) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """分页拉取全部 freepublish 记录（默认最多 5000）。"""
    all_items: list[dict[str, Any]] = []
    offset = 0
    total = 0
    while offset < max_items:
        chunk, total, err = freepublish_batchget(offset=offset, count=20, no_content=True)
        if err:
            return all_items, err
        if not chunk:
            break
        all_items.extend(chunk)
        offset += len(chunk)
        if total and offset >= total:
            break
        if len(chunk) < 20:
            break
    return all_items, None


def freepublish_delete(*, article_id: str, index: int = 0) -> dict[str, Any] | None:
    """删除已发布文章（不可逆）。index=0 删除该 article_id 下全部图文。"""
    token, err = get_access_token()
    if err:
        return err
    url = f"{API_BASE}/freepublish/delete"
    payload: dict[str, Any] = {"article_id": article_id}
    if index:
        payload["index"] = index
    data = _mp_post_json(url, params={"access_token": token}, payload=payload)
    if data.get("errcode"):
        return data
    return None


def freepublish_first_title(item: dict[str, Any]) -> str:
    content = item.get("content") or {}
    news = content.get("news_item") or []
    if news and isinstance(news[0], dict):
        return normalize_draft_text(str(news[0].get("title") or ""))
    return ""


def batchget_material_news(
    *,
    offset: int = 0,
    count: int = 20,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """拉取永久图文素材列表（素材库 news）。"""
    token, err = get_access_token()
    if err:
        return [], err
    count = max(1, min(20, count))
    url = f"{API_BASE}/material/batchget_material"
    data = _mp_post_json(
        url,
        params={"access_token": token},
        payload={"type": "news", "offset": offset, "count": count},
    )
    if data.get("errcode"):
        return [], data
    return list(data.get("item") or []), None


def list_all_material_news(*, max_items: int = 5000) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """分页拉取全部 news 永久素材。"""
    all_items: list[dict[str, Any]] = []
    offset = 0
    while offset < max_items:
        chunk, err = batchget_material_news(offset=offset, count=20)
        if err:
            return all_items, err
        if not chunk:
            break
        all_items.extend(chunk)
        offset += len(chunk)
        if len(chunk) < 20:
            break
    return all_items, None


def material_news_first_title(item: dict[str, Any]) -> str:
    content = item.get("content") or {}
    news = content.get("news_item") or []
    if news and isinstance(news[0], dict):
        return normalize_draft_text(str(news[0].get("title") or ""))
    return ""


def get_material_count() -> tuple[dict[str, int], dict[str, Any] | None]:
    """返回各类型永久素材数量，如 news_count / image_count。"""
    token, err = get_access_token()
    if err:
        return {}, err
    url = f"{API_BASE}/material/get_materialcount"
    resp = _mp_session().get(url, params={"access_token": token}, timeout=30)
    data = resp.json()
    if data.get("errcode"):
        return {}, data
    counts = {k: int(v) for k, v in data.items() if k.endswith("_count")}
    return counts, None
