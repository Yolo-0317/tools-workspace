"""公众号插图池主题约束。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_figure_pool import (
    FIGURE_DOMAIN_TAGS,
    figure_matches_domain,
    list_available_figures,
)


def test_figure_matches_domain() -> None:
    assert figure_matches_domain(("market", "chart"))
    assert figure_matches_domain(("tech", "ai"))
    assert not figure_matches_domain(("home", "kitchen"))
    assert not figure_matches_domain(("global", "news"))
    assert not figure_matches_domain(("city", "office"))


def test_manifest_figures_match_domain() -> None:
    figures = list_available_figures()
    assert figures
    for fig in figures:
        assert figure_matches_domain(fig.tags), fig.file
        assert set(fig.tags) & FIGURE_DOMAIN_TAGS
