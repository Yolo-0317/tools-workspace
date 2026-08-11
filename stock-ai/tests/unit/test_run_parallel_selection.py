"""run_parallel_selection 调度逻辑。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.selection import run_parallel_selection as rps


def test_lane_order_has_four_entries():
    assert rps.LANE_ORDER == (
        "combined",
        "ma5",
        "five_factor",
        "bottom_breakout",
    )


def test_execute_lane_unknown():
    lane, code, err, _ = rps._execute_lane("nope")
    assert lane == "nope"
    assert code == 1
    assert "unknown" in (err or "")


def test_main_uses_parallel_by_default():
    with patch("scripts.tools.ensure_daily_bars.ensure_daily_bars_at_selection_start") as ensure:
        with patch.object(rps, "_run_lanes_parallel", return_value=0) as parallel:
            with patch.object(rps, "_run_lanes_sequential") as sequential:
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("SELECTION_LANES_SEQUENTIAL", None)
                    assert rps.main() == 0
                    ensure.assert_called_once_with()
                    parallel.assert_called_once()
                    sequential.assert_not_called()


def test_main_sequential_when_env_set():
    with patch("scripts.tools.ensure_daily_bars.ensure_daily_bars_at_selection_start") as ensure:
        with patch.object(rps, "_run_lanes_sequential", return_value=0) as sequential:
            with patch.object(rps, "_run_lanes_parallel") as parallel:
                with patch.dict(os.environ, {"SELECTION_LANES_SEQUENTIAL": "1"}):
                    assert rps.main() == 0
                    ensure.assert_called_once_with()
                    sequential.assert_called_once()
                    parallel.assert_not_called()
