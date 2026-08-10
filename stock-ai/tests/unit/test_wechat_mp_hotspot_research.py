"""热点深评联网取材与标题路牌。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_hotspot_research import (
    ResearchHit,
    build_hotspot_title_from_facts,
    format_hotspot_reference_imitation_block,
    title_is_acceptable,
)


def test_build_hotspot_title_from_facts_market_cap():
    hits = [
        ResearchHit(
            title="A股市值前十，红了9个",
            snippet=(
                "同花顺数据显示，A股市值前十的个股中，长鑫科技下跌5.19%，"
                "其余工商银行、建设银行、农业银行等上涨，建行、工行盘中创历史新高。"
            ),
            source="中国证券报",
            url="http://example.com",
            published="2026-07-30",
        )
    ]
    title = build_hotspot_title_from_facts(hits, trend="A股市值前10红了9个")
    assert "市值前十" in title
    assert "和A股啥关系" not in title
    assert title_is_acceptable(title)


def test_reference_imitation_block_has_samples():
    hits = [
        ResearchHit(
            title="测试标题",
            snippet="工商银行涨2%，建设银行创历史新高，九只个股收涨。",
            source="证券时报",
            url="",
        )
    ]
    block = format_hotspot_reference_imitation_block(hits)
    assert "参考文章·仿写" in block
    assert "工商银行" in block
