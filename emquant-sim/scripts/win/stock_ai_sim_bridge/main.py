# coding=utf-8
"""
掘金终端统一入口（策略 ID 不变，改 strategy_entry.json 切换逻辑）

- dragon   → dragon_main.py（龙头观察池，默认）
- combined → main_combined.py（综合选股 + 执行卡）
"""
from __future__ import print_function, absolute_import, unicode_literals

import json
import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

ENTRY_FILE = os.path.join(_DIR, "strategy_entry.json")
DEFAULT_ENTRY = "dragon"


def _load_entry():
    if os.path.isfile(ENTRY_FILE):
        try:
            with open(ENTRY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            entry = str(data.get("entry") or DEFAULT_ENTRY).strip()
            if entry in ("combined", "dragon"):
                return entry
        except Exception as exc:
            print("[entry] read error", exc)
    env = os.environ.get("EMQUANT_ENTRY", "").strip()
    if env in ("combined", "dragon"):
        return env
    return DEFAULT_ENTRY


_ENTRY = _load_entry()
print("[entry] mode=%s (strategy_entry.json: combined|dragon)" % _ENTRY)

if _ENTRY == "combined":
    from main_combined import *  # noqa: F401,F403
else:
    from dragon_main import *  # noqa: F401,F403

if __name__ == "__main__":
    from gm.api import MODE_LIVE, run

    run(
        strategy_id="REPLACE_STRATEGY_ID",
        filename="main.py",
        mode=MODE_LIVE,
        token="REPLACE_TOKEN",
    )
