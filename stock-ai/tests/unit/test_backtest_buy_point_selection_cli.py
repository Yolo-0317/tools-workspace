from __future__ import annotations

import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path


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
    assert payload["schema"] == "buy-point-selection-validation-v1"
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
