"""交易型选股门控单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.advisor_selection import (
    PRINCIPAL_CNY,
    advisor_cap_action,
    ai_selection_review_enabled,
    execution_card_probe_enabled,
    parse_advisor_phase,
    reapply_advisor_to_rows,
    selection_watch_sync_enabled,
    sop_review_enabled,
    top5_eligible_actions,
)


def test_phase0_turns_buy_signal_into_observation():
    assert advisor_cap_action("观察买入", "000001", phase=0) == "交易观察"


def test_phase1_turns_eod_signal_into_next_day_confirmation():
    assert advisor_cap_action("小仓埋伏", "600995", phase=1) == "次日确认"


def test_phase0_top5_is_observation_only():
    assert top5_eligible_actions(phase=0) == frozenset({"交易观察", "次日确认", "持有", "—", ""})


def test_phase_gates_enable_review_after_building_stage(monkeypatch):
    monkeypatch.delenv("DISABLE_SOP_TOP5", raising=False)
    assert selection_watch_sync_enabled(phase=0) is False
    assert sop_review_enabled(phase=0) is True
    assert ai_selection_review_enabled(phase=0) is False
    assert execution_card_probe_enabled(phase=0) is False
    assert selection_watch_sync_enabled(phase=1) is True
    assert ai_selection_review_enabled(phase=1) is True


def test_disable_sop_top5_env(monkeypatch):
    monkeypatch.setenv("DISABLE_SOP_TOP5", "1")
    assert sop_review_enabled(phase=0) is False
    assert sop_review_enabled(phase=1) is False


def test_reapply_marks_eod_signal_for_confirmation():
    rows = [{"代码": "000001", "建议动作": "小仓埋伏"}]
    reapply_advisor_to_rows(rows, phase=1)
    assert rows[0]["建议动作"] == "次日确认"
    assert "收盘候选" in rows[0].get("投顾备注", "")


def test_parse_explicit_current_trade_phase():
    text = "## 二、交易定位\n**当前交易阶段：阶段 1 · 小仓验证与规则建档。**"
    assert parse_advisor_phase(text) == 1


def test_execution_card_requires_intraday_confirmation():
    from scripts.tools.execution_card_buys import execution_card_buys_from_selection

    rows = [{"代码": "603697", "建议动作": "小仓埋伏", "总分": 80}]
    out = execution_card_buys_from_selection(rows, holding_codes=set(), top_n=5)
    assert not any(item["kind"] == "probe_buy" for item in out)


def test_build_advisor_dashboard_payload():
    from stock_ai.advisor_selection import build_advisor_dashboard_payload

    payload = build_advisor_dashboard_payload(total_assets=118078.0, position_ratio_pct=40.4, holding_pnl=-3617.0)
    assert payload["principal_cny"] == PRINCIPAL_CNY == 100000
    assert payload["phase"] == 1
    assert payload["selection"]["mode"] == "next_day_confirmation"
    assert len(payload["weekly_must_do"]) >= 1
