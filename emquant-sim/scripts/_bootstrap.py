"""emquant-sim 路径：本仓库根 + 只读引用 stock-ai（执行卡解析）。"""

from __future__ import annotations

import sys
from pathlib import Path

_EMQUANT_ROOT = Path(__file__).resolve().parents[1]
_STOCK_AI_ROOT = _EMQUANT_ROOT.parent / "stock-ai"


def emquant_root() -> Path:
    return _EMQUANT_ROOT


def stock_ai_root() -> Path:
    return _STOCK_AI_ROOT


def ensure_paths() -> Path:
    s = str(_EMQUANT_ROOT)
    if s not in sys.path:
        sys.path.insert(0, s)
    return _EMQUANT_ROOT


def import_stock_ai_module(relative: str):
    """按文件路径加载 stock-ai 模块，避免与 emquant-sim 的 scripts 包名冲突。"""
    import importlib.util

    path = _STOCK_AI_ROOT / relative
    if not path.is_file():
        raise ImportError(f"stock-ai 模块不存在: {path}")
    name = "sa_" + relative.replace("/", "_").replace(".py", "")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod
