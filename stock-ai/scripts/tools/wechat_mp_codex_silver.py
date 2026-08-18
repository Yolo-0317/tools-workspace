"""读取并校验 Codex 准备的公众号银发长图文 JSON。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from scripts.tools.wechat_mp_originality import (
    OriginalityReport,
    evaluate_hotspot_longform,
    require_originality,
)

SILVER_LANES = frozenset({"relation", "health", "money"})
SILVER_SLOT_KEY = "silver"

_FIXED_TITLE_PREFIXES = ("银发栏目", "五十岁以后｜", "退休以后｜", "人生下半场｜")
_HEALTH_AUTHORITY_DOMAINS = ("nhc.gov.cn", "chinacdc.cn")
_MONEY_AUTHORITY_DOMAINS = (
    "mohrss.gov.cn",
    "mps.gov.cn",
    "nfra.gov.cn",
    "samr.gov.cn",
    "court.gov.cn",
    "gov.cn",
)
_HEALTH_ADVICE_PATTERNS = (
    r"确诊为",
    r"可以自行服用",
    r"建议服用",
    r"推荐购买.{0,12}保健品",
    r"(?:自行)?停药",
    r"替代治疗",
)
_MONEY_ADVICE_PATTERNS = (
    r"保证收益",
    r"稳赚",
    r"推荐购买.{0,16}(?:理财|保险|基金|股票)",
    r"建议买入",
    r"年化收益.{0,8}%",
)


@dataclass(frozen=True)
class SilverFact:
    claim: str
    source_url: str


@dataclass(frozen=True)
class CodexSilverDraft:
    title: str
    digest: str
    body: str
    topic: str
    lane: str
    research_urls: tuple[str, ...]
    original_thesis: str
    reader_problem: str
    facts: tuple[SilverFact, ...]
    practical_steps: tuple[str, ...]
    cautions: tuple[str, ...]
    rejected_claims: tuple[str, ...]
    slot_key: str = SILVER_SLOT_KEY

    def as_discussion_topic(self) -> dict[str, object]:
        slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", self.topic) or "silver"
        return {
            "trend_title": self.topic,
            "title_zh": self.topic,
            "cover_slug": slug,
            "from_trend": False,
            "research_urls": list(self.research_urls),
        }


def _required_text(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"银发草稿字段 {field} 必须是非空字符串")
    return value.strip()


def _required_text_list(data: dict[str, Any], field: str) -> tuple[str, ...]:
    value = data.get(field)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"银发草稿字段 {field} 必须是字符串数组")
    return tuple(item.strip() for item in value)


def _source_domain(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    host = (parsed.hostname or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def distinct_source_domain_count(urls: Iterable[str]) -> int:
    return len({domain for url in urls if (domain := _source_domain(str(url).strip()))})


def _domain_matches(domain: str, suffixes: tuple[str, ...]) -> bool:
    return any(domain == suffix or domain.endswith(f".{suffix}") for suffix in suffixes)


def _normalized_claim(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def _contains_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def validate_silver_draft(draft: CodexSilverDraft) -> CodexSilverDraft:
    if draft.lane not in SILVER_LANES:
        raise ValueError(f"银发草稿 lane 必须是 {sorted(SILVER_LANES)} 之一")
    if draft.slot_key != SILVER_SLOT_KEY:
        raise ValueError("银发草稿 slot_key 必须是 silver")
    if draft.title.startswith(_FIXED_TITLE_PREFIXES):
        raise ValueError("银发草稿标题不得添加固定栏目名")

    body_chars = len(re.sub(r"\s+", "", draft.body))
    if not 1600 <= body_chars <= 2600:
        raise ValueError(f"银发草稿正文去空白后须为 1600 至 2600 字（当前 {body_chars}）")
    if distinct_source_domain_count(draft.research_urls) < 3:
        raise ValueError("银发草稿至少需要 3 个不同来源域")
    if len(draft.original_thesis.strip()) < 20:
        raise ValueError("银发草稿 original_thesis 不少于 20 字")
    if not draft.reader_problem.strip():
        raise ValueError("银发草稿 reader_problem 不能为空")
    if not draft.facts:
        raise ValueError("银发草稿 facts 至少需要 1 条事实")

    allowed_urls = set(draft.research_urls)
    for fact in draft.facts:
        if not fact.claim.strip() or fact.source_url not in allowed_urls:
            raise ValueError("银发草稿 facts 的 source_url 必须位于 research_urls")

    public_blob = _normalized_claim("\n".join((draft.title, draft.digest, draft.body)))
    for claim in draft.rejected_claims:
        normalized = _normalized_claim(claim)
        if normalized and normalized in public_blob:
            raise ValueError("银发草稿 rejected_claims 不得写回标题、摘要或正文")

    source_domains = tuple(_source_domain(url) for url in draft.research_urls)
    if draft.lane == "health":
        if not any(_domain_matches(domain, _HEALTH_AUTHORITY_DOMAINS) for domain in source_domains):
            raise ValueError("银发健康稿至少需要 1 个权威健康来源")
        if _contains_pattern(public_blob, _HEALTH_ADVICE_PATTERNS):
            raise ValueError("银发健康稿不得提供诊断、用药或治疗建议")
    if draft.lane == "money":
        if not any(_domain_matches(domain, _MONEY_AUTHORITY_DOMAINS) for domain in source_domains):
            raise ValueError("银发钱财稿至少需要 1 个权威政务或监管来源")
        if _contains_pattern(public_blob, _MONEY_ADVICE_PATTERNS):
            raise ValueError("银发钱财稿不得包含收益承诺或产品推荐")
    return draft


def load_codex_silver_draft_data(data: Any) -> CodexSilverDraft:
    if not isinstance(data, dict):
        raise ValueError("银发草稿顶层必须是 JSON 对象")
    facts_raw = data.get("facts")
    if not isinstance(facts_raw, list):
        raise ValueError("银发草稿字段 facts 必须是对象数组")
    facts: list[SilverFact] = []
    for row in facts_raw:
        if not isinstance(row, dict):
            raise ValueError("银发草稿字段 facts 必须是对象数组")
        facts.append(
            SilverFact(
                claim=_required_text(row, "claim"),
                source_url=_required_text(row, "source_url"),
            )
        )
    raw_slot = data.get("slot_key", SILVER_SLOT_KEY)
    if not isinstance(raw_slot, str):
        raise ValueError("银发草稿字段 slot_key 必须是字符串")
    draft = CodexSilverDraft(
        title=_required_text(data, "title"),
        digest=_required_text(data, "digest"),
        body=_required_text(data, "body"),
        topic=_required_text(data, "topic"),
        lane=_required_text(data, "lane"),
        research_urls=_required_text_list(data, "research_urls"),
        original_thesis=_required_text(data, "original_thesis"),
        reader_problem=_required_text(data, "reader_problem"),
        facts=tuple(facts),
        practical_steps=_required_text_list(data, "practical_steps"),
        cautions=_required_text_list(data, "cautions"),
        rejected_claims=_required_text_list(data, "rejected_claims"),
        slot_key=raw_slot.strip(),
    )
    return validate_silver_draft(draft)


def load_codex_silver_draft(path: Path) -> CodexSilverDraft:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"银发草稿 JSON 无效: {source}: {exc.msg}") from exc
    return load_codex_silver_draft_data(data)


def validate_codex_silver_originality(
    draft: CodexSilverDraft,
    *,
    history_posts: list[dict[str, Any]],
) -> OriginalityReport:
    validate_silver_draft(draft)
    return require_originality(
        evaluate_hotspot_longform(
            title=draft.title,
            body=draft.body,
            research_urls=draft.research_urls,
            thesis=draft.original_thesis,
            history_posts=history_posts,
        )
    )
