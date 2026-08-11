from __future__ import annotations

from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
import sys
import time

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "analysis" / "backtest_short_term_trade.py"


def _module():
    name = "backtest_short_term_trade_v21_test"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _flat_frame(*, sessions: int = 600, codes: tuple[str, ...] = ("600001",)) -> pd.DataFrame:
    start = date(2024, 1, 2)
    rows = []
    for session in range(sessions):
        trade_date = start + timedelta(days=session)
        for code_index, code in enumerate(codes):
            close = 10.0 + code_index + session * (code_index + 1) / 1000
            rows.append(
                {
                    "ts_code": f"{code}.SH" if code.startswith("6") else f"{code}.SZ",
                    "code": code,
                    "trade_date": trade_date,
                    "open": close,
                    "high": close + 0.1,
                    "low": close - 0.1,
                    "close": close,
                    "pct_chg": 0.1,
                    "amount": 50_000.0,
                    "name": code,
                    "sector": "测试",
                }
            )
    return pd.DataFrame(rows)


def test_relative_strength_uses_the_whole_fixture_universe() -> None:
    module = _module()
    frame = _flat_frame(sessions=21, codes=("600001", "600002", "000001", "000002"))
    analysis_date = max(frame["trade_date"])

    snapshots = module.build_cross_section_snapshots(frame)
    snapshot = snapshots[analysis_date]

    assert snapshot.current_count == 4
    assert snapshot.eligible_count == 4
    assert set(snapshot.percentiles) == {"600001", "600002", "000001", "000002"}
    assert snapshot.percentiles["000002"] > snapshot.percentiles["600001"]


def test_relative_strength_does_not_substitute_an_older_code_specific_bar() -> None:
    module = _module()
    frame = _flat_frame(sessions=22, codes=("600001", "600002"))
    missing_date = sorted(set(frame["trade_date"]))[1]
    frame = frame[
        ~((frame["code"] == "600002") & (frame["trade_date"] == missing_date))
    ]
    analysis_date = max(frame["trade_date"])

    snapshot = module.build_cross_section_snapshots(frame)[analysis_date]

    assert snapshot.current_count == 2
    assert snapshot.eligible_count == 1
    assert snapshot.coverage_ratio == 0.5
    assert "600002" not in snapshot.percentiles


def test_policy_research_uses_identical_dates_costs_and_portfolio_limits() -> None:
    module = _module()
    frame = _flat_frame()
    start = min(frame["trade_date"])
    end = max(frame["trade_date"])

    outcome = module.run_policy_research(
        frame,
        start=start,
        end=end,
        commission_rate=0.001,
        slippage_rate=0.002,
        max_positions=2,
        cooldown_sessions=5,
    )

    common = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "commission_rate": 0.001,
        "slippage_rate": 0.002,
        "max_positions": 2,
        "cooldown_sessions": 5,
    }
    assert outcome.payload["report_type"] == "technical_execution_proxy"
    assert set(outcome.payload["policies"]) == {
        "BASELINE",
        "STRICT_A",
        "STRICT_B",
        "STRICT_C",
    }
    assert all(
        result["configuration"] == common
        for result in outcome.payload["policies"].values()
    )
    assert outcome.artifact.promoted is False


def test_signal_histories_never_include_bars_after_the_signal_date(monkeypatch) -> None:
    module = _module()
    frame = _flat_frame(sessions=65)
    frame["amount"] = 150_000.0
    frame.loc[frame.index[-1], ["open", "high", "low", "close", "pct_chg", "amount"]] = (
        11.80,
        12.10,
        11.70,
        12.00,
        5.0,
        225_000.0,
    )
    observed: list[tuple[date, date]] = []

    def selector(**kwargs):
        for bars in kwargs["bars_by_code"].values():
            observed.append((kwargs["analysis_date"], max(bar.trade_date for bar in bars)))
        return module.SelectionResult(kwargs["analysis_date"], (), ())

    monkeypatch.setattr(module, "select_short_term_candidates", selector)
    end = max(frame["trade_date"])
    module.build_policy_opportunities(frame, start=end, end=end, top_n=5)

    assert observed
    assert all(latest <= signal_date for signal_date, latest in observed)


def test_malformed_chronology_returns_code_2_without_writing_artifact(
    monkeypatch, tmp_path, capsys
) -> None:
    module = _module()
    frame = _flat_frame(sessions=596)
    artifact_path = tmp_path / "validation.json"
    monkeypatch.setattr(module, "_mysql_engine", lambda: object())
    monkeypatch.setattr(module, "load_prices", lambda *_: frame)

    result = module.main(
        [
            "--start",
            str(min(frame["trade_date"])),
            "--end",
            str(max(frame["trade_date"])),
            "--output",
            "json",
            "--write-validation",
            str(artifact_path),
        ]
    )

    assert result == 2
    assert not artifact_path.exists()
    assert "promoted" not in capsys.readouterr().out


def test_json_report_contains_no_connection_or_holdings_fields() -> None:
    module = _module()
    frame = _flat_frame()
    outcome = module.run_policy_research(
        frame,
        start=min(frame["trade_date"]),
        end=max(frame["trade_date"]),
    )

    encoded = json.dumps(outcome.payload, ensure_ascii=False)
    assert "technical_execution_proxy" in encoded
    assert "MYSQL" not in encoded
    assert "password" not in encoded.lower()
    assert "holdings" not in encoded.lower()


def test_empty_candidate_fixture_benchmark_finishes_under_five_seconds() -> None:
    module = _module()
    frame = _flat_frame()
    started = time.perf_counter()

    module.run_policy_research(
        frame,
        start=min(frame["trade_date"]),
        end=max(frame["trade_date"]),
    )

    assert time.perf_counter() - started < 5.0
