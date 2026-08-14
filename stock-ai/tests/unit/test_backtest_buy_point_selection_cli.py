from __future__ import annotations

import importlib.util
import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from stock_ai.buy_point_selection.models import OutcomeLabel, SetupType
from stock_ai.buy_point_selection.validation import OutcomeCalibration, TradeObservation


SCRIPT = Path(__file__).parents[2] / "scripts" / "analysis" / "backtest_buy_point_selection.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("backtest_buy_point_selection", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_dates(path: Path) -> None:
    start = date(2024, 1, 2)
    dates = [(start + timedelta(days=index)).isoformat() for index in range(630)]
    path.write_text(json.dumps(dates), encoding="utf-8")


def test_run_test_requires_a_frozen_profile(tmp_path, capsys) -> None:
    """Catches test-set execution before the policy and split are immutable."""
    module = _load_module()
    dates = tmp_path / "dates.json"
    artifact = tmp_path / "artifact.json"
    _write_dates(dates)
    result = module.main(
        [
            "--run-test",
            "--write-artifact",
            "--trading-dates",
            str(dates),
            "--profile",
            str(tmp_path / "missing-profile.json"),
            "--artifact",
            str(artifact),
        ]
    )
    assert result == 2
    assert not artifact.exists()
    assert "frozen profile" in capsys.readouterr().err.lower()


def test_freeze_then_run_writes_separate_non_promotable_technical_metrics(tmp_path) -> None:
    """Catches incomplete historical references being blended into formal metrics."""
    module = _load_module()
    dates = tmp_path / "dates.json"
    observations = tmp_path / "observations.json"
    profile = tmp_path / "profile.json"
    artifact = tmp_path / "artifact.json"
    _write_dates(dates)
    observations.write_text("[]", encoding="utf-8")
    assert module.main(
        ["--freeze-profile", "--trading-dates", str(dates), "--profile", str(profile)]
    ) == 0
    assert module.main(
        [
            "--run-test",
            "--write-artifact",
            "--trading-dates",
            str(dates),
            "--observations",
            str(observations),
            "--profile",
            str(profile),
            "--artifact",
            str(artifact),
        ]
    ) == 0
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["schema"] == "buy-point-selection-validation-v2"
    assert payload["calibrations"] == {}
    assert payload["promoted"] is False
    assert "POINT_IN_TIME_COVERAGE_INCOMPLETE" in payload["reasons"]
    assert payload["technical_core_metrics"] is not None
    assert payload["fully_gated_metrics"] is None


def test_run_rejects_a_tampered_frozen_hash(tmp_path, capsys) -> None:
    """Catches silent policy changes after profile freezing."""
    module = _load_module()
    dates = tmp_path / "dates.json"
    profile = tmp_path / "profile.json"
    _write_dates(dates)
    assert module.main(
        ["--freeze-profile", "--trading-dates", str(dates), "--profile", str(profile)]
    ) == 0
    payload = json.loads(profile.read_text(encoding="utf-8"))
    payload["policy_hash"] = "tampered"
    profile.write_text(json.dumps(payload), encoding="utf-8")
    result = module.main(
        [
            "--run-test",
            "--trading-dates",
            str(dates),
            "--profile",
            str(profile),
        ]
    )
    assert result == 2
    assert "hash mismatch" in capsys.readouterr().err.lower()


def test_observation_without_path_fields_fails_closed(tmp_path, capsys) -> None:
    """Catches legacy net-return-only rows entering calibrated validation."""
    module = _load_module()
    dates = tmp_path / "dates.json"
    observations = tmp_path / "observations.json"
    _write_dates(dates)
    observations.write_text(
        json.dumps(
            [
                {
                    "exit_date": "2026-01-02",
                    "setup_type": "PRE_BREAKOUT",
                    "sector_code": "S1",
                    "net_return": "0.01",
                    "net_pnl": "100",
                }
            ]
        ),
        encoding="utf-8",
    )
    result = module.main(
        [
            "--research-train-validation",
            "--trading-dates",
            str(dates),
            "--observations",
            str(observations),
        ]
    )
    assert result == 2
    assert "outcome" in capsys.readouterr().err.lower()


def _write_complete_replay_bundle(tmp_path: Path) -> tuple[Path, Path, Path]:
    dates_path = tmp_path / "dates.json"
    observations_path = tmp_path / "observations.json"
    manifest_path = tmp_path / "manifest.json"
    _write_dates(dates_path)
    dates = json.loads(dates_path.read_text(encoding="utf-8"))
    observations = []
    for index, value in enumerate(dates):
        winner = index % 4 != 3
        observations.append(
            {
                "signal_date": value,
                "exit_date": value,
                "code": f"600{index % 1000:03d}",
                "structure_id": f"structure-{index}",
                "setup_type": "PRE_BREAKOUT",
                "sector_code": f"S{index % 4}",
                "net_return": "0.02" if winner else "-0.01",
                "net_pnl": "80" if winner else "-40",
                "outcome": "TARGET_2R_FIRST" if winner else "STOP_FIRST",
                "market_status": "ALLOW",
                "sector_resonating": True,
                "mfe": "0.06" if winner else "0.01",
                "mae": "0.01" if winner else "0.04",
                "risk_fraction": "0.03",
            }
        )
    observations_path.write_text(
        json.dumps(observations, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "schema": "buy-point-replay-integrity-v1",
                "complete": True,
                "rule_version": "buy-point-selection-3.1.0",
                "policy_hash": "filled-by-test",
                "trading_date_count": 630,
                "observation_count": 630,
                "trading_dates_sha256": hashlib.sha256(
                    dates_path.read_bytes()
                ).hexdigest(),
                "observations_sha256": hashlib.sha256(
                    observations_path.read_bytes()
                ).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    return dates_path, observations_path, manifest_path


def test_freeze_profile_v2_excludes_frozen_test_outcomes(tmp_path) -> None:
    """Catches test results leaking into the calibration used to rank that same test."""
    module = _load_module()
    dates, observations, manifest = _write_complete_replay_bundle(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_payload["policy_hash"] = module.policy_hash(module.SelectionPolicy())
    manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
    profile = tmp_path / "profile.json"

    result = module.main(
        [
            "--freeze-profile",
            "--trading-dates",
            str(dates),
            "--observations",
            str(observations),
            "--manifest",
            str(manifest),
            "--profile",
            str(profile),
            "--point-in-time-complete",
        ]
    )

    assert result == 0
    payload = json.loads(profile.read_text(encoding="utf-8"))
    assert payload["schema"] == "buy-point-selection-frozen-profile-v2"
    assert payload["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    setup = payload["calibrations"]["PRE_BREAKOUT|*|*"]
    assert setup["triggered_trades"] == 504
    assert setup["promoted"] is True


def test_point_in_time_freeze_rejects_manifest_hash_mismatch(tmp_path, capsys) -> None:
    """Catches observations changing after their integrity manifest was produced."""
    module = _load_module()
    dates, observations, manifest = _write_complete_replay_bundle(tmp_path)
    observations.write_text("[]\n", encoding="utf-8")

    result = module.main(
        [
            "--freeze-profile",
            "--trading-dates",
            str(dates),
            "--observations",
            str(observations),
            "--manifest",
            str(manifest),
            "--profile",
            str(tmp_path / "profile.json"),
            "--point-in-time-complete",
        ]
    )

    assert result == 2
    assert "hash mismatch" in capsys.readouterr().err.lower()


def test_run_test_v2_uses_frozen_calibrations_and_only_test_signals(tmp_path) -> None:
    """Catches final metrics being computed from train rows or recalibrated on test outcomes."""
    module = _load_module()
    dates, observations, manifest = _write_complete_replay_bundle(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_payload["policy_hash"] = module.policy_hash(module.SelectionPolicy())
    manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
    profile = tmp_path / "profile.json"
    artifact = tmp_path / "artifact.json"
    common = [
        "--trading-dates",
        str(dates),
        "--observations",
        str(observations),
        "--manifest",
        str(manifest),
        "--profile",
        str(profile),
        "--point-in-time-complete",
    ]
    assert module.main(["--freeze-profile", *common]) == 0

    result = module.main(
        ["--run-test", "--write-artifact", *common, "--artifact", str(artifact)]
    )

    assert result == 0
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["calibrations"]["PRE_BREAKOUT|*|*"]["triggered_trades"] == 504
    assert payload["technical_core_metrics"]["aggregate"]["triggered_trades"] == 126
    assert len(payload["selected_test_structure_ids"]) == 126

    before = artifact.read_bytes()
    repeated = module.main(
        ["--run-test", "--write-artifact", *common, "--artifact", str(artifact)]
    )
    assert repeated == 2
    assert artifact.read_bytes() == before


def test_frozen_test_ranking_does_not_use_candidate_outcome() -> None:
    """Catches test winners being selected with hindsight inside a same-sector tie."""
    module = _load_module()
    day = date(2026, 1, 2)
    calibration = OutcomeCalibration(
        key="PRE_BREAKOUT|ALLOW|1",
        setup_type=SetupType.PRE_BREAKOUT,
        market_status="ALLOW",
        sector_resonating=True,
        data_end=date(2025, 12, 31),
        total_plans=40,
        triggered_trades=40,
        untriggered_plans=0,
        target_2r_rate=Decimal("0.60"),
        target_2r_interval=(Decimal("0.44"), Decimal("0.74")),
        stop_first_rate=Decimal("0.25"),
        stop_first_interval=(Decimal("0.14"), Decimal("0.40")),
        net_expectancy=Decimal("0.01"),
        positive_rolling_window_ratio=Decimal("0.70"),
        frozen_test_expectancy=Decimal("0.01"),
        average_profit_loss_ratio=Decimal("2"),
        profit_factor=Decimal("1.5"),
        mfe_median=Decimal("0.05"),
        mfe_p25=Decimal("0.03"),
        mae_median=Decimal("0.02"),
        mae_p75=Decimal("0.04"),
        promoted=True,
        reasons=(),
    )

    def observation(code: str, outcome: str, risk: str):
        return TradeObservation(
            exit_date=day,
            setup_type=SetupType.PRE_BREAKOUT,
            sector_code="S1",
            net_return=Decimal("0.20" if outcome == "TARGET_2R_FIRST" else "-0.02"),
            net_pnl=Decimal("800" if outcome == "TARGET_2R_FIRST" else "-80"),
            outcome=OutcomeLabel(outcome),
            market_status="ALLOW",
            sector_resonating=True,
            mfe=Decimal("0.20"),
            mae=Decimal("0.02"),
            signal_date=day,
            code=code,
            structure_id=f"structure-{code}",
            risk_fraction=Decimal(risk),
        )

    selected = module._frozen_test_observations(
        (
            observation("600001", "TARGET_2R_FIRST", "0.04"),
            observation("600002", "STOP_FIRST", "0.02"),
        ),
        test_dates=(day,),
        calibrations={calibration.key: calibration},
    )

    assert [value.code for value in selected] == ["600002"]


def test_frozen_test_enforces_three_concurrent_positions() -> None:
    """Catches independently simulated winners exceeding the stage-1 portfolio limit."""
    module = _load_module()
    start = date(2026, 1, 2)
    dates = tuple(start + timedelta(days=index) for index in range(4))
    calibration = OutcomeCalibration(
        key="PRE_BREAKOUT|ALLOW|1",
        setup_type=SetupType.PRE_BREAKOUT,
        market_status="ALLOW",
        sector_resonating=True,
        data_end=date(2025, 12, 31),
        total_plans=40,
        triggered_trades=40,
        untriggered_plans=0,
        target_2r_rate=Decimal("0.60"),
        target_2r_interval=(Decimal("0.44"), Decimal("0.74")),
        stop_first_rate=Decimal("0.25"),
        stop_first_interval=(Decimal("0.14"), Decimal("0.40")),
        net_expectancy=Decimal("0.01"),
        positive_rolling_window_ratio=Decimal("0.70"),
        frozen_test_expectancy=Decimal("0.01"),
        average_profit_loss_ratio=Decimal("2"),
        profit_factor=Decimal("1.5"),
        mfe_median=Decimal("0.05"),
        mfe_p25=Decimal("0.03"),
        mae_median=Decimal("0.02"),
        mae_p75=Decimal("0.04"),
        promoted=True,
        reasons=(),
    )
    observations = tuple(
        TradeObservation(
            exit_date=dates[-1],
            setup_type=SetupType.PRE_BREAKOUT,
            sector_code=f"S{index}",
            net_return=Decimal("0.02"),
            net_pnl=Decimal("80"),
            outcome=OutcomeLabel.TARGET_2R_FIRST,
            market_status="ALLOW",
            sector_resonating=True,
            mfe=Decimal("0.05"),
            mae=Decimal("0.01"),
            signal_date=day,
            entry_date=day,
            code=f"60000{index}",
            structure_id=f"structure-{index}",
            risk_fraction=Decimal("0.03"),
        )
        for index, day in enumerate(dates, start=1)
    )

    selected = module._frozen_test_observations(
        observations,
        test_dates=dates,
        calibrations={calibration.key: calibration},
    )

    assert [value.code for value in selected] == ["600001", "600002", "600003"]
