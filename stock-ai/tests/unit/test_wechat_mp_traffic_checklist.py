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


def test_traffic_checklist_marks_empathy_items_as_advisory() -> None:
    rep = run_traffic_checklist(
        title="银发栏目：高叶在职场里的坚持",
        digest="高叶新片反转与真实生活共振。",
        body=(
            "高叶的表演让观众第一次看见，工作家庭和自我之间并不对立。"
            "她在账本和理想间反复折中，为了孩子也不愿放弃这份体面的职业。"
            "同事推她加班，父母担心她放弃体面，三方都在施加压力。"
            "如果是你，你会让她先保住家庭？还是先保住自己的选择？"
        ),
        kind="silver",
    )
    empathy = [i for i in rep.items if i.id in {"empathy_subject_early", "concrete_cost_before_third", "balanced_tension_before_third", "reader_choice_connected"}]
    assert empathy
    assert all(i.advisory for i in empathy)
