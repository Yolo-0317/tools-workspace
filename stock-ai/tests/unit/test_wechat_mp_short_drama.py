"""公众号短剧池、选剧、归因与组件门禁。"""

from __future__ import annotations

import sys
import json
import os
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
SAMPLE_SHORT_PLAY = '''<mp-common-cpsad data-pluginname="mpcps" data-adtype="short-play"
 data-videocarddata="{&quot;dramaName&quot;:&quot;测试短剧&quot;,&quot;categoryName&quot;:&quot;现代/职场&quot;,&quot;videoCoverUrl&quot;:&quot;https://example.test/c.jpg&quot;,&quot;dramaNum&quot;:60}"
 data-dramaid="123" data-srcappid="wx-source" data-playappid="wx-play"
 data-planid="plan-123" data-traceid="trace-old"
 data-defaultpath="plugin-private%3A%2F%2Fplayer%2Fpages%2Fplaylet%3FdramaId%3D123%26wxTicket%3Dticket-test"></mp-common-cpsad>'''


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
        self.last_data: dict = {}
        self.last_headers: dict = {}
        self.last_timeout = 0

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.last_url = url
        self.last_json = dict(kwargs.get("json") or {})
        self.last_data = dict(kwargs.get("data") or {})
        self.last_headers = dict(kwargs.get("headers") or {})
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


def attribution(
    drama_id: str = "123",
    **overrides: object,
) -> short_drama.ShortDramaAttribution:
    item = short_drama.ShortDramaAttribution(
        drama_id=drama_id,
        plan_id=f"plan-{drama_id}",
        src_appid="wx-source",
        play_appid="wx-play",
        default_path=f"plugin-private://player/pages/playlet?dramaId={drama_id}&wxTicket=ticket-test",
        wx_ticket="ticket-test",
        captured_at=NOW.isoformat(timespec="seconds"),
    )
    return replace(item, **overrides)


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


def test_load_drama_web_session_requires_private_file(tmp_path: Path) -> None:
    path = tmp_path / "web-session.json"
    path.write_text(
        json.dumps(
            {
                "cookie": "cookie-fixture",
                "token": "token-fixture",
                "fingerprint": "fingerprint-fixture",
            }
        ),
        encoding="utf-8",
    )
    os.chmod(path, 0o600)

    loaded = short_drama.load_drama_web_session(path)

    assert loaded.cookie == "cookie-fixture"
    assert loaded.token == "token-fixture"
    assert loaded.fingerprint == "fingerprint-fixture"
    assert loaded.lang == "zh_CN"

    os.chmod(path, 0o644)
    with pytest.raises(RuntimeError, match="权限"):
        short_drama.load_drama_web_session(path)


def test_parse_minidrama_link_response_extracts_validated_attribution() -> None:
    row = drama("123", plan_id="plan-123")
    payload = {
        "base_resp": {"err_msg": "ok", "ret": 0},
        "data": json.dumps(
            {
                "errcode": 0,
                "errmsg": "ok",
                "path": (
                    "plugin-private://player/pages/playlet/playlet"
                    "?dramaId=123&srcAppid=wx-source&wxTicket=ticket-fixture"
                ),
            }
        ),
    }

    parsed = short_drama.parse_minidrama_link_response(payload, row, now=NOW)

    assert parsed.drama_id == "123"
    assert parsed.plan_id == "plan-123"
    assert parsed.src_appid == "wx-source"
    assert parsed.play_appid == "wx-play"
    assert parsed.wx_ticket == "ticket-fixture"
    assert parsed.captured_at == "2026-08-16T12:00:00+08:00"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"base_resp": {"ret": 200003}}, "outer_ret=200003"),
        (
            {
                "base_resp": {"ret": 0},
                "data": json.dumps({"errcode": 41001, "errmsg": "expired"}),
            },
            "inner_errcode=41001",
        ),
        (
            {
                "base_resp": {"ret": 0},
                "data": json.dumps(
                    {
                        "errcode": 0,
                        "path": (
                            "plugin-private://player/pages/playlet/playlet"
                            "?dramaId=999&srcAppid=wx-source"
                            "&wxTicket=ticket-fixture"
                        ),
                    }
                ),
            },
            "短剧身份不匹配",
        ),
        (
            {
                "base_resp": {"ret": 0},
                "data": json.dumps(
                    {
                        "errcode": 0,
                        "path": (
                            "plugin-private://player/pages/playlet/playlet"
                            "?dramaId=123&srcAppid=wx-source"
                        ),
                    }
                ),
            },
            "缺少归因票据",
        ),
    ],
)
def test_parse_minidrama_link_response_fails_closed_without_secrets(
    payload: dict,
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message) as caught:
        short_drama.parse_minidrama_link_response(payload, drama("123"), now=NOW)

    error = str(caught.value)
    assert "ticket-fixture" not in error
    assert "plugin-private" not in error


def test_fetch_short_drama_attribution_posts_exact_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WECHAT_MP_DRAMA_KOL_ID", "kol-fixture")
    row = drama("123", plan_id="plan-123")
    web_session = short_drama.WeChatDramaWebSession(
        cookie="cookie-fixture",
        token="token-fixture",
        fingerprint="fingerprint-fixture",
    )
    http = FakeSession(
        {
            "base_resp": {"ret": 0, "err_msg": "ok"},
            "data": json.dumps(
                {
                    "errcode": 0,
                    "errmsg": "ok",
                    "path": (
                        "plugin-private://player/pages/playlet/playlet"
                        "?dramaId=123&srcAppid=wx-source"
                        "&wxTicket=ticket-fixture"
                    ),
                }
            ),
        }
    )

    parsed = short_drama.fetch_short_drama_attribution(
        row,
        web_session=web_session,
        session=http,
        now=NOW,
        random_value=0.125,
    )

    assert parsed.drama_id == "123"
    assert http.last_url == short_drama.MINIDRAMA_LINK_URL
    assert http.last_timeout == 30
    assert http.last_data["token"] == "token-fixture"
    assert http.last_data["lang"] == "zh_CN"
    assert http.last_data["f"] == "json"
    assert http.last_data["ajax"] == "1"
    assert http.last_data["fingerprint"] == "fingerprint-fixture"
    assert http.last_data["random"] == "0.125"
    assert json.loads(http.last_data["cps_detail"]) == {
        "request_id": "1786852800000",
        "biz_type": 0,
        "appid": "wx-play",
        "plan_id": "plan-123",
        "promoter_id": "kol-fixture",
        "ext_info": "",
    }
    assert http.last_headers["Cookie"] == "cookie-fixture"
    assert http.last_headers["X-Requested-With"] == "XMLHttpRequest"
    assert "token-fixture" in http.last_headers["Referer"]
    assert not any(key.lower().startswith("sec-ch-") for key in http.last_headers)


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


def test_refresh_drama_pool_stops_at_explicit_item_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def fake_fetch(*, page_no: int, page_size: int, **_: object):
        calls.append(page_no)
        start = (page_no - 1) * page_size
        return ([drama(str(start + 1)), drama(str(start + 2))], 100)

    monkeypatch.setattr(short_drama, "fetch_drama_page", fake_fetch)

    rows = short_drama.refresh_drama_pool(
        cache_path=tmp_path / "pool.json",
        page_size=2,
        max_items=3,
        now=NOW,
    )

    assert calls == [1, 2]
    assert [row.drama_id for row in rows] == ["1", "2", "3"]


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


def test_score_drama_uses_revenue_weights_and_log_heat() -> None:
    rows = [
        drama(
            "high-rate",
            "城市故事",
            theme="都市",
            rate_bp=7000,
            hot_degree=100,
        ),
        drama(
            "high-heat",
            "城市故事",
            theme="都市",
            rate_bp=6000,
            hot_degree=10_000,
        ),
    ]

    high_rate = short_drama.score_drama(rows[0], population=rows)
    high_heat = short_drama.score_drama(rows[1], population=rows)

    assert high_rate.commission_score == 45.0
    assert high_rate.heat_score == 0.0
    assert high_rate.appeal_score == 2.0
    assert high_rate.final_score == 47.0
    assert high_heat.commission_score == 0.0
    assert high_heat.heat_score == 35.0
    assert high_heat.final_score == 37.0


def test_score_drama_gives_equal_population_metrics_full_credit() -> None:
    rows = [
        drama("one", "城市故事", theme="都市", rate_bp=6000, hot_degree=100),
        drama("two", "家庭故事", theme="家庭", rate_bp=6000, hot_degree=100),
    ]

    score = short_drama.score_drama(rows[0], population=rows)

    assert score.commission_score == 45.0
    assert score.heat_score == 35.0


def test_score_short_drama_feature_uses_approved_revenue_weights() -> None:
    rows = [
        drama("commission", "城市故事", theme="都市", rate_bp=7000, hot_degree=100),
        drama("heat", "城市故事", theme="都市", rate_bp=6000, hot_degree=10_000),
    ]

    commission = short_drama.score_short_drama_feature(rows[0], population=rows)
    heat = short_drama.score_short_drama_feature(rows[1], population=rows)

    assert commission.commission_score == 50.0
    assert commission.heat_score == 0.0
    assert commission.appeal_score == 2.0
    assert commission.final_score == 52.0
    assert heat.commission_score == 0.0
    assert heat.heat_score == 30.0
    assert heat.final_score == 32.0


def test_rank_short_drama_candidates_excludes_previously_used_drama(
    tmp_path: Path,
) -> None:
    usage_path = tmp_path / "usage.json"
    usage_path.write_text(
        json.dumps(
            [
                {
                    "drama_id": "top",
                    "drama_name": "高佣逆袭",
                    "article_title": "历史推广稿",
                    "used_at": NOW.isoformat(),
                }
            ]
        ),
        encoding="utf-8",
    )
    rows = [
        drama("top", "高佣逆袭", rate_bp=8000, hot_degree=9000),
        drama("second", "豪门反击", rate_bp=7000, hot_degree=8000),
        drama("third", "职场翻身", rate_bp=6000, hot_degree=7000),
        drama("fourth", "普通爱情", rate_bp=1000, hot_degree=1000),
    ]

    ranked = short_drama.rank_short_drama_candidates(
        rows,
        usage_path=usage_path,
        now=NOW,
        limit=3,
        exclude_previously_used=True,
    )

    assert [row.drama_id for row, _score in ranked] == ["second", "third", "fourth"]


def test_drama_appeal_points_caps_strong_and_medium_hooks_at_twenty() -> None:
    row = drama(
        "hook",
        "豪门千金重生后反击",
        theme="都市、爱情、家庭",
    )

    assert short_drama.drama_appeal_points(row) == 20


def test_pick_short_drama_allows_weak_relevance_for_higher_revenue(
    tmp_path: Path,
) -> None:
    rows = [
        drama(
            "commercial",
            "千金反击",
            theme="都市、家庭",
            description="豪门千金身份反转",
            rate_bp=7000,
            hot_degree=10_000,
        ),
        drama(
            "relevant",
            "报销制度",
            theme="职场",
            description="公司报销观察",
            rate_bp=5000,
            hot_degree=100,
        ),
    ]
    article = {
        "title": "公司报销为什么越来越严格",
        "digest": "职场制度观察",
        "body_text": "员工提交报销单之后，财务开始逐项核查。",
    }

    picked, score = short_drama.pick_short_drama(
        article,
        rows,
        kind="workspace",
        usage_path=tmp_path / "usage.json",
        now=NOW,
    )

    assert picked.drama_id == "commercial"
    assert score.commission_score == 45.0


def test_pick_short_drama_avoids_recently_recorded_drama(tmp_path: Path) -> None:
    usage_path = tmp_path / "usage.json"
    rows = [
        drama("hot", "职场风云", theme="职场", hot_degree=1000),
        drama("other", "城市故事", theme="都市", hot_degree=1000),
    ]
    article = {
        "title": "职场风云",
        "digest": "职场观察",
        "body_text": "公司里的选择",
    }
    first, _ = short_drama.pick_short_drama(
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

    second, second_score = short_drama.pick_short_drama(
        article,
        rows,
        kind="workspace",
        usage_path=usage_path,
        now=NOW + timedelta(days=1),
    )

    assert first.drama_id == "hot"
    assert second.drama_id == "other"
    assert second_score.usage_penalty == 0.0
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

    picked, score = short_drama.pick_short_drama(
        {"title": "职场风云", "digest": "职场", "body_text": "公司"},
        rows,
        kind="workspace",
        usage_path=usage_path,
        now=NOW + timedelta(days=1),
    )

    assert picked.drama_id == "best"
    assert score.usage_penalty == 3.0


def test_pick_short_drama_blocks_escapist_drama_for_casualty_news(
    tmp_path: Path,
) -> None:
    rows = [
        drama(
            "romance",
            "豪门甜宠",
            theme="爱情",
            rate_bp=7000,
            hot_degree=10_000,
        ),
        drama(
            "workplace",
            "职场故事",
            theme="职场",
            rate_bp=5000,
            hot_degree=100,
        ),
    ]

    picked, _ = short_drama.pick_short_drama(
        {"title": "某地火灾造成伤亡", "digest": "官方通报救援进展"},
        rows,
        kind="hotspot",
        usage_path=tmp_path / "usage.json",
        now=NOW,
    )

    assert picked.drama_id == "workplace"


def test_rotation_never_promotes_candidate_outside_commercial_top_three(
    tmp_path: Path,
) -> None:
    usage_path = tmp_path / "usage.json"
    rows = [
        drama("top1", "豪门千金重生", theme="都市、爱情、家庭"),
        drama("top2", "豪门千金重生", theme="都市"),
        drama("top3", "豪门千金", theme="都市、爱情、家庭"),
        drama("fourth", "豪门千金", theme="都市、爱情"),
    ]
    for row in rows[:3]:
        for offset in range(3):
            short_drama.record_drama_usage(
                row,
                article_title=f"历史稿-{offset}",
                usage_path=usage_path,
                used_at=NOW - timedelta(days=offset),
            )

    picked, score = short_drama.pick_short_drama(
        {"title": "普通热点观察"},
        rows,
        kind="hotspot",
        usage_path=usage_path,
        now=NOW,
    )

    assert picked.drama_id == "top1"
    assert score.usage_penalty == 9.0


def test_recorded_usage_matches_drama_and_article_title(tmp_path: Path) -> None:
    usage_path = tmp_path / "usage.json"
    short_drama.record_drama_usage(
        drama("used"),
        article_title="已经写入的单剧稿",
        usage_path=usage_path,
        used_at=NOW,
    )

    assert short_drama.has_recorded_drama_usage(
        "used",
        article_title="已经写入的单剧稿",
        usage_path=usage_path,
    ) is True
    assert short_drama.has_recorded_drama_usage(
        "used",
        article_title="另一篇稿",
        usage_path=usage_path,
    ) is False


def test_parse_short_drama_component_extracts_attribution() -> None:
    parsed = short_drama.parse_short_drama_component(SAMPLE_SHORT_PLAY, now=NOW)

    assert parsed.drama_id == "123"
    assert parsed.plan_id == "plan-123"
    assert parsed.src_appid == "wx-source"
    assert parsed.play_appid == "wx-play"
    assert parsed.wx_ticket == "ticket-test"
    assert parsed.captured_at == "2026-08-16T12:00:00+08:00"


def test_parse_short_drama_components_ignores_plain_product_card() -> None:
    html = '<mp-common-cpsad data-pid="101_1"></mp-common-cpsad>' + SAMPLE_SHORT_PLAY

    parsed = short_drama.parse_short_drama_components(html, now=NOW)

    assert [item.drama_id for item in parsed] == ["123"]


def test_load_attribution_for_drama_requires_exact_plan_and_apps(
    tmp_path: Path,
) -> None:
    path = tmp_path / "attribution.json"
    path.write_text(
        json.dumps(
            {
                "123": {
                    "drama_id": "123",
                    "plan_id": "plan-123",
                    "src_appid": "wx-source",
                    "play_appid": "wx-play",
                    "default_path": "plugin-private://player/pages/playlet?dramaId=123&wxTicket=ticket-test",
                    "wx_ticket": "ticket-test",
                    "captured_at": "2026-08-16T12:00:00+08:00",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    matching = drama("123", plan_id="plan-123")
    mismatched = drama("123", plan_id="another-plan")

    assert short_drama.has_attribution_for_drama(matching, path=path) is True
    assert short_drama.load_attribution_for_drama(matching, path=path).wx_ticket == "ticket-test"
    assert short_drama.has_attribution_for_drama(mismatched, path=path) is False
    with pytest.raises(RuntimeError, match="短剧归因与候选不匹配"):
        short_drama.load_attribution_for_drama(mismatched, path=path)


def test_ensure_attribution_reuses_valid_cache_without_fetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "attribution.json"
    row = drama("123", plan_id="plan-123")
    short_drama._save_attributions([attribution()], path=path)
    monkeypatch.setattr(
        short_drama,
        "fetch_short_drama_attribution",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("fetch")),
    )

    result = short_drama.ensure_attribution_for_drama(row, path=path, now=NOW)

    assert result.wx_ticket == "ticket-test"


def test_ensure_attribution_fetches_and_saves_missing_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "attribution.json"
    row = drama("456", plan_id="plan-456")
    fetched = attribution("456", wx_ticket="ticket-fetched")
    monkeypatch.setattr(
        short_drama,
        "fetch_short_drama_attribution",
        lambda selected, **_: fetched if selected.drama_id == "456" else None,
    )

    result = short_drama.ensure_attribution_for_drama(row, path=path, now=NOW)

    assert result.wx_ticket == "ticket-fetched"
    assert short_drama.load_attribution_for_drama(row, path=path) == fetched


def test_ensure_attribution_failure_does_not_change_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "attribution.json"
    short_drama._save_attributions([attribution("123")], path=path)
    before = path.read_bytes()
    monkeypatch.setattr(
        short_drama,
        "fetch_short_drama_attribution",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("expired")),
    )

    with pytest.raises(RuntimeError, match="expired"):
        short_drama.ensure_attribution_for_drama(
            drama("456", plan_id="plan-456"),
            path=path,
            now=NOW,
        )

    assert path.read_bytes() == before


def test_build_short_drama_html_round_trips_validated_identity() -> None:
    row = drama(
        "123",
        "报销风波",
        plan_id="plan-123",
        era="现代",
        theme="都市、职场",
        media_count=60,
    )

    component = short_drama.build_short_drama_html(
        row,
        attribution(),
        trace_id="trace-new",
    )

    assert component.count("<mp-common-cpsad") == 1
    assert 'contenteditable="false"' in component
    assert (
        'class="js_uneditable custom_select_card new_cps_iframe mp_common_widget"'
        in component
    )
    assert 'data-adtype="short-play"' in component
    assert 'data-templateid="card"' in component
    assert 'data-cpsversion="v122"' in component
    assert 'data-goodssouce="1"' in component
    assert 'data-showchangebtn="1"' in component
    assert 'data-traceid="trace-new"' in component
    assert "data-videocarddata" not in component
    parsed = short_drama.validate_short_drama_component(component, row)
    assert parsed.drama_id == "123"
    assert parsed.wx_ticket == "ticket-test"


def test_build_short_drama_html_rejects_another_drama_ticket() -> None:
    with pytest.raises(RuntimeError, match="短剧归因与候选不匹配"):
        short_drama.build_short_drama_html(
            drama("123", plan_id="plan-123"),
            attribution("999"),
        )


def test_capture_sample_attributions_requires_one_exact_title(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_batchget(*, offset: int, count: int, no_content: bool):
        assert offset == 0
        assert count == 20
        assert no_content is False
        return (
            [
                {
                    "media_id": "sample-media",
                    "content": {
                        "news_item": [
                            {"title": "短剧组件测试-勿发", "content": SAMPLE_SHORT_PLAY}
                        ]
                    },
                }
            ],
            None,
        )

    monkeypatch.setattr(short_drama, "draft_batchget", fake_batchget)
    path = tmp_path / "attribution.json"

    captured = short_drama.capture_sample_attributions(
        "短剧组件测试-勿发",
        path=path,
        now=NOW,
    )

    assert [item.drama_id for item in captured] == ["123"]
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["123"]["plan_id"] == "plan-123"
    assert saved["123"]["wx_ticket"] == "ticket-test"


def test_capture_sample_file_writes_attribution_cache(tmp_path: Path) -> None:
    sample_path = tmp_path / "sample.html"
    sample_path.write_text(SAMPLE_SHORT_PLAY, encoding="utf-8")
    attribution_path = tmp_path / "attribution.json"

    captured = short_drama.capture_sample_file(
        sample_path,
        attribution_path=attribution_path,
        now=NOW,
    )

    assert [item.drama_id for item in captured] == ["123"]
    saved = json.loads(attribution_path.read_text(encoding="utf-8"))
    assert saved["123"]["plan_id"] == "plan-123"
    assert saved["123"]["wx_ticket"] == "ticket-test"


def test_capture_sample_file_cli_never_prints_ticket(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        short_drama,
        "capture_sample_file",
        lambda _: [attribution()],
    )

    exit_code = short_drama.main(["--capture-sample-file", "data/sample.html"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "drama_id=123" in output
    assert "含票据=是" in output
    assert "ticket-test" not in output


def test_probe_short_drama_component_creates_non_publishable_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = drama("123", "报销风波", plan_id="plan-123")
    monkeypatch.setattr(
        short_drama,
        "load_or_refresh_drama_pool",
        lambda **_: [row],
    )
    monkeypatch.setattr(
        short_drama,
        "load_attribution_for_drama",
        lambda _: attribution(),
    )
    uploaded: list[dict] = []

    def fake_draft_add(*, articles: list[dict]):
        uploaded.extend(articles)
        return "probe-media", None

    monkeypatch.setattr(short_drama, "draft_add", fake_draft_add, raising=False)

    media_id = short_drama.probe_short_drama_component("123", now=NOW)

    assert media_id == "probe-media"
    assert uploaded[0]["title"] == "短剧组件探针-勿发-08161200"
    assert uploaded[0]["content"].count('data-adtype="short-play"') == 1
    assert uploaded[0]["need_open_comment"] == 0


def test_capture_cli_never_prints_ticket(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        short_drama,
        "capture_sample_attributions",
        lambda _: [attribution()],
    )

    exit_code = short_drama.main(
        ["--capture-sample-title", "短剧组件测试-勿发"]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "drama_id=123" in output
    assert "plan_id=plan-123" in output
    assert "含票据=是" in output
    assert "ticket-test" not in output


def test_fetch_attribution_cli_never_prints_ticket_or_path(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    row = drama("123", plan_id="plan-123")
    monkeypatch.setattr(short_drama, "load_or_refresh_drama_pool", lambda **_: [row])
    monkeypatch.setattr(
        short_drama,
        "ensure_attribution_for_drama",
        lambda *_args, **_kwargs: attribution(),
    )

    exit_code = short_drama.main(
        ["--fetch-attribution", "--drama-id", "123"]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "drama_id=123" in output
    assert "plan_id=plan-123" in output
    assert "含票据=是" in output
    assert "ticket-test" not in output
    assert "plugin-private" not in output


def test_fetch_attribution_cli_reports_safe_session_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    row = drama("123")
    monkeypatch.setattr(short_drama, "load_or_refresh_drama_pool", lambda **_: [row])
    monkeypatch.setattr(
        short_drama,
        "ensure_attribution_for_drama",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("缺少 WECHAT_MP_DRAMA_WEB_SESSION_FILE")
        ),
    )

    exit_code = short_drama.main(
        ["--fetch-attribution", "--drama-id", "123"]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "缺少 WECHAT_MP_DRAMA_WEB_SESSION_FILE" in captured.err
    assert "Traceback" not in captured.err


def test_refresh_cli_prints_filtered_pool_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rows = [
        drama(
            "1",
            "职场风云",
            offline_timestamp=int((NOW + timedelta(days=30)).timestamp()),
        ),
        drama(
            "2",
            "城市故事",
            offline_timestamp=int((NOW + timedelta(days=30)).timestamp()),
        ),
    ]
    monkeypatch.setattr(short_drama, "refresh_drama_pool", lambda **_: rows)

    exit_code = short_drama.main(["--refresh", "--limit", "1"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "total=2 eligible=2 deduped=2" in output
    assert output.count("drama_id=") == 1


@pytest.mark.parametrize(
    "kind",
    ["hotspot", "hot_business", "silver", "tv_review", "market", "workspace"],
)
def test_ordinary_longform_never_auto_attaches_short_drama(
    kind: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    article = {
        "title": "普通长文",
        "body_text": "正文",
        "content": "<p>正文</p>",
    }
    monkeypatch.setenv("WECHAT_MP_SHORT_DRAMA", "1")
    monkeypatch.setattr(
        short_drama,
        "load_or_refresh_drama_pool",
        lambda **_: pytest.fail("普通长文不得读取短剧返佣池"),
    )

    out = short_drama.attach_short_drama(article, kind=kind, now=NOW)

    assert out == article
    assert "short_drama" not in out
    short_drama.assert_longform_promotion_safe(out, kind=kind)


def test_attach_selected_short_drama_uses_exact_researched_drama() -> None:
    chosen = drama(
        "researched",
        "已核验短剧",
        plan_id="plan-researched",
        offline_timestamp=int((NOW + timedelta(days=30)).timestamp()),
    )
    body = "".join(f'<p id="p{i}">段{i}</p>' for i in range(6))
    score = short_drama.DramaScore(50.0, 30.0, 10.0, 0.0, 90.0)

    out = short_drama.attach_selected_short_drama(
        {"title": "单剧推荐", "digest": "剧情钩子", "content": body},
        kind="short_drama_feature",
        drama=chosen,
        score=score,
        attribution=attribution("researched"),
    )

    components = short_drama.parse_short_drama_components(out["content"], now=NOW)
    assert [component.drama_id for component in components] == ["researched"]
    assert out["short_drama"]["drama_id"] == "researched"


def test_longform_preflight_blocks_plain_product_card() -> None:
    article = {"content": '<mp-common-cpsad data-pid="101_1"></mp-common-cpsad>'}
    with pytest.raises(RuntimeError, match="普通返佣商品"):
        short_drama.assert_longform_promotion_safe(article, kind="market")


def test_short_drama_feature_preflight_requires_short_play_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WECHAT_MP_SHORT_DRAMA", "1")
    with pytest.raises(RuntimeError, match="缺少短剧组件"):
        short_drama.assert_longform_promotion_safe(
            {"content": "<p>正文</p>"},
            kind="short_drama_feature",
        )


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ('<mp-common-cpsad data-pid="101_1"></mp-common-cpsad>', "普通返佣商品"),
        (SAMPLE_SHORT_PLAY + SAMPLE_SHORT_PLAY, "短剧组件数量异常"),
    ],
)
def test_hot_business_soft_policy_keeps_component_safety_gates(
    monkeypatch: pytest.MonkeyPatch,
    content: str,
    message: str,
) -> None:
    monkeypatch.setenv("WECHAT_MP_SHORT_DRAMA", "1")

    with pytest.raises(RuntimeError, match=message):
        short_drama.assert_longform_promotion_safe(
            {"content": content},
            kind="hot_business",
        )


def test_verify_saved_short_drama_rejects_stripped_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WECHAT_MP_SHORT_DRAMA", "1")
    monkeypatch.setattr(
        short_drama,
        "fetch_draft_news_item",
        lambda **_: ({"content": "<p>正文</p>"}, None),
        raising=False,
    )

    with pytest.raises(RuntimeError, match="回读未发现"):
        short_drama.verify_saved_short_drama(
            media_id="m1",
            expected_drama_id="123",
            kind="market",
        )


def test_promotion_summary_reports_score_without_attribution_secrets() -> None:
    article = {
        "short_drama": {
            "drama_id": "123",
            "drama_name": "报销风波",
            "era": "现代",
            "theme": "都市、职场",
            "media_count": 60,
            "rate_bp": 6000,
            "hot_degree": 10_000,
            "plan_id": "plan-123",
            "score": {
                "commission": 45.0,
                "heat": 35.0,
                "appeal": 20.0,
                "penalty": 3.0,
                "final": 97.0,
            },
            "excluded_reasons": ["豪门甜宠: 严肃事件不匹配娱乐钩子"],
        }
    }

    summary = short_drama.promotion_summary(article)

    assert "短剧推广: 报销风波" in summary
    assert "分佣60.00%" in summary
    assert "热度10000" in summary
    assert "返佣分45.0" in summary
    assert "热度分35.0" in summary
    assert "吸引力分20.0" in summary
    assert "轮换-3.0" in summary
    assert "最终分97.0" in summary
    assert "门禁排除豪门甜宠: 严肃事件不匹配娱乐钩子" in summary
    assert "123" not in summary
    assert "plan-123" not in summary
    assert "wxTicket" not in summary
