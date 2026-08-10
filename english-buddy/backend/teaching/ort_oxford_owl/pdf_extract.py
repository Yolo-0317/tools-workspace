"""Extract ORT story page JPEGs from 橙果 PDF scans."""

from __future__ import annotations

import io
from pathlib import Path

ORT_PKG = Path(__file__).resolve().parent
ROOT = ORT_PKG.parents[2]
ORT_PUBLIC = ROOT / "frontend" / "public" / "ort"
ORT_DIST = ROOT / "frontend" / "dist" / "ort"


def pdf_story_page_count(
    pdf_path: Path,
    *,
    story_start: int = 3,
    tail: int = 2,
) -> int:
    """橙果 PDF 故事页数：封面 + 导读 + N 故事 + tail 封底/活动。"""
    import fitz

    doc = fitz.open(pdf_path)
    return max(1, doc.page_count - story_start - tail + 1)


def story_pdf_pages(
    page_count: int,
    *,
    story_start: int = 3,
) -> list[int]:
    """1-based PDF page index for each catalog story page (sequential)."""
    return list(range(story_start, story_start + page_count))


def _rotate_for_image(img, pdf_page: int, rotate: int) -> int:
    """Return PIL rotate degrees; 0 = skip rotation."""
    w, h = img.size
    if h > w:
        # 部分 L2 扫描（如 Poor Floppy）内嵌图已是竖版，勿再 ±90°
        return 0
    # 横图扫描：奇数 PDF 页 -90°，偶数 PDF 页 +90°
    return rotate if pdf_page % 2 == 1 else -rotate


def extract_pdf_page_jpeg(
    pdf_path: Path,
    pdf_page: int,
    *,
    rotate: int = -90,
    jpeg_quality: int = 88,
) -> bytes:
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise RuntimeError(
            "PyMuPDF required: pip install pymupdf pillow"
        ) from e
    from PIL import Image

    doc = fitz.open(pdf_path)
    if pdf_page < 1 or pdf_page > doc.page_count:
        raise ValueError(f"PDF page {pdf_page} out of range (1–{doc.page_count})")
    page = doc[pdf_page - 1]
    imgs = page.get_images(full=True)
    if not imgs:
        raise ValueError(f"no embedded image on PDF page {pdf_page}")
    info = doc.extract_image(imgs[0][0])
    img = Image.open(io.BytesIO(info["image"]))
    page_rotate = _rotate_for_image(img, pdf_page, rotate)
    if page_rotate:
        img = img.rotate(page_rotate, expand=True)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
    return buf.getvalue()


def write_cover_image(book_id: str, data: bytes) -> list[Path]:
    written: list[Path] = []
    for root in (ORT_PUBLIC, ORT_DIST):
        if root is ORT_DIST and not ORT_DIST.is_dir():
            continue
        dest = root / book_id / "cover.jpg"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        written.append(dest)
    return written


def extract_cover_jpeg(
    pdf_path: Path,
    *,
    cover_page: int = 1,
    rotate: int = -90,
    jpeg_quality: int = 88,
) -> bytes:
    return extract_pdf_page_jpeg(
        pdf_path,
        cover_page,
        rotate=rotate,
        jpeg_quality=jpeg_quality,
    )


def write_story_page_image(book_id: str, page_index: int, data: bytes) -> list[Path]:
    """Write pNN.jpg to public/ort and dist/ort (when dist exists)."""
    rel = f"p{page_index:02d}.jpg"
    written: list[Path] = []
    for root in (ORT_PUBLIC, ORT_DIST):
        if root is ORT_DIST and not ORT_DIST.is_dir():
            continue
        dest = root / book_id / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        written.append(dest)
    return written
