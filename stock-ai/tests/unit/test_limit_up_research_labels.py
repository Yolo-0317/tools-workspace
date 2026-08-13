from __future__ import annotations

from datetime import date

import pytest

from stock_ai.limit_up_research.labels import compute_forward_labels


def _bars():
    dates = (
        date(2026, 8, 7),
        date(2026, 8, 10),
        date(2026, 8, 11),
        date(2026, 8, 12),
        date(2026, 8, 13),
        date(2026, 8, 14),
    )
    closes = (10.0, 11.0, 10.5, 12.0, 11.5, 12.5)
    return dates, [
        {
            "trade_date": day,
            "close": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "pct_chg": 10.0 if day == date(2026, 8, 10) else 1.0,
        }
        for day, close in zip(dates, closes)
    ]


def test_forward_labels_use_market_sessions_and_literal_returns() -> None:
    dates, bars = _bars()

    labels = compute_forward_labels(date(2026, 8, 7), "600000", bars, dates)

    assert [item.outcome_date for item in labels] == [
        date(2026, 8, 10),
        date(2026, 8, 12),
        date(2026, 8, 14),
    ]
    assert [item.close_return_pct for item in labels] == pytest.approx([10.0, 20.0, 25.0])
    assert labels[0].closed_limit_up is True


def test_missing_exact_code_bar_marks_horizon_incomplete_without_substitution() -> None:
    dates, bars = _bars()
    bars = [row for row in bars if row["trade_date"] != date(2026, 8, 12)]

    labels = compute_forward_labels(date(2026, 8, 7), "600000", bars, dates)

    t3 = next(item for item in labels if item.horizon == "T3")
    assert t3.outcome_date == date(2026, 8, 12)
    assert t3.data_complete is False
    assert t3.outcome_close is None
    assert "OUTCOME_BAR_MISSING" in t3.missing_fields


def test_not_due_horizons_are_not_emitted() -> None:
    dates, bars = _bars()

    labels = compute_forward_labels(
        date(2026, 8, 7), "600000", bars[:3], dates[:3]
    )

    assert [item.horizon for item in labels] == ["T1"]
