"""单剧推广稿的公开来源研究与剧情事实台账。"""

from __future__ import annotations

from dataclasses import dataclass

from scripts.tools.wechat_mp_short_drama import ShortDrama


CORE_FACT_TYPES = frozenset({"character", "relationship", "conflict", "reversal"})
ALLOWED_FACT_TYPES = frozenset(
    {
        *CORE_FACT_TYPES,
        "premise",
        "motivation",
        "obstacle",
        "turning_point",
    }
)
ALLOWED_SOURCE_TYPES = frozenset(
    {"platform", "producer", "official_account", "report", "reference"}
)


@dataclass(frozen=True)
class DramaSource:
    source_id: str
    url: str
    title: str
    source_name: str
    source_type: str
    official: bool
    excerpt: str


@dataclass(frozen=True)
class DramaFact:
    fact_id: str
    fact_type: str
    claim: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class DramaResearch:
    drama_id: str
    drama_name: str
    sources: tuple[DramaSource, ...]
    facts: tuple[DramaFact, ...]
    rejected_claims: tuple[str, ...]


def validate_drama_research(research: DramaResearch) -> DramaResearch:
    if not research.drama_id.strip() or not research.drama_name.strip():
        raise ValueError("短剧研究缺少剧目身份")
    if len(research.sources) < 2:
        raise ValueError("短剧研究至少需要两个有效来源")
    source_ids = [source.source_id for source in research.sources]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("短剧研究来源 ID 重复")
    for source in research.sources:
        if source.source_type not in ALLOWED_SOURCE_TYPES:
            raise ValueError("短剧研究来源类型无效")
        if not source.url.startswith(("http://", "https://")):
            raise ValueError("短剧研究来源必须是公开网页")
        if not source.title.strip() or not source.excerpt.strip():
            raise ValueError("短剧研究来源缺少标题或正文摘录")
    if not any(source.official for source in research.sources):
        raise ValueError("短剧研究至少需要一个官方来源")
    fact_types = {fact.fact_type for fact in research.facts}
    if not CORE_FACT_TYPES <= fact_types:
        raise ValueError("剧情事实缺少人物、关系、冲突或反转")
    allowed_sources = set(source_ids)
    fact_ids: set[str] = set()
    for fact in research.facts:
        if not fact.fact_id.strip() or fact.fact_id in fact_ids:
            raise ValueError("剧情事实 ID 为空或重复")
        fact_ids.add(fact.fact_id)
        if fact.fact_type not in ALLOWED_FACT_TYPES:
            raise ValueError("剧情事实类型无效")
        if not fact.claim.strip():
            raise ValueError("剧情事实内容不能为空")
        bound_sources = set(fact.source_ids)
        if not bound_sources <= allowed_sources:
            raise ValueError("剧情事实引用了未登记来源")
        if len(bound_sources) < 2:
            raise ValueError("公开剧情事实至少需要两个来源")
        if "platform" not in bound_sources or not (bound_sources - {"platform"}):
            raise ValueError("公开剧情事实必须同时绑定平台来源和独立来源")
    return research


def platform_source_for_drama(drama: ShortDrama) -> DramaSource:
    if not drama.exp_url.startswith(("http://", "https://")):
        raise ValueError("短剧平台资料缺少公开剧目链接")
    if not drama.description.strip():
        raise ValueError("短剧平台资料缺少剧情简介")
    return DramaSource(
        source_id="platform",
        url=drama.exp_url,
        title=f"{drama.drama_name}平台剧目资料",
        source_name="微信短剧推广平台",
        source_type="platform",
        official=True,
        excerpt=drama.description.strip(),
    )
