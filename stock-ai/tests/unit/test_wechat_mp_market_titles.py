"""market 标题轮换池。"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_content import (
    TITLE_MAX,
    _clip_wechat_title,
    _market_title,
    _titles_too_similar,
)
from scripts.tools.wechat_mp_market_titles import (
    MARKET_TITLE_TEMPLATES,
    build_market_title_options,
    load_recent_market_titles,
    pick_rotated_market_title,
    rotate_options,
)


def test_each_edition_has_many_templates() -> None:
    assert len(MARKET_TITLE_TEMPLATES["pre"]) >= 15
    assert len(MARKET_TITLE_TEMPLATES["midday"]) >= 15
    assert len(MARKET_TITLE_TEMPLATES["close"]) >= 15


def test_rotate_options_cycles() -> None:
    opts = ["a", "b", "c", "d"]
    assert rotate_options(opts, seed=1) == ["b", "c", "d", "a"]
    assert rotate_options(opts, seed=0) == opts


def test_pick_rotated_avoids_recent(tmp_path: Path) -> None:
    log = tmp_path / "log.json"
    log.write_text(
        json.dumps({"2026-06-02": {"close": "收盘复盘：油价+半导体牵动哪些线？"}}),
        encoding="utf-8",
    )
    options = build_market_title_options("close", wd="周二", tags="油价+半导体")
    now = datetime(2026, 6, 3, 17, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    recent = load_recent_market_titles("close", log_path=log, today=date(2026, 6, 3))
    title = pick_rotated_market_title(
        options,
        now=now,
        edition="close",
        peer_title=None,
        recent_titles=recent,
        clip_fn=_clip_wechat_title,
        too_similar_fn=_titles_too_similar,
    )
    assert len(title) <= TITLE_MAX
    assert not _titles_too_similar(title, "收盘复盘：油价+半导体牵动哪些线？")


def test_market_title_uses_edition_pools() -> None:
    ai = "富时A50期货盘前微跌，煤化工煤油比走阔，MLCC产能缺口，半导体震荡。"
    now = datetime(2026, 6, 2, 17, 45, tzinfo=ZoneInfo("Asia/Shanghai"))
    peer = "收盘复盘：油价+半导体牵动哪些线？"
    pre = _market_title(ai, now=now, edition="pre", peer_title=peer)
    assert "盘前" in pre or "开市" in pre or "开盘" in pre or "竞价" in pre or "早读" in pre
    assert not _titles_too_similar(pre, peer)
