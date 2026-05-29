from __future__ import annotations

import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ensure_repo_root_on_path() -> Path:
    """把仓库根目录加入 sys.path，便于导入 tushare_mcp、scripts、core_v2 等。"""
    root = repo_root()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root
