from __future__ import annotations

from datetime import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.limit_up_logic import LimitUpContext, analyze_limit_up_logic  # noqa: E402


def _hedun_bars_through_august_6() -> list[dict[str, object]]:
    raw = [
        ("2026-07-20", 20.27, 20.74, 18.23, 18.23, -9.98, 776050487.0),
        ("2026-07-21", 17.99, 18.37, 16.41, 18.10, -0.71, 895609646.0),
        ("2026-07-22", 17.89, 18.88, 17.43, 17.64, -2.54, 734866407.0),
        ("2026-07-23", 17.76, 18.72, 17.50, 18.12, 2.72, 724345920.0),
        ("2026-07-24", 17.94, 18.66, 17.54, 17.61, -2.81, 557647500.0),
        ("2026-07-27", 17.61, 18.65, 17.37, 18.56, 5.39, 573164459.0),
        ("2026-07-28", 18.43, 19.10, 17.88, 18.03, -2.86, 731819018.0),
        ("2026-07-29", 18.06, 18.10, 17.00, 17.71, -1.77, 739830503.0),
        ("2026-07-30", 17.55, 18.24, 16.44, 16.50, -6.83, 695963432.0),
        ("2026-07-31", 17.20, 18.06, 16.91, 16.91, 2.48, 781817728.0),
        ("2026-08-03", 17.81, 18.60, 17.50, 18.60, 9.99, 417708441.0),
        ("2026-08-04", 19.85, 19.86, 18.60, 19.44, 4.52, 1912158215.0),
        ("2026-08-05", 19.10, 20.31, 19.08, 20.29, 4.37, 1848193564.0),
        ("2026-08-06", 20.03, 20.93, 19.99, 20.62, 1.63, 1515309713.0),
    ]
    return [
        {
            "trade_date": day,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "pct_chg": pct,
            "amount": amount,
        }
        for day, open_price, high, low, close, pct, amount in raw
    ]


def test_hedun_august_6_replay_is_second_wave_candidate() -> None:
    result = analyze_limit_up_logic(
        "603011",
        "合锻智能",
        _hedun_bars_through_august_6(),
        LimitUpContext(
            concepts=("可控核聚变", "光通信模块", "工业母机"),
            active_themes=("可控核聚变",),
            sector_change_pct=2.1,
            sector_limit_up_count=3,
            sector_leader_strength="strong",
            observed_at=datetime(2026, 8, 6, 15, 0),
        ),
    )

    assert result.identity == "SECOND_WAVE_CANDIDATE"
    assert result.paths.acceleration <= 45
    assert sum(result.paths.as_tuple()) == 100
    assert any("首板后" in item for item in result.drivers)
    assert "auction_strength" in result.missing_fields
    assert "seal_quality" in result.missing_fields
