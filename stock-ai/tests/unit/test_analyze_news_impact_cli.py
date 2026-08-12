import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.analysis.analyze_news_impact import parse_probabilities


def test_parse_probabilities_requires_three_values_totaling_100():
    assert parse_probabilities("35,45,20").as_tuple() == (35, 45, 20)
    for invalid in ("35,65", "40,40,30"):
        try:
            parse_probabilities(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"应拒绝非法概率: {invalid}")


def test_cli_runs_directly_from_project_root():
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/analysis/analyze_news_impact.py",
            "--code", "600186",
            "--name", "莲花控股",
            "--concept", "算力租赁",
            "--base", "35,45,20",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert proc.returncode == 0, proc.stderr
    assert "【消息面影响】" in proc.stdout
