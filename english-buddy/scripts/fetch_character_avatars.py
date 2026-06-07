#!/usr/bin/env python3
"""Download square character avatars via Playwright (Bing image search)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "characters"

QUERIES = {
    "elsa": "Elsa Frozen Disney official portrait",
    "ultra": "Ultraman official hero portrait",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", choices=list(QUERIES))
    args = parser.parse_args()
    keys = args.only or list(QUERIES)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && playwright install chromium", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        )
        for key in keys:
            q = QUERIES[key]
            url = f"https://www.bing.com/images/search?q={q.replace(' ', '+')}&qft=+filterui:photo-photo"
            print(f"[{key}] {q}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)
            img = page.locator("img.mimg").first
            src = img.get_attribute("src") or img.get_attribute("data-src") or ""
            if not src or src.startswith("data:"):
                print(f"  skip: no src", file=sys.stderr)
                continue
            if src.startswith("//"):
                src = "https:" + src
            resp = page.request.get(src, timeout=60000)
            if not resp.ok:
                print(f"  skip: HTTP {resp.status}", file=sys.stderr)
                continue
            body = resp.body()
            if len(body) < 8000:
                print(f"  skip: too small ({len(body)} B)", file=sys.stderr)
                continue
            ext = ".jpg"
            ct = resp.headers.get("content-type", "")
            if "png" in ct:
                ext = ".png"
            dest = OUT / f"{key}{ext}"
            dest.write_bytes(body)
            # Normalize to .jpg name for frontend (copy png as jpg path if png)
            jpg = OUT / f"{key}.jpg"
            if ext != ".jpg":
                jpg.write_bytes(body)
            else:
                if dest != jpg:
                    jpg.write_bytes(body)
            print(f"  saved {jpg} ({len(body)//1024} KB)")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
