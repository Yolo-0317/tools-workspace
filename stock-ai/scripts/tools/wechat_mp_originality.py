"""公众号热点长文原创增量门禁。"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class OriginalityReport:
    content_route: str
    text_length: int
    max_title_similarity_14d: float = 0.0
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
    if length < 1920:
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


def format_originality_report(report: OriginalityReport) -> str:
    state = "PASS" if report.gate_passed else "BLOCK"
    reasons = ",".join(report.failures) if report.failures else "none"
    return (
        f"原创增量报告 [{state}] route={report.content_route} "
        f"text={report.text_length} similarity14d={report.max_title_similarity_14d:.3f} "
        f"failures={reasons}"
    )


def require_originality(report: OriginalityReport) -> OriginalityReport:
    if not report.gate_passed:
        raise ValueError(format_originality_report(report))
    return report
