import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.tools.fetch_eastmoney_quotes import INTERNATIONAL_INDEX_SPECS


def test_international_market_specs_include_korean_indices():
    specs = dict(INTERNATIONAL_INDEX_SPECS)
    assert specs["韩国KOSPI"] == "100.KS11"
    assert specs["韩国KOSDAQ"] == "100.KQ11"
