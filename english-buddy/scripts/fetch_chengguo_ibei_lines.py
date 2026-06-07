#!/usr/bin/env python3
"""从爱贝亲子网中文指导页拉取 ORT 课文句（非 PDF/OCR）。输出 JSON 供 merge 脚本合并进 books.json。"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" / "teaching" / "ort_oxford_owl"))

from chengguo_maps import CHENGGUO_LEVEL2, IBEI_LEVEL2_AIDS  # noqa: E402

OUT_DEFAULT = ROOT / "backend" / "teaching" / "ort_oxford_owl" / "chengguo_level2_ibei.json"


def _fetch_html(aid: int) -> str:
    url = f"https://www.i-bei.com/plus/view.php?aid={aid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")


def _extract_lines(html: str) -> list[str]:
    text = re.sub(r"<[^>]+>", "\n", html)
    lines: list[str] = []
    for raw in text.splitlines():
        if "Entry=function" in raw or "Element(" in raw:
            continue
        for m in re.finditer(r'([A-Z][^。\n]{2,100}?\.)', raw):
            en = m.group(1).strip()
            en = en.replace("&rsquo;", "'").replace("&quot;", '"').replace("&nbsp;", " ")
            en = re.sub(r"\s+", " ", en)
            if sum(1 for c in en if ord(c) > 127) > 2:
                continue
            if len(en) < 5 or en in lines:
                continue
            if en.startswith("Entry"):
                continue
            lines.append(en)
        if "Oh no" in raw and "Oh no!" not in lines:
            lines.append("Oh no!")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--delay", type=float, default=0.12, help="秒，请求间隔")
    args = parser.parse_args()

    books_out: list[dict] = []
    for _pdf, book_id, title in CHENGGUO_LEVEL2:
        aid = IBEI_LEVEL2_AIDS.get(book_id)
        if not aid:
            books_out.append({"id": book_id, "title": title, "aid": None, "lines": []})
            continue
        try:
            html = _fetch_html(aid)
            lines = _extract_lines(html)
            books_out.append({"id": book_id, "title": title, "aid": aid, "lines": lines})
            print(f"ok {book_id} aid={aid} lines={len(lines)}")
        except Exception as e:
            print(f"fail {book_id} aid={aid}: {e}", file=sys.stderr)
            books_out.append({"id": book_id, "title": title, "aid": aid, "lines": [], "error": str(e)})
        time.sleep(args.delay)

    payload = {"source": "i-bei.com ORT L2 guides", "books": books_out}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
