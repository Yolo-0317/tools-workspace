from __future__ import annotations

from datetime import date, timedelta
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.limit_up_logic import LimitUpContext, analyze_limit_up_logic  # noqa: E402


def _trend_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(25):
        close = 10 + index * 0.08
        rows.append(
            {
                "trade_date": (date(2026, 7, 1) + timedelta(days=index)).isoformat(),
                "open": close - 0.04,
                "high": close + 0.10,
                "low": close - 0.10,
                "close": close,
                "pct_chg": 0.7,
                "amount": 100_000 + index * 1_000,
            }
        )
    return rows


def test_concept_labels_without_active_theme_do_not_add_sector_score() -> None:
    result = analyze_limit_up_logic(
        "603011",
        "合锻智能",
        _trend_rows(),
        LimitUpContext(concepts=("光通信模块", "工业母机", "可控核聚变")),
    )

    assert result.score.theme_sector == 0
    assert result.identity == "NORMAL_TREND"


def test_material_risk_vetoes_new_risk_but_keeps_probability_auditable() -> None:
    result = analyze_limit_up_logic(
        "603011",
        "合锻智能",
        _trend_rows(),
        LimitUpContext(
            material_risk=True,
            material_risk_reasons=("官方重大风险公告",),
        ),
    )

    assert result.identity == "RISK_VETOED"
    assert result.new_risk_forbidden is True
    assert result.paths.failure >= 80
    assert sum(result.paths.as_tuple()) == 100


def test_post_board_volume_breakdown_is_relay_failure() -> None:
    rows = _trend_rows()
    rows[20].update(
        {"open": 11.55, "high": 12.40, "low": 11.50, "close": 12.35, "pct_chg": 10.01, "amount": 300_000}
    )
    rows[21].update(
        {"open": 12.10, "high": 12.15, "low": 10.90, "close": 11.00, "pct_chg": -10.9, "amount": 500_000}
    )

    result = analyze_limit_up_logic("603011", "合锻智能", rows, LimitUpContext())

    assert result.identity == "RELAY_FAILED"
    assert result.paths.failure >= 65

