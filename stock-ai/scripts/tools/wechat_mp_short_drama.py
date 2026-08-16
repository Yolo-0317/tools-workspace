#!/usr/bin/env python3
"""公众号短剧池、选剧、归因与 short-play 组件门禁。"""

from __future__ import annotations

import os
import json
import math
import random
import re
import html
import stat
import uuid
import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, quote, unquote, urlparse
from zoneinfo import ZoneInfo

import requests

from scripts.tools.wechat_mp_client import (
    draft_add,
    draft_batchget,
    fetch_draft_news_item,
)


DRAMA_SELECT_URL = (
    "https://daihuo.qq.com/trpc.cps.weixin_select.WeiXinSelect/DramaSelect"
)
MINIDRAMA_LINK_URL = "https://mp.weixin.qq.com/cgi-bin/minidrama?action=link"
TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = ROOT / "data" / "wechat_mp_short_drama_pool.json"
USAGE_PATH = ROOT / "data" / "wechat_mp_short_drama_usage.json"
ATTRIBUTION_PATH = ROOT / "data" / "wechat_mp_short_drama_attribution.json"
WORKPLACE_KINDS = frozenset(
    {"sector", "market", "news", "top5", "dragons", "workspace", "temp"}
)
LONGFORM_KINDS = frozenset(
    {
        "hotspot",
        "tv_review",
        "tv",
        "film",
        "movie",
        "sector",
        "market",
        "news",
        "top5",
        "dragons",
        "workspace",
        "temp",
    }
)
PLAIN_CPS_RE = re.compile(
    r'<mp-common-cpsad\b(?![^>]*\bdata-adtype=["\']short-play["\'])',
    re.IGNORECASE,
)
SHORT_PLAY_RE = re.compile(
    r'<mp-common-cpsad\b[^>]*\bdata-adtype=["\']short-play["\']',
    re.IGNORECASE,
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


@dataclass(frozen=True)
class ShortDramaAttribution:
    drama_id: str
    plan_id: str
    src_appid: str
    play_appid: str
    default_path: str
    wx_ticket: str
    captured_at: str


@dataclass(frozen=True)
class WeChatDramaWebSession:
    cookie: str
    token: str
    fingerprint: str
    lang: str = "zh_CN"


@dataclass(frozen=True)
class DramaScore:
    commission_score: float
    heat_score: float
    appeal_score: float
    usage_penalty: float
    final_score: float


STRONG_APPEAL_TERMS = (
    "反击",
    "逆袭",
    "复仇",
    "身份反转",
    "豪门",
    "千金",
    "职场冲突",
    "家庭冲突",
    "离婚",
    "追妻",
    "重生",
)
MEDIUM_APPEAL_TERMS = ("都市", "爱情", "家庭", "职场", "励志")
SERIOUS_EVENT_TERMS = (
    "伤亡",
    "遇难",
    "死亡",
    "火灾",
    "地震",
    "洪水",
    "坠机",
    "事故",
    "灾害",
    "救援",
)
ESCAPIST_DRAMA_TERMS = (
    "甜宠",
    "霸总",
    "豪门",
    "追妻",
    "闪婚",
    "宠妻",
    "复仇",
    "重生",
)


class _ShortPlayParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.matches: list[dict[str, str]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "mp-common-cpsad" and values.get("data-adtype") == "short-play":
            self.matches.append(values)


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


def load_drama_web_session(
    path: Path | None = None,
) -> WeChatDramaWebSession:
    target = path
    if target is None:
        raw = os.getenv("WECHAT_MP_DRAMA_WEB_SESSION_FILE", "").strip()
        if not raw:
            raise RuntimeError("缺少 WECHAT_MP_DRAMA_WEB_SESSION_FILE")
        target = Path(raw).expanduser()
    try:
        mode = stat.S_IMODE(target.stat().st_mode)
    except OSError as exc:
        raise RuntimeError("短剧网页会话文件不可用") from exc
    if mode & 0o077:
        raise RuntimeError("短剧网页会话文件权限必须为 0600 或更严格")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("短剧网页会话文件格式无效") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("短剧网页会话文件格式无效")
    values = {
        "cookie": str(payload.get("cookie") or "").strip(),
        "token": str(payload.get("token") or "").strip(),
        "fingerprint": str(payload.get("fingerprint") or "").strip(),
        "lang": str(payload.get("lang") or "zh_CN").strip(),
    }
    missing = [key for key in ("cookie", "token", "fingerprint") if not values[key]]
    if missing:
        raise RuntimeError("短剧网页会话字段缺失: " + ",".join(missing))
    return WeChatDramaWebSession(**values)


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
    max_items: int | None = None,
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
        if max_items is not None and len(rows) >= max_items:
            rows = rows[: max(0, max_items)]
            break
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


def _minmax(value: float, values: Sequence[float]) -> float:
    low, high = min(values), max(values)
    return 1.0 if low == high else (value - low) / (high - low)


def drama_appeal_points(drama: ShortDrama) -> int:
    text = " ".join(
        (drama.drama_name, drama.era, drama.theme, drama.description)
    )
    strong = min(15, sum(5 for term in STRONG_APPEAL_TERMS if term in text))
    medium = min(5, sum(2 for term in MEDIUM_APPEAL_TERMS if term in text))
    return strong + medium


def score_drama(
    drama: ShortDrama,
    *,
    population: Sequence[ShortDrama],
    usage_count: int = 0,
) -> DramaScore:
    commission = _minmax(
        drama.rate_bp,
        [row.rate_bp for row in population],
    ) * 45
    heat = _minmax(
        math.log1p(max(0, drama.hot_degree)),
        [math.log1p(max(0, row.hot_degree)) for row in population],
    ) * 35
    appeal = float(drama_appeal_points(drama))
    penalty = float(min(max(0, usage_count) * 3, 9))
    return DramaScore(
        commission_score=commission,
        heat_score=heat,
        appeal_score=appeal,
        usage_penalty=penalty,
        final_score=commission + heat + appeal - penalty,
    )


def drama_repeat_days() -> int:
    try:
        value = int(os.getenv("WECHAT_MP_DRAMA_REPEAT_DAYS", "7"))
    except ValueError:
        value = 7
    return max(0, value)


def drama_min_valid_days() -> int:
    try:
        value = int(os.getenv("WECHAT_MP_DRAMA_MIN_VALID_DAYS", "7"))
    except ValueError:
        value = 7
    return max(0, value)


def incompatibility_reason(
    article: Mapping[str, Any],
    drama: ShortDrama,
) -> str | None:
    article_text = article_match_text(article)
    drama_text = " ".join(
        (drama.drama_name, drama.era, drama.theme, drama.description)
    )
    serious = next((term for term in SERIOUS_EVENT_TERMS if term in article_text), None)
    escapist = next((term for term in ESCAPIST_DRAMA_TERMS if term in drama_text), None)
    if serious and escapist:
        return f"严肃事件“{serious}”不匹配娱乐钩子“{escapist}”"
    return None


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
) -> tuple[ShortDrama, DramaScore]:
    if not rows:
        raise RuntimeError("没有可用短剧候选")
    current = now or datetime.now(TZ)
    cutoff = current - timedelta(days=drama_repeat_days())
    recent_counts: dict[str, int] = {}
    for item in _load_usage(usage_path):
        try:
            used_at = datetime.fromisoformat(str(item.get("used_at") or ""))
        except ValueError:
            continue
        if used_at.tzinfo is None:
            used_at = used_at.replace(tzinfo=TZ)
        if used_at >= cutoff:
            drama_id = str(item.get("drama_id") or "")
            if drama_id:
                recent_counts[drama_id] = recent_counts.get(drama_id, 0) + 1
    candidates = [row for row in rows if incompatibility_reason(article, row) is None]
    if not candidates:
        raise RuntimeError("没有通过题材安全门禁的短剧")
    base_scores = {
        row.drama_id: score_drama(row, population=candidates)
        for row in candidates
    }
    ranked = sorted(
        candidates,
        key=lambda row: (
            -base_scores[row.drama_id].final_score,
            -row.rate_bp,
            -row.hot_degree,
            -row.offline_timestamp,
            row.drama_id,
        ),
    )
    shortlist = ranked[:3]
    final_scores = {
        row.drama_id: score_drama(
            row,
            population=candidates,
            usage_count=recent_counts.get(row.drama_id, 0),
        )
        for row in shortlist
    }
    picked = min(
        shortlist,
        key=lambda row: (
            -final_scores[row.drama_id].final_score,
            -base_scores[row.drama_id].final_score,
            -row.rate_bp,
            -row.hot_degree,
            row.drama_id,
        ),
    )
    return picked, final_scores[picked.drama_id]


def record_drama_usage(
    drama: ShortDrama | Mapping[str, Any],
    *,
    article_title: str,
    usage_path: Path = USAGE_PATH,
    used_at: datetime | None = None,
) -> None:
    current = used_at or datetime.now(TZ)
    if isinstance(drama, Mapping):
        drama_id = str(drama.get("drama_id") or "")
        drama_name = str(drama.get("drama_name") or "")
    else:
        drama_id = drama.drama_id
        drama_name = drama.drama_name
    if not drama_id or not drama_name:
        raise RuntimeError("短剧使用记录缺少剧目身份")
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
            "drama_id": drama_id,
            "drama_name": drama_name,
            "article_title": article_title,
            "used_at": current.isoformat(timespec="seconds"),
        }
    )
    _atomic_write_json(usage_path, retained)


def assert_longform_promotion_safe(
    article: Mapping[str, Any],
    *,
    kind: str | None,
) -> None:
    normalized = (kind or "").strip().lower()
    if normalized not in LONGFORM_KINDS:
        return
    content = str(article.get("content") or "")
    footer = ((article.get("product_info") or {}).get("footer_product_info"))
    if PLAIN_CPS_RE.search(content) or footer:
        raise RuntimeError("长文仍含普通返佣商品")
    count = len(SHORT_PLAY_RE.findall(content))
    if short_drama_enabled() and count == 0:
        raise RuntimeError("长文缺少短剧组件")
    if count > 1:
        raise RuntimeError(f"长文短剧组件数量异常: {count}")


def attach_short_drama(
    article: Mapping[str, Any],
    *,
    kind: str | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    normalized = (kind or "").strip().lower()
    out = dict(article)
    if normalized not in LONGFORM_KINDS or not short_drama_enabled():
        return out
    current = now or datetime.now(TZ)
    rows = dedupe_dramas(
        eligible_dramas(
            load_or_refresh_drama_pool(now=current),
            now=current,
            min_valid_days=drama_min_valid_days(),
        )
    )
    attributed_rows = [row for row in rows if has_attribution_for_drama(row)]
    if not attributed_rows:
        raise RuntimeError("没有同时满足内容和归因门禁的短剧")
    excluded_reasons = [
        f"{row.drama_name}: {reason}"
        for row in attributed_rows
        if (reason := incompatibility_reason(out, row)) is not None
    ]
    drama, score = pick_short_drama(
        out,
        attributed_rows,
        kind=normalized,
        now=current,
    )
    attribution = load_attribution_for_drama(drama)
    component = build_short_drama_html(drama, attribution)
    content = str(out.get("content") or "")
    if not SHORT_PLAY_RE.search(content):
        from scripts.tools.wechat_mp_product import cps_injection_index

        position = cps_injection_index(content)
        out["content"] = content[:position] + component + content[position:]
    else:
        validate_short_drama_component(content, drama)
    out["short_drama"] = {
        "drama_id": drama.drama_id,
        "drama_name": drama.drama_name,
        "era": drama.era,
        "theme": drama.theme,
        "media_count": drama.media_count,
        "rate_bp": drama.rate_bp,
        "hot_degree": drama.hot_degree,
        "plan_id": drama.plan_id,
        "score": {
            "commission": round(score.commission_score, 1),
            "heat": round(score.heat_score, 1),
            "appeal": round(score.appeal_score, 1),
            "penalty": round(score.usage_penalty, 1),
            "final": round(score.final_score, 1),
        },
        "excluded_reasons": excluded_reasons,
    }
    assert_longform_promotion_safe(out, kind=normalized)
    return out


def promotion_summary(article: Mapping[str, Any]) -> str:
    item = article.get("short_drama") or {}
    if not isinstance(item, Mapping) or not item.get("drama_name"):
        return "短剧推广: 未启用"
    category = "/".join(
        str(item.get(key) or "").strip() for key in ("era", "theme")
        if str(item.get(key) or "").strip()
    )
    media_count = _as_int(item.get("media_count"))
    rate_percent = _as_int(item.get("rate_bp")) / 100
    summary = (
        f"短剧推广: {item.get('drama_name')} · {category or '未分类'} · "
        f"{media_count}集 · 分佣{rate_percent:.2f}% · "
        f"热度{_as_int(item.get('hot_degree'))}"
    )
    score = item.get("score") or {}
    if isinstance(score, Mapping):
        summary += (
            f" · 返佣分{float(score.get('commission') or 0):.1f}"
            f"/热度分{float(score.get('heat') or 0):.1f}"
            f"/吸引力分{float(score.get('appeal') or 0):.1f}"
            f"/轮换-{float(score.get('penalty') or 0):.1f}"
            f"/最终分{float(score.get('final') or 0):.1f}"
        )
    excluded = item.get("excluded_reasons") or []
    if isinstance(excluded, Sequence) and not isinstance(excluded, (str, bytes)):
        safe_reasons = [str(reason) for reason in excluded[:3] if str(reason)]
        if safe_reasons:
            summary += " · 门禁排除" + "；".join(safe_reasons)
    return summary


def _attribution_from_attrs(
    attrs: Mapping[str, str],
    *,
    captured_at: datetime,
) -> ShortDramaAttribution:
    default_path = unquote(html.unescape(attrs.get("data-defaultpath", "")))
    wx_ticket = parse_qs(urlparse(default_path).query).get("wxTicket", [""])[0]
    values = {
        "drama_id": attrs.get("data-dramaid", ""),
        "plan_id": attrs.get("data-planid", ""),
        "src_appid": attrs.get("data-srcappid", ""),
        "play_appid": attrs.get("data-playappid", ""),
        "default_path": default_path,
        "wx_ticket": wx_ticket,
    }
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise RuntimeError(f"短剧归因字段缺失: {','.join(missing)}")
    return ShortDramaAttribution(
        **values,
        captured_at=captured_at.isoformat(timespec="seconds"),
    )


def parse_short_drama_components(
    html_text: str,
    *,
    now: datetime | None = None,
) -> list[ShortDramaAttribution]:
    parser = _ShortPlayParser()
    parser.feed(html_text)
    captured_at = now or datetime.now(TZ)
    return [
        _attribution_from_attrs(attrs, captured_at=captured_at)
        for attrs in parser.matches
    ]


def parse_short_drama_component(
    html_text: str,
    *,
    now: datetime | None = None,
) -> ShortDramaAttribution:
    matches = parse_short_drama_components(html_text, now=now)
    if not matches:
        raise RuntimeError("未发现 short-play 组件")
    if len(matches) != 1:
        raise RuntimeError(f"short-play 组件数量异常: {len(matches)}")
    return matches[0]


def parse_minidrama_link_response(
    payload: Mapping[str, Any],
    drama: ShortDrama,
    *,
    now: datetime | None = None,
) -> ShortDramaAttribution:
    base_resp = payload.get("base_resp") or {}
    outer_ret = _as_int(
        base_resp.get("ret") if isinstance(base_resp, Mapping) else None,
        -1,
    )
    if outer_ret != 0:
        raise RuntimeError(f"短剧归因接口失败: outer_ret={outer_ret}")
    raw_data = payload.get("data")
    try:
        inner = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    except json.JSONDecodeError as exc:
        raise RuntimeError("短剧归因接口响应格式无效") from exc
    if not isinstance(inner, Mapping):
        raise RuntimeError("短剧归因接口响应格式无效")
    inner_code = _as_int(inner.get("errcode"), -1)
    if inner_code != 0:
        raise RuntimeError(f"短剧归因接口失败: inner_errcode={inner_code}")
    default_path = str(inner.get("path") or "").strip()
    parsed_path = urlparse(default_path)
    if parsed_path.scheme != "plugin-private":
        raise RuntimeError("短剧归因接口缺少有效归因路径")
    query = parse_qs(parsed_path.query)
    path_drama_id = query.get("dramaId", [""])[0]
    path_src_appid = query.get("srcAppid", [""])[0]
    wx_ticket = query.get("wxTicket", [""])[0]
    if path_drama_id != drama.drama_id or path_src_appid != drama.src_appid:
        raise RuntimeError("短剧身份不匹配")
    if not wx_ticket:
        raise RuntimeError("短剧归因接口缺少归因票据")
    current = now or datetime.now(TZ)
    return ShortDramaAttribution(
        drama_id=drama.drama_id,
        plan_id=drama.plan_id,
        src_appid=drama.src_appid,
        play_appid=drama.play_appid,
        default_path=default_path,
        wx_ticket=wx_ticket,
        captured_at=current.isoformat(timespec="seconds"),
    )


def fetch_short_drama_attribution(
    drama: ShortDrama,
    *,
    web_session: WeChatDramaWebSession | None = None,
    session: requests.Session | None = None,
    now: datetime | None = None,
    random_value: float | None = None,
) -> ShortDramaAttribution:
    current = now or datetime.now(TZ)
    credentials = web_session or load_drama_web_session()
    request_id = str(int(current.timestamp() * 1000))
    cps_detail = json.dumps(
        {
            "request_id": request_id,
            "biz_type": 0,
            "appid": drama.play_appid,
            "plan_id": drama.plan_id,
            "promoter_id": drama_kol_id(),
            "ext_info": "",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    client = session or requests.Session()
    client.trust_env = False
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Cookie": credentials.cookie,
        "Referer": (
            "https://mp.weixin.qq.com/cgi-bin/appmsg"
            f"?t=media/appmsg_edit&action=edit&token={quote(credentials.token)}"
            f"&lang={quote(credentials.lang)}"
        ),
    }
    form = {
        "token": credentials.token,
        "lang": credentials.lang,
        "f": "json",
        "ajax": "1",
        "fingerprint": credentials.fingerprint,
        "random": str(random.random() if random_value is None else random_value),
        "cps_detail": cps_detail,
    }
    try:
        response = client.post(
            MINIDRAMA_LINK_URL,
            headers=headers,
            data=form,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError("短剧归因接口请求失败，请更新本地网页会话") from exc
    if not isinstance(payload, Mapping):
        raise RuntimeError("短剧归因接口响应格式无效")
    return parse_minidrama_link_response(payload, drama, now=current)


def load_attribution_map(
    path: Path = ATTRIBUTION_PATH,
) -> dict[str, ShortDramaAttribution]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("attribution root must be an object")
        return {
            str(drama_id): ShortDramaAttribution(**item)
            for drama_id, item in payload.items()
            if isinstance(item, dict)
        }
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"短剧归因缓存无效: {exc}") from exc


def _attribution_matches(
    drama: ShortDrama,
    attribution: ShortDramaAttribution,
) -> bool:
    default_query = parse_qs(urlparse(attribution.default_path).query)
    path_drama_id = default_query.get("dramaId", [""])[0]
    return (
        attribution.drama_id == drama.drama_id
        and path_drama_id == drama.drama_id
        and attribution.plan_id == drama.plan_id
        and attribution.src_appid == drama.src_appid
        and attribution.play_appid == drama.play_appid
        and bool(attribution.wx_ticket)
    )


def has_attribution_for_drama(
    drama: ShortDrama,
    path: Path = ATTRIBUTION_PATH,
) -> bool:
    item = load_attribution_map(path).get(drama.drama_id)
    return item is not None and _attribution_matches(drama, item)


def load_attribution_for_drama(
    drama: ShortDrama,
    path: Path = ATTRIBUTION_PATH,
) -> ShortDramaAttribution:
    item = load_attribution_map(path).get(drama.drama_id)
    if item is None:
        raise RuntimeError(f"缺少短剧归因: {drama.drama_id}")
    if not _attribution_matches(drama, item):
        raise RuntimeError("短剧归因与候选不匹配")
    return item


def build_short_drama_html(
    drama: ShortDrama,
    attribution: ShortDramaAttribution,
    *,
    trace_id: str | None = None,
) -> str:
    if not _attribution_matches(drama, attribution):
        raise RuntimeError("短剧归因与候选不匹配")
    attrs = {
        "contenteditable": "false",
        "class": "js_uneditable custom_select_card new_cps_iframe mp_common_widget",
        "data-pluginname": "mpcps",
        "data-adtype": "short-play",
        "data-templateid": "card",
        "data-cpsversion": "v122",
        "data-goodssouce": "1",
        "data-showchangebtn": "1",
        "data-dramaid": drama.drama_id,
        "data-srcappid": drama.src_appid,
        "data-playappid": drama.play_appid,
        "data-planid": drama.plan_id,
        "data-traceid": trace_id or str(uuid.uuid4()),
        "data-defaultpath": quote(attribution.default_path, safe=""),
    }
    rendered = " ".join(
        f'{key}="{html.escape(value, quote=True)}"' for key, value in attrs.items()
    )
    component = f"<mp-common-cpsad {rendered}></mp-common-cpsad>"
    validate_short_drama_component(component, drama)
    return component


def validate_short_drama_component(
    component: str,
    drama: ShortDrama,
) -> ShortDramaAttribution:
    parsed = parse_short_drama_component(component)
    if not _attribution_matches(drama, parsed):
        raise RuntimeError("短剧归因与候选不匹配")
    return parsed


def capture_sample_attributions(
    title: str,
    *,
    path: Path = ATTRIBUTION_PATH,
    now: datetime | None = None,
    max_items: int = 100,
) -> list[ShortDramaAttribution]:
    target = title.strip()
    matches: list[dict[str, Any]] = []
    offset = 0
    while offset < max_items:
        items, err = draft_batchget(offset=offset, count=20, no_content=False)
        if err:
            raise RuntimeError(f"短剧样本草稿读取失败: {err.get('errmsg') or err}")
        if not items:
            break
        for item in items:
            news_items = ((item.get("content") or {}).get("news_item") or [])
            for news in news_items:
                if str(news.get("title") or "").strip() == target:
                    matches.append(news)
        offset += len(items)
        if len(items) < 20:
            break
    if len(matches) != 1:
        raise RuntimeError(f"短剧样本草稿匹配数量异常: {len(matches)}")

    captured = parse_short_drama_components(
        str(matches[0].get("content") or ""),
        now=now,
    )
    if not captured:
        raise RuntimeError("样本草稿未发现 short-play 组件")
    _save_attributions(captured, path=path)
    return captured


def _save_attributions(
    captured: Sequence[ShortDramaAttribution],
    *,
    path: Path,
) -> None:
    merged = load_attribution_map(path)
    for item in captured:
        merged[item.drama_id] = item
    _atomic_write_json(
        path,
        {drama_id: asdict(item) for drama_id, item in merged.items()},
    )


def capture_sample_file(
    sample_path: Path,
    *,
    attribution_path: Path = ATTRIBUTION_PATH,
    now: datetime | None = None,
) -> list[ShortDramaAttribution]:
    try:
        html_text = sample_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"无法读取短剧样本文件: {exc}") from exc
    captured = parse_short_drama_components(html_text, now=now)
    if not captured:
        raise RuntimeError("样本文件未发现 short-play 组件")
    _save_attributions(captured, path=attribution_path)
    return captured


def probe_short_drama_component(
    drama_id: str,
    *,
    now: datetime | None = None,
) -> str:
    target = drama_id.strip()
    rows = load_or_refresh_drama_pool(now=now)
    drama = next((row for row in rows if row.drama_id == target), None)
    if drama is None:
        raise RuntimeError(f"短剧池未找到 drama_id={target}")
    try:
        attribution = load_attribution_for_drama(drama)
    except RuntimeError as exc:
        raise RuntimeError(
            "缺少该短剧的归因建卡数据，请抓取选择短剧时的建卡请求"
        ) from exc
    component = build_short_drama_html(drama, attribution)
    current = now or datetime.now(TZ)
    article = {
        "article_type": "news",
        "title": f"短剧组件探针-勿发-{current.strftime('%m%d%H%M')}",
        "author": os.getenv("WECHAT_MP_AUTHOR", "R2D2").strip(),
        "digest": "短剧组件归因探针，仅供后台预览，请勿发表。",
        "content": f"<p>短剧组件归因探针，请勿发表。</p>{component}",
        "show_cover_pic": 0,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }
    media_id, err = draft_add(articles=[article])
    if err or not media_id:
        raise RuntimeError(f"短剧组件探针写入失败: {(err or {}).get('errmsg') or err}")
    return media_id


def verify_saved_short_drama(
    *,
    media_id: str,
    expected_drama_id: str,
    kind: str,
) -> ShortDramaAttribution:
    news, err = fetch_draft_news_item(media_id=media_id)
    if err:
        raise RuntimeError(f"短剧草稿回读失败: {err.get('errmsg') or err}")
    content = str((news or {}).get("content") or "")
    assert_longform_promotion_safe(news or {}, kind=kind)
    if not SHORT_PLAY_RE.search(content):
        raise RuntimeError("短剧草稿回读未发现 short-play 组件")
    parsed = parse_short_drama_component(content)
    if parsed.drama_id != expected_drama_id:
        raise RuntimeError(
            "短剧草稿回读不一致: "
            f"expected={expected_drama_id} actual={parsed.drama_id}"
        )
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="公众号短剧池与归因诊断")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--capture-sample-title")
    parser.add_argument("--capture-sample-file", type=Path)
    parser.add_argument("--probe-component", action="store_true")
    parser.add_argument("--drama-id")
    args = parser.parse_args(argv)

    if args.refresh:
        rows = (
            refresh_drama_pool(max_items=max(0, args.limit))
            if args.limit is not None
            else refresh_drama_pool()
        )
        eligible = eligible_dramas(
            rows,
            now=datetime.now(TZ),
            min_valid_days=drama_min_valid_days(),
        )
        deduped = dedupe_dramas(eligible)
        print(
            f"短剧池: ret=0 total={len(rows)} eligible={len(eligible)} "
            f"deduped={len(deduped)}"
        )
        display_limit = max(0, args.limit) if args.limit is not None else 10
        for item in deduped[:display_limit]:
            print(
                f"drama_id={item.drama_id} name={item.drama_name} "
                f"theme={item.era}/{item.theme} episodes={item.media_count} "
                f"rate={item.rate_bp / 100:.2f}%"
            )
        return 0
    if args.capture_sample_title:
        captured = capture_sample_attributions(args.capture_sample_title)
        for item in captured:
            print(
                f"drama_id={item.drama_id} plan_id={item.plan_id} "
                f"含票据={'是' if item.wx_ticket else '否'} captured_at={item.captured_at}"
            )
        return 0
    if args.capture_sample_file:
        captured = capture_sample_file(args.capture_sample_file)
        for item in captured:
            print(
                f"drama_id={item.drama_id} plan_id={item.plan_id} "
                f"含票据={'是' if item.wx_ticket else '否'} captured_at={item.captured_at}"
            )
        return 0
    if args.probe_component:
        if not args.drama_id:
            parser.error("--probe-component 需要 --drama-id")
        media_id = probe_short_drama_component(args.drama_id)
        print(f"探针草稿 media_id={media_id}，请在后台预览并确认跳转和归因")
        return 0
    parser.error(
        "需要 --refresh、--capture-sample-title、--capture-sample-file 或 --probe-component"
    )
    return 2


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


if __name__ == "__main__":
    raise SystemExit(main())
