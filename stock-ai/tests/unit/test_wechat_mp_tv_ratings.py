"""评分与剧照。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_tv_ratings import (
    collect_rating_rows,
    format_ratings_lines,
    format_ratings_text,
    generate_rating_card,
    rating_card_path,
)
from scripts.tools.wechat_mp_tv_topics import CURATED_HOT


def test_format_ratings_lines_vertical() -> None:
    topic = next(t for t in CURATED_HOT if t["title_en"] == "Euphoria")
    bullets, foot = format_ratings_lines(topic)
    assert len(bullets) >= 5
    assert all(b.startswith("·") for b in bullets)
    assert foot.startswith("（截至")
    assert any("豆瓣" in ln and "8.0" in ln for ln in bullets)
    assert any("TMDB" in ln and "8.1" in ln for ln in bullets)
    tmdb_line = next(ln for ln in bullets if "TMDB" in ln)
    assert " · " not in tmdb_line


def test_format_ratings_text() -> None:
    topic = next(t for t in CURATED_HOT if t["title_en"] == "Euphoria")
    text = format_ratings_text(topic)
    assert "8.0" in text
    assert "42" in text
    assert text.count("\n") >= 4


def test_collect_rating_rows() -> None:
    topic = next(t for t in CURATED_HOT if t["title_en"] == "Euphoria")
    rows = collect_rating_rows(topic["ratings"])
    names = [r[0] for r in rows]
    assert names == ["豆瓣", "IMDb", "烂番茄", "烂番茄观众", "Metacritic", "TMDB"]


def test_generate_rating_card() -> None:
    topic = next(t for t in CURATED_HOT if t["title_en"] == "Euphoria")
    path = generate_rating_card(topic)
    assert path is not None
    assert path.is_file()
    assert path == rating_card_path("euphoria")
