#!/usr/bin/env python3
"""公众号情绪共鸣与讨论点检查器（非阻断增强项）。"""

from __future__ import annotations

import re
from dataclasses import dataclass


SUPPORTED_KINDS = {"hotspot", "hot_business", "tv_review", "silver"}
# 历史兼容：上游清单/调用方使用 EMPATHY... 变量名
EMPATHY_SUPPORTED_KINDS = SUPPORTED_KINDS


def _normalize_body(body: str) -> str:
    text = re.sub(r"\[\[(?:fig|hl):[^]]*\]\]", "", body or "")
    text = re.sub(r"(?m)^资料说明[:：].*$", "", text)
    text = re.sub(r"\n{3,}", "\n", text).strip()
    return text


def _compact(body: str) -> str:
    return re.sub(r"\s+", "", _normalize_body(body))


def _extract_early(body: str) -> str:
    return _compact(body)[:150]


def _extract_first_third(body: str) -> str:
    body = _compact(body)
    if not body:
        return ""
    target = max(220, len(body) // 3)
    target = min(target, 420)
    return body[:target]


def _extract_tail(body: str) -> str:
    body = _compact(body)
    if not body:
        return ""
    return body[-320:]


def _contains_cost_word(text: str, cost_terms: tuple[str, ...]) -> bool:
    return any(term in text for term in cost_terms)


def _contains_numbers(text: str) -> bool:
    return bool(re.search(r"\d", text))


def _contains_cn_numbers(text: str) -> bool:
    return bool(re.search(r"[一二三四五六七八九十百千万两点零]+", text))


def _contains_number_money_term(text: str) -> bool:
    return bool(re.search(r"\d+万|十万|百万|亿元|元|点位|小时|天数|周|个月", text))


def _common_tokens(texts: list[str]) -> set[str]:
    tokens = set()
    for text in texts:
        for i in range(len(text) - 1):
            tokens.add(text[i : i + 2])
    return tokens


def _has_subject_reference(early: str) -> bool:
    subject_markers = (
        "爸",
        "妈",
        "母",
        "父",
        "女儿",
        "儿子",
        "妻",
        "夫",
        "同事",
        "员工",
        "员工",
        "同学",
        "家长",
        "学生",
        "观众",
        "消费者",
        "商户",
        "角色",
        "高叶",
        "胖东来",
        "沈腾",
        "牛来",
        "小区",
        "孩子",
        "老人",
        "家人",
        "你",
        "我",
    )
    action_words = ("决定", "选", "面对", "陷入", "要", "开始", "却", "撑", "守", "承担", "放弃", "守护", "撑起", "离开", "回到")
    return any(m in early for m in subject_markers) and any(a in early for a in action_words)


def _has_generic_subject(early: str) -> bool:
    generic_markers = ("大家", "社会", "行业", "市场", "全民", "群体", "大众", "企业界", "网友", "年轻人")
    return any(m in early for m in generic_markers)


def _concrete_cost_before_third(first_third: str) -> bool:
    cost_terms = (
        "学费",
        "工资",
        "收入",
        "养老",
        "家底",
        "存款",
        "关系",
        "尊严",
        "岗位",
        "加薪",
        "失去",
        "被骗",
        "欠薪",
        "风险",
        "错过",
        "就业",
        "转岗",
        "库存",
        "租",
        "孩子",
        "时间",
        "夜班",
        "加重",
        "代价",
        "代办",
    )
    return (
        _contains_cost_word(first_third, cost_terms)
        and (_contains_numbers(first_third) or _contains_cn_numbers(first_third))
    ) or _contains_number_money_term(first_third)


def _tension_ok(body: str, first_third: str) -> bool:
    tension_markers = ("但", "却", "既", "又", "与此同时", "一边", "另一方面", "还是", "如果", "却又", "要么")
    if not any(m in first_third for m in tension_markers):
        return False
    roles_or_goals = (
        "家人",
        "公司",
        "平台",
        "团队",
        "父母",
        "孩子",
        "同事",
        "上级",
        "同学",
        "医院",
        "商家",
        "顾客",
        "店长",
        "店铺",
        "供应商",
        "客户",
        "律师",
        "同伴",
        "银行",
        "家里人",
        "会员",
    )
    if _contains_cost_word(first_third, ("违法", "诈骗", "侵权", "隐瞒", "失联", "欠债", "调休", "压力", "替代")):
        if any(g in body for g in ("怎么办", "要不要", "是否", "怎么办")):
            return True
    if any(m in first_third for m in tension_markers) and any(
        c in first_third for c in ("压力", "对立", "矛盾", "博弈", "冲突", "争")
    ):
        return True
    return sum(1 for r in roles_or_goals if r in first_third) >= 2


def _choice_signal(text: str) -> bool:
    choices = (
        "如果是你",
        "你会",
        "你会不会",
        "你会更",
        "你更",
        "要不要",
        "该不该",
        "愿不愿意",
        "更希望",
        "还是",
        "该选",
    )
    return any(c in text for c in choices)


def _choice_connected(first_third: str, title: str, tail: str) -> bool:
    if not _choice_signal(tail):
        return False
    generic = ("你怎么看", "大家怎么看", "欢迎评论", "留言")
    if any(g in tail for g in generic):
        return False
    if re.search(r"买哪个|想买|毛绒|徽章|设定集|海报", tail) and "决策" not in tail and "代价" not in tail:
        return False
    t = _common_tokens([title, first_third, tail])
    if len(t) >= 1:
        return _common_tokens([tail]).intersection(_common_tokens([title, first_third]))

    return False


def _choice_connected_any(first_third: str, title: str, tail: str) -> bool:
    return bool(_choice_connected(first_third, title, tail))


def _reader_choice_ok(first_third: str, title: str, tail: str) -> bool:
    if not tail:
        return False
    if _has_generic_subject(first_third):
        return False
    return bool(_choice_connected_any(first_third, title, tail))


@dataclass(frozen=True)
class EmpathyDiscussionCheck:
    id: str
    label: str
    passed: bool
    hint: str = ""


def run_empathy_discussion_checks(
    *, title: str, body: str, kind: str
) -> list[EmpathyDiscussionCheck]:
    if kind not in SUPPORTED_KINDS:
        return []

    normalized = _compact(_normalize_body(body))
    early = _extract_early(normalized)
    first_third = _extract_first_third(normalized)
    tail = _extract_tail(normalized)

    subject_ok = _has_subject_reference(early) and not _has_generic_subject(early)
    cost_ok = _concrete_cost_before_third(first_third)
    tension_ok = _tension_ok(normalized, first_third)
    choice_ok = _reader_choice_ok(first_third, title, tail)

    return [
        EmpathyDiscussionCheck(
            id="empathy_subject_early",
            label="具象人物先行",
            passed=subject_ok,
            hint="前 150 字先给出具体人物/角色与处境动作",
        ),
        EmpathyDiscussionCheck(
            id="concrete_cost_before_third",
            label="正文 1/3 内有具体代价",
            passed=cost_ok,
            hint="第一段写明谁要付出什么（时间、名誉、收入、关系）",
        ),
        EmpathyDiscussionCheck(
            id="balanced_tension_before_third",
            label="前三段先给出两侧张力",
            passed=tension_ok,
            hint="尽量在正文 1/3 讲清“谁想要什么/谁受阻碍”",
        ),
        EmpathyDiscussionCheck(
            id="reader_choice_connected",
            label="正文末尾接读者选择",
            passed=choice_ok,
            hint="用“如果是你/你会如何”等与文章情境相关的选择题收束",
        ),
    ]
