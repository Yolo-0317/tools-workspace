from __future__ import annotations

from datetime import date, timedelta
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.limit_up_logic import (  # noqa: E402
    extract_limit_up_features,
    limit_up_threshold,
    normalize_bars,
)


def _bar(day: int, close: float, pct: float, amount: float = 100.0) -> dict[str, object]:
    return {
        "trade_date": (date(2026, 7, 1) + timedelta(days=day)).isoformat(),
        "open": close * 0.99,
        "high": close * 1.01,
        "low": close * 0.98,
        "close": close,
        "pct_chg": pct,
        "amount": amount,
    }


def test_board_specific_limit_up_thresholds_prevent_wrong_board_detection() -> None:
    assert limit_up_threshold("603011") == 9.5
    assert limit_up_threshold("300001") == 19.5
    assert limit_up_threshold("688001") == 19.5
    assert limit_up_threshold("603011", is_st=True) is None


def test_two_recent_limit_ups_create_strong_limit_up_gene() -> None:
    rows = [_bar(i, 10 + i * 0.05, 0.5) for i in range(20)]
    rows[12] = _bar(12, 12.0, 10.01, 250.0)
    rows[17] = _bar(17, 13.2, 9.99, 280.0)

    features = extract_limit_up_features("603011", normalize_bars(rows))

    assert features.recent_limit_up_count == 2
    assert features.limit_up_gene == "STRONG"


def test_short_history_returns_structured_insufficient_data() -> None:
    features = extract_limit_up_features(
        "603011", normalize_bars([_bar(i, 10 + i * 0.05, 0.5) for i in range(9)])
    )

    assert features.data_sufficient is False
    assert features.limit_up_gene == "UNKNOWN"
    assert "daily_bars_10" in features.missing_fields
