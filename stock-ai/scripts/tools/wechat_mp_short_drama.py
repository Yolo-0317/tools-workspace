#!/usr/bin/env python3
"""公众号短剧池、选剧、归因与 short-play 组件门禁。"""

from __future__ import annotations

import os
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import requests


DRAMA_SELECT_URL = (
    "https://daihuo.qq.com/trpc.cps.weixin_select.WeiXinSelect/DramaSelect"
)
TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = ROOT / "data" / "wechat_mp_short_drama_pool.json"


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


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
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
