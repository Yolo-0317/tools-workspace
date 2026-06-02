#!/usr/bin/env python3
"""dragon_head_gm v2 纯函数测试（无需掘金 SDK）。"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts" / "win" / "stock_ai_sim_bridge"
sys.path.insert(0, str(BRIDGE))

import dragon_head_gm as dhg  # noqa: E402


class DragonHeadGmV2Tests(unittest.TestCase):
    def _header(self, phase="启动"):
        return {
            "phase": phase,
            "allow_new_open": 1,
            "limit_up_premium_pct": 2.0,
            "explode_rate_pct": 20.0,
            "position_cap_pct": 40.0,
        }

    def _dragon(self, rank=1, board=3):
        return {
            "rank_no": rank,
            "ts_code": "600280",
            "name": "中央商场",
            "board_height": board,
            "checklist_pass": 6,
        }

    def test_rank_allowed_by_phase(self):
        ok, _ = dhg.rank_allowed(self._dragon(rank=1), self._header("启动"))
        self.assertTrue(ok)
        ok, reason = dhg.rank_allowed(self._dragon(rank=2), self._header("启动"))
        self.assertFalse(ok)
        self.assertIn("rank", reason)

    def test_ban_high_acceleration(self):
        banned, _ = dhg.ban_high_acceleration(self._dragon(board=3), 7.5)
        self.assertTrue(banned)
        banned, _ = dhg.ban_high_acceleration(self._dragon(board=2), 7.5)
        self.assertFalse(banned)

    def test_reseal_entry(self):
        dt = datetime(2026, 6, 2, 10, 30)
        state = dhg.new_intraday_state("2026-06-02")
        dhg.update_intraday_state(state, 9.2, dt)
        dhg.update_intraday_state(state, 6.5, dt)
        ok, tag = dhg.entry_signal(
            self._dragon(),
            10.0,
            8.8,
            self._header(),
            dt=dt,
            intraday_state=state,
        )
        self.assertTrue(ok)
        self.assertEqual(tag, "re-seal")

    def test_open_chaos_blocked(self):
        dt = datetime(2026, 6, 2, 9, 35)
        state = dhg.new_intraday_state("2026-06-02")
        ok, reason = dhg.entry_signal(
            self._dragon(),
            10.0,
            3.0,
            self._header(),
            dt=dt,
            intraday_state=state,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "open_chaos")

    def test_exit_broken_board(self):
        state = {"touched_limit": True, "high_pct": 9.5, "pullback_seen": True}
        action, reason = dhg.exit_signal(self._header(), 4.0, intraday_state=state)
        self.assertEqual(action, "sell_all")
        self.assertEqual(reason, "broken_board")

    def test_exit_take_profit_half(self):
        action, reason = dhg.exit_signal(self._header(), 7.5, half_taken=False)
        self.assertEqual(action, "sell_half")
        self.assertEqual(reason, "take_profit_half")

    def test_max_shares_by_rank(self):
        cash = {"nav": 1_000_000.0}
        shares = dhg.max_shares_for_dragon(
            self._header(),
            cash,
            lambda c: c["nav"],
            self._dragon(rank=1),
            10.0,
        )
        # 1M * 40% * 40% / 10 = 16000 -> 16000 shares
        self.assertEqual(shares, 16000)
        shares_r3 = dhg.max_shares_for_dragon(
            self._header(),
            cash,
            lambda c: c["nav"],
            self._dragon(rank=3),
            10.0,
        )
        self.assertLess(shares_r3, shares)


if __name__ == "__main__":
    unittest.main()
