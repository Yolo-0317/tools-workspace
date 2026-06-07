"""公众号正文插图：本地 inline 素材 + 微信 uploadimg + 当日去重池。"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_figure_pool import FigureSlot, allocate_figure

FIGURE_UPLOAD_TZ = ZoneInfo("Asia/Shanghai")

ROOT = Path(__file__).resolve().parents[2]
INLINE_ROOT = ROOT / "assets" / "wechat_mp" / "inline"

FIGURE_LINE_RE = re.compile(r"^\[\[fig:([^|\]]+)\|([^\]]*)\]\]\s*$")
_SECTION_LINE_RE = re.compile(r"^>\s*(.+)\s*$")

MARKET_FIGURE_SLOTS: list[FigureSlot] = [
    FigureSlot("market-2", "before", "外围与资金", ("global", "finance")),
    FigureSlot("market-3", "before", "结构判断", ("screen", "tech")),
    FigureSlot(
        "market-4",
        "after",
        "结构判断",
        ("trading", "market"),
    ),
]

NEWS_FIGURE_SLOTS: list[FigureSlot] = [
    FigureSlot("news-2", "after_item", "3", ("global", "news")),
    FigureSlot("news-3", "after_item", "6", ("energy", "global")),
    FigureSlot("news-4", "after_item", "10", ("tech", "ai")),
]

TOP5_FIGURE_SLOTS: list[FigureSlot] = [
    FigureSlot("top5-2", "before", "组合特征", ("selection", "trading")),
]

DRAGON_FIGURE_SLOTS: list[FigureSlot] = [
    FigureSlot("dragons-2", "before", "明日计划与纪律", ("emotion", "chart")),
]

# 带货 home：节标题后插图（开篇段落后才插图）
HOME_COMMERCE_FIGURE_SLOTS: list[FigureSlot] = [
    FigureSlot("commerce-home-1", "after", "窄台面为什么先谈收纳", ("kitchen", "home")),
    FigureSlot("commerce-home-2", "before", "两类通常更值的", ("kitchen", "home")),
    FigureSlot("commerce-home-3", "before", "买之前对照三件事", ("kitchen", "home")),
]

_COMMERCE_SLOTS_BY_VERTICAL: dict[str, list[FigureSlot]] = {
    "home": HOME_COMMERCE_FIGURE_SLOTS,
}


def _figure_marker_lines(fname: str, caption: str = "") -> list[str]:
    """插图独占一段，前后留空行，避免与小标题挤进同一个 <p>。"""
    _ = caption
    return ["", f"[[fig:{fname}|]]", ""]


def _figure_marker(fname: str, caption: str) -> str:
    return "\n".join(_figure_marker_lines(fname, caption)) + "\n"


def _section_bare(line: str) -> str | None:
    m = _SECTION_LINE_RE.match(line.strip())
    return m.group(1).strip() if m else None


def _find_section_line(lines: list[str], section: str) -> int | None:
    for i, line in enumerate(lines):
        bare = _section_bare(line)
        if bare == section:
            return i
        s = line.strip()
        m = re.match(r"^[一二三四五六七八九十]、(.+)$", s)
        if m and m.group(1).strip() == section:
            return i
    return None


def _inject_before_line(lines: list[str], idx: int, fname: str, caption: str) -> list[str]:
    block = _figure_marker_lines(fname, caption)
    return lines[:idx] + block + lines[idx:]


def _inject_after_section(lines: list[str], section: str, fname: str, caption: str) -> list[str]:
    start = _find_section_line(lines, section)
    if start is None:
        return lines
    j = start + 1
    while j < len(lines):
        if _section_bare(lines[j]) is not None:
            break
        if lines[j].strip().startswith(">"):
            break
        j += 1
    block = _figure_marker_lines(fname, caption)
    return lines[:j] + block + lines[j:]


def _inject_after_news_item(
    lines: list[str],
    item_no: int,
    fname: str,
    caption: str,
) -> list[str]:
    count = 0
    insert_at: int | None = None
    for i, line in enumerate(lines):
        if re.match(r"^\d+\.\s", line.strip()):
            count += 1
            if count == item_no:
                j = i + 1
                while j < len(lines):
                    ns = lines[j].strip()
                    if re.match(r"^\d+\.\s", ns) or ns.startswith(">"):
                        break
                    j += 1
                insert_at = j
                break
    if insert_at is None:
        return lines
    block = _figure_marker_lines(fname, caption)
    return lines[:insert_at] + block + lines[insert_at:]


def _apply_slots(
    body: str,
    slots: list[FigureSlot],
    *,
    allocator=None,
) -> str:
    lines = body.splitlines()
    pending_before: list[tuple[int, str, str]] = []
    pick = allocator or (
        lambda slot: allocate_figure(
            key=slot.key,
            tags=slot.tags,
            caption=slot.caption,
        )
    )
    for slot in slots:
        fname, caption = pick(slot)
        if slot.anchor == "before":
            idx = _find_section_line(lines, slot.section)
            if idx is not None:
                pending_before.append((idx, fname, caption))
        elif slot.anchor == "after":
            lines = _inject_after_section(lines, slot.section, fname, caption)
        elif slot.anchor == "after_item":
            try:
                n = int(slot.section)
            except ValueError:
                continue
            lines = _inject_after_news_item(lines, n, fname, caption)
    for idx, fname, caption in sorted(pending_before, key=lambda x: x[0], reverse=True):
        lines = _inject_before_line(lines, idx, fname, caption)
    return "\n".join(lines)


def inject_market_figures(body: str) -> str:
    return _apply_slots(body, MARKET_FIGURE_SLOTS)


def inject_news_figures(body: str) -> str:
    return _apply_slots(body, NEWS_FIGURE_SLOTS)


def inject_top5_figures(body: str) -> str:
    return _apply_slots(body, TOP5_FIGURE_SLOTS)


def inject_dragons_figures(body: str) -> str:
    return _apply_slots(body, DRAGON_FIGURE_SLOTS)


def inject_commerce_figures(body: str, *, vertical: str = "home") -> str:
    """带货稿按垂直插入插图；节名须与 FigureSlot.section 一致。"""
    vert = (vertical or "home").strip().lower()
    slots = _COMMERCE_SLOTS_BY_VERTICAL.get(vert)
    if not slots:
        return body

    def _pick(slot: FigureSlot) -> tuple[str, str]:
        if vert == "home":
            from scripts.tools.wechat_mp_figure_pool import allocate_commerce_home_figure

            return allocate_commerce_home_figure(key=slot.key)
        return allocate_figure(key=slot.key, tags=slot.tags, caption=slot.caption)

    try:
        return _apply_slots(body, slots, allocator=_pick)
    except FileNotFoundError:
        return body


def resolve_inline_path(filename: str) -> Path:
    """财经五槽正文插图（仅 assets/wechat_mp/inline）；带货用 resolve_commerce_home_inline_path。"""
    path = INLINE_ROOT / Path(filename).name
    if not path.is_file():
        raise FileNotFoundError(f"正文插图不存在: {path}")
    return path


def figure_max_height_px() -> int:
    raw = os.environ.get("WECHAT_MP_FIGURE_MAX_HEIGHT", "200").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 200
    return max(120, min(value, 320))


def _figure_style_from_caption(caption: str) -> tuple[int, str]:
    """解析 [[fig:file|max-h=480;fit=contain]] 中的展示参数。"""
    max_h = figure_max_height_px()
    fit = "cover"
    for part in caption.split(";"):
        token = part.strip().lower()
        if token.startswith("max-h="):
            try:
                max_h = int(token.split("=", 1)[1])
            except ValueError:
                pass
        elif token.startswith("fit="):
            fit = token.split("=", 1)[1].strip() or fit
    max_h = max(120, min(max_h, 720))
    if fit not in {"cover", "contain", "fill", "scale-down"}:
        fit = "cover"
    return max_h, fit


def figure_to_html(
    filename: str,
    caption: str,
    *,
    image_url: str | None = None,
    local_preview: bool = False,
) -> str:
    from scripts.tools.wechat_mp_client import _escape_html
    from scripts.tools.wechat_mp_layout import active_layout

    layout = active_layout()
    max_h, fit = _figure_style_from_caption(caption)
    if image_url:
        src = _escape_html(image_url)
    elif local_preview:
        path = resolve_inline_path(filename).resolve()
        src = path.as_uri()
    else:
        return '<p style="color:#888;font-size:13px;text-align:center;">（配图）</p>'
    return (
        f'<section style="margin:{layout.figure_margin};text-align:center;">'
        f'<img src="{src}" alt="" '
        f'style="max-width:100%;width:100%;max-height:{max_h}px;height:auto;'
        f"object-fit:{fit};border-radius:{layout.figure_radius};"
        'display:block;margin:0 auto;"/>'
        "</section>"
    )


def parse_figure_line(line: str) -> tuple[str, str] | None:
    m = FIGURE_LINE_RE.match(line.strip())
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip()


UPLOAD_CACHE_PATH = ROOT / "data" / "wechat_mp_figure_upload_cache.json"


def figure_upload_cache_key(path: Path) -> str:
    """按文件名 + 内容哈希缓存，换图同文件名也会重新 uploadimg。"""
    digest = hashlib.md5(path.read_bytes()).hexdigest()[:16]
    return f"{path.name}#{digest}"


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
    payload = {"updated_at": datetime.now(FIGURE_UPLOAD_TZ).isoformat(), "urls": urls}
    UPLOAD_CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def inline_figure_url_from_cache(filename: str) -> str | None:
    """仅读 uploadimg 缓存，不触发新上传（重建 HTML 时用）。"""
    try:
        path = resolve_inline_path(filename)
    except Exception:
        return None
    key = figure_upload_cache_key(path)
    return _load_upload_cache().get(key)


def upload_inline_figure(filename: str) -> tuple[str | None, dict | None]:
    from scripts.tools.wechat_mp_client import upload_article_image

    path = resolve_inline_path(filename)
    key = figure_upload_cache_key(path)
    cache = _load_upload_cache()
    if key in cache:
        return cache[key], None
    url, err = upload_article_image(path)
    if url:
        cache[key] = url
        _save_upload_cache(cache)
    return url, err


def write_market_preview_html(article: dict[str, str], *, out_path: Path | None = None) -> Path:
    """本地手机预览：插图用 file://，富文本与草稿一致。"""
    from scripts.tools.wechat_mp_client import text_to_html
    from scripts.tools.wechat_mp_masthead import masthead_html

    body = article.get("body_text") or ""
    html_body = article.get("content") or (
        f"{masthead_html('market', upload_images=False, local_preview=True)}"
        f"{text_to_html(body, upload_figures=False, local_figure_preview=True)}"
    )
    title = article.get("title", "大盘分析预览")
    digest = article.get("digest", "")
    out = out_path or (ROOT / "output" / "wechat_mp_market_preview.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    page = f"""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;
  max-width:420px;margin:0 auto;padding:14px 12px 40px;background:#ffffff;color:#333333;
  line-height:1.72;font-size:16px;}}
h1{{font-size:20px;line-height:1.35;color:#111111;margin:0 0 6px;}}
.digest{{font-size:14px;color:#666666;margin:0 0 14px;padding-bottom:12px;border-bottom:1px solid #eeeeee;}}
</style></head><body>
<h1>{title}</h1>
<p class="digest">{digest}</p>
{html_body}
</body></html>"""
    out.write_text(page, encoding="utf-8")
    return out
