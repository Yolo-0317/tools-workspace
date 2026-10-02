"""热点深评面向读者的公开文案门禁。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence
from urllib.parse import urlparse


@dataclass(frozen=True)
class HotspotGateFinding:
    code: str
    field: str
    excerpt: str
    message: str


@dataclass(frozen=True)
class HotspotEditorialCheck:
    name: str
    passed: bool
    message: str


@dataclass(frozen=True)
class HotspotEditorialScore:
    score: int
    total: int
    passed: bool
    checks: tuple[HotspotEditorialCheck, ...]


_EDITORIAL_PATTERNS = (
    re.compile(r"(?:不能|不要|不应|避免|切勿)(?:再|直接|这样|如此|把|将)?写成"),
    re.compile(r"(?:应|应该|需要|建议)(?:改写|改成|表述为|写成)"),
    re.compile(
        r"(?:正文|标题|摘要|稿件|文章)(?:中|里|内)?"
        r"(?:应当|应该|需要|不要|不能|不得|建议)(?:写|改|补|删|标|使用|出现)"
    ),
    re.compile(r"(?:提示词|审稿|编辑说明|配图建议|来源列表)(?:要求|需要|如下|中|里|为)"),
)
_TITLE_HYPE_WORDS = ("震惊", "重磅", "炸裂", "看完即删")
_SCOPE_WORDS = ("全国统一", "全面取消", "所有学生", "全部学生", "一律")
_SCOPE_NEGATIONS = (
    "不代表全国统一",
    "并非全国统一",
    "不是全国统一",
    "没有全面取消",
    "并未全面取消",
    "并非所有学生",
    "不是所有学生",
)
_SCHOOL_CHOICE_CONTEXT_MARKERS = (
    "择校",
    "学区",
    "学位",
    "幼升小",
    "小升初",
    "小学",
    "初中",
    "高中",
    "学校入学",
    "积分入学",
    "电脑派位",
    "公民同招",
)
_SCHOOL_CHOICE_PROMISE_PATTERNS = (
    re.compile(
        r"(?:买|购买).{0,4}(?:学区房|房产).{0,10}"
        r"(?:必上|稳上|包上|保证(?:入学|学位|录取))"
    ),
    re.compile(
        r"(?:落户|租房|缴纳?社保|报名(?:课程|培训)).{0,10}"
        r"(?:必上|稳上|包上|保证(?:入学|学位|录取)|百分百录取)"
    ),
    re.compile(
        r"(?:内部名额|关系入学|花钱保录取|包录取|保录取|保证进名校|百分百录取)"
    ),
)
_SELF_REVIEW_VOICE_PATTERNS = (
    re.compile(
        r"(?:不能|不应|不要)把[^。！？\n]{0,60}"
        r"(?:理解成|解读为|视为|当成)[^。！？\n]{0,90}[，；]"
        r"(?:更|也)?(?:不能|不应|不要)把[^。！？\n]{0,90}"
        r"(?:理解成|解读为|视为|当成)"
    ),
    re.compile(r"(?:为了避免|以免)(?:读者)?误解[^。！？\n]{0,100}"),
    re.compile(
        r"(?:本文|本篇|这篇文章|这篇稿子|本稿)[^。！？\n]{0,20}"
        r"(?:不是要|并不是要|不能被理解为|不应被理解为|想讨论的不是)"
    ),
)
_DATA_USAGE_DISCLAIMER_PATTERNS = (
    re.compile(
        r"(?:数据|数字|平均数|均值|调查(?:结果)?|\d+(?:\.\d+)?元)"
        r"[^。！？\n]{0,40}(?:可以|能)(?:用来|拿来|作为)"
        r"[^。！？\n]{0,50}[，；][^。！？\n]{0,12}"
        r"(?:不能|不该)(?:拿来|用来|作为)"
        r"[^。！？\n]{0,50}(?:标准|结论|依据)"
    ),
)
_SCHOOL_CHOICE_WARNING_MARKERS = (
    "不能",
    "无法",
    "并非",
    "不是",
    "没有",
    "不存在",
    "严禁",
    "禁止",
    "不要相信",
    "警惕",
    "骗局",
    "诈骗",
    "查处",
)
_SCHOOL_CHOICE_CLAUSE_BOUNDARIES = (
    "。",
    "！",
    "？",
    "；",
    "\n",
    "，但",
    "，不过",
    "，然而",
)
_TITLE_NUMBER_RE = re.compile(
    r"\d+(?:\.\d+)?(?:%|万|亿|元|岁|年|月|天|科|项|人|次|家|所|页|个)?"
)
_ARABIC_TO_CHINESE = {
    "0": "零",
    "1": "一",
    "2": "二",
    "3": "三",
    "4": "四",
    "5": "五",
    "6": "六",
    "7": "七",
    "8": "八",
    "9": "九",
    "10": "十",
}
_PUBLIC_IMPACT_MARKERS = (
    "普通人",
    "群众",
    "家长",
    "学生",
    "孩子",
    "家庭",
    "消费者",
    "劳动者",
    "上班族",
    "老人",
    "车主",
    "乘客",
    "费用",
    "工资",
    "月供",
    "时间成本",
    "选择",
)
_COUNTERPOINT_MARKERS = (
    "但是",
    "但",
    "不过",
    "同时",
    "另一方面",
    "也要看到",
    "可以理解",
    "不等于",
    "并不意味着",
    "不是",
)


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _excerpt(text: str, match: re.Match[str] | None = None) -> str:
    compact = _compact(text)
    if not compact:
        return ""
    if match is None:
        return compact[:80]
    start = max(0, match.start() - 20)
    end = min(len(text), match.end() + 40)
    return _compact(text[start:end])[:80]


def _finding(code: str, field: str, text: str, message: str, match=None) -> HotspotGateFinding:
    return HotspotGateFinding(
        code=code,
        field=field,
        excerpt=_excerpt(text, match),
        message=message,
    )


def _is_authoritative_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return host == "gov.cn" or host.endswith(".gov.cn") or host.endswith(".edu.cn")


def _number_variants(token: str) -> tuple[str, ...]:
    match = re.fullmatch(r"(\d+)(.*)", token)
    if not match:
        return (token,)
    digits, suffix = match.groups()
    chinese = _ARABIC_TO_CHINESE.get(digits)
    return (token, f"{chinese}{suffix}") if chinese else (token,)


def _normalized_paragraphs(body: str) -> list[str]:
    return [
        _compact(paragraph)
        for paragraph in re.split(r"\n\s*\n+", (body or "").strip())
        if _compact(paragraph)
    ]


def _has_school_choice_context(text: str) -> bool:
    compact = _compact(text)
    return any(marker in compact for marker in _SCHOOL_CHOICE_CONTEXT_MARKERS)


def _matching_clause(text: str, match: re.Match[str]) -> str:
    starts = [
        index + len(mark)
        for mark in _SCHOOL_CHOICE_CLAUSE_BOUNDARIES
        if (index := text.rfind(mark, 0, match.start())) >= 0
    ]
    start = max(starts, default=0)
    ends = [text.find(mark, match.end()) for mark in _SCHOOL_CHOICE_CLAUSE_BOUNDARIES]
    valid_ends = [index for index in ends if index >= 0]
    end = min(valid_ends) if valid_ends else len(text)
    return text[start:end]


def _is_school_choice_warning(clause: str) -> bool:
    compact = _compact(clause)
    return any(marker in compact for marker in _SCHOOL_CHOICE_WARNING_MARKERS)


def scan_hotspot_public_copy(
    *,
    title: str,
    digest: str,
    body: str,
    research_urls: Sequence[str],
) -> tuple[HotspotGateFinding, ...]:
    """返回能稳定自动判断的公开文案问题。"""

    findings: list[HotspotGateFinding] = []
    for field, text in (("title", title), ("digest", digest), ("body", body)):
        for pattern in _EDITORIAL_PATTERNS:
            match = pattern.search(text or "")
            if match:
                findings.append(
                    _finding(
                        "editorial_instruction_leak",
                        field,
                        text,
                        "出现面向写作者或编辑者的过程性指令",
                        match,
                    )
                )
                break
        for pattern in _SELF_REVIEW_VOICE_PATTERNS:
            match = pattern.search(text or "")
            if match:
                findings.append(
                    _finding(
                        "self_review_voice",
                        field,
                        text,
                        "出现向读者解释文章应如何理解的连续自我辩护句",
                        match,
                    )
                )
                break
        for pattern in _DATA_USAGE_DISCLAIMER_PATTERNS:
            match = pattern.search(text or "")
            if match:
                findings.append(
                    _finding(
                        "data_usage_disclaimer_voice",
                        field,
                        text,
                        "出现规定数据该如何使用的审稿式免责声明",
                        match,
                    )
                )
                break

    hype = next((word for word in _TITLE_HYPE_WORDS if word in (title or "")), "")
    if hype:
        findings.append(
            _finding("title_hype", "title", title, f"标题含夸大营销词：{hype}")
        )

    school_choice_text = "\n".join((title or "", digest or "", body or ""))
    if _has_school_choice_context(school_choice_text):
        for field, text in (("title", title), ("digest", digest), ("body", body)):
            for pattern in _SCHOOL_CHOICE_PROMISE_PATTERNS:
                for match in pattern.finditer(text or ""):
                    clause = _matching_clause(text or "", match)
                    if _is_school_choice_warning(clause):
                        continue
                    findings.append(
                        _finding(
                            "school_choice_admission_promise",
                            field,
                            text,
                            "出现学位或录取的确定性承诺，请改为当年主管部门审核边界",
                            match,
                        )
                    )
                    break
                else:
                    continue
                break

    has_scope_claim = any(word in (title or "") for word in _SCOPE_WORDS)
    scope_is_negated = any(phrase in (title or "") for phrase in _SCOPE_NEGATIONS)
    has_authority = any(_is_authoritative_url(url) for url in research_urls)
    if has_scope_claim and not scope_is_negated and not has_authority:
        findings.append(
            _finding(
                "unsupported_scope",
                "title",
                title,
                "标题扩大政策适用范围，但来源中没有权威政策页面",
            )
        )

    fulfillment_text = _compact(f"{digest}{body}")
    for token in _TITLE_NUMBER_RE.findall(title or ""):
        if not any(variant in fulfillment_text for variant in _number_variants(token)):
            findings.append(
                _finding(
                    "title_number_unfulfilled",
                    "title",
                    title,
                    f"标题数字未在摘要或正文兑现：{token}",
                )
            )

    paragraphs = _normalized_paragraphs(body)
    seen: set[str] = set()
    duplicate = ""
    for paragraph in paragraphs:
        if len(paragraph) >= 8 and paragraph in seen:
            duplicate = paragraph
            break
        seen.add(paragraph)
    if duplicate:
        findings.append(
            _finding(
                "duplicate_paragraph",
                "body",
                duplicate,
                "正文含完全重复段落",
            )
        )

    if re.search(r"^\s*#{1,6}\s+", body or "", flags=re.MULTILINE):
        findings.append(_finding("markdown_heading", "body", body, "正文仍含 Markdown 标题"))
    if re.search(r"^\s*(?:[-*+]\s+|\d+[.、]\s*)", body or "", flags=re.MULTILINE):
        findings.append(_finding("list_format", "body", body, "热点深评正文仍含清单格式"))
    return tuple(findings)


def require_hotspot_public_copy(**kwargs) -> None:
    findings = scan_hotspot_public_copy(**kwargs)
    if findings:
        details = "；".join(f"{item.code}[{item.field}]:{item.excerpt}" for item in findings)
        raise ValueError(f"热点公开文案未通过门禁：{details}")


def _topic_overlap(opening: str, title: str, topic: str) -> bool:
    opening_compact = _compact(opening)
    source = _compact(f"{topic}{title}")
    chunks = re.findall(r"[\u4e00-\u9fff]{2,}", source)
    bigrams = {chunk[index : index + 2] for chunk in chunks for index in range(len(chunk) - 1)}
    return any(token in opening_compact for token in bigrams)


def _distinct_source_domains(research_urls: Sequence[str]) -> int:
    return len(
        {
            (urlparse(url).hostname or "").lower().removeprefix("www.")
            for url in research_urls
            if (urlparse(url).hostname or "")
        }
    )


def evaluate_hotspot_editorial_quality(
    *,
    title: str,
    body: str,
    topic: str,
    original_thesis: str,
    research_urls: Sequence[str],
) -> HotspotEditorialScore:
    """用多项弱信号评估完整度；任何单项都不会独立否决稿件。"""

    paragraphs = _normalized_paragraphs(body)
    compact_body = _compact(body)
    first_third = compact_body[: max(1, len(compact_body) // 3)]
    ending = "".join(paragraphs[-2:]) if paragraphs else ""
    checks = (
        HotspotEditorialCheck(
            "focused_thesis",
            len(_compact(original_thesis)) >= 20,
            "原创核心判断不少于20字",
        ),
        HotspotEditorialCheck(
            "source_diversity",
            _distinct_source_domains(research_urls) >= 3,
            "至少三个不同来源域",
        ),
        HotspotEditorialCheck(
            "event_opening",
            bool(paragraphs and _topic_overlap(paragraphs[0], title, topic)),
            "首段出现题目或事件实体",
        ),
        HotspotEditorialCheck(
            "public_impact",
            any(marker in first_third for marker in _PUBLIC_IMPACT_MARKERS),
            "正文前段落到具体人群或现实成本",
        ),
        HotspotEditorialCheck(
            "counterpoint_boundary",
            any(marker in compact_body for marker in _COUNTERPOINT_MARKERS),
            "正文回应对立理由或说明边界",
        ),
        HotspotEditorialCheck(
            "specific_ending_question",
            "？" in ending and len(ending.replace("评论区聊聊", "")) >= 20,
            "结尾包含由正文推出的具体问句",
        ),
        HotspotEditorialCheck(
            "mobile_readability",
            len(paragraphs) >= 5 and max((len(item) for item in paragraphs), default=0) <= 180,
            "至少五段且单段不超过180字",
        ),
    )
    score = sum(check.passed for check in checks)
    return HotspotEditorialScore(
        score=score,
        total=len(checks),
        passed=score >= 5,
        checks=checks,
    )


def require_hotspot_editorial_quality(**kwargs) -> HotspotEditorialScore:
    report = evaluate_hotspot_editorial_quality(**kwargs)
    if not report.passed:
        failed = "、".join(check.name for check in report.checks if not check.passed)
        raise ValueError(f"热点深评编辑质量未通过：{report.score}/{report.total}；缺项：{failed}")
    return report
