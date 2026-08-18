"""公众号草稿写入前的 Codex 来源门禁。"""

from __future__ import annotations

from scripts.tools import wechat_mp_draft as draft_cli
from scripts.tools.wechat_mp_codex_client import CodexGenerationEvent


BUILD_KWARGS = {
    "edition": None,
    "market_title": None,
    "variant": None,
    "topic_hint": "",
    "silver_lane": None,
    "upload_figures": False,
}


def test_build_records_manual_codex_draft_as_interactive(monkeypatch) -> None:
    monkeypatch.setattr(
        draft_cli,
        "_build_for_kind",
        lambda kind, **kwargs: {"title": f"{kind}-title"},
    )
    marker = object()

    article, events = draft_cli._build_with_codex_provenance(
        "silver",
        codex_draft=marker,
        **BUILD_KWARGS,
    )

    assert article == {"title": "silver-title"}
    assert [(event.provider, event.mode, event.kind) for event in events] == [
        ("codex", "interactive_draft", "silver")
    ]


def test_non_codex_generation_is_rejected() -> None:
    event = CodexGenerationEvent(
        provider="deepseek",
        mode="codex_exec",
        cli_version="codex-cli test",
        generated_at="2026-08-17T00:00:00+08:00",
        kind="silver",
    )

    try:
        draft_cli._assert_article_provenance(
            (event,),
            codex_draft_supplied=False,
        )
    except RuntimeError as exc:
        assert "只允许 Codex" in str(exc)
    else:
        raise AssertionError("非 Codex 来源不应通过公众号推送门禁")


def test_manual_codex_draft_requires_a_source_event() -> None:
    try:
        draft_cli._assert_article_provenance((), codex_draft_supplied=True)
    except RuntimeError as exc:
        assert "缺少生成来源" in str(exc)
    else:
        raise AssertionError("人工 Codex 草稿缺少来源时不应通过")


def test_generation_events_do_not_leak_between_kinds(monkeypatch) -> None:
    monkeypatch.setattr(
        draft_cli,
        "_build_for_kind",
        lambda kind, **kwargs: {"title": f"{kind}-title"},
    )

    _, first = draft_cli._build_with_codex_provenance(
        "silver",
        codex_draft=object(),
        **BUILD_KWARGS,
    )
    _, second = draft_cli._build_with_codex_provenance(
        "market",
        codex_draft=None,
        **BUILD_KWARGS,
    )

    assert [event.kind for event in first] == ["silver"]
    assert second == ()
