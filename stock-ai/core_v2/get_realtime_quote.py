"""盘中现价：OpenCLI 打开东财行情页（不再调用 push2 API）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.fetch_eastmoney_quotes import fetch_sop_snapshots


def fetch_realtime_quote(code: str) -> dict | None:
    code6 = str(code).split(".")[0].zfill(6)
    snaps = fetch_sop_snapshots([code6])
    snap = snaps.get(code6)
    if not snap:
        return None
    return {
        "code": snap.code,
        "name": snap.name,
        "price": snap.price,
        "change_amt": snap.change_amt,
        "change_pct": snap.change_pct,
        "info": snap.info_text,
        "source": snap.source,
    }


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "002266"
    quote = fetch_realtime_quote(c)
    if quote:
        print(json.dumps(quote, indent=2, ensure_ascii=False))
    else:
        print("Failed to fetch quote")
