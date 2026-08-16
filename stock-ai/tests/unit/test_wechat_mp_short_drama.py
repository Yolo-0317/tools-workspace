"""公众号短剧池、选剧、归因与组件门禁。"""

from __future__ import annotations

import sys
import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.tools import wechat_mp_short_drama as short_drama


TZ = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=TZ)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.trust_env = True
        self.last_url = ""
        self.last_json: dict = {}
        self.last_timeout = 0

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.last_url = url
        self.last_json = dict(kwargs["json"])
        self.last_timeout = int(kwargs["timeout"])
        return FakeResponse(self.payload)


def drama(
    drama_id: str,
    name: str = "测试短剧",
    **overrides: object,
) -> short_drama.ShortDrama:
    row = short_drama.ShortDrama(
        drama_id=drama_id,
        drama_name=name,
        src_appid="wx-source",
        play_appid="wx-play",
        cover_url="https://example.test/cover.jpg",
        era="现代",
        theme="职场",
        description="公司里的故事",
        status=1,
        plan_id=f"plan-{drama_id}",
        rate_bp=6000,
        hot_degree=100,
        media_count=60,
        offline_timestamp=1797992049,
        preview_path=f"plugin-private://player/pages/playlet?dramaId={drama_id}",
        preview_sn=f"preview-{drama_id}",
        exp_url="",
        click_url="",
        trace_id="trace",
        fetched_at=NOW.isoformat(timespec="seconds"),
    )
    return replace(row, **overrides)


def test_parse_drama_response_uses_recommend_list() -> None:
    payload = {
        "ret": 0,
        "msg": "success",
        "total": "2145",
        "trace_id": "trace-page-1",
        "recommend_list": [
            {
                "drama_id": "1713873",
                "drama_name": "修好铁疙瘩转身踏青云",
                "src_appid": "wx-source",
                "play_appid": "wx-player",
                "cover_url": "https://example.test/cover.jpg",
                "era": "现代",
                "theme": "职场",
                "desc": "下岗技师修复精密机床。",
                "status": 1,
                "plan_id": "plan-1",
                "rate": "6000",
                "hot_degree": 21052623,
                "media_count": "60",
                "real_offline_time": "1797992049",
                "preview_path": "plugin-private://player/pages/playlet?dramaId=1713873",
                "preview_sn": "preview-1",
            }
        ],
    }

    rows, total = short_drama.parse_drama_response(payload, fetched_at=NOW)

    assert total == 2145
    assert len(rows) == 1
    assert rows[0].drama_id == "1713873"
    assert rows[0].rate_bp == 6000
    assert rows[0].media_count == 60
    assert rows[0].trace_id == "trace-page-1"
    assert rows[0].fetched_at == "2026-08-16T12:00:00+08:00"


def test_parse_drama_response_rejects_failed_response() -> None:
    with pytest.raises(RuntimeError, match="DramaSelect 返回失败"):
        short_drama.parse_drama_response({"ret": 1001, "msg": "denied"}, fetched_at=NOW)


def test_short_drama_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WECHAT_MP_SHORT_DRAMA", raising=False)
    assert short_drama.short_drama_enabled() is False


def test_short_drama_accepts_explicit_enabled_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WECHAT_MP_SHORT_DRAMA", "true")
    assert short_drama.short_drama_enabled() is True


def test_fetch_drama_page_posts_exact_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_MP_DRAMA_KOL_ID", "kol-test")
    session = FakeSession(
        {"ret": 0, "msg": "success", "total": 2145, "recommend_list": []}
    )

    rows, total = short_drama.fetch_drama_page(
        page_no=4,
        page_size=10,
        session=session,
        fetched_at=NOW,
    )

    assert rows == []
    assert total == 2145
    assert session.last_url == short_drama.DRAMA_SELECT_URL
    assert session.last_json == {
        "flow_type": 3,
        "query": {},
        "page": {"no": 4, "size": 10},
        "kol_info": {"id": "kol-test"},
    }
    assert session.last_timeout == 30
    assert session.trust_env is False


def test_refresh_drama_pool_paginates_until_total(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def fake_fetch(*, page_no: int, page_size: int, **_: object):
        calls.append(page_no)
        pages = {
            1: ([drama("1"), drama("2")], 3),
            2: ([drama("3")], 3),
        }
        return pages[page_no]

    monkeypatch.setattr(short_drama, "fetch_drama_page", fake_fetch)
    cache_path = tmp_path / "pool.json"

    rows = short_drama.refresh_drama_pool(
        cache_path=cache_path,
        page_size=2,
        now=NOW,
    )

    assert calls == [1, 2]
    assert [row.drama_id for row in rows] == ["1", "2", "3"]
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["fetched_at"] == "2026-08-16T12:00:00+08:00"
    assert payload["total"] == 3
    assert [item["drama_id"] for item in payload["items"]] == ["1", "2", "3"]


def test_load_drama_pool_uses_fresh_cache_without_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_path = tmp_path / "pool.json"
    cached = drama("cached")
    cache_path.write_text(
        json.dumps(
            {
                "fetched_at": (NOW - timedelta(hours=1)).isoformat(),
                "total": 1,
                "items": [cached.__dict__],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("WECHAT_MP_DRAMA_CACHE_TTL_HOURS", "6")

    def unexpected_refresh(**_: object):
        raise AssertionError("fresh cache must not refresh")

    monkeypatch.setattr(short_drama, "refresh_drama_pool", unexpected_refresh)

    rows = short_drama.load_or_refresh_drama_pool(cache_path=cache_path, now=NOW)

    assert [row.drama_id for row in rows] == ["cached"]


def test_load_drama_pool_rejects_expired_cache_when_refresh_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_path = tmp_path / "pool.json"
    cached = drama("expired")
    cache_path.write_text(
        json.dumps(
            {
                "fetched_at": (NOW - timedelta(hours=7)).isoformat(),
                "total": 1,
                "items": [cached.__dict__],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("WECHAT_MP_DRAMA_CACHE_TTL_HOURS", "6")

    def failed_refresh(**_: object):
        raise RuntimeError("network")

    monkeypatch.setattr(short_drama, "refresh_drama_pool", failed_refresh)

    with pytest.raises(RuntimeError, match="短剧列表刷新失败且缓存已过期"):
        short_drama.load_or_refresh_drama_pool(cache_path=cache_path, now=NOW)


def test_load_drama_pool_keeps_soft_stale_cache_when_refresh_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_path = tmp_path / "pool.json"
    cached = drama("soft-stale")
    cache_path.write_text(
        json.dumps(
            {
                "fetched_at": (NOW - timedelta(hours=5, minutes=40)).isoformat(),
                "total": 1,
                "items": [cached.__dict__],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("WECHAT_MP_DRAMA_CACHE_TTL_HOURS", "6")
    monkeypatch.setattr(
        short_drama,
        "refresh_drama_pool",
        lambda **_: (_ for _ in ()).throw(RuntimeError("network")),
    )

    rows = short_drama.load_or_refresh_drama_pool(cache_path=cache_path, now=NOW)

    assert [row.drama_id for row in rows] == ["soft-stale"]


def test_eligible_and_dedupe_dramas_keep_best_live_plan() -> None:
    rows = [
        drama(
            "1",
            "同名剧",
            rate_bp=6000,
            offline_timestamp=int((NOW + timedelta(days=90)).timestamp()),
            hot_degree=100,
        ),
        drama(
            "2",
            "同名剧",
            rate_bp=7000,
            offline_timestamp=int((NOW + timedelta(days=30)).timestamp()),
            hot_degree=50,
        ),
        drama(
            "3",
            "即将下线",
            offline_timestamp=int((NOW + timedelta(days=3)).timestamp()),
        ),
        drama("4", "字段缺失", play_appid=""),
    ]

    eligible = short_drama.eligible_dramas(rows, now=NOW, min_valid_days=7)
    deduped = short_drama.dedupe_dramas(eligible)

    assert [row.drama_id for row in deduped] == ["2"]


def test_pick_short_drama_prefers_relevant_workplace_story(tmp_path: Path) -> None:
    rows = [
        drama(
            "romance",
            "总裁甜宠",
            theme="爱情",
            description="豪门爱情",
            hot_degree=1000,
        ),
        drama(
            "expense",
            "报销风波后整个公司都慌了",
            theme="都市、职场",
            description="员工提交报销单，公司报销制度突然收紧。",
            hot_degree=500,
        ),
    ]
    article = {
        "title": "公司报销为什么越来越严格",
        "digest": "职场制度观察",
        "body_text": "员工提交报销单之后，财务开始逐项核查。",
    }

    picked = short_drama.pick_short_drama(
        article,
        rows,
        kind="workspace",
        usage_path=tmp_path / "usage.json",
        now=NOW,
    )

    assert picked.drama_id == "expense"


def test_pick_short_drama_avoids_recently_recorded_drama(tmp_path: Path) -> None:
    usage_path = tmp_path / "usage.json"
    rows = [
        drama("hot", "职场风云", theme="职场", hot_degree=1000),
        drama("other", "城市故事", theme="都市", hot_degree=500),
    ]
    article = {
        "title": "职场风云",
        "digest": "职场观察",
        "body_text": "公司里的选择",
    }
    first = short_drama.pick_short_drama(
        article,
        rows,
        kind="workspace",
        usage_path=usage_path,
        now=NOW,
    )
    short_drama.record_drama_usage(
        first,
        article_title="第一篇",
        usage_path=usage_path,
        used_at=NOW,
    )

    second = short_drama.pick_short_drama(
        article,
        rows,
        kind="workspace",
        usage_path=usage_path,
        now=NOW + timedelta(days=1),
    )

    assert first.drama_id == "hot"
    assert second.drama_id == "other"
    saved = json.loads(usage_path.read_text(encoding="utf-8"))
    assert saved == [
        {
            "drama_id": "hot",
            "drama_name": "职场风云",
            "article_title": "第一篇",
            "used_at": "2026-08-16T12:00:00+08:00",
        }
    ]


def test_pick_short_drama_restores_pool_when_every_candidate_is_recent(
    tmp_path: Path,
) -> None:
    usage_path = tmp_path / "usage.json"
    rows = [
        drama("best", "职场风云", theme="职场", hot_degree=1000),
        drama("second", "城市故事", theme="都市", hot_degree=500),
    ]
    for row in rows:
        short_drama.record_drama_usage(
            row,
            article_title="历史稿",
            usage_path=usage_path,
            used_at=NOW,
        )

    picked = short_drama.pick_short_drama(
        {"title": "职场风云", "digest": "职场", "body_text": "公司"},
        rows,
        kind="workspace",
        usage_path=usage_path,
        now=NOW + timedelta(days=1),
    )

    assert picked.drama_id == "best"
