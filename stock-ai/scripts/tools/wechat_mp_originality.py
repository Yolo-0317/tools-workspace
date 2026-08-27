"""公众号原创增量门禁。所有检查均在上传或微信 API 调用前完成。"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


TZ = ZoneInfo("Asia/Shanghai")


def hotspot_originality_min_chars() -> int:
    """热点原创报告默认 1800 字，可由一次性命令显式调整。"""
    try:
        requested = int(os.getenv("WECHAT_MP_CODEX_HOTSPOT_MIN_BODY", "1800"))
    except ValueError:
        requested = 1800
    return max(1200, min(1920, requested))
DISABLED_NEWPIC_LANES = {
    "popular_film",
    "classic_single",
    "classic_list",
    "ai_film",
    "nonfilm_hotspot",
}
ALLOWED_NEWPIC_LANES = {"zhixia_daily", "ai_human", "system_log"}
ANCHOR_FIELDS = {
    "scene",
    "character",
    "action",
    "counterpart_or_pressure",
    "consequence",
    "source_url",
    "stage",
}


@dataclass(frozen=True)
class OriginalityReport:
    content_route: str
    text_length: int
    plot_anchor_count: int = 0
    original_image_ratio: float = 0.0
    duplicate_image_count: int = 0
    max_title_similarity_14d: float = 0.0
    same_work_published_30d: bool = False
    specificity_markers: int = 0
    gate_passed: bool = False
    failures: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _normalize_title(title: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", (title or "").lower())


def _published_at(post: Mapping[str, Any]) -> datetime | None:
    if str(post.get("status") or "published") != "published":
        return None
    try:
        value = datetime.fromisoformat(str(post.get("published_at") or ""))
    except ValueError:
        return None
    return value.replace(tzinfo=TZ) if value.tzinfo is None else value.astimezone(TZ)


def _recent_posts(
    posts: Iterable[Mapping[str, Any]], *, days: int, now: datetime
) -> list[Mapping[str, Any]]:
    threshold = now - timedelta(days=days)
    return [post for post in posts if (stamp := _published_at(post)) and stamp >= threshold]


def _max_title_similarity(
    title: str, posts: Iterable[Mapping[str, Any]], *, now: datetime
) -> float:
    target = _normalize_title(title)
    if not target:
        return 0.0
    scores = [
        SequenceMatcher(None, target, _normalize_title(str(post.get("title") or ""))).ratio()
        for post in _recent_posts(posts, days=14, now=now)
        if _normalize_title(str(post.get("title") or ""))
    ]
    return max(scores, default=0.0)


def _normalized_work(value: str) -> str:
    return re.sub(r"[《》！!：:\s·•]+", "", value or "").lower()


def _same_film_recently_published(
    film_titles: Sequence[str], posts: Iterable[Mapping[str, Any]], *, now: datetime
) -> bool:
    requested = {_normalized_work(item) for item in film_titles if _normalized_work(item)}
    for post in _recent_posts(posts, days=30, now=now):
        existing = {
            _normalized_work(str(item))
            for item in (post.get("film_titles") or [])
            if _normalized_work(str(item))
        }
        if requested & existing:
            return True
    return False


def _duplicate_image_count(
    paths: Sequence[Path], sources: Mapping[str, Mapping[str, Any]]
) -> int:
    hashes: list[str] = []
    for path in paths:
        if path.is_file():
            hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
    duplicate_hashes = len(hashes) - len(set(hashes))
    urls = [
        str(source.get("image_url") or "").strip()
        for source in sources.values()
        if str(source.get("image_url") or "").strip()
    ]
    duplicate_urls = len(urls) - len(set(urls))
    return duplicate_hashes + duplicate_urls


_SPECIFICITY_PATTERNS = {
    "action": re.compile(r"铺开|卷起|伸展|拿起|放下|删掉|保留|换成|比较|调整|走到|打开|关上|生成"),
    "object": re.compile(r"瑜伽垫|水杯|毛巾|咖啡杯|衣架|窗帘|桌|椅|外套|手机|书|包|鞋|画面|版本"),
    "scene": re.compile(r"清晨|傍晚|窗边|街角|客厅|卧室|厨房|门口|车站|工位|阳台|楼下"),
    "choice": re.compile(r"只保留|不再|而不是|最后选|取舍|删掉|第一版|第二版|修改|重做|换掉"),
}


def _specificity(text: str) -> tuple[int, int]:
    categories = 0
    total = 0
    for pattern in _SPECIFICITY_PATTERNS.values():
        hits = pattern.findall(text or "")
        if hits:
            categories += 1
            total += len(hits)
    return total, categories


def evaluate_zhixia_newspic(
    *,
    title: str,
    content: str,
    content_lane: str,
    image_paths: Sequence[Path],
    image_sources: Mapping[str, Mapping[str, Any]],
    history_posts: Iterable[Mapping[str, Any]],
    now: datetime | None = None,
) -> OriginalityReport:
    current = now or datetime.now(TZ)
    failures: list[str] = []
    length = len(_clean_text(content))
    markers, marker_categories = _specificity(content)
    originals = sum(
        1 for source in image_sources.values() if str(source.get("source_type") or "") == "original"
    )
    ratio = originals / len(image_sources) if image_sources else 0.0
    duplicates = _duplicate_image_count(image_paths, image_sources)
    similarity = _max_title_similarity(title, history_posts, now=current)
    if content_lane in DISABLED_NEWPIC_LANES or content_lane not in ALLOWED_NEWPIC_LANES:
        failures.append("route_disabled")
    if length < 400:
        failures.append("text_too_short")
    if markers < 3 or marker_categories < 2:
        failures.append("specificity_too_low")
    if image_sources and ratio < 1.0:
        failures.append("non_original_images")
    if duplicates:
        failures.append("duplicate_images")
    if similarity >= 0.78:
        failures.append("similar_recent_title")
    return OriginalityReport(
        content_route="zhixia_original_newspic",
        text_length=length,
        original_image_ratio=round(ratio, 3),
        duplicate_image_count=duplicates,
        max_title_similarity_14d=round(similarity, 3),
        specificity_markers=markers,
        gate_passed=not failures,
        failures=tuple(failures),
    )


def evaluate_hotspot_longform(
    *,
    title: str,
    body: str,
    research_urls: Sequence[str],
    thesis: str,
    history_posts: Iterable[Mapping[str, Any]],
    now: datetime | None = None,
) -> OriginalityReport:
    current = now or datetime.now(TZ)
    failures: list[str] = []
    length = len(_clean_text(body))
    distinct_hosts = {
        urlparse(url).netloc.lower()
        for url in research_urls
        if urlparse(url).scheme == "https" and urlparse(url).netloc
    }
    similarity = _max_title_similarity(title, history_posts, now=current)
    if length < hotspot_originality_min_chars():
        failures.append("text_too_short")
    if len(distinct_hosts) < 3:
        failures.append("sources_too_few")
    if len(_clean_text(thesis)) < 20:
        failures.append("missing_original_thesis")
    if similarity >= 0.78:
        failures.append("similar_recent_title")
    return OriginalityReport(
        content_route="hotspot_longform",
        text_length=length,
        max_title_similarity_14d=round(similarity, 3),
        gate_passed=not failures,
        failures=tuple(failures),
    )


def evaluate_film_longform(
    *,
    title: str,
    body: str,
    film_titles: Sequence[str],
    plot_anchors: Sequence[Mapping[str, Any]],
    history_posts: Iterable[Mapping[str, Any]],
    now: datetime | None = None,
) -> OriginalityReport:
    current = now or datetime.now(TZ)
    failures: list[str] = []
    length = len(_clean_text(body))
    complete = [
        anchor
        for anchor in plot_anchors
        if ANCHOR_FIELDS <= set(anchor)
        and all(str(anchor.get(field) or "").strip() for field in ANCHOR_FIELDS)
        and str(anchor.get("source_url") or "").startswith("https://")
    ]
    same_film = _same_film_recently_published(film_titles, history_posts, now=current)
    similarity = _max_title_similarity(title, history_posts, now=current)
    if length < 1800:
        failures.append("text_too_short")
    if len(complete) < 2:
        failures.append("plot_anchors_incomplete")
    elif len({str(anchor["stage"]).strip() for anchor in complete}) < 2:
        failures.append("plot_anchor_stages_too_few")
    if same_film:
        failures.append("same_film_recently_published")
    if similarity >= 0.78:
        failures.append("similar_recent_title")
    return OriginalityReport(
        content_route="film_longform",
        text_length=length,
        plot_anchor_count=len(complete),
        max_title_similarity_14d=round(similarity, 3),
        same_work_published_30d=same_film,
        gate_passed=not failures,
        failures=tuple(failures),
    )


def format_originality_report(report: OriginalityReport) -> str:
    state = "PASS" if report.gate_passed else "BLOCK"
    reasons = ",".join(report.failures) if report.failures else "none"
    return (
        f"原创增量报告 [{state}] route={report.content_route} "
        f"text={report.text_length} anchors={report.plot_anchor_count} "
        f"original_images={report.original_image_ratio:.3f} "
        f"duplicates={report.duplicate_image_count} "
        f"similarity14d={report.max_title_similarity_14d:.3f} "
        f"specificity={report.specificity_markers} failures={reasons}"
    )


def require_originality(report: OriginalityReport) -> OriginalityReport:
    if not report.gate_passed:
        raise ValueError(format_originality_report(report))
    return report
