#!/usr/bin/env python3
"""按橙果 PDF 逐页 OCR 把现有 lines[] 对齐为 pages[]（保留 books.json 原文）。

与 extract_ort_pdf_lines.py 不同：只借 OCR 判断每插图页有几句，不覆盖课文文本。

示例：
  .venv/bin/python scripts/apply_ort_pdf_page_groups.py --level 3 --dry-run
  .venv/bin/python scripts/apply_ort_pdf_page_groups.py --level 3
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS_JSON = ROOT / "backend" / "teaching" / "ort_oxford_owl" / "books.json"
GROUPS_JSON = ROOT / "backend" / "teaching" / "ort_oxford_owl" / f"ort_l{{level}}_page_groups.json"
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from teaching.ort_oxford_owl.chengguo_maps import CHENGGUO_BY_LEVEL, chengguo_batch_dir  # noqa: E402
from teaching.ort_oxford_owl.book_lines import build_pages_field, flatten_lines  # noqa: E402
from extract_ort_pdf_lines import ocr_story_sentence  # noqa: E402
from teaching.ort_oxford_owl.pdf_extract import (  # noqa: E402
    extract_pdf_page_jpeg,
    pdf_story_page_count,
    story_pdf_pages,
)

# L4 4-01～4-06：原 OCR 课文不全，以 PDF 页底 OCR 为真源
L4_OCR_TEXT_BOOKS = frozenset(
    bid for _pdf, bid, _title in CHENGGUO_BY_LEVEL.get("4", [])[:6]
)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _ocr_page_texts(pdf_path: Path, *, story_start: int = 3) -> list[str]:
    n = pdf_story_page_count(pdf_path)
    out: list[str] = []
    for pdf_page in story_pdf_pages(n, story_start=story_start):
        jpeg = extract_pdf_page_jpeg(pdf_path, pdf_page)
        out.append(ocr_story_sentence(jpeg))
    return out


def _ocr_sentence_guess(ocr: str) -> int:
    if not ocr.strip():
        return 0
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", ocr.strip()) if p.strip()]
    return max(1, min(3, len(parts)))


def _line_starts_match(ocr: str, line: str) -> bool:
    a = _norm(ocr)
    b = _norm(line)
    if not a or not b:
        return False
    probe = b[: min(len(b), 24)]
    return a.startswith(probe) or probe in a[: len(probe) + 20]


def _score_join(ocr: str, chunk: list[str]) -> float:
    if not ocr.strip():
        return 0.0 if chunk else 1.0
    if not chunk:
        return 0.0
    a = _norm(ocr)
    b = _norm(" ".join(chunk))
    if not a or not b:
        return 0.0
    if not _line_starts_match(ocr, chunk[0]):
        return 0.0
    if a in b or b in a:
        return 0.95
    return SequenceMatcher(None, a, b).ratio()


def clean_artifact_lines(lines: list[str]) -> list[str]:
    """去掉源文本里单独的 OCR 残片（如 Swap 的 \"Nadim\"）。"""
    out: list[str] = []
    for ln in lines:
        s = ln.strip()
        if s in ("Nadim", "Nadim,", "Aneema", "Aneema,"):
            continue
        out.append(ln)
    return out


def _distribute_remainder(
    groups: list[list[str]],
    ocr_pages: list[str],
    rest: list[str],
) -> None:
    """把对齐剩余的句子按 OCR 页容量摊到后段插图页，避免整本堆在最后一页。"""
    if not rest:
        return
    idx = 0
    for gi, ocr in enumerate(ocr_pages):
        if idx >= len(rest) or not ocr.strip():
            continue
        cap = max(1, min(3, _ocr_sentence_guess(ocr)))
        room = cap - len(groups[gi])
        if room <= 0:
            continue
        take = min(room, len(rest) - idx)
        groups[gi].extend(rest[idx : idx + take])
        idx += take
    if idx < len(rest):
        for gi in range(len(groups) - 1, -1, -1):
            if idx >= len(rest):
                break
            if not ocr_pages[gi].strip():
                continue
            while len(groups[gi]) < 2 and idx < len(rest):
                groups[gi].append(rest[idx])
                idx += 1
    if idx < len(rest):
        groups[-1].extend(rest[idx:])


def split_ocr_sentences(ocr: str) -> list[str]:
    if not ocr.strip():
        return []
    parts = [
        p.strip()
        for p in re.split(r'(?<=[.!?])\s+', ocr.strip())
        if p.strip()
    ]
    return parts


def groups_from_ocr_text(ocr_pages: list[str]) -> list[list[str]]:
    """橙果页底 OCR 分句 → pages[]（4-01～4-06 等课文不全时用）。"""
    return [split_ocr_sentences(ocr) for ocr in ocr_pages]


def align_lines_to_ocr_pages(lines: list[str], ocr_pages: list[str]) -> list[list[str]]:
    """Greedy：每页 OCR 匹配连续 1–3 句原文。"""
    idx = 0
    groups: list[list[str]] = []
    for ocr in ocr_pages:
        if not ocr.strip():
            groups.append([])
            continue
        guess = _ocr_sentence_guess(ocr)
        best_take = 1
        best_score = -1.0
        for take in range(1, min(4, len(lines) - idx + 1)):
            if idx + take > len(lines):
                break
            sc = _score_join(ocr, lines[idx : idx + take])
            if take == guess:
                sc += 0.08
            if sc > best_score:
                best_score = sc
                best_take = take
        if idx >= len(lines):
            groups.append([])
            continue
        if best_score <= 0:
            best_take = 1
        take = min(best_take, len(lines) - idx)
        groups.append(lines[idx : idx + take])
        idx += take
    if idx < len(lines):
        _distribute_remainder(groups, ocr_pages, lines[idx:])
    return groups


def apply_groups_to_book(book: dict, groups: list[list[str]]) -> dict:
    bid = book["id"]
    flat = [ln for g in groups for ln in g]
    old_flat = flatten_lines(book)
    if _norm("".join(old_flat)) != _norm("".join(flat)) and old_flat != flat:
        print(f"  warn: flattened lines changed for {bid}", file=sys.stderr)
    book = dict(book)
    book["lines"] = flat
    book["pages"] = build_pages_field(flat, bid, groups=groups)
    return book


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", choices=["2", "3", "4"], required=True)
    parser.add_argument("--book", action="append")
    parser.add_argument("--batch-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    batch = (args.batch_dir or chengguo_batch_dir(args.level)).expanduser()
    if not batch.is_dir():
        raise SystemExit(f"batch dir not found: {batch}")

    pdf_map = {bid: (pdf, title) for pdf, bid, title in CHENGGUO_BY_LEVEL.get(args.level, [])}
    targets = list(args.book) if args.book else list(pdf_map.keys())
    for b in targets:
        if b not in pdf_map:
            raise SystemExit(f"unknown book: {b}")

    raw = json.loads(BOOKS_JSON.read_text(encoding="utf-8"))
    by_id = {b["id"]: b for b in raw.get("books") or []}
    groups_out: dict = {"note": f"ORT L{args.level} PDF OCR 对齐分组（真源 books.json pages[]）", "books": {}}

    for bid in targets:
        pdf_name, _title = pdf_map[bid]
        pdf_path = batch / pdf_name
        if not pdf_path.is_file():
            print(f"SKIP {bid}: missing PDF")
            continue
        book = by_id.get(bid)
        if not book:
            print(f"SKIP {bid}: not in books.json")
            continue
        lines = clean_artifact_lines(flatten_lines(book))
        if not lines:
            print(f"SKIP {bid}: no lines")
            continue

        ocr_pages = _ocr_page_texts(pdf_path)
        if bid in L4_OCR_TEXT_BOOKS:
            groups = groups_from_ocr_text(ocr_pages)
            mode = "ocr-text"
        else:
            groups = align_lines_to_ocr_pages(lines, ocr_pages)
            mode = "align"
        sizes = [len(g) for g in groups]
        flat_n = sum(len(g) for g in groups)
        print(f"{bid} [{mode}]: {len(lines)} json lines → {flat_n} lines, {len(groups)} pages {sizes}")

        if args.dry_run:
            for i, (ocr, g) in enumerate(zip(ocr_pages, groups), start=1):
                print(f"  p{i:02d} ocr={ocr[:50]!r}…" if len(ocr) > 50 else f"  p{i:02d} ocr={ocr!r}")
                for ln in g:
                    print(f"       → {ln}")
            continue

        by_id[bid] = apply_groups_to_book(book, groups)
        groups_out["books"][bid] = {
            "pdf_story_pages": len(groups),
            "groups": groups,
        }

    if args.dry_run:
        return 0

    raw["books"] = [by_id.get(b["id"], b) for b in raw.get("books") or []]
    BOOKS_JSON.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {BOOKS_JSON}")

    gpath = ROOT / "backend" / "teaching" / "ort_oxford_owl" / f"ort_l{args.level}_page_groups.json"
    gpath.write_text(json.dumps(groups_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {gpath}")
    print("next: cd backend && python3 -c \"from teaching.ort_oxford_owl.catalog import write_catalog; write_catalog(13)\"")
    print("      python3 teaching/build_lessons_v5.py")
    print(f"      .venv/bin/python scripts/extract_ort_pdf_pages.py --batch-level {args.level} --batch-dir \"{batch}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
