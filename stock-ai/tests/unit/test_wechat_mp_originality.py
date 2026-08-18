from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.tools.wechat_mp_originality import (
    evaluate_film_longform,
    evaluate_hotspot_longform,
    evaluate_zhixia_newspic,
)


TZ = ZoneInfo("Asia/Shanghai")


def _specific_copy(length: int = 430) -> str:
    seed = (
        "清晨七点，栀夏把燕麦色瑜伽垫铺到窗边，先删掉完整课程，只保留肩背伸展。"
        "白色水杯放在垫子左侧，深灰毛巾搭在椅背上。她比较两版画面后，删掉像广告的正面摆拍，"
        "保留卷起垫子再出门的动作，因为这张图能说明今天真正做出的取舍。"
    )
    return (seed * ((length // len(seed)) + 1))[:length]


def _source_file(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_zhixia_rejects_disabled_routes_and_short_generic_copy(tmp_path: Path) -> None:
    image = tmp_path / "one.jpg"
    image.write_bytes(b"one")
    sources = {"one.jpg": {"source_type": "original"}}

    film = evaluate_zhixia_newspic(
        title="电影贴图",
        content=_specific_copy(),
        content_lane="popular_film",
        image_paths=[image],
        image_sources=sources,
        history_posts=[],
    )
    short = evaluate_zhixia_newspic(
        title="普通早晨",
        content="今天很松弛。" * 30,
        content_lane="zhixia_daily",
        image_paths=[image],
        image_sources=sources,
        history_posts=[],
    )

    assert "route_disabled" in film.failures
    assert "text_too_short" in short.failures
    assert "specificity_too_low" in short.failures


def test_zhixia_accepts_400_character_specific_original_post(tmp_path: Path) -> None:
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.jpg"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    sources = {
        "first.jpg": {"source_type": "original"},
        "second.jpg": {"source_type": "original"},
    }

    report = evaluate_zhixia_newspic(
        title="我删掉了像广告的第一版",
        content=_specific_copy(400),
        content_lane="system_log",
        image_paths=[first, second],
        image_sources=sources,
        history_posts=[],
    )

    assert report.gate_passed is True
    assert report.text_length == 400
    assert report.original_image_ratio == 1.0
    assert report.specificity_markers >= 3


def test_zhixia_rejects_non_original_duplicate_files_and_urls(tmp_path: Path) -> None:
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.jpg"
    first.write_bytes(b"same")
    second.write_bytes(b"same")
    sources = {
        "first.jpg": {"source_type": "original", "image_url": "https://img/a.jpg"},
        "second.jpg": {"source_type": "report", "image_url": "https://img/a.jpg"},
    }

    report = evaluate_zhixia_newspic(
        title="我删掉了像广告的第一版",
        content=_specific_copy(),
        content_lane="ai_human",
        image_paths=[first, second],
        image_sources=sources,
        history_posts=[],
    )

    assert "non_original_images" in report.failures
    assert "duplicate_images" in report.failures
    assert report.duplicate_image_count == 2


def test_history_blocks_similar_title_and_same_film() -> None:
    now = datetime.now(TZ)
    history = [
        {
            "title": "早上只做十分钟，我没有把一天排满",
            "published_at": (now - timedelta(days=2)).isoformat(),
            "status": "published",
            "film_titles": ["年会不能停2！"],
        }
    ]

    report = evaluate_zhixia_newspic(
        title="早上只做十分钟：没有把一天排满",
        content=_specific_copy(),
        content_lane="zhixia_daily",
        image_paths=[],
        image_sources={},
        history_posts=history,
        now=now,
    )
    film = evaluate_film_longform(
        title="《年会不能停2！》里的升职",
        body="剧情专属内容" * 500,
        film_titles=["年会不能停2！"],
        plot_anchors=[
            {"scene": "会议室", "character": "Kathy", "action": "提交方案", "counterpart_or_pressure": "绩效考核", "consequence": "进入复核", "source_url": "https://example.com/1", "stage": "起点"},
            {"scene": "年会", "character": "Kathy", "action": "公开回应", "counterpart_or_pressure": "岗位竞争", "consequence": "关系改变", "source_url": "https://example.com/2", "stage": "转折"},
        ],
        history_posts=history,
        now=now,
    )

    assert "similar_recent_title" in report.failures
    assert "same_film_recently_published" in film.failures


def test_hotspot_requires_long_body_three_sources_and_original_thesis() -> None:
    weak = evaluate_hotspot_longform(
        title="消费为什么不增长？",
        body="消费很重要。" * 100,
        research_urls=["https://example.com/1"],
        thesis="",
        history_posts=[],
    )
    strong = evaluate_hotspot_longform(
        title="消费增长，为什么不能只催人花钱？",
        body=("2026年规划提出具体目标，家庭仍要在收入、教育、医疗与养老之间做选择。" * 60),
        research_urls=[
            "https://example.com/1",
            "https://example.org/2",
            "https://example.net/3",
        ],
        thesis="消费意愿不是宣传出来的，稳定预期本身就是消费政策。",
        history_posts=[],
    )

    assert {"text_too_short", "sources_too_few", "missing_original_thesis"} <= set(weak.failures)
    assert strong.gate_passed is True


def test_film_longform_requires_two_complete_anchors() -> None:
    report = evaluate_film_longform(
        title="《某电影》为什么动人",
        body="人物和剧情。" * 400,
        film_titles=["某电影"],
        plot_anchors=[{"scene": "车站"}],
        history_posts=[],
    )

    assert "plot_anchors_incomplete" in report.failures
