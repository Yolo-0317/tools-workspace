#!/usr/bin/env python3
"""公众号短剧池、选剧、归因与 short-play 组件门禁。"""

from __future__ import annotations

import os
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

import requests


DRAMA_SELECT_URL = (
    "https://daihuo.qq.com/trpc.cps.weixin_select.WeiXinSelect/DramaSelect"
)
TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = ROOT / "data" / "wechat_mp_short_drama_pool.json"
USAGE_PATH = ROOT / "data" / "wechat_mp_short_drama_usage.json"
WORKPLACE_KINDS = frozenset(
    {"sector", "market", "news", "top5", "dragons", "workspace", "temp"}
)


@dataclass(frozen=True)
class ShortDrama:
    drama_id: str
    drama_name: str
    src_appid: str
    play_appid: str
    cover_url: str
    era: str
    theme: str
    description: str
    status: int
    plan_id: str
    rate_bp: int
    hot_degree: int
    media_count: int
    offline_timestamp: int
    preview_path: str
    preview_sn: str
    exp_url: str
    click_url: str
    trace_id: str
    fetched_at: str


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def drama_kol_id() -> str:
    value = os.getenv("WECHAT_MP_DRAMA_KOL_ID", "").strip()
    if not value:
        raise RuntimeError("缺少 WECHAT_MP_DRAMA_KOL_ID")
    return value


def short_drama_enabled() -> bool:
    return os.getenv("WECHAT_MP_SHORT_DRAMA", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def drama_cache_ttl() -> timedelta:
    raw = os.getenv("WECHAT_MP_DRAMA_CACHE_TTL_HOURS", "6").strip()
    try:
        hours = float(raw)
    except ValueError:
        hours = 6.0
    return timedelta(hours=max(0.25, hours))


def fetch_drama_page(
    *,
    page_no: int,
    page_size: int = 30,
    session: requests.Session | None = None,
    fetched_at: datetime | None = None,
) -> tuple[list[ShortDrama], int]:
    client = session or requests.Session()
    client.trust_env = False
    response = client.post(
        DRAMA_SELECT_URL,
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "Referer": "https://file.daihuo.qq.com/",
            "Origin": "https://file.daihuo.qq.com",
        },
        json={
            "flow_type": 3,
            "query": {},
            "page": {"no": page_no, "size": page_size},
            "kol_info": {"id": drama_kol_id()},
        },
        timeout=30,
    )
    response.raise_for_status()
    return parse_drama_response(
        response.json(),
        fetched_at=fetched_at or datetime.now(TZ),
    )


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def refresh_drama_pool(
    *,
    cache_path: Path = CACHE_PATH,
    page_size: int = 30,
    max_pages: int | None = None,
    now: datetime | None = None,
) -> list[ShortDrama]:
    current = now or datetime.now(TZ)
    rows: list[ShortDrama] = []
    total = 0
    page_no = 1
    while max_pages is None or page_no <= max_pages:
        page_rows, total = fetch_drama_page(
            page_no=page_no,
            page_size=page_size,
            fetched_at=current,
        )
        if not page_rows:
            break
        rows.extend(page_rows)
        if total and len(rows) >= total:
            break
        page_no += 1

    _atomic_write_json(
        cache_path,
        {
            "fetched_at": current.isoformat(timespec="seconds"),
            "total": total,
            "items": [asdict(row) for row in rows],
        },
    )
    return rows


def _read_drama_cache(path: Path) -> tuple[datetime, list[ShortDrama]] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(str(payload["fetched_at"]))
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=TZ)
        rows = [ShortDrama(**item) for item in payload.get("items") or []]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return fetched_at, rows


def load_or_refresh_drama_pool(
    *,
    cache_path: Path = CACHE_PATH,
    now: datetime | None = None,
) -> list[ShortDrama]:
    current = now or datetime.now(TZ)
    cached = _read_drama_cache(cache_path)
    ttl = drama_cache_ttl()
    if cached is None:
        try:
            return refresh_drama_pool(cache_path=cache_path, now=current)
        except Exception as exc:
            raise RuntimeError(f"短剧列表刷新失败: {exc}") from exc

    fetched_at, rows = cached
    hard_expiry = fetched_at + ttl
    refresh_margin = min(timedelta(minutes=30), ttl / 4)
    refresh_at = hard_expiry - refresh_margin
    if current < refresh_at:
        return rows

    try:
        return refresh_drama_pool(cache_path=cache_path, now=current)
    except Exception as exc:
        if current < hard_expiry:
            return rows
        raise RuntimeError("短剧列表刷新失败且缓存已过期") from exc


def normalize_drama_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value).lower()


def eligible_dramas(
    rows: Sequence[ShortDrama],
    *,
    now: datetime,
    min_valid_days: int,
) -> list[ShortDrama]:
    cutoff = int((now + timedelta(days=min_valid_days)).timestamp())
    eligible: list[ShortDrama] = []
    for row in rows:
        required = (
            row.drama_id,
            row.drama_name,
            row.src_appid,
            row.play_appid,
            row.cover_url,
            row.plan_id,
            row.preview_path,
        )
        if (
            row.status == 1
            and all(required)
            and row.offline_timestamp >= cutoff
            and row.media_count > 0
            and row.rate_bp > 0
        ):
            eligible.append(row)
    return eligible


def dedupe_dramas(rows: Sequence[ShortDrama]) -> list[ShortDrama]:
    winners: dict[str, ShortDrama] = {}
    for row in rows:
        key = normalize_drama_name(row.drama_name)
        current = winners.get(key)
        row_key = (
            -row.rate_bp,
            -row.offline_timestamp,
            -row.hot_degree,
            row.drama_id,
        )
        if current is None:
            winners[key] = row
            continue
        current_key = (
            -current.rate_bp,
            -current.offline_timestamp,
            -current.hot_degree,
            current.drama_id,
        )
        if row_key < current_key:
            winners[key] = row
    return sorted(winners.values(), key=lambda row: (-row.hot_degree, row.drama_id))


def article_match_text(article: Mapping[str, Any]) -> str:
    raw = " ".join(
        str(article.get(key) or "") for key in ("title", "digest", "body_text")
    )
    return raw[:1200]


def _bigrams(value: str) -> set[str]:
    compact = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value).lower()
    return {compact[index : index + 2] for index in range(max(0, len(compact) - 1))}


def _minmax(value: int, values: Sequence[int]) -> float:
    low, high = min(values), max(values)
    return 0.5 if low == high else (value - low) / (high - low)


def score_drama(
    drama: ShortDrama,
    *,
    match_text: str,
    kind: str,
    population: Sequence[ShortDrama],
) -> float:
    article_terms = _bigrams(match_text)
    drama_terms = _bigrams(
        " ".join((drama.drama_name, drama.era, drama.theme, drama.description))
    )
    relevance = len(article_terms & drama_terms) / max(1, min(20, len(drama_terms)))
    if kind in WORKPLACE_KINDS and any(
        term in drama.theme for term in ("职场", "都市", "励志")
    ):
        relevance = min(1.0, relevance + 0.15)
    heat = _minmax(drama.hot_degree, [row.hot_degree for row in population])
    rate = _minmax(drama.rate_bp, [row.rate_bp for row in population])
    return relevance * 0.50 + heat * 0.30 + rate * 0.20


def drama_repeat_days() -> int:
    try:
        value = int(os.getenv("WECHAT_MP_DRAMA_REPEAT_DAYS", "7"))
    except ValueError:
        value = 7
    return max(0, value)


def _load_usage(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def pick_short_drama(
    article: Mapping[str, Any],
    rows: Sequence[ShortDrama],
    *,
    kind: str,
    usage_path: Path = USAGE_PATH,
    now: datetime | None = None,
) -> ShortDrama:
    if not rows:
        raise RuntimeError("没有可用短剧候选")
    current = now or datetime.now(TZ)
    cutoff = current - timedelta(days=drama_repeat_days())
    recent_ids: set[str] = set()
    for item in _load_usage(usage_path):
        try:
            used_at = datetime.fromisoformat(str(item.get("used_at") or ""))
        except ValueError:
            continue
        if used_at.tzinfo is None:
            used_at = used_at.replace(tzinfo=TZ)
        if used_at >= cutoff:
            recent_ids.add(str(item.get("drama_id") or ""))
    candidates = [row for row in rows if row.drama_id not in recent_ids]
    if not candidates:
        candidates = list(rows)
    match_text = article_match_text(article)
    return min(
        candidates,
        key=lambda row: (
            -score_drama(
                row,
                match_text=match_text,
                kind=kind,
                population=candidates,
            ),
            -row.hot_degree,
            -row.offline_timestamp,
            row.drama_id,
        ),
    )


def record_drama_usage(
    drama: ShortDrama,
    *,
    article_title: str,
    usage_path: Path = USAGE_PATH,
    used_at: datetime | None = None,
) -> None:
    current = used_at or datetime.now(TZ)
    keep_after = current - timedelta(days=30)
    retained: list[dict[str, Any]] = []
    for item in _load_usage(usage_path):
        try:
            item_time = datetime.fromisoformat(str(item.get("used_at") or ""))
        except ValueError:
            continue
        if item_time.tzinfo is None:
            item_time = item_time.replace(tzinfo=TZ)
        if item_time >= keep_after:
            retained.append(item)
    retained.append(
        {
            "drama_id": drama.drama_id,
            "drama_name": drama.drama_name,
            "article_title": article_title,
            "used_at": current.isoformat(timespec="seconds"),
        }
    )
    _atomic_write_json(usage_path, retained)


def parse_drama_response(
    payload: Mapping[str, Any],
    *,
    fetched_at: datetime,
) -> tuple[list[ShortDrama], int]:
    if _as_int(payload.get("ret"), -1) != 0:
        raise RuntimeError(
            f"DramaSelect 返回失败: {payload.get('ret')} {payload.get('msg') or ''}".strip()
        )

    trace_id = str(payload.get("trace_id") or "")
    timestamp = fetched_at.isoformat(timespec="seconds")
    rows: list[ShortDrama] = []
    for raw in payload.get("recommend_list") or []:
        if not isinstance(raw, Mapping):
            continue
        rows.append(
            ShortDrama(
                drama_id=str(raw.get("drama_id") or ""),
                drama_name=str(raw.get("drama_name") or ""),
                src_appid=str(raw.get("src_appid") or ""),
                play_appid=str(raw.get("play_appid") or ""),
                cover_url=str(raw.get("cover_url") or ""),
                era=str(raw.get("era") or ""),
                theme=str(raw.get("theme") or ""),
                description=str(raw.get("desc") or ""),
                status=_as_int(raw.get("status")),
                plan_id=str(raw.get("plan_id") or ""),
                rate_bp=_as_int(raw.get("rate")),
                hot_degree=_as_int(raw.get("hot_degree")),
                media_count=_as_int(raw.get("media_count")),
                offline_timestamp=_as_int(raw.get("real_offline_time")),
                preview_path=str(raw.get("preview_path") or ""),
                preview_sn=str(raw.get("preview_sn") or ""),
                exp_url=str(raw.get("exp_url") or ""),
                click_url=str(raw.get("click_url") or ""),
                trace_id=trace_id,
                fetched_at=timestamp,
            )
        )
    return rows, _as_int(payload.get("total"))
