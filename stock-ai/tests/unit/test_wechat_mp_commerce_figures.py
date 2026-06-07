"""带货稿插图注入。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_figures import inject_commerce_figures


def test_inject_commerce_figures_inserts_markers() -> None:
    body = """> 窄台面为什么先谈收纳

一段文字。

> 两类通常更值的

更多文字。

> 买之前对照三件事

清单。
"""
    out = inject_commerce_figures(body, vertical="home")
    assert "01-compact-kitchen.jpg" in out
    assert "02-small-kitchen.jpg" in out
    assert "03-counter.jpg" in out
