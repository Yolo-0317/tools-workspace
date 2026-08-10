"""年份/刑期阿拉伯数字规范化。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_prose import normalize_arabic_year_numerals


def test_cn_year_to_arabic() -> None:
    assert normalize_arabic_year_numerals("二〇一八年判决") == "2018年判决"
    assert normalize_arabic_year_numerals("二零一八年案发") == "2018年案发"


def test_cn_duration_years_to_arabic() -> None:
    assert normalize_arabic_year_numerals("获刑近六年") == "获刑近6年"
    assert normalize_arabic_year_numerals("有期徒刑十七年") == "有期徒刑17年"


def test_arabic_years_unchanged() -> None:
    assert normalize_arabic_year_numerals("2018年案发") == "2018年案发"
