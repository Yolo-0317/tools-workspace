from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.tools.wechat_mp_virtual_editorial import content_mix_counts
from scripts.tools.wechat_mp_virtual_ledger import (
    match_pending_publication,
    record_pending_draft,
    record_verified_publication,
)


TZ = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 8, 10, 17, 45, tzinfo=TZ)


def _valid_card() -> dict[str, object]:
    return {
        "topic": "一个热点",
        "content_type": "A",
        "content_lane": "nonfilm_hotspot",
        "score_total": 82,
        "observed_at": "2026-08-10T17:30:00+08:00",
    }


def _pending(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "media_id": "draft-1",
        "title": "这是一个标题",
        "content_type": "A",
        "content_lane": "nonfilm_hotspot",
        "topic": "一个热点",
        "topic_card_sha256": "abc123",
        "drafted_at": NOW.isoformat(),
        "mix_override_reason": "",
    }
    payload.update(overrides)
    return payload


def _published(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "article_id": "article-1",
        "update_time": int(NOW.timestamp()) + 60,
        "content": {"news_item": [{"title": "这是一个标题"}]},
    }
    payload.update(overrides)
    return payload


def test_record_pending_draft_does_not_create_publication_history(tmp_path: Path) -> None:
    pending_path = tmp_path / "pending.json"
    history_path = tmp_path / "history.json"

    pending = record_pending_draft(
        media_id="draft-1",
        title="这是一个标题",
        topic_card=_valid_card(),
        topic_card_sha256="abc123",
        drafted_at=NOW,
        pending_path=pending_path,
    )

    assert pending["media_id"] == "draft-1"
    assert pending["content_type"] == "A"
    assert pending["content_lane"] == "nonfilm_hotspot"
    assert pending["drafted_at"] == "2026-08-10T17:45:00+08:00"
    assert pending_path.is_file()
    assert not history_path.exists()


def test_verified_publication_assigns_first_number(tmp_path: Path) -> None:
    ledger = record_verified_publication(
        pending=_pending(),
        publication=_published(),
        ledger_path=tmp_path / "history.json",
    )

    assert ledger["sequence"] == 1
    assert ledger["round"] == 1
    assert ledger["posts"][0]["post_no"] == "ZX-001"
    assert ledger["posts"][0]["status"] == "published"
    assert ledger["posts"][0]["content_lane"] == "nonfilm_hotspot"


def test_film_metadata_survives_pending_and_publication_ledger(tmp_path: Path) -> None:
    pending_path = tmp_path / "pending.json"
    card = _valid_card() | {
        "content_lane": "popular_film",
        "film_titles": ["一部电影"],
        "spoiler_level": "S0",
    }
    pending = record_pending_draft(
        media_id="draft-1",
        title="这是一个标题",
        topic_card=card,
        topic_card_sha256="abc123",
        drafted_at=NOW,
        pending_path=pending_path,
    )

    ledger = record_verified_publication(
        pending=pending,
        publication=_published(),
        ledger_path=tmp_path / "history.json",
    )

    assert pending["film_titles"] == ["一部电影"]
    assert pending["spoiler_level"] == "S0"
    assert ledger["posts"][0]["film_titles"] == ["一部电影"]
    assert ledger["posts"][0]["spoiler_level"] == "S0"


def test_pending_record_preserves_platform_publish_disclosure_mode(
    tmp_path: Path,
) -> None:
    pending = record_pending_draft(
        media_id="draft-1",
        title="这是一个标题",
        topic_card=_valid_card() | {"ai_disclosure_mode": "platform_publish"},
        topic_card_sha256="abc123",
        drafted_at=NOW,
        pending_path=tmp_path / "pending.json",
    )

    assert pending["ai_disclosure_mode"] == "platform_publish"


def test_same_article_id_is_idempotent(tmp_path: Path) -> None:
    ledger_path = tmp_path / "history.json"

    first = record_verified_publication(
        pending=_pending(), publication=_published(), ledger_path=ledger_path
    )
    second = record_verified_publication(
        pending=_pending(), publication=_published(), ledger_path=ledger_path
    )

    assert second == first


def test_pending_publication_match_requires_same_title_and_newer_time() -> None:
    title_mismatch = _published(
        article_id="wrong-title",
        content={"news_item": [{"title": "另一个标题"}]},
    )
    older = _published(
        article_id="older",
        update_time=int(NOW.timestamp()) - 1,
    )
    matching = _published(article_id="matching")

    assert match_pending_publication(_pending(), [title_mismatch, older]) is None
    assert match_pending_publication(_pending(), [title_mismatch, matching]) == matching


def test_invalid_post_keeps_number_but_is_excluded_from_mix(tmp_path: Path) -> None:
    ledger = record_verified_publication(
        pending=_pending(status="invalid"),
        publication=_published(),
        ledger_path=tmp_path / "history.json",
    )

    assert ledger["posts"][0]["post_no"] == "ZX-001"
    assert ledger["posts"][0]["status"] == "invalid"
    assert content_mix_counts(ledger["posts"]) == {"A": 0, "B": 0, "A+C": 0, "C": 0}


def test_round_allows_only_one_experiment_variable(tmp_path: Path) -> None:
    ledger_path = tmp_path / "history.json"
    record_verified_publication(
        pending=_pending(experiment_variable="标题句式"),
        publication=_published(),
        ledger_path=ledger_path,
    )

    try:
        record_verified_publication(
            pending=_pending(title="第二条", experiment_variable="图片顺序"),
            publication=_published(
                article_id="article-2",
                content={"news_item": [{"title": "第二条"}]},
            ),
            ledger_path=ledger_path,
        )
    except ValueError as exc:
        assert "每轮只能调整一个变量" in str(exc)
    else:
        raise AssertionError("同一轮第二个实验变量应被拒绝")


def test_sync_cli_records_only_matched_publication(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    import json

    from scripts.tools import wechat_mp_virtual_lifestyle_sync as sync_cli

    pending_path = tmp_path / "pending.json"
    history_path = tmp_path / "history.json"
    pending_path.write_text(json.dumps(_pending(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(
        sync_cli,
        "list_all_freepublish",
        lambda: ([_published()], None),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "wechat_mp_virtual_lifestyle_sync",
            "--pending",
            str(pending_path),
            "--history",
            str(history_path),
        ],
    )

    assert sync_cli.main() == 0
    ledger = json.loads(history_path.read_text(encoding="utf-8"))
    assert ledger["posts"][0]["article_id"] == "article-1"
    assert "SYNCED ZX-001" in capsys.readouterr().out


def test_sync_module_never_imports_publish_submit() -> None:
    from scripts.tools import wechat_mp_virtual_lifestyle_sync as sync_cli

    source = Path(sync_cli.__file__).read_text(encoding="utf-8")
    assert "freepublish_submit" not in source
