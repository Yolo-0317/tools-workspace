"""公众号正文不再渲染旧牛马品牌头。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_masthead import masthead_html


def test_all_public_articles_disable_legacy_masthead() -> None:
    for kind in (
        "market",
        "news",
        "sector",
        "hotspot",
        "hot_business",
        "silver",
        "literary",
        "tv_review",
        "workspace",
        "temp",
    ):
        assert masthead_html(kind, upload_images=False, local_preview=True) == ""
