from __future__ import annotations

import sys
from pathlib import Path

_repo = Path(__file__).resolve().parents[1]
_repo_str = str(_repo)
if _repo_str not in sys.path:
    sys.path.insert(0, _repo_str)

from stock_ai.bootstrap import ensure_repo_root_on_path  # noqa: E402

__all__ = ["ensure_repo_root_on_path"]
