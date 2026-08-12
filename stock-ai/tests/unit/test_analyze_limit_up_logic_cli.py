from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.analysis import analyze_limit_up_logic as cli  # noqa: E402


HEDUN_ROWS = [
    {"trade_date": "2026-07-20", "open": 20.27, "high": 20.74, "low": 18.23, "close": 18.23, "pct_chg": -9.98, "amount": 776050487.0},
    {"trade_date": "2026-07-21", "open": 17.99, "high": 18.37, "low": 16.41, "close": 18.10, "pct_chg": -0.71, "amount": 895609646.0},
    {"trade_date": "2026-07-22", "open": 17.89, "high": 18.88, "low": 17.43, "close": 17.64, "pct_chg": -2.54, "amount": 734866407.0},
    {"trade_date": "2026-07-23", "open": 17.76, "high": 18.72, "low": 17.50, "close": 18.12, "pct_chg": 2.72, "amount": 724345920.0},
    {"trade_date": "2026-07-24", "open": 17.94, "high": 18.66, "low": 17.54, "close": 17.61, "pct_chg": -2.81, "amount": 557647500.0},
    {"trade_date": "2026-07-27", "open": 17.61, "high": 18.65, "low": 17.37, "close": 18.56, "pct_chg": 5.39, "amount": 573164459.0},
    {"trade_date": "2026-07-28", "open": 18.43, "high": 19.10, "low": 17.88, "close": 18.03, "pct_chg": -2.86, "amount": 731819018.0},
    {"trade_date": "2026-07-29", "open": 18.06, "high": 18.10, "low": 17.00, "close": 17.71, "pct_chg": -1.77, "amount": 739830503.0},
    {"trade_date": "2026-07-30", "open": 17.55, "high": 18.24, "low": 16.44, "close": 16.50, "pct_chg": -6.83, "amount": 695963432.0},
    {"trade_date": "2026-07-31", "open": 17.20, "high": 18.06, "low": 16.91, "close": 16.91, "pct_chg": 2.48, "amount": 781817728.0},
    {"trade_date": "2026-08-03", "open": 17.81, "high": 18.60, "low": 17.50, "close": 18.60, "pct_chg": 9.99, "amount": 417708441.0},
    {"trade_date": "2026-08-04", "open": 19.85, "high": 19.86, "low": 18.60, "close": 19.44, "pct_chg": 4.52, "amount": 1912158215.0},
    {"trade_date": "2026-08-05", "open": 19.10, "high": 20.31, "low": 19.08, "close": 20.29, "pct_chg": 4.37, "amount": 1848193564.0},
    {"trade_date": "2026-08-06", "open": 20.03, "high": 20.93, "low": 19.99, "close": 20.62, "pct_chg": 1.63, "amount": 1515309713.0},
]


def test_cli_prints_historical_replay_card(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "load_stock_daily_bars", lambda *args, **kwargs: HEDUN_ROWS)

    exit_code = cli.main(
        [
            "--code",
            "603011",
            "--name",
            "合锻智能",
            "--as-of",
            "2026-08-06",
            "--concept",
            "可控核聚变,光通信模块,工业母机",
            "--active-theme",
            "可控核聚变",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "二波加速候选" in output
    assert "涨停加速" in output


def test_cli_returns_nonzero_when_mysql_has_no_bars(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "load_stock_daily_bars", lambda *args, **kwargs: [])

    exit_code = cli.main(["--code", "603011", "--name", "合锻智能"])

    assert exit_code == 2
    assert "没有可用的完整日线" in capsys.readouterr().err
