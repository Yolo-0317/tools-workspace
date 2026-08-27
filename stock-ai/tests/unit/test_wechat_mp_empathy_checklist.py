"""情绪共鸣与讨论点检查器单测。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_empathy_checklist import (
    SUPPORTED_KINDS,
    run_empathy_discussion_checks,
)


def _as_map(items):
    return {item.id: item.passed for item in items}


def test_empathy_checks_pass_for_hotspot_persona() -> None:
    rep = run_empathy_discussion_checks(
        title="《年会不能停2》里那个“要不要加薪”",
        kind="hotspot",
        body=(
            "高叶的角色连着三年没加薪，还要照顾年迈父母和刚上大学的妹妹。"
            "同事催着她冲锋，但老客户也在等她把账单讲清。"
            "她一边守住团队士气，一边担心下一次排班换掉她的岗位。"
            "如果是你，选择保住这份工作还是先离开？你会先保护哪一方？"
        ),
    )
    m = _as_map(rep)
    assert m["empathy_subject_early"]
    assert m["concrete_cost_before_third"]
    assert m["balanced_tension_before_third"]
    assert m["reader_choice_connected"]


def test_macro_theme_fails_all_empathy_items() -> None:
    rep = run_empathy_discussion_checks(
        title="政策一线新变量",
        kind="hotspot",
        body="大家都知道，社会变化很快，大家都在担忧。行业和市场都在讨论同一件事，大家怎么看？",
    )
    m = _as_map(rep)
    assert not m["empathy_subject_early"]
    assert not m["concrete_cost_before_third"]
    assert not m["balanced_tension_before_third"]
    assert not m["reader_choice_connected"]


def test_hot_business_product_preference_fails_reader_choice() -> None:
    rep = run_empathy_discussion_checks(
        title="《胖东来》爆火后，IP 周边热了吗？",
        kind="hot_business",
        body=(
            "胖东来店长为了守住现金流，连续三个月压缩库存预算，和家里人的生活也更紧。"
            "团队说要清库，供应商说等不到回款，店铺也担心会员流失，三方都在施压。"
            "如果是你，会先补货还是先保工资？你更想买哪个毛绒徽章？你会买吗？"
        ),
    )
    m = _as_map(rep)
    assert m["empathy_subject_early"]
    assert m["concrete_cost_before_third"]
    assert m["balanced_tension_before_third"]
    assert not m["reader_choice_connected"]


def test_silver_autonomy_vs_family_supports_choice() -> None:
    rep = run_empathy_discussion_checks(
        title="银发专栏：晚年独立与家庭边界",
        kind="silver",
        body=(
            "张阿姨想学习智能支付，怕被儿女笑话。"
            "她一边想省出看病时间，一边又不想让孩子担心，她爸又担心她摔倒。"
            "家里人希望她保守，银行又要她尽快办完续约。"
            "如果是你，你支持张阿姨先坚持独立，还是先听从家人的安排？"
        ),
    )
    m = _as_map(rep)
    assert m["empathy_subject_early"]
    assert m["concrete_cost_before_third"]
    assert m["balanced_tension_before_third"]
    assert m["reader_choice_connected"]


def test_film_generic_theme_fails_subject_and_cost() -> None:
    rep = run_empathy_discussion_checks(
        title="今年最热电影讨论：它为什么能拿奖",
        kind="tv_review",
        body="这部电影节奏紧凑，主题也很明确，观众口碑很好。每个人都会有自己的理解。你怎么看？",
    )
    m = _as_map(rep)
    assert not m["empathy_subject_early"]
    assert not m["concrete_cost_before_third"]
    assert not m["reader_choice_connected"]


def test_abusive_scenario_is_discussable_without_defending_offender() -> None:
    rep = run_empathy_discussion_checks(
        title="《杀死比尔：血色全传》最痛的不是对错",
        kind="tv_review",
        body=(
            "她被胁迫签下不利条款，明知有风险却仍先保命。"
            "律师说这是生存策略，不是认罪；但她的选择也会伤到同伴。"
            "她在守护自己和同伴之间反复拉扯，而不是替她的人去“替罪”。"
            "如果是你，在她面前，你更看重安全还是忠诚？"
        ),
    )
    m = _as_map(rep)
    assert m["balanced_tension_before_third"]


def test_unsupported_kind_returns_empty() -> None:
    assert run_empathy_discussion_checks(kind="market", title="市场快讯", body="正文") == []
    assert SUPPORTED_KINDS == {"hotspot", "hot_business", "tv_review", "silver"}
