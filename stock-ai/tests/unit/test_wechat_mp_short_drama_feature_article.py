"""公众号单剧强情节推广稿。"""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.tools import wechat_mp_short_drama as short_drama
from scripts.tools import wechat_mp_content as content_mod
from scripts.tools import wechat_mp_seo as seo_mod
from scripts.tools import wechat_mp_short_drama_feature_article as feature
from scripts.tools.wechat_mp_codex_short_drama import CodexShortDramaDraft
from scripts.tools.wechat_mp_short_drama_research import (
    DramaFact,
    DramaResearch,
    DramaSource,
)


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def drama(drama_id: str, name: str, rate_bp: int) -> short_drama.ShortDrama:
    return short_drama.ShortDrama(
        drama_id=drama_id,
        drama_name=name,
        src_appid="wx-source",
        play_appid="wx-play",
        cover_url="https://example.test/cover.jpg",
        era="现代",
        theme="职场",
        description="李建军进入工厂，用维修技术解决机床难题。",
        status=1,
        plan_id=f"plan-{drama_id}",
        rate_bp=rate_bp,
        hot_degree=rate_bp * 10,
        media_count=60,
        offline_timestamp=int((NOW + timedelta(days=30)).timestamp()),
        preview_path=f"plugin-private://player/pages/playlet?dramaId={drama_id}",
        preview_sn="preview",
        exp_url=f"https://daihuo.qq.com/cps_drama_expo?drama_id={drama_id}",
        click_url="",
        trace_id="trace",
        fetched_at=NOW.isoformat(),
    )


def attribution(item: short_drama.ShortDrama) -> short_drama.ShortDramaAttribution:
    return short_drama.ShortDramaAttribution(
        drama_id=item.drama_id,
        plan_id=item.plan_id,
        src_appid=item.src_appid,
        play_appid=item.play_appid,
        default_path=(
            "plugin-private://player/pages/playlet?"
            f"dramaId={item.drama_id}&wxTicket=ticket-test"
        ),
        wx_ticket="ticket-test",
        captured_at=NOW.isoformat(),
    )


def research(item: short_drama.ShortDrama) -> DramaResearch:
    source_ids = ("platform", "source-1")
    return DramaResearch(
        drama_id=item.drama_id,
        drama_name=item.drama_name,
        sources=(
            DramaSource(
                "platform",
                item.exp_url,
                "平台资料",
                "微信短剧推广平台",
                "platform",
                True,
                item.description,
            ),
            DramaSource(
                "source-1",
                f"https://news.example.test/{item.drama_id}",
                "剧情介绍",
                "测试媒体",
                "report",
                False,
                item.description,
            ),
        ),
        facts=(
            DramaFact("character-1", "character", "主角名叫李建军。", source_ids),
            DramaFact("relationship-1", "relationship", "李建军进入一家工厂工作。", source_ids),
            DramaFact("conflict-1", "conflict", "故障机床成为他的技术考验。", source_ids),
            DramaFact("reversal-1", "reversal", "维修结果改变了旁人对他的判断。", source_ids),
        ),
        rejected_claims=("李建军最终获得国家奖项",),
    )


def valid_copy() -> feature.FeatureCopy:
    fact_ids = ("character-1", "relationship-1", "conflict-1", "reversal-1")
    paragraphs = tuple(
        feature.FeatureParagraph(
            text=(
                "李建军失去原来的工作后进入工厂，摆在他面前的是一台让众人束手无策的机床。"
                "他没有急着证明自己，只是盯着故障一步步排查。"
                "周围人的怀疑没有消失，维修结果却开始改变他们的判断。"
            )
            * 3,
            fact_ids=fact_ids,
        )
        for _ in range(6)
    )
    return feature.FeatureCopy(
        title="下岗技师进厂第一天，就接下没人敢碰的机床",
        digest="一台故障机床，把一个下岗技师逼到了必须证明自己的位置。",
        paragraphs=paragraphs,
        title_fact_ids=("character-1", "conflict-1"),
        digest_fact_ids=("character-1", "conflict-1"),
    )


def codex_draft(item: short_drama.ShortDrama) -> CodexShortDramaDraft:
    copy = valid_copy()
    item_research = research(item)
    return CodexShortDramaDraft(
        drama_id=item.drama_id,
        drama_name=item.drama_name,
        title=copy.title,
        digest=copy.digest,
        title_fact_ids=copy.title_fact_ids,
        digest_fact_ids=copy.digest_fact_ids,
        paragraphs=copy.paragraphs,
        sources=item_research.sources[1:],
        facts=item_research.facts,
        rejected_claims=item_research.rejected_claims,
        slot_key="short_drama_feature",
    )


def test_validate_feature_copy_rejects_unbound_public_paragraph() -> None:
    item = drama("2", "修好铁疙瘩转身踏青云", 7000)
    copy = valid_copy()
    bad = replace(
        copy,
        paragraphs=(*copy.paragraphs[:-1], feature.FeatureParagraph("突然又出现一个妹妹。", ())),
    )

    with pytest.raises(ValueError, match="段落必须绑定剧情事实"):
        feature.validate_feature_copy(bad, research=research(item))


def test_validate_feature_copy_rejects_rejected_plot_claim() -> None:
    item = drama("2", "修好铁疙瘩转身踏青云", 7000)
    copy = valid_copy()
    bad_paragraph = replace(
        copy.paragraphs[-1],
        text=copy.paragraphs[-1].text + "李建军最终获得国家奖项。",
    )

    with pytest.raises(ValueError, match="未采用剧情"):
        feature.validate_feature_copy(
            replace(copy, paragraphs=(*copy.paragraphs[:-1], bad_paragraph)),
            research=research(item),
        )


def test_article_shell_can_skip_automatic_short_drama_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        short_drama,
        "attach_short_drama",
        lambda *_a, **_k: pytest.fail("automatic selection must be skipped"),
    )

    article = content_mod._article_shell(
        title="单剧推荐",
        digest="剧情摘要",
        body_text="第一段。\n\n第二段。",
        upload_figures=False,
        kind="short_drama_feature",
        attach_promotion=False,
    )

    assert article["title"] == "单剧推荐"
    assert "short_drama" not in article


def test_publish_hints_can_rebuild_feature_without_auto_selecting_drama(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        short_drama,
        "attach_short_drama",
        lambda *_a, **_k: pytest.fail("发布提示不得自动选择另一部短剧"),
    )
    article = content_mod._article_shell(
        title="单剧推荐",
        digest="剧情摘要",
        body_text="第一段。\n\n第二段。",
        upload_figures=False,
        kind="short_drama_feature",
        engagement_kind="short_drama_feature",
        attach_promotion=False,
    )

    rebuilt = seo_mod.attach_publish_hints(
        article,
        "short_drama_feature",
        engagement_kind="short_drama_feature",
        attach_promotion=False,
    )

    assert "data-adtype=\"short-play\"" not in rebuilt["content"]


def test_build_feature_article_uses_exact_drama_selected_by_codex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = drama("1", "高佣但资料不足", 8000)
    second = drama("2", "修好铁疙瘩转身踏青云", 7000)
    scores = [
        short_drama.DramaScore(50, 30, 10, 0, 90),
        short_drama.DramaScore(40, 25, 10, 0, 75),
    ]
    monkeypatch.setattr(feature, "load_or_refresh_drama_pool", lambda **_k: [first, second])
    monkeypatch.setattr(feature, "eligible_dramas", lambda rows, **_k: list(rows))
    monkeypatch.setattr(feature, "dedupe_dramas", lambda rows: list(rows))
    def fake_rank(*_args, exclude_previously_used: bool, **_kwargs):
        if exclude_previously_used:
            return []
        return [(first, scores[0]), (second, scores[1])]

    monkeypatch.setattr(feature, "rank_short_drama_candidates", fake_rank)
    monkeypatch.setattr(
        feature,
        "has_recorded_drama_usage",
        lambda *_a, **_k: True,
        raising=False,
    )
    monkeypatch.setattr(feature, "ensure_attribution_for_drama", lambda item, **_k: attribution(item))

    monkeypatch.setattr(
        feature,
        "_article_shell",
        lambda **kwargs: {
            "title": kwargs["title"],
            "digest": kwargs["digest"],
            "body_text": kwargs["body_text"],
            "content": "".join(f'<p id="p{i}">正文{i}</p>' for i in range(6)),
        },
    )
    monkeypatch.setattr(feature, "attach_publish_hints", lambda article, *_a, **_k: article)

    article = feature.build_short_drama_feature_article(
        codex_draft=codex_draft(second),
        upload_figures=False,
        now=NOW,
    )

    assert article["short_drama"]["drama_id"] == "2"
    assert article["short_drama_feature_report"]["fact_gate"] == "passed"
    assert article["short_drama_feature_report"]["claim_audit"] == "codex_fact_bindings_passed"


def test_inject_verified_stills_uses_three_local_official_frames(tmp_path: Path) -> None:
    still_dir = tmp_path / "short-drama-2"
    still_dir.mkdir()
    for index in range(1, 4):
        (still_dir / f"still-{index:02d}.jpg").write_bytes(b"verified-frame")
    body = "\n\n".join(f"第{index}段正文。" for index in range(1, 7))

    enriched = feature.inject_verified_stills(
        body,
        drama_id="2",
        asset_root=tmp_path,
    )

    assert enriched.count("[[fig:tv/short-drama-2/still-") == 3
    assert enriched.count("画面来源：爱奇艺官方正片页") == 3
    assert enriched.index("still-01.jpg") > enriched.index("第1段正文")
    assert enriched.index("still-03.jpg") < enriched.index("第6段正文")


def test_build_rejects_used_drama_without_matching_article_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = drama("2", "修好铁疙瘩转身踏青云", 7000)
    score = short_drama.DramaScore(40, 25, 10, 3, 72)
    monkeypatch.setattr(feature, "load_or_refresh_drama_pool", lambda **_k: [item])
    monkeypatch.setattr(feature, "eligible_dramas", lambda rows, **_k: list(rows))
    monkeypatch.setattr(feature, "dedupe_dramas", lambda rows: list(rows))

    def fake_rank(*_args, exclude_previously_used: bool, **_kwargs):
        return [] if exclude_previously_used else [(item, score)]

    monkeypatch.setattr(feature, "rank_short_drama_candidates", fake_rank)
    monkeypatch.setattr(
        feature,
        "has_recorded_drama_usage",
        lambda *_a, **_k: False,
        raising=False,
    )

    with pytest.raises(ValueError, match="不在当前收益前三"):
        feature.build_short_drama_feature_article(
            codex_draft=codex_draft(item),
            upload_figures=False,
            now=NOW,
        )


def test_build_feature_article_normalizes_omitted_now_before_date_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[datetime | None] = []
    monkeypatch.setattr(feature, "load_or_refresh_drama_pool", lambda **_k: [])

    def fake_eligible(rows, *, now, min_valid_days):
        captured.append(now)
        return list(rows)

    monkeypatch.setattr(feature, "eligible_dramas", fake_eligible)

    with pytest.raises(RuntimeError, match="没有未使用"):
        feature.prepare_short_drama_feature_request()

    assert len(captured) == 1
    assert isinstance(captured[0], datetime)
    assert captured[0].tzinfo is not None


def test_candidate_request_redacts_attribution_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = drama("1", "归因失败短剧", 8000)
    usable = drama("2", "可用候选短剧", 7000)
    score = short_drama.DramaScore(50, 30, 10, 0, 90)
    monkeypatch.setattr(feature, "_ranked_candidates", lambda _now: [(item, score), (usable, score)])

    def fake_attribution(selected, **_kwargs):
        if selected.drama_id == "1":
            raise RuntimeError("cookie=secret token=secret wxTicket=secret")
        return attribution(selected)

    monkeypatch.setattr(feature, "ensure_attribution_for_drama", fake_attribution)

    request = feature.prepare_short_drama_feature_request(now=NOW)

    serialized = str(request).lower()
    assert "secret" not in serialized
    assert "[redacted]" in serialized
    assert request["output_schema"]["slot_key"] == "short_drama_feature"
    assert request["output_schema"]["sources_note"] == "不得提供 source_id=platform"
