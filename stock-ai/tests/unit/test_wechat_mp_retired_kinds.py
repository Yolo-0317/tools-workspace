from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools import wechat_mp_content as content


@pytest.mark.parametrize("kind", ["top5", "dragons", "dragon", "leaders"])
def test_retired_finance_kinds_are_not_public_routes(kind: str) -> None:
    assert "top5" not in content.DRAFT_KINDS
    assert "dragons" not in content.DRAFT_KINDS
    with pytest.raises(ValueError, match="未知 kind"):
        content.build_article(kind)


@pytest.mark.parametrize(
    "module",
    [
        "scripts.tools.wechat_mp_commerce_draft",
        "scripts.tools.wechat_mp_commerce_slots",
        "scripts.tools.wechat_mp_top5_article",
        "scripts.tools.wechat_mp_top5_polish",
        "scripts.tools.wechat_mp_dragons_article",
        "scripts.tools.wechat_mp_dragons_polish",
        "scripts.tools.wechat_mp_evening_align",
        "scripts.tools.wechat_mp_growth",
        "scripts.tools.wechat_mp_growth_check",
        "scripts.tools.wechat_mp_growth_remind",
    ],
)
def test_retired_modules_are_absent(module: str) -> None:
    assert importlib.util.find_spec(module) is None
