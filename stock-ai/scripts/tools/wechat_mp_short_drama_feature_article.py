"""公众号单剧强情节推广稿：Python 选剧，Codex 写稿。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.tools.wechat_mp_codex_short_drama import (
    CodexShortDramaDraft,
    FeatureParagraph,
)
from scripts.tools.wechat_mp_content import _article_shell
from scripts.tools.wechat_mp_seo import attach_publish_hints
from scripts.tools.wechat_mp_short_drama import (
    TZ,
    DramaScore,
    ShortDrama,
    attach_selected_short_drama,
    dedupe_dramas,
    drama_min_valid_days,
    eligible_dramas,
    ensure_attribution_for_drama,
    has_recorded_drama_usage,
    load_or_refresh_drama_pool,
    normalize_drama_name,
    rank_short_drama_candidates,
)
from scripts.tools.wechat_mp_short_drama_research import (
    DramaResearch,
    platform_source_for_drama,
    validate_drama_research,
)


_BANNED_HYPE = ("全网第一", "所有人都在追", "全网都在追", "不看后悔", "真实事件改编")
_EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")
_STILL_ROOT = Path(__file__).resolve().parents[2] / "assets" / "wechat_mp" / "inline-tv"


@dataclass(frozen=True)
class FeatureCopy:
    title: str
    digest: str
    paragraphs: tuple[FeatureParagraph, ...]
    title_fact_ids: tuple[str, ...]
    digest_fact_ids: tuple[str, ...]

    @property
    def body(self) -> str:
        return "\n\n".join(paragraph.text for paragraph in self.paragraphs)


def validate_feature_copy(copy: FeatureCopy, *, research: DramaResearch) -> FeatureCopy:
    validate_drama_research(research)
    title = copy.title.strip()
    digest = copy.digest.strip()
    if not title or len(title) > 32:
        raise ValueError("单剧推广稿标题必须为 1 至 32 字")
    if not digest or len(digest) > 128:
        raise ValueError("单剧推广稿摘要必须为 1 至 128 字")
    if not 5 <= len(copy.paragraphs) <= 9:
        raise ValueError("单剧推广稿正文必须包含 5 至 9 个完整段落")
    fact_ids = {fact.fact_id for fact in research.facts}
    for label, bound in (("标题", copy.title_fact_ids), ("摘要", copy.digest_fact_ids)):
        if not bound or not set(bound) <= fact_ids:
            raise ValueError(f"{label}必须绑定已核验剧情事实")
    for paragraph in copy.paragraphs:
        if not paragraph.text.strip():
            raise ValueError("正文段落不能为空")
        if not paragraph.fact_ids:
            raise ValueError("正文段落必须绑定剧情事实")
        if not set(paragraph.fact_ids) <= fact_ids:
            raise ValueError("正文段落引用了未登记剧情事实")
    body_chars = len(re.sub(r"\s+", "", copy.body))
    if not 1200 <= body_chars <= 1800:
        raise ValueError(f"单剧推广稿正文需为 1200 至 1800 字（当前 {body_chars}）")
    public_text = "\n".join((title, digest, copy.body))
    if re.search(r"(?m)^\s*(?:#{1,6}|[-*+]\s+|\d+[.)、]\s+)", public_text):
        raise ValueError("单剧推广稿不得使用 Markdown 标题或列表")
    if _EMOJI_RE.search(public_text):
        raise ValueError("单剧推广稿不得包含 emoji")
    hype = next((term for term in _BANNED_HYPE if term in public_text), None)
    if hype:
        raise ValueError(f"单剧推广稿包含无法核验的夸张表述: {hype}")
    normalized_public = re.sub(r"\s+", "", public_text)
    for claim in research.rejected_claims:
        normalized_claim = re.sub(r"\s+", "", claim)
        if normalized_claim and normalized_claim in normalized_public:
            raise ValueError("单剧推广稿写入了研究阶段未采用剧情")
    return copy


def _ranked_candidates(
    now: datetime,
    *,
    exclude_previously_used: bool = True,
    limit: int = 3,
) -> list[tuple[ShortDrama, DramaScore]]:
    rows = dedupe_dramas(
        eligible_dramas(
            load_or_refresh_drama_pool(now=now),
            now=now,
            min_valid_days=drama_min_valid_days(),
        )
    )
    return rank_short_drama_candidates(
        rows,
        now=now,
        limit=limit,
        exclude_previously_used=exclude_previously_used,
    )


def _safe_reason(exc: Exception) -> str:
    text = re.sub(r"\s+", " ", str(exc) or type(exc).__name__).strip()
    text = re.sub(r"(?i)wxTicket=[^&\s\"']+", "wxTicket=[redacted]", text)
    text = re.sub(
        r"(?i)(cookie|token|ticket)\s*[:=]\s*\S+",
        r"\1=[redacted]",
        text,
    )
    return text[:160] or type(exc).__name__


def prepare_short_drama_feature_request(*, now: datetime | None = None) -> dict[str, Any]:
    """生成供当前 Codex 研究与写作的无敏感信息请求。"""
    current = now or datetime.now(TZ)
    ranked = _ranked_candidates(current)
    if not ranked:
        raise RuntimeError("没有未使用且满足收益门槛的短剧候选")
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for drama, score in ranked:
        try:
            ensure_attribution_for_drama(drama, now=current)
        except Exception as exc:
            rejected.append(
                {
                    "drama_id": drama.drama_id,
                    "drama_name": drama.drama_name,
                    "reason": _safe_reason(exc),
                }
            )
            continue
        candidates.append(
            {
                "drama_id": drama.drama_id,
                "drama_name": drama.drama_name,
                "era": drama.era,
                "theme": drama.theme,
                "description": drama.description,
                "cover_url": drama.cover_url,
                "exp_url": drama.exp_url,
                "media_count": drama.media_count,
                "rate_bp": drama.rate_bp,
                "hot_degree": drama.hot_degree,
                "score": {
                    "commission": round(score.commission_score, 2),
                    "heat": round(score.heat_score, 2),
                    "appeal": round(score.appeal_score, 2),
                    "penalty": round(score.usage_penalty, 2),
                    "final": round(score.final_score, 2),
                },
            }
        )
    if not candidates:
        raise RuntimeError("收益前三短剧均无法生成有效推广归因")
    return {
        "request_type": "short_drama_feature",
        "slot_key": "short_drama_feature",
        "candidates": candidates,
        "rejected_candidates": rejected,
        "instructions": {
            "writer": "current_codex",
            "select_one": True,
            "research": "浏览公开网页；每项剧情事实至少绑定 platform 和一个独立公开来源",
            "article": "强情节推荐稿，正文 1200 至 1800 个去空白字符，5 至 9 段，不泄露完整结局",
            "output": "CodexShortDramaDraft JSON",
        },
        "output_schema": {
            "drama_id": "从 candidates 原样选择",
            "drama_name": "与所选 candidate 完全一致",
            "title": "32 字以内",
            "digest": "128 字以内",
            "title_fact_ids": ["character-1", "conflict-1"],
            "digest_fact_ids": ["character-1", "conflict-1"],
            "paragraphs": [
                {"text": "完整自然段", "fact_ids": ["character-1", "conflict-1"]}
            ],
            "sources": [
                {
                    "source_id": "source-1",
                    "url": "https://公开来源",
                    "title": "来源标题",
                    "source_name": "发布主体",
                    "source_type": "producer|official_account|report|reference",
                    "official": False,
                    "excerpt": "支持事实的简短摘录或准确转述",
                }
            ],
            "sources_note": "不得提供 source_id=platform",
            "facts": [
                {
                    "fact_id": "character-1",
                    "fact_type": "character|relationship|conflict|reversal|premise|motivation|obstacle|turning_point",
                    "claim": "可核实剧情事实",
                    "source_ids": ["platform", "source-1"],
                }
            ],
            "rejected_claims": ["未采用或未能双重核实的说法"],
            "slot_key": "short_drama_feature",
        },
    }


def _copy_from_draft(draft: CodexShortDramaDraft) -> FeatureCopy:
    return FeatureCopy(
        title=draft.title,
        digest=draft.digest,
        paragraphs=draft.paragraphs,
        title_fact_ids=draft.title_fact_ids,
        digest_fact_ids=draft.digest_fact_ids,
    )


def inject_verified_stills(
    body: str,
    *,
    drama_id: str,
    asset_root: Path = _STILL_ROOT,
) -> str:
    """把已落盘的官方正片截图均匀插入单剧稿；没有素材时不伪造占位图。"""
    slug = f"short-drama-{str(drama_id).strip()}"
    stills = [
        asset_root / slug / f"still-{index:02d}.jpg"
        for index in range(1, 4)
    ]
    available = [path for path in stills if path.is_file() and path.stat().st_size > 0]
    paragraphs = [part.strip() for part in body.split("\n\n") if part.strip()]
    if not available or len(paragraphs) < 2:
        return body

    last_insertable = max(0, len(paragraphs) - 2)
    if len(available) == 1:
        positions = [last_insertable // 2]
    else:
        positions = [
            round(index * last_insertable / (len(available) - 1))
            for index in range(len(available))
        ]
    inserts: dict[int, list[str]] = {}
    for position, path in zip(positions, available):
        marker = (
            f"[[fig:tv/{slug}/{path.name}|max-h=520;fit=contain;"
            "scene=正片画面;cap=画面来源：爱奇艺官方正片页]]"
        )
        inserts.setdefault(position, []).append(marker)

    enriched: list[str] = []
    for index, paragraph in enumerate(paragraphs):
        enriched.append(paragraph)
        enriched.extend(inserts.get(index, ()))
    return "\n\n".join(enriched)


def build_short_drama_feature_article(
    *,
    codex_draft: CodexShortDramaDraft,
    upload_figures: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(TZ)
    ranked = _ranked_candidates(current)
    draft_id = codex_draft.drama_id
    def find_selected(
        candidates: list[tuple[ShortDrama, DramaScore]],
    ) -> tuple[ShortDrama, DramaScore] | None:
        return next(
            (
                (drama, score)
                for drama, score in candidates
                if drama.drama_id == draft_id
                and normalize_drama_name(drama.drama_name)
                == normalize_drama_name(codex_draft.drama_name)
            ),
            None,
        )

    selected = find_selected(ranked)
    if selected is None and has_recorded_drama_usage(
        draft_id,
        article_title=codex_draft.title,
    ):
        selected = find_selected(
            _ranked_candidates(
                current,
                exclude_previously_used=False,
                limit=10_000,
            )
        )
    if selected is None:
        raise ValueError("Codex 单剧稿选择的剧目不在当前收益前三候选中")
    drama, score = selected
    attribution = ensure_attribution_for_drama(drama, now=current)
    research = validate_drama_research(
        DramaResearch(
            drama_id=codex_draft.drama_id,
            drama_name=codex_draft.drama_name,
            sources=(platform_source_for_drama(drama), *codex_draft.sources),
            facts=codex_draft.facts,
            rejected_claims=codex_draft.rejected_claims,
        )
    )
    copy = validate_feature_copy(_copy_from_draft(codex_draft), research=research)
    body_with_stills = inject_verified_stills(copy.body, drama_id=drama.drama_id)
    article = _article_shell(
        title=copy.title,
        digest=copy.digest,
        body_text=body_with_stills,
        upload_figures=upload_figures,
        kind="short_drama_feature",
        engagement_kind="short_drama_feature",
        attach_promotion=False,
    )
    article = attach_publish_hints(
        article,
        "short_drama_feature",
        engagement_kind="short_drama_feature",
        attach_promotion=False,
    )
    article = attach_selected_short_drama(
        article,
        kind="short_drama_feature",
        drama=drama,
        score=score,
        attribution=attribution,
    )
    article["slot_key"] = "short_drama_feature"
    article["short_drama_feature_report"] = {
        "sources": [
            {"url": source.url, "source_type": source.source_type, "official": source.official}
            for source in research.sources
        ],
        "facts": [
            {"fact_id": fact.fact_id, "fact_type": fact.fact_type, "claim": fact.claim}
            for fact in research.facts
        ],
        "body_chars": len(re.sub(r"\s+", "", copy.body)),
        "fact_gate": "passed",
        "claim_audit": "codex_fact_bindings_passed",
    }
    return article
