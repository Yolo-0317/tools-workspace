"""阅读量优化清单。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_seo import enrich_digest, market_digest_core, recommended_hashtags
from scripts.tools.wechat_mp_traffic_checklist import (
    format_traffic_report,
    run_traffic_checklist,
)
from scripts.tools.wechat_mp_workspace_article import generate_workspace_overview_body


def test_market_digest_core_by_edition() -> None:
    assert "盘前" in market_digest_core("pre")[1]
    assert "午间" in market_digest_core("midday")[1]
    assert "收盘" in market_digest_core("close")[1]


def test_enrich_digest_market_pre_edition() -> None:
    out = enrich_digest("【06-03 盘前】A50偏弱", "market", edition="pre")
    assert "A股" in out
    assert "盘前" in out


def test_traffic_checklist_workspace_passes_core_auto_items() -> None:
    body = generate_workspace_overview_body()
    rep = run_traffic_checklist(
        title="脚本越写越散？后来全收进了一个仓库",
        digest=enrich_digest("工具工作区全景与自动化复盘", "workspace"),
        body=body,
        kind="workspace",
        recommended_tags=recommended_hashtags("workspace"),
    )
    failed_auto = [i for i in rep.items if not i.manual and not i.passed]
    assert rep.auto_passed >= 8, failed_auto
    text = format_traffic_report(rep)
    assert "阅读量清单" in text
    assert "后台" in text


def test_traffic_checklist_flags_bad_title() -> None:
    rep = run_traffic_checklist(
        title="震惊！重磅内幕",
        digest="x" * 200,
        body="首先，在当今数字化时代。",
        kind="market",
    )
    assert not rep.items[0].passed  # title len or hook
    assert not rep.items[3].passed  # banned


def test_silver_natural_ending_question_counts_as_engagement() -> None:
    body = (
        "7月底，一名家属报警称亲人接到陌生电话后失联，这个场景值得先记住。\n\n"
        "> 先恢复联系\n\n"
        "陌生电话要求保密时，先挂断，再联系家人。\n\n"
        "如果今天约定一个防骗动作，你最想先写下哪一步？"
    )
    rep = run_traffic_checklist(
        title="陌生电话让你躲起来，先别照做",
        digest="退休生活防骗不靠背话术",
        body=body,
        kind="silver",
    )

    by_id = {item.id: item for item in rep.items}
    assert by_id["engagement_hook"].passed
