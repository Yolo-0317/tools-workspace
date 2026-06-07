"""投顾选股过滤单元测试."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.advisor_selection import (
    EXCLUDE_CODES,
    advisor_cap_action,
    ai_selection_review_enabled,
    execution_card_probe_enabled,
    parse_advisor_phase,
    reapply_advisor_to_rows,
    selection_watch_sync_enabled,
    sop_review_enabled,
    top5_eligible_actions,
)


def test_phase0_caps_buy_actions():
    assert advisor_cap_action("观察买入", "000001", phase=0) == "继续观察"
    assert advisor_cap_action("小仓埋伏", "600995", phase=0) == "继续观察"


def test_meihua_always_forbidden():
    code = "600873"
    assert code in EXCLUDE_CODES
    assert advisor_cap_action("持有", code, phase=2) == "禁止"


def test_phase0_top5_intel_only():
    assert top5_eligible_actions(phase=0) == frozenset({"继续观察", "持有", "—", ""})


def test_phase0_no_watch_sop_on_ai_off():
    assert selection_watch_sync_enabled(phase=0) is False
    assert sop_review_enabled(phase=0) is True
    assert ai_selection_review_enabled(phase=0) is False
    assert execution_card_probe_enabled(phase=0) is False
    assert selection_watch_sync_enabled(phase=1) is True
    assert execution_card_probe_enabled(phase=1) is True


def test_reapply_advisor_after_b_tier():
    rows = [{"代码": "000001", "建议动作": "小仓埋伏"}]
    reapply_advisor_to_rows(rows, phase=0)
    assert rows[0]["建议动作"] == "继续观察"
    assert "阶段0禁买" in rows[0].get("投顾备注", "")


def test_parse_phase_from_strategy_file():
    text = "## 三、阶段战略\n### 阶段 0（当前～4 周）"
    assert parse_advisor_phase(text) == 0


def test_execution_card_buys_phase0_trims_only():
    from scripts.tools.execution_card_buys import execution_card_buys_from_selection

    rows = [{"代码": "603697", "建议动作": "小仓埋伏", "总分": 80}]
    out = execution_card_buys_from_selection(rows, holding_codes=set(), top_n=5)
    assert all(item["kind"] == "trim" for item in out)
    assert not any(item["kind"] == "probe_buy" for item in out)


def test_build_advisor_dashboard_payload():
    from stock_ai.advisor_selection import build_advisor_dashboard_payload

    p = build_advisor_dashboard_payload(
        total_assets=52962.0,
        position_ratio_pct=84.4,
        holding_pnl=-2711.0,
    )
    assert p["principal_cny"] == 60000
    assert p["phase"] == 0
    assert p["selection"]["mode"] == "intel_only"
    assert len(p["weekly_must_do"]) >= 1
