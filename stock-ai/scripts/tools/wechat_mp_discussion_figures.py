#!/usr/bin/env python3
"""话题讨论稿配图：公开报道 og:image 下载 + 段落间注入。"""

from __future__ import annotations

import hashlib
import os
import re
import urllib.request
from html import unescape
from pathlib import Path
from typing import Any

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_figures import FIGURE_LINE_RE, _figure_marker_lines
from scripts.tools.wechat_mp_discussion_research import fetch_discussion_research
from scripts.tools.wechat_mp_hotspot_research import ResearchHit

ROOT = Path(__file__).resolve().parents[2]
INLINE_DISCUSSION_ROOT = ROOT / "assets" / "wechat_mp" / "inline-discussion"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_OG_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:image(?::url)?["\'][^>]+content=["\']([^"\']+)["\']',
    re.I,
)
_OG_IMAGE_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image(?::url)?["\']',
    re.I,
)
_IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)
_LAZY_IMG_RE = re.compile(
    r'<(?:img|source)[^>]+(?:data-src|data-original|data-lazy-src|data-url)=["\']([^"\']+)["\']',
    re.I,
)
_CONTENT_IMG_RE = re.compile(
    r"https://[^\s\"'<>]+(?:newspic|sinakd|dingyue|sinaimg|126\.net|gtimg|qpic|ifengimg|imgcdc|baidu|zhimg|toutiaoimg)[^\s\"'<>]*",
    re.I,
)
_SKIP_IMG_HINTS = (
    "kline",
    "metadata",
    "logo",
    "icon",
    "qrcode",
    "sprite",
    "w145h95",
    "w95h",
    "1x1.png",
    "default/1x1",
    "avatar",
    "/130x0/",
    "/barcode/",
    "fotomore",
    "ifeng/client",
    "ifengnews",
    "matrix",
    "binary",
    "hacker",
    "cyber",
    "stock_photo",
    "shutterstock",
    "gettyimages",
    "placeholder",
    "default_cover",
    "banner_ad",
)
_STOCK_ILLUSTRATION_URL_HINTS = (
    "matrix",
    "binary",
    "hacker",
    "cyber",
    "code_bg",
    "programming",
    "keyboard",
    "stock",
    "illustration",
    "concept",
    "abstract",
    "wallpaper",
    "banner",
    "default",
    "placeholder",
)
_VIDEO_FRAME_SIZES: frozenset[tuple[int, int]] = frozenset(
    {
        (1280, 720),
        (1080, 720),
        (960, 540),
        (854, 480),
        (640, 360),
        (720, 1280),
        (720, 1080),
        (540, 960),
    }
)
_TECH_TOPIC_PAGE_HOST_BOOSTS = (
    ("tech.sina.com.cn", 40),
    ("finance.sina.com.cn/tech", 35),
    ("36kr.com", 35),
    ("ithome.com", 30),
    ("jiemian.com/article", 20),
    ("thepaper.cn", 25),
    ("stcn.com", 20),
)
_SOCIAL_VIDEO_PAGE_HINTS = (
    "/socialgd/",
    "/video/",
    "/v/",
    "video.sina",
    "v.qq.com",
)
_TV_BROADCAST_IMG_HINTS = (
    "cctv.com",
    "cntv.cn",
    "cmntv",
    "/video/",
    "vthumb",
    "broadcast",
    "livephoto",
    "news_banner",
)
_EVENT_IMG_HOSTS = (
    "np-newspic.dfcfw.com",
    "k.sinaimg.cn",
    "n.sinaimg.cn",
    "sinaimg.cn",
    "nimg.ws.126.net",
    "dingyue.ws.126.net",
    "videoimg.ws.126.net",
    "img.jinantimes.com.cn",
    "attach.setn.com",
    "inews.gtimg.com",
    "qpic.cn",
    "ifengimg.com",
    "imgcdc.com",
    "utuku.china.com",
    "utuku.imgcdc.com",
    "pic.rmb.bdstatic.com",
    "img.baidu.com",
    "bcebos.com",
    "zhimg.com",
    "doubanio.com",
    "toutiaoimg.com",
    "pstatp.com",
    "byteimg.com",
    "cctv.com",
    "xinhuanet.com",
    "people.com.cn",
    "cyol.com",
    "gmw.cn",
    "chinanews.com",
    "thepaper.cn",
    "sohu.com",
    "qq.com",
    "163.com",
    "huanqiu.com",
    "bjnews.com.cn",
    "jiemian.com",
    "yicai.com",
    "caixin.com",
)
_NEWS_PAGE_HOST_HINTS = (
    "163.com",
    "sina.com.cn",
    "sina.cn",
    "sohu.com",
    "qq.com",
    "ifeng.com",
    "thepaper.cn",
    "china.com",
    "huanqiu.com",
    "people.com.cn",
    "xinhuanet.com",
    "cctv.com",
    "chinanews.com.cn",
    "bjnews.com.cn",
    "toutiao.com",
    "baidu.com",
)

_MIN_FIGURE_BYTES = 18_000
_MAX_FIGURE_BYTES = 450_000
_MIN_FIGURE_WIDTH = 280
_MIN_FIGURE_HEIGHT = 200


def _min_figure_bytes() -> int:
    try:
        return max(8000, int(os.getenv("WECHAT_MP_DISCUSSION_FIGURE_MIN_BYTES", str(_MIN_FIGURE_BYTES))))
    except ValueError:
        return _MIN_FIGURE_BYTES


_DISCUSSION_FIGURE_STYLE = "max-h=520;fit=contain"
_FIGURE_SOURCES_META = "figure_sources.json"
_OFFTOPIC_PAGE_TITLE_HINTS = (
    "韩剧",
    "netflix",
    "网剧",
    "综艺",
    "票房",
    "影评",
    "剧评",
    "nba",
    "篮球",
    "勇士",
    "湖人",
    "cba",
    "足球",
    "欧冠",
    "日军",
    "抗战",
    "谍战",
    "仪仗",
    "阅兵",
    "武侠",
    "仙侠",
    "爱豆",
    "追星",
    "漫威",
    "迪士尼",
)


def _figure_sources_meta_path(out_dir: Path) -> Path:
    return out_dir / _FIGURE_SOURCES_META


def _load_figure_sources(out_dir: Path) -> dict[str, dict[str, str]]:
    path = _figure_sources_meta_path(out_dir)
    if not path.is_file():
        return {}
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): dict(v) for k, v in data.items() if isinstance(v, dict)}
    except Exception:
        pass
    return {}


def _save_figure_sources(out_dir: Path, meta: dict[str, dict[str, str]]) -> None:
    import json

    out_dir.mkdir(parents=True, exist_ok=True)
    _figure_sources_meta_path(out_dir).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _topic_figure_keywords(topic: dict[str, Any]) -> list[str]:
    from scripts.tools.wechat_mp_discussion_research import _event_keywords

    return _event_keywords(topic)


def _offtopic_page_title(title: str, topic: dict[str, Any], keywords: list[str]) -> bool:
    low = (title or "").lower()
    if not any(h in low for h in _OFFTOPIC_PAGE_TITLE_HINTS):
        return False
    trend = str(topic.get("trend_title") or topic.get("title_zh") or "")
    if keywords and sum(1 for k in keywords if k in title) >= 2:
        return False
    if any(k in title for k in re.findall(r"[\u4e00-\u9fff]{2,8}", trend)[:6]):
        return False
    return True


def _page_relevant_for_figures(
    topic: dict[str, Any],
    *,
    page_url: str,
    html: str | None,
    hit: ResearchHit | None,
    keywords: list[str],
    strict: bool = True,
) -> tuple[bool, ResearchHit | None]:
    from scripts.tools.wechat_mp_discussion_research import _hit_relevant, _parse_article_page

    parsed = hit
    if parsed is None and html:
        parsed = _parse_article_page(page_url, html)
    if parsed is None:
        return False, None
    if _offtopic_page_title(parsed.title, topic, keywords):
        return False, parsed
    if strict and not _hit_relevant(parsed, keywords):
        return False, parsed
    if strict and not _strict_figure_page_relevant(topic, parsed, keywords):
        return False, parsed
    return True, parsed


def _strict_figure_page_relevant(
    topic: dict[str, Any], hit: ResearchHit, keywords: list[str]
) -> bool:
    """配图报道须与选题锚点一致，避免旧案/泛话题混入。"""
    trend = str(topic.get("trend_title") or topic.get("title_zh") or "")
    title = f"{hit.title} {hit.snippet}"
    anchors: list[str] = []
    tb_m = re.search(r"(\d+)\s*TB", trend, flags=re.I)
    if tb_m:
        anchors.extend([tb_m.group(1), f"{tb_m.group(1)}TB", "TB"])
    hr_m = re.search(r"(\d+)\s*小时", trend)
    if hr_m:
        anchors.append(f"{hr_m.group(1)}小时")
    for num in re.findall(r"\d{2,}", trend):
        if num not in anchors:
            anchors.append(num)
    for token in re.findall(r"[\u4e00-\u9fff]{4,12}", trend)[:4]:
        if token not in anchors:
            anchors.append(token)
    if not anchors:
        return True
    hit_n = sum(1 for a in anchors if a and a in title)
    if tb_m and hit_n < 1:
        return False
    if len(anchors) >= 4 and hit_n < 2:
        return False
    return hit_n >= 1


def _keyword_relevance_score(title: str, keywords: list[str]) -> int:
    if not title or not keywords:
        return 0
    return sum(2 if len(k) >= 4 else 1 for k in keywords if k in title)


def _filter_stills_with_meta(
    topic: dict[str, Any],
    paths: list[Path],
    meta: dict[str, dict[str, str]],
    keywords: list[str],
) -> list[Path]:
    from scripts.tools.wechat_mp_discussion_research import _hit_relevant

    out: list[Path] = []
    for p in paths:
        info = meta.get(p.name) or {}
        title = str(info.get("page_title") or "").strip()
        url = str(info.get("page_url") or "").strip()
        if not title:
            continue
        if _offtopic_page_title(title, topic, keywords):
            continue
        hit = ResearchHit(title=title, snippet=title, source="", url=url)
        if not _hit_relevant(hit, keywords):
            continue
        out.append(p)
    return out


def _distributed_inject_para_indices(num_blocks: int, num_figures: int) -> list[int]:
    """按全文均匀选插入点（0-based 段落块索引），避免短段模式下挤在开头。"""
    if num_figures <= 0 or num_blocks <= 0:
        return []
    n = num_blocks
    if num_figures >= n:
        return list(range(max(0, n - num_figures), n))

    start_skip = max(1, n // 8)
    end_reserve = max(1, n // 8)
    usable_end = max(start_skip + 1, n - end_reserve)
    span = max(1, usable_end - start_skip)
    min_step = max(2, span // (num_figures + 1))

    indices: list[int] = []
    for i in range(num_figures):
        if num_figures == 1:
            idx = start_skip + span // 2
        else:
            idx = start_skip + int((i + 0.5) * span / num_figures)
        idx = max(0, min(idx, n - 1))
        if indices and idx <= indices[-1]:
            idx = min(indices[-1] + min_step, n - 1)
        indices.append(idx)
    return indices


def discussion_figures_enabled() -> bool:
    raw = (os.getenv("WECHAT_MP_DISCUSSION_FIGURES") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def discussion_body_figure_target() -> int:
    """热点/话题正文固定三图；仅调试时允许通过 env 缩减。"""
    try:
        return max(0, min(3, int(os.getenv("WECHAT_MP_DISCUSSION_BODY_FIGURES", "3"))))
    except ValueError:
        return 3


def _slug(topic: dict[str, Any]) -> str:
    slug = str(topic.get("cover_slug") or "").strip().lower()
    if slug:
        return slug
    zh = str(topic.get("title_zh") or "").strip()
    safe = re.sub(r"[^\w\-]+", "-", zh).strip("-").lower()
    return safe or "discussion"


def resolve_discussion_inline_path(filename: str) -> Path:
    raw = (filename or "").strip().replace("\\", "/")
    parts = [p for p in Path(raw).parts if p and p not in {".", ".."}]
    if parts and parts[0] == "discussion":
        parts = parts[1:]
    path = INLINE_DISCUSSION_ROOT.joinpath(*parts)
    if not path.is_file():
        raise FileNotFoundError(f"话题讨论插图不存在: {path}")
    return path


def _research_query(topic: dict[str, Any]) -> str:
    trend = str(topic.get("trend_title") or "").strip()
    if trend:
        return trend[:24]
    return str(topic.get("title_zh") or "").strip()[:18]


def _normalize_image_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return u
    if u.startswith("//"):
        u = "https:" + u
    # 网易 nimg 包装层 → 解出原图
    if "nimg.ws.126.net" in u and "url=" in u:
        from urllib.parse import parse_qs, urlparse

        q = parse_qs(urlparse(u).query)
        inner = (q.get("url") or [""])[0]
        if inner.startswith("http"):
            u = inner
    # 新浪 http → https，去掉裁切后缀再试原图
    if "sinaimg.cn" in u or "sina.com.cn" in u:
        u = u.replace("http://", "https://")
        u = re.sub(r"/w\d+d\d+q$", "", u)
    if u.startswith("http://dingyue.ws.126.net"):
        u = u.replace("http://", "https://", 1)
    # 中华网 utuku：650x0 常 <25KB，升 1200x0 取更清晰原图
    if "utuku.imgcdc.com" in u:
        u = re.sub(r"/\d+x0/", "/1200x0/", u)
    return u


def _image_sort_score(url: str) -> int:
    score = _img_width(url)
    if "sinakd" in url:
        score += 800
    if "dingyue.ws.126.net" in url:
        score += 900
    if "w2048h" in url or "upload/" in url:
        score += 1200
    if "front" in url and "sinakd" not in url:
        score -= 300
    if "w200h200" in url or "w380h210" in url:
        score -= 500
    return score


def _is_news_article_page(page_url: str) -> bool:
    low = (page_url or "").lower()
    return any(h in low for h in _NEWS_PAGE_HOST_HINTS)


def _looks_like_content_photo(url: str) -> bool:
    """门户正文图启发式：非白名单 CDN 但路径像新闻配图。"""
    low = (url or "").lower()
    if _skip_image_url(url):
        return False
    if not re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", low):
        return False
    if re.search(r"w\d{1,2}h\d{1,2}", low):
        return False
    if any(
        x in low
        for x in (
            "/news/",
            "/photo/",
            "/pic/",
            "/upload/",
            "/img/",
            "newspic",
            "sinakd",
            "dingyue",
            "article",
            "content",
        )
    ):
        return True
    if _img_width(url) >= 420:
        return True
    return False


def _is_event_image_url(url: str, *, from_news_page: bool = False) -> bool:
    low = (url or "").lower()
    if _skip_image_url(url):
        return False
    if any(h in low for h in _EVENT_IMG_HOSTS):
        return True
    if re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", low) and "sinakd" in low:
        return True
    if from_news_page and _looks_like_content_photo(url):
        return True
    return False


def _content_images_from_html(html: str, page_url: str) -> list[str]:
    from_news = _is_news_article_page(page_url)
    found: list[str] = []
    for raw in _CONTENT_IMG_RE.findall(html):
        if _is_event_image_url(raw, from_news_page=from_news):
            found.append(raw)
    for pattern in (_IMG_SRC_RE, _LAZY_IMG_RE):
        for m in pattern.finditer(html):
            src = unescape(m.group(1).strip())
            if not src or src.startswith("data:"):
                continue
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                from urllib.parse import urljoin

                src = urljoin(page_url, src)
            if src.startswith("http") and _is_event_image_url(src, from_news_page=from_news):
                found.append(src)
    # og:image 兜底
    for pat in (_OG_IMAGE_RE, _OG_IMAGE_RE2):
        m = pat.search(html)
        if m:
            url = unescape(m.group(1).strip())
            if _is_event_image_url(url, from_news_page=True):
                found.append(url)
    uniq: dict[str, int] = {}
    for u in found:
        norm = _normalize_image_url(u)
        uniq[norm] = max(uniq.get(norm, 0), _image_sort_score(norm))
    return [u for u, _ in sorted(uniq.items(), key=lambda x: x[1], reverse=True)]


def _fetch_html(url: str, *, timeout: float = 14.0) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _UA, "Referer": url},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(180_000)
    return raw.decode("utf-8", errors="replace")


def _extract_image_url(html: str, page_url: str) -> str | None:
    content = _content_images_from_html(html, page_url)
    if content:
        return content[0]
    for pat in (_OG_IMAGE_RE, _OG_IMAGE_RE2):
        m = pat.search(html)
        if m:
            url = unescape(m.group(1).strip())
            if url and _is_event_image_url(url, from_news_page=True):
                return url
    return None


def _guess_ext(url: str, content_type: str = "") -> str:
    low = (url or "").lower()
    if ".png" in low or "png" in content_type:
        return ".png"
    if ".webp" in low or "webp" in content_type:
        return ".webp"
    return ".jpg"


def _download_image(url: str, dest: Path, *, referer: str = "") -> bool:
    try:
        ref = referer or url
        req = urllib.request.Request(
            url,
            headers={"User-Agent": _UA, "Referer": ref},
        )
        with urllib.request.urlopen(req, timeout=18.0) as resp:
            data = resp.read(900_000)
            ctype = str(resp.headers.get("Content-Type") or "")
        if len(data) < 8000:
            return False
        if dest.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            dest = dest.with_suffix(_guess_ext(url, ctype))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return dest.is_file() and dest.stat().st_size >= 1200
    except Exception:
        return False


def _is_junk_discussion_figure(path: Path) -> bool:
    """排除门户二维码、电视新闻截帧、Matrix 示意插画等。"""
    try:
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
    except Exception:
        return True
    if w * h < 120_000:
        return True
    # 凤凰/门户文末「扫码下载客户端」小方图
    if w < 420 and h < 350:
        return True
    if _is_video_news_frame(w, h):
        return True
    if _is_generic_stock_illustration(path):
        return True
    ratio = w / max(h, 1)
    # 竖屏短视频截图（九派新闻等带大字幕）
    if ratio <= 0.78 and h >= 650:
        return True
    # 二维码/关注公众号小方图
    if w <= 580 and h <= 580 and 0.82 <= ratio <= 1.22:
        return True
    return False


def _score_discussion_figure(path: Path, *, page_url: str = "") -> float:
    """越高越适合正文/封面；优先现场实拍，排除电视宽屏与示意插画。"""
    if _is_junk_discussion_figure(path):
        return -1.0
    try:
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
    except Exception:
        return -1.0
    ratio = w / max(h, 1)
    score = min(w * h, 1_200_000) / 1000.0
    score += _photo_naturalness_score(path)
    if 0.85 <= ratio <= 1.35:
        score += 180.0
    elif 1.35 < ratio < 1.48:
        score += 40.0
    elif ratio >= 1.48:
        score -= 500.0
    if 0.85 <= ratio <= 1.55 and 280 <= h <= 720:
        score += 60.0
    if _is_decorative_image_url(page_url):
        score -= 300.0
    if any(h in (page_url or "").lower() for h in _SOCIAL_VIDEO_PAGE_HINTS):
        score -= 120.0
    if "/socialgd/" in (page_url or "").lower():
        score -= 180.0
    return score


def _is_embedded_unrelated_photo(w: int, h: int) -> bool:
    """门户正文内嵌的旧案大图/拼图（常误当现场图）。"""
    if w >= 1000 and h >= 900:
        return True
    if w >= 1100 and h >= 800 and 0.95 <= (w / max(h, 1)) <= 1.35:
        return True
    return False


def _collect_page_figure_trials(
    *,
    topic: dict[str, Any],
    page_url: str,
    candidates: list[str],
    out_dir: Path,
    pool_name: str,
    cap: str,
    page_title: str,
    rel_score: int,
    page_idx: int,
    host_boost: int,
    used_urls: set[str],
    max_per_page: int = 2,
    max_scan: int = 28,
) -> list[tuple[int, float, int, int, Path, str, str, str, int]]:
    """逐张试下载，跳过 junk，每页最多保留 max_per_page 张。"""
    out: list[tuple[int, float, int, int, Path, str, str, str, int]] = []
    for cand_idx, img_url in enumerate(candidates[:max_scan]):
        if len(out) >= max_per_page:
            break
        if not img_url or img_url in used_urls:
            continue
        if _is_recommendation_junk_image(img_url) or _is_decorative_image_url(img_url):
            continue
        trial = out_dir / f"{pool_name}{page_idx}_{cand_idx}.jpg"
        if not _download_image(img_url, trial, referer=page_url):
            trial.unlink(missing_ok=True)
            continue
        sz = trial.stat().st_size
        min_bytes = _min_figure_bytes()
        if sz < min_bytes or sz > _MAX_FIGURE_BYTES or not _figure_dimensions_ok(trial):
            trial.unlink(missing_ok=True)
            continue
        try:
            from PIL import Image

            w, h = Image.open(trial).size
        except Exception:
            trial.unlink(missing_ok=True)
            continue
        if _is_embedded_unrelated_photo(w, h):
            trial.unlink(missing_ok=True)
            continue
        if _is_junk_discussion_figure(trial):
            trial.unlink(missing_ok=True)
            continue
        score = _score_discussion_figure(trial, page_url=page_url)
        if score < 80:
            trial.unlink(missing_ok=True)
            continue
        used_urls.add(img_url)
        out.append((rel_score, score, page_idx, cand_idx, trial, cap, page_title, page_url, host_boost))
    return out


def _figure_editorial_rank(path: Path) -> tuple[int, float, int]:
    """正文插图排序：方图/竖图优先，宽屏电视截图靠后。"""
    try:
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
    except Exception:
        return (0, -1.0, 0)
    ratio = w / max(h, 1)
    tier = 0
    if 0.8 <= ratio <= 1.4:
        tier = 3
    elif ratio < 1.68:
        tier = 2
    elif ratio >= 1.68:
        tier = 0
    return (tier, _score_discussion_figure(path, page_url=""), w * h)


def _figure_rank_tuple(
    *,
    rel_score: int,
    img_score: float,
    page_idx: int,
    cand_idx: int,
    host_boost: int = 0,
) -> tuple[float, float, int, int]:
    """综合排序：同题相关 + 画面质量 + 来源加权。"""
    combined = rel_score * 12.0 + img_score + host_boost
    return (-combined, -img_score, page_idx, cand_idx)


def _pick_discussion_cover_source(
    out_dir: Path, topic: dict[str, Any] | None = None
) -> Path | None:
    """从已下载 still 里选最适合做首图的（同题报道优先，排除无关截图）。"""
    stills = sorted(out_dir.glob("still-*.jpg"))
    if not stills:
        return None
    meta = _load_figure_sources(out_dir)
    keywords = _topic_figure_keywords(topic) if topic else []
    scored: list[tuple[int, float, Path]] = []
    for p in stills:
        if p.stat().st_size < _min_figure_bytes():
            continue
        url = str((meta.get(p.name) or {}).get("page_url") or "")
        s = _score_discussion_figure(p, page_url=url)
        if s < 0:
            continue
        title = str((meta.get(p.name) or {}).get("page_title") or "")
        rel = _keyword_relevance_score(title, keywords) if title else 0
        scored.append((rel, s, p))
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return scored[0][2]


def ensure_discussion_cover(topic: dict[str, Any]) -> Path:
    """话题讨论首图：同题报道配图裁 2.35:1，不用牛马 sector 主图。"""
    from scripts.tools.wechat_mp_tv_cover import COVER_H, COVER_W

    slug = _slug(topic)
    out_dir = INLINE_DISCUSSION_ROOT / slug
    cover = out_dir / "cover.jpg"
    force = os.getenv("WECHAT_MP_DISCUSSION_FIGURES_FORCE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if cover.is_file() and cover.stat().st_size > 8000 and not force:
        return cover

    ensure_discussion_figures(topic, max_images=3)
    src_path = _pick_discussion_cover_source(out_dir, topic)
    if src_path is None or not src_path.is_file():
        if cover.is_file() and cover.stat().st_size > 8000:
            return cover
        raise FileNotFoundError(f"话题讨论封面缺事件配图: {slug}")

    from PIL import Image

    out_dir.mkdir(parents=True, exist_ok=True)
    src = Image.open(src_path).convert("RGB")
    sw, sh = src.size
    target_ratio = COVER_W / COVER_H
    crop_h = int(sw / target_ratio)
    if crop_h > sh:
        top = 0
        crop_h = sh
    else:
        top = max(0, (sh - crop_h) // 2)
    if top + crop_h > sh:
        top = max(0, sh - crop_h)
    img = src.crop((0, top, sw, min(sh, top + crop_h))).resize(
        (COVER_W, COVER_H), Image.Resampling.LANCZOS
    )
    img.save(cover, format="JPEG", quality=93, optimize=True)
    return cover


def _img_width(url: str) -> int:
    m = re.search(r"_w(\d+)h", url or "")
    if m:
        return int(m.group(1))
    m = re.search(r"/w(\d+)h(\d+)", url or "")
    return int(m.group(1)) if m else 400


def _skip_image_url(url: str) -> bool:
    low = (url or "").lower()
    if any(h in low for h in _SKIP_IMG_HINTS):
        return True
    if any(h in low for h in _STOCK_ILLUSTRATION_URL_HINTS):
        return True
    return any(h in low for h in _TV_BROADCAST_IMG_HINTS)


def _is_decorative_image_url(url: str) -> bool:
    low = (url or "").lower()
    return any(h in low for h in _STOCK_ILLUSTRATION_URL_HINTS)


def _page_host_figure_boost(page_url: str, topic: dict[str, Any]) -> int:
    """科技/删库类话题优先科技媒体正文图，降低社会视频稿配图权重。"""
    low = (page_url or "").lower()
    boost = 0
    if _topic_allows_it_figure_fallback(topic):
        for host, pts in _TECH_TOPIC_PAGE_HOST_BOOSTS:
            if host in low:
                boost = max(boost, pts)
        if any(h in low for h in _SOCIAL_VIDEO_PAGE_HINTS):
            boost -= 35
    return boost


def _is_video_news_frame(w: int, h: int) -> bool:
    if (w, h) in _VIDEO_FRAME_SIZES:
        return True
    ratio = w / max(h, 1)
    # 3:2 / 16:9 / 超宽新闻视频截帧（含 1080x720、1380x704）
    if w >= 900 and h >= 480 and ratio >= 1.45:
        return True
    if w >= 620 and h <= 420 and ratio > 1.55:
        return True
    return False


def _is_generic_stock_illustration(path: Path) -> bool:
    """排除 Matrix 绿幕、抽象科技插画等示意性配图。"""
    try:
        from PIL import Image

        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((180, 180))
            w, h = im.size
            pixels = list(im.getdata())
    except Exception:
        return False
    if not pixels:
        return False
    n = len(pixels)
    green_dom = sum(
        1 for r, g, b in pixels if g >= 70 and g > r + 18 and g > b + 12
    )
    if green_dom / n > 0.26:
        return True
    blue_dom = sum(
        1 for r, g, b in pixels if b >= 95 and b > r + 28 and b > g + 12
    )
    try:
        quant = im.quantize(colors=20, method=Image.Quantize.MEDIANCUT)
        colors_used = len(quant.getcolors(maxcolors=256) or [])
    except Exception:
        colors_used = 32
    if blue_dom / n > 0.42 and colors_used <= 14:
        return True
    if colors_used <= 9 and max(w, h) <= 180:
        return True
    # 高对比黑白「代码雨」：亮度两极多、中间色少
    dark = sum(1 for r, g, b in pixels if (r + g + b) < 90)
    bright = sum(1 for r, g, b in pixels if (r + g + b) > 620)
    if dark / n > 0.2 and bright / n > 0.08 and colors_used <= 16:
        return True
    return False


def _photo_naturalness_score(path: Path) -> float:
    """越高越像现场实拍，越低越像插画/截图。"""
    try:
        from PIL import Image

        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((200, 200))
            pixels = list(im.getdata())
    except Exception:
        return 0.0
    if not pixels:
        return 0.0
    uniq = len({(r // 8, g // 8, b // 8) for r, g, b in pixels})
    diversity = min(uniq / 120.0, 1.0)
    sat = sum(max(r, g, b) - min(r, g, b) for r, g, b in pixels) / (len(pixels) * 255.0)
    return diversity * 60.0 + sat * 40.0


def _cap_from_hit(hit: ResearchHit) -> str:
    src = (hit.source or "公开报道").strip()
    return f"图源：{src}（公开报道引用）"


def _figure_dimensions_ok(path: Path) -> bool:
    try:
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
    except Exception:
        return False
    return w >= _MIN_FIGURE_WIDTH and h >= _MIN_FIGURE_HEIGHT


def _is_recommendation_junk_image(url: str) -> bool:
    """网易/门户文末「猜你喜欢」大图，常与正文无关。"""
    low = (url or "").lower()
    if "qtng" in low:
        return True
    if re.search(r"dingyue\.ws\.126\.net/20\d{2}/\d{2}/\d{2}/", low):
        return True
    return False


def _pool_rank_key(item: tuple[int, Path, str, str, int, int]) -> tuple:
    sz, _trial, _cap, img_url, page_idx, cand_idx = item
    return (
        _is_recommendation_junk_image(img_url),
        sz > _MAX_FIGURE_BYTES,
        cand_idx,
        page_idx,
        -sz,
    )


def _figure_fingerprint(path: Path) -> str:
    """24x24 缩略图指纹：同图不同压缩/尺寸仍可判重复。"""
    import hashlib

    from PIL import Image

    with Image.open(path) as im:
        thumb = im.convert("RGB").resize((24, 24), Image.Resampling.BILINEAR)
    return hashlib.md5(thumb.tobytes()).hexdigest()


def _dedupe_figure_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        try:
            fp = _figure_fingerprint(p)
        except Exception:
            continue
        if fp in seen:
            continue
        seen.add(fp)
        out.append(p)
    return out


def _dedupe_figure_dicts(
    figures: list[dict[str, str]],
    *,
    slug: str,
    exclude_paths: list[Path] | None = None,
) -> list[dict[str, str]]:
    exclude_fp: set[str] = set()
    for p in exclude_paths or []:
        if p.is_file():
            try:
                exclude_fp.add(_figure_fingerprint(p))
            except Exception:
                pass
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for fig in figures:
        rel = str(fig.get("rel") or "").strip()
        if not rel:
            continue
        try:
            path = resolve_discussion_inline_path(rel.replace("discussion/", "", 1))
            fp = _figure_fingerprint(path)
        except Exception:
            fp = rel
        if fp in exclude_fp or fp in seen:
            continue
        seen.add(fp)
        out.append(fig)
    return out


def _consolidate_stills(
    out_dir: Path,
    *,
    topic: dict[str, Any],
    max_images: int,
) -> None:
    """去重同源/同指纹 still，保留高分图并连续编号。"""
    meta = _load_figure_sources(out_dir)
    keywords = _topic_figure_keywords(topic)
    ranked: list[tuple[float, int, str, Path]] = []
    for p in sorted(out_dir.glob("still-*.jpg")):
        if p.stat().st_size < _min_figure_bytes():
            p.unlink(missing_ok=True)
            continue
        url = str((meta.get(p.name) or {}).get("page_url") or "")
        if _is_junk_discussion_figure(p):
            p.unlink(missing_ok=True)
            meta.pop(p.name, None)
            continue
        title = str((meta.get(p.name) or {}).get("page_title") or "")
        rel = _keyword_relevance_score(title, keywords) if title else 0
        score = _score_discussion_figure(p, page_url=url) + rel * 8.0
        page_key = url.split("?")[0]
        ranked.append((score, rel, page_key, p))
    ranked.sort(key=lambda x: (-x[0], -x[1]))
    keep: list[Path] = []
    seen_fp: set[str] = set()
    seen_pages: set[str] = set()
    for _score, _rel, page_key, p in ranked:
        if len(keep) >= max_images:
            p.unlink(missing_ok=True)
            meta.pop(p.name, None)
            continue
        try:
            fp = _figure_fingerprint(p)
        except Exception:
            p.unlink(missing_ok=True)
            meta.pop(p.name, None)
            continue
        if fp in seen_fp or (page_key and page_key in seen_pages):
            p.unlink(missing_ok=True)
            meta.pop(p.name, None)
            continue
        seen_fp.add(fp)
        if page_key:
            seen_pages.add(page_key)
        keep.append(p)
    for extra in out_dir.glob("still-*.jpg"):
        if extra not in keep:
            extra.unlink(missing_ok=True)
            meta.pop(extra.name, None)
    new_meta: dict[str, dict[str, str]] = {}
    for i, src in enumerate(keep, 1):
        dest = out_dir / f"still-{i:02d}.jpg"
        if src != dest:
            if dest.is_file():
                dest.unlink()
            src.rename(dest)
        old = meta.get(src.name) or meta.get(dest.name) or {}
        new_meta[dest.name] = old
    if new_meta:
        _save_figure_sources(out_dir, new_meta)
    elif meta:
        _save_figure_sources(out_dir, {})


def _figure_dicts_from_dir(out_dir: Path, *, slug: str, max_images: int) -> list[dict[str, str]]:
    paths = [
        p
        for p in sorted(out_dir.glob("still-*.jpg"))
        if p.is_file() and p.stat().st_size >= _min_figure_bytes()
    ][:max_images]
    return [
        {"rel": f"discussion/{slug}/{p.name}", "cap": "图源：公开报道（引用）"}
        for p in paths
    ]


def _finalize_figure_stills(
    out_dir: Path,
    *,
    topic: dict[str, Any],
    slug: str,
    max_images: int,
) -> list[dict[str, str]]:
    _consolidate_stills(out_dir, topic=topic, max_images=max_images)
    return _figure_dicts_from_dir(out_dir, slug=slug, max_images=max_images)


def ensure_discussion_figures(topic: dict[str, Any], *, max_images: int = 3) -> list[dict[str, str]]:
    """从同题报道页抓取配图：优先正文靠前图，排除文末推荐 junk，兼顾清晰度。"""
    if not discussion_figures_enabled():
        return []
    slug = _slug(topic)
    out_dir = INLINE_DISCUSSION_ROOT / slug
    keywords = _topic_figure_keywords(topic)
    figure_meta = _load_figure_sources(out_dir)
    existing = sorted(out_dir.glob("still-*.*")) if out_dir.is_dir() else []
    force = os.getenv("WECHAT_MP_DISCUSSION_FIGURES_FORCE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if existing and not force:
        if not figure_meta:
            existing = []
        else:
            existing = [p for p in existing if p.name in figure_meta]
            existing = _filter_stills_with_meta(topic, existing, figure_meta, keywords)
    if existing and not force:
        good = [
            p
            for p in existing
            if p.stat().st_size >= _min_figure_bytes()
            and _figure_dimensions_ok(p)
            and not _is_junk_discussion_figure(p)
        ]
        good.sort(
            key=lambda p: _score_discussion_figure(
                p,
                page_url=str((figure_meta.get(p.name) or {}).get("page_url") or ""),
            ),
            reverse=True,
        )
        use = _dedupe_figure_paths(good)[:max_images]
        result = [
            {
                "rel": f"discussion/{slug}/{p.name}",
                "cap": "图源：公开报道（引用）",
            }
            for p in use
        ]
        if len(result) < max_images:
            _supplement_missing_figures(
                topic,
                slug=slug,
                out_dir=out_dir,
                need=max_images - len(result),
                still_start=len(result) + 1,
            )
        return _finalize_figure_stills(out_dir, topic=topic, slug=slug, max_images=max_images)

    hits = fetch_discussion_research(topic, limit=max_images + 3)
    extra_urls = topic.get("research_urls") or []
    if isinstance(extra_urls, str):
        extra_urls = [extra_urls]
    priority_urls = [str(u).strip() for u in extra_urls if str(u).strip().startswith("http")]
    hit_urls = [h.url for h in hits if h.url]
    ordered_urls: list[tuple[str, ResearchHit | None]] = []
    tech_only_urls: set[str] = set()
    seen_pages: set[str] = set()
    for u in priority_urls + hit_urls:
        if u in seen_pages:
            continue
        seen_pages.add(u)
        hit = next((h for h in hits if h.url == u), None)
        ordered_urls.append((u, hit))

    if len(ordered_urls) < max_images + 2:
        from scripts.tools.wechat_mp_discussion_research import (
            _fetch_news_search_urls,
            figure_search_queries,
        )

        for q in figure_search_queries(topic):
            for page_url in _fetch_news_search_urls(q, limit=max_images + 4):
                if page_url in seen_pages:
                    continue
                seen_pages.add(page_url)
                ordered_urls.append((page_url, None))
                if len(ordered_urls) >= max_images + 10:
                    break
            if len(ordered_urls) >= max_images + 10:
                break

    if not ordered_urls:
        from scripts.tools.wechat_mp_discussion_research import (
            _fetch_news_search_urls,
            figure_search_queries,
        )

        for q in figure_search_queries(topic):
            for page_url in _fetch_news_search_urls(q, limit=max_images + 6):
                if page_url not in seen_pages:
                    seen_pages.add(page_url)
                    ordered_urls.append((page_url, None))
                if len(ordered_urls) >= max_images + 8:
                    break
            if len(ordered_urls) >= max_images + 8:
                break

    if _topic_allows_it_figure_fallback(topic):
        from scripts.tools.wechat_mp_discussion_research import _fetch_news_search_urls

        tech_first: list[tuple[str, ResearchHit | None]] = []
        for q in _it_figure_fallback_queries(topic)[:5]:
            for page_url in _fetch_news_search_urls(q, limit=5):
                if page_url in seen_pages:
                    continue
                seen_pages.add(page_url)
                tech_first.append((page_url, None))
                tech_only_urls.add(page_url)
                if len(tech_first) >= 8:
                    break
            if len(tech_first) >= 8:
                break
        if tech_first:
            ordered_urls = tech_first + ordered_urls

    # 全页候选 → 下载 → 按「同题相关 + 非 junk + 清晰度」取 Top N
    downloaded: list[tuple[int, float, int, int, Path, str, str, str, int]] = []
    used_urls: set[str] = set()
    out_dir.mkdir(parents=True, exist_ok=True)
    figure_meta = figure_meta if figure_meta else {}
    for page_idx, (page_url, hit) in enumerate(ordered_urls):
        cap = _cap_from_hit(hit) if hit else "图源：公开报道（引用）"
        html = ""
        try:
            html = _fetch_html(page_url)
        except Exception:
            continue
        ok, parsed = _page_relevant_for_figures(
            topic,
            page_url=page_url,
            html=html,
            hit=hit,
            keywords=keywords,
            strict=page_url not in tech_only_urls,
        )
        if not ok:
            continue
        page_title = (parsed.title if parsed else "") or ""
        rel_score = _keyword_relevance_score(page_title, keywords)
        try:
            candidates = [_normalize_image_url(u) for u in _content_images_from_html(html, page_url)]
            if not candidates:
                raw = _extract_image_url(html, page_url)
                if raw:
                    candidates = [_normalize_image_url(raw)]
        except Exception:
            continue
        host_boost = _page_host_figure_boost(page_url, topic)
        downloaded.extend(
            _collect_page_figure_trials(
                topic=topic,
                page_url=page_url,
                candidates=candidates,
                out_dir=out_dir,
                pool_name="_pool_",
                cap=cap,
                page_title=page_title,
                rel_score=rel_score,
                page_idx=page_idx,
                host_boost=host_boost,
                used_urls=used_urls,
            )
        )

    ranked: list[tuple[int, float, int, int, Path, str, str, str, int]] = []
    for rel_score, img_score, page_idx, cand_idx, trial, cap, page_title, page_url, host_boost in downloaded:
        ranked.append((rel_score, img_score, page_idx, cand_idx, trial, cap, page_title, page_url, host_boost))
    ranked.sort(
        key=lambda x: _figure_rank_tuple(
            rel_score=x[0],
            img_score=x[1],
            page_idx=x[2],
            cand_idx=x[3],
            host_boost=x[8],
        )
    )
    saved: list[dict[str, str]] = []
    seen_fp: set[str] = set()
    seen_pages_saved: set[str] = set()
    still_no = 1
    for _rel, _img_sc, _pi, _ci, trial, cap, page_title, page_url, _host in ranked:
        if still_no > max_images:
            trial.unlink(missing_ok=True)
            continue
        page_key = (page_url or "").split("?")[0].strip()
        if page_key and page_key in seen_pages_saved:
            trial.unlink(missing_ok=True)
            continue
        try:
            fp = _figure_fingerprint(trial)
        except Exception:
            trial.unlink(missing_ok=True)
            continue
        if fp in seen_fp:
            trial.unlink(missing_ok=True)
            continue
        seen_fp.add(fp)
        if page_key:
            seen_pages_saved.add(page_key)
        dest = out_dir / f"still-{still_no:02d}.jpg"
        if dest.is_file():
            dest.unlink()
        trial.rename(dest)
        figure_meta[dest.name] = {
            "page_title": page_title,
            "page_url": page_url,
        }
        saved.append({"rel": f"discussion/{slug}/{dest.name}", "cap": cap})
        still_no += 1
    # 清理未入选 trial
    for p in out_dir.glob("_pool_*.jpg"):
        p.unlink(missing_ok=True)
    if figure_meta:
        _save_figure_sources(out_dir, figure_meta)
    if saved:
        if len(saved) < max_images:
            _supplement_missing_figures(
                topic,
                slug=slug,
                out_dir=out_dir,
                need=max_images - len(saved),
                still_start=still_no,
                seen_fp=seen_fp,
            )
        return _finalize_figure_stills(out_dir, topic=topic, slug=slug, max_images=max_images)
    extra = _supplement_missing_figures(
        topic,
        slug=slug,
        out_dir=out_dir,
        need=max_images,
        still_start=1,
    )
    if extra:
        return _finalize_figure_stills(out_dir, topic=topic, slug=slug, max_images=max_images)
    borrowed = _borrow_stills_from_pool(topic, slug=slug, out_dir=out_dir, max_images=max_images)
    if borrowed:
        return _finalize_figure_stills(out_dir, topic=topic, slug=slug, max_images=max_images)
    return []


_IT_FIGURE_SEARCH_QUERIES = (
    "数据中心 机房 照片",
    "服务器机房 运维",
    "互联网公司 办公 电脑",
    "网络安全 服务器",
)
_IT_TOPIC_KEYWORDS = (
    "删",
    "数据",
    "代码",
    "工程师",
    "程序员",
    "TB",
    "tb",
    "算法",
    "服务器",
    "宕机",
    "泄露",
)


def _topic_allows_it_figure_fallback(topic: dict[str, Any]) -> bool:
    """仅职场/删库/数据类科技话题允许 IT 示意图兜底；社会民生稿只用新闻图。"""
    text = f"{topic.get('trend_title') or ''} {topic.get('title_zh') or ''}"
    return any(k in text for k in _IT_TOPIC_KEYWORDS)


def _news_figure_fallback_queries(topic: dict[str, Any]) -> list[str]:
    from scripts.tools.wechat_mp_discussion_research import figure_search_queries

    out = list(figure_search_queries(topic))
    trend = str(topic.get("trend_title") or topic.get("title_zh") or "").strip()
    for suffix in (" 报道", " 现场", " 新闻", " 图"):
        q = f"{trend[:22]}{suffix}".strip()
        if len(q) >= 4 and q not in out:
            out.append(q)
    for token in re.findall(r"[\u4e00-\u9fff]{4,12}", trend)[:4]:
        for suffix in (" 现场", " 通报"):
            q = f"{token}{suffix}"
            if q not in out:
                out.append(q)
    return out[:12]


def _it_figure_fallback_queries(topic: dict[str, Any]) -> list[str]:
    if not _topic_allows_it_figure_fallback(topic):
        return []
    text = f"{topic.get('trend_title') or ''} {topic.get('title_zh') or ''}"
    extra: list[str] = []
    if any(k in text for k in ("删", "数据", "代码", "工程师", "程序员", "TB", "算法", "服务器", "tb")):
        extra.extend(["程序员删库", "IT运维 数据中心", "网络安全 服务器"])
    out: list[str] = []
    for q in extra + list(_IT_FIGURE_SEARCH_QUERIES):
        if q not in out:
            out.append(q)
    return out[:8]


def _supplement_figures_from_queries(
    queries: list[str],
    *,
    topic: dict[str, Any],
    slug: str,
    out_dir: Path,
    need: int,
    still_start: int,
    seen_fp: set[str] | None,
    cap: str,
    pool_prefix: str,
    strict_page_relevance: bool = True,
) -> list[dict[str, str]]:
    if need <= 0 or not queries:
        return []
    from scripts.tools.wechat_mp_discussion_research import _fetch_news_search_urls

    keywords = _topic_figure_keywords(topic)
    seen_fp = seen_fp if seen_fp is not None else set()
    figure_meta = _load_figure_sources(out_dir)
    page_urls: list[str] = []
    seen_pages: set[str] = set()
    for q in queries:
        for page_url in _fetch_news_search_urls(q, limit=6):
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            page_urls.append(page_url)
            if len(page_urls) >= 12:
                break
        if len(page_urls) >= 12:
            break

    downloaded: list[tuple[int, float, int, int, Path, str, str, str, int]] = []
    used_urls: set[str] = set()
    out_dir.mkdir(parents=True, exist_ok=True)
    for page_idx, page_url in enumerate(page_urls):
        try:
            html = _fetch_html(page_url)
        except Exception:
            continue
        ok, parsed = _page_relevant_for_figures(
            topic,
            page_url=page_url,
            html=html,
            hit=None,
            keywords=keywords,
            strict=strict_page_relevance,
        )
        if not ok:
            continue
        page_title = (parsed.title if parsed else "") or ""
        rel_score = _keyword_relevance_score(page_title, keywords)
        try:
            candidates = [_normalize_image_url(u) for u in _content_images_from_html(html, page_url)]
            if not candidates:
                raw = _extract_image_url(html, page_url)
                if raw:
                    candidates = [_normalize_image_url(raw)]
        except Exception:
            continue
        host_boost = _page_host_figure_boost(page_url, topic)
        downloaded.extend(
            _collect_page_figure_trials(
                topic=topic,
                page_url=page_url,
                candidates=candidates,
                out_dir=out_dir,
                pool_name=pool_prefix,
                cap=cap,
                page_title=page_title,
                rel_score=rel_score,
                page_idx=page_idx,
                host_boost=host_boost,
                used_urls=used_urls,
            )
        )

    downloaded.sort(
        key=lambda x: _figure_rank_tuple(
            rel_score=int(x[0]),
            img_score=float(x[1]),
            page_idx=x[2],
            cand_idx=x[3],
            host_boost=x[8],
        )
    )
    saved: list[dict[str, str]] = []
    still_no = still_start
    seen_pages_saved: set[str] = set()
    for _rel, _sc, _pi, _ci, trial, cap_text, page_title, page_url, _host in downloaded:
        if len(saved) >= need:
            trial.unlink(missing_ok=True)
            continue
        page_key = (page_url or "").split("?")[0].strip()
        if page_key and page_key in seen_pages_saved:
            trial.unlink(missing_ok=True)
            continue
        try:
            fp = _figure_fingerprint(trial)
        except Exception:
            trial.unlink(missing_ok=True)
            continue
        if fp in seen_fp:
            trial.unlink(missing_ok=True)
            continue
        seen_fp.add(fp)
        if page_key:
            seen_pages_saved.add(page_key)
        dest = out_dir / f"still-{still_no:02d}.jpg"
        if dest.is_file():
            dest.unlink()
        trial.rename(dest)
        figure_meta[dest.name] = {"page_title": page_title, "page_url": page_url}
        saved.append({"rel": f"discussion/{slug}/{dest.name}", "cap": cap_text})
        still_no += 1
    for p in out_dir.glob(f"{pool_prefix}*.jpg"):
        p.unlink(missing_ok=True)
    if figure_meta:
        _save_figure_sources(out_dir, figure_meta)
    return saved


def _supplement_missing_figures(
    topic: dict[str, Any],
    *,
    slug: str,
    out_dir: Path,
    need: int,
    still_start: int,
    seen_fp: set[str] | None = None,
) -> list[dict[str, str]]:
    """报道图不足：科技话题先 IT 实拍示意，再扩新闻检索。"""
    if need <= 0:
        return []
    seen_fp = seen_fp if seen_fp is not None else set()
    cap_news = "图源：公开报道（引用）"
    saved: list[dict[str, str]] = []
    if _topic_allows_it_figure_fallback(topic):
        saved = _supplement_figures_from_queries(
            _it_figure_fallback_queries(topic),
            topic=topic,
            slug=slug,
            out_dir=out_dir,
            need=need,
            still_start=still_start,
            seen_fp=seen_fp,
            cap="图源：公开报道（IT/科技示意）",
            pool_prefix="_itpool_",
            strict_page_relevance=False,
        )
    if len(saved) >= need:
        return saved
    saved += _supplement_figures_from_queries(
        _news_figure_fallback_queries(topic),
        topic=topic,
        slug=slug,
        out_dir=out_dir,
        need=need - len(saved),
        still_start=still_start + len(saved),
        seen_fp=seen_fp,
        cap=cap_news,
        pool_prefix="_newspool_",
    )
    return saved


def _borrow_stills_from_pool(
    topic: dict[str, Any],
    *,
    slug: str,
    out_dir: Path,
    max_images: int,
) -> list[dict[str, str]]:
    """检索失败时，从同题已下载 still 目录复用（按标题关键词匹配）。"""
    import shutil

    from scripts.tools.wechat_mp_hot_trends import _titles_overlap

    title = str(topic.get("trend_title") or topic.get("title_zh") or "").strip()
    if not title:
        return []
    best_dir: Path | None = None
    best_score = -1
    for child in INLINE_DISCUSSION_ROOT.iterdir():
        if not child.is_dir() or child.name == slug:
            continue
        stills = sorted(child.glob("still-*.jpg"))
        if not stills:
            continue
        score = 0
        if _titles_overlap(title, child.name):
            score += 100
        for token in re.findall(r"[\u4e00-\u9fff]{2,6}", title)[:6]:
            if token in child.name:
                score += 10
        if score > best_score:
            best_score = score
            best_dir = child
    if best_dir is None or best_score < 10:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[dict[str, str]] = []
    for i, src in enumerate(sorted(best_dir.glob("still-*.jpg"))[:max_images], 1):
        if src.stat().st_size < _min_figure_bytes():
            continue
        dest = out_dir / f"still-{i:02d}.jpg"
        shutil.copy2(src, dest)
        saved.append({"rel": f"discussion/{slug}/{dest.name}", "cap": "图源：公开报道（引用）"})
    return saved


def _discussion_figure_rel_slug(rel: str) -> str:
    return Path((rel or "").replace("\\", "/")).name


def _sort_figure_dicts_for_body(
    figures: list[dict[str, str]], *, slug: str
) -> list[dict[str, str]]:
    """正文插图：方图/竖图报道实拍优先，避免宽屏电视截图排第一。"""

    def _key(fig: dict[str, str]) -> tuple[int, float, int]:
        rel = str(fig.get("rel") or "")
        name = Path(rel.replace("\\", "/")).name
        path = INLINE_DISCUSSION_ROOT / slug / name
        if not path.is_file():
            return (0, -1.0, 0)
        return _figure_editorial_rank(path)

    return sorted(figures, key=_key, reverse=True)


def _unique_existing_figure_dicts(
    figures: list[dict[str, str]], *, slug: str
) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for fig in figures:
        rel = str(fig.get("rel") or "")
        name = Path(rel.replace("\\", "/")).name
        if not name or name in seen:
            continue
        path = INLINE_DISCUSSION_ROOT / slug / name
        if not path.is_file():
            continue
        seen.add(name)
        out.append(fig)
    return out


def _manual_figure_dicts(out_dir: Path, *, slug: str, limit: int) -> list[dict[str, str]]:
    """Agent 生成的事件插画只用于补足公开报道图缺口。"""
    paths = [
        path
        for path in sorted(out_dir.glob("manual-*.*"))
        if path.is_file()
        and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        and path.stat().st_size >= 8000
        and _figure_dimensions_ok(path)
    ][:limit]
    return [
        {
            "rel": f"discussion/{slug}/{path.name}",
            "cap": "原创新闻插画",
        }
        for path in paths
    ]


def ensure_discussion_body_figures(
    topic: dict[str, Any], *, max_images: int = 2
) -> list[dict[str, str]]:
    """正文插图：排除与封面同源 still，优先证据截图/第二现场图。"""
    slug = _slug(topic)
    out_dir = INLINE_DISCUSSION_ROOT / slug
    figures = ensure_discussion_figures(topic, max_images=max(3, max_images + 2))
    cover_src = _pick_discussion_cover_source(out_dir, topic)
    exclude = [cover_src] if cover_src and cover_src.is_file() else []
    figures = _dedupe_figure_dicts(figures, slug=slug, exclude_paths=exclude)
    figures = _sort_figure_dicts_for_body(figures, slug=slug)
    if len(figures) < max_images:
        out_dir = INLINE_DISCUSSION_ROOT / slug
        seen_fp: set[str] = set()
        for fig in figures:
            rel = str(fig.get("rel") or "")
            name = Path(rel.replace("\\", "/")).name
            path = out_dir / name
            if path.is_file():
                try:
                    seen_fp.add(_figure_fingerprint(path))
                except Exception:
                    pass
        figures.extend(
            _supplement_missing_figures(
                topic,
                slug=slug,
                out_dir=out_dir,
                need=max_images - len(figures),
                still_start=len(figures) + 1,
                seen_fp=seen_fp,
            )
        )
    figures = _unique_existing_figure_dicts(figures, slug=slug)
    if len(figures) < max_images:
        manual = _manual_figure_dicts(
            out_dir,
            slug=slug,
            limit=max_images - len(figures),
        )
        figures = _dedupe_figure_dicts(
            figures + manual,
            slug=slug,
            exclude_paths=exclude,
        )
    return figures[:max_images]


def _is_figure_line(line: str) -> bool:
    return bool(FIGURE_LINE_RE.match(line.strip()))


def _split_body_paragraphs(text: str) -> list[str]:
    """按空行分段（保留一句一段结构，不用 splitlines 吞空行）。"""
    return [p.strip() for p in re.split(r"\n\n+", (text or "").strip()) if p.strip()]


def _text_paragraph_indices(paragraphs: list[str]) -> list[int]:
    """可插入配图的正文段落下标（跳过插图与高亮段）。"""
    out: list[int] = []
    for i, para in enumerate(paragraphs):
        if _is_figure_line(para) or para.startswith("[[hl:"):
            continue
        out.append(i)
    return out


def strip_discussion_figures(body: str) -> str:
    """去掉正文中的 [[fig:]] 段，便于换图重插。"""
    paragraphs = _split_body_paragraphs(body or "")
    kept: list[str] = []
    for para in paragraphs:
        lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
        if any(_is_figure_line(ln) for ln in lines):
            continue
        kept.append(para)
    return "\n\n".join(kept).strip()


def refresh_discussion_figures(body: str, topic: dict[str, Any]) -> str:
    """去掉旧配图后重新抓取并注入。"""
    core = strip_discussion_figures(body)
    if not core:
        return body
    return inject_discussion_figures(core, topic)


def inject_discussion_figures(body: str, topic: dict[str, Any]) -> str:
    """在正文均匀段落位插入公开配图（会先去掉已有 [[fig:]] 再重插）。"""
    text = strip_discussion_figures((body or "").strip())
    if not text:
        return body
    figures = ensure_discussion_body_figures(
        topic, max_images=discussion_body_figure_target()
    )
    if not figures:
        return body

    paragraphs = _split_body_paragraphs(text)
    text_idxs = _text_paragraph_indices(paragraphs)
    if not text_idxs:
        return body

    para_indices = _distributed_inject_para_indices(len(text_idxs), len(figures))
    insert_after: dict[int, list[str]] = {}
    for fig_idx, para_idx in enumerate(para_indices):
        if fig_idx >= len(figures):
            break
        para_i = text_idxs[para_idx]
        fig = figures[fig_idx]
        cap = fig.get("cap") or "图源：公开报道（引用）"
        marker = "\n".join(
            _figure_marker_lines(fig["rel"], _DISCUSSION_FIGURE_STYLE, cap)
        )
        insert_after.setdefault(para_i, []).append(marker)

    if not insert_after:
        return text

    out: list[str] = []
    for i, para in enumerate(paragraphs):
        out.append(para)
        for extra in insert_after.get(i, []):
            out.append(extra)

    merged = "\n\n".join(out).strip()
    from scripts.tools.wechat_mp_discussion_polish import finalize_discussion_body

    return finalize_discussion_body(merged) + "\n"
