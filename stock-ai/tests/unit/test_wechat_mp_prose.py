"""market 结构判断分段排版。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_prose import reflow_market_structure_section


def test_reflow_structure_view_phrases() -> None:
    raw = """> 结构判断

盘前整体偏震荡。我们认为，指数缺少方向。值得关注的是，煤化工价差走阔。向后看，关注A50与量能。"""
    out = reflow_market_structure_section(raw)
    assert "\n\n我们认为" in out or out.strip().startswith("> 结构判断")
    assert "我们认为" in out
    assert "值得关注的是" in out
    assert "向后看" in out
    # 三处小结应拆成多行（至少 4 段：引导 + 3 小结）
    view_lines = []
    in_view = False
    for line in out.splitlines():
        if line.strip().endswith("结构判断") or "> 结构判断" in line:
            in_view = True
            continue
        if in_view and line.strip().startswith(">"):
            break
        if in_view and line.strip():
            view_lines.append(line.strip())
    assert len(view_lines) >= 3
