"""核验用户主动热点稿在事实、图片与正文确认之间的交付记录。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.tools.wechat_mp_browser_workflow import BrowserWritingWorkflow
    from scripts.tools.wechat_mp_hotspot_image_policy import VerifiedHotspotImages


_CLAIM_KINDS = {"source_fact", "reported_snapshot", "party_statement", "author_inference"}
_IMAGE_ROLES = {"price_snapshot", "document", "scene", "other"}
_SNAPSHOT_TIME_MARKERS = ("当时", "报道时", "刊发时", "截图时", "截至")


@dataclass(frozen=True)
class HandoffSummary:
    claim_count: int
    image_count: int


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _required_text(item: dict, key: str, *, owner: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{owner} 缺少 {key}")
    return value.strip()


def validate_handoff(
    path: Path,
    *,
    workflow: BrowserWritingWorkflow,
    article_path: Path,
    selected_images: VerifiedHotspotImages,
) -> HandoffSummary:
    """只核机器可核的对应关系；事实真伪与图像内容仍由编辑目检。"""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("交付记录必须是 JSON 对象")
    if _required_text(payload, "workflow_id", owner="交付记录") != workflow.workflow_id:
        raise ValueError("交付记录与当前 workflow 不一致")
    if _required_text(payload, "article_sha256", owner="交付记录") != sha256_file(article_path):
        raise ValueError("文章摘要不一致，暂存后稿件可能被替换")
    confirmed_hash = workflow.response_sha256 or hashlib.sha256(
        workflow.raw_response.strip().encode("utf-8")
    ).hexdigest()
    if _required_text(payload, "confirmed_body_sha256", owner="交付记录") != confirmed_hash:
        raise ValueError("已确认正文摘要不一致")
    if _required_text(payload, "confirmation_mode", owner="交付记录") != workflow.response_provider:
        raise ValueError("正文确认方式与 workflow 不一致")

    article = json.loads(Path(article_path).read_text(encoding="utf-8"))
    body = str(article.get("body") or "")
    review = payload.get("editorial_review")
    if not isinstance(review, dict):
        raise ValueError("交付记录缺少文章级审稿")
    for field in (
        "target_reader", "reader_question", "central_thesis",
        "thesis_anchor", "paragraph_progression", "decision",
    ):
        _required_text(review, field, owner="文章级审稿")
    if review["decision"] != "pass":
        raise ValueError("文章级审稿未通过，不得暂存")
    if review["thesis_anchor"].strip() not in body:
        raise ValueError("文章级审稿的核心判断锚点不存在于正文")
    claims = payload.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("交付记录缺少关键主张")
    for index, claim in enumerate(claims, 1):
        if not isinstance(claim, dict):
            raise ValueError(f"关键主张 {index} 不是对象")
        owner = f"关键主张 {index}"
        for field in (
            "text", "kind", "source_url", "published_at", "observed_at",
            "scope_or_period", "body_anchor",
        ):
            _required_text(claim, field, owner=owner)
        if claim["kind"] not in _CLAIM_KINDS:
            raise ValueError(f"{owner} kind 无效")
        if not claim["source_url"].startswith(("https://", "http://")):
            raise ValueError(f"{owner} 来源链接无效")
        anchor = claim["body_anchor"].strip()
        if anchor not in body:
            raise ValueError(f"{owner} 正文锚点不存在")
        if claim["kind"] == "reported_snapshot" and not any(
            marker in anchor for marker in _SNAPSHOT_TIME_MARKERS
        ):
            raise ValueError("页面快照缺少时间限定")

    selected_names = {figure.path.name for figure in selected_images.body_figures}
    if selected_images.cover_source.name not in selected_names:
        raise ValueError("封面没有同时进入正文")
    images = payload.get("images")
    if not isinstance(images, list) or not images:
        raise ValueError("交付记录缺少入选图片")
    listed_names: set[str] = set()
    for index, item in enumerate(images, 1):
        if not isinstance(item, dict):
            raise ValueError(f"图片 {index} 不是对象")
        filename = _required_text(item, "filename", owner=f"图片 {index}")
        role = _required_text(item, "evidence_role", owner=f"图片 {index}")
        if filename in listed_names:
            raise ValueError("交付记录重复列入同一张图片")
        listed_names.add(filename)
        if filename not in selected_names:
            raise ValueError("交付记录图片与正文入选图片不一致")
        figure = next(figure for figure in selected_images.body_figures if figure.path.name == filename)
        if _required_text(item, "sha256", owner=f"图片 {index}") != sha256_file(figure.path):
            raise ValueError("图片摘要不一致")
        meta = selected_images.source_meta.get(filename) or {}
        if role not in _IMAGE_ROLES or role != meta.get("evidence_role"):
            raise ValueError("图片用途不一致")
        _required_text(meta, "visual_description", owner=f"图片 {index} 来源")
        _required_text(meta, "visual_checked_at", owner=f"图片 {index} 来源")
        if role == "price_snapshot":
            description = meta["visual_description"]
            if not any(unit in description for unit in ("元", "¥", "￥")):
                raise ValueError("价格截图的视觉说明未写出价格")
    if listed_names != selected_names:
        raise ValueError("入选正文图片未全部写入交付记录")
    return HandoffSummary(claim_count=len(claims), image_count=len(images))
