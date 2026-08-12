from __future__ import annotations

from datetime import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.limit_up_logic import (  # noqa: E402
    LimitUpPaths,
    LimitUpResult,
    LimitUpScoreBreakdown,
    format_limit_up_logic_card,
)


def test_card_contains_required_audit_fields_without_inevitable_language() -> None:
    result = LimitUpResult(
        code="603011",
        name="合锻智能",
        identity="SECOND_WAVE_CANDIDATE",
        gene="STRONG",
        score=LimitUpScoreBreakdown(30, 24, 18, 5),
        paths=LimitUpPaths(40, 40, 20),
        drivers=("近20日出现1次涨停", "首板后连续承接，未破首板低点"),
        prerequisites=("板块形成共振", "突破前高后回踩不破"),
        suppressors=("业绩预亏",),
        missing_fields=(
            "turnover_rate",
            "sector_change_pct",
            "sector_limit_up_count",
            "sector_leader_strength",
            "auction_strength",
            "seal_quality",
        ),
        data_cutoff=datetime(2026, 8, 6, 15, 0),
    )

    card = format_limit_up_logic_card(result)

    for text in (
        "【涨停逻辑】",
        "涨停基因",
        "封板驱动",
        "封板前提",
        "压制因素",
        "三路径",
        "数据缺口",
        "数据截止",
    ):
        assert text in card
    assert "涨停加速40% / 趋势延续40% / 接力失败20%" in card
    assert "竞价强度" in card
    assert "封单质量" in card
    assert "必然涨停" not in card
    assert "自动买入" not in card
