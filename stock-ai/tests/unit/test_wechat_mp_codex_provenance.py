"""公众号草稿写入前的 Codex 来源门禁。"""

from __future__ import annotations

import pytest

from scripts.tools import wechat_mp_draft as draft_cli
from scripts.tools.wechat_mp_codex_client import CodexGenerationEvent


BUILD_KWARGS = {
    "edition": None,
    "market_title": None,
    "variant": None,
    "upload_figures": False,
}


def test_build_records_manual_codex_draft_as_interactive(monkeypatch) -> None:
    monkeypatch.setattr(
        draft_cli,
        "_build_for_kind",
        lambda kind, **kwargs: {"title": f"{kind}-title"},
    )

    article, events = draft_cli._build_with_codex_provenance(
        "hotspot",
        codex_draft=object(),
        **BUILD_KWARGS,
    )

    assert article == {"title": "hotspot-title"}
    assert [(event.provider, event.mode, event.kind) for event in events] == [
        ("codex", "interactive_draft", "hotspot")
    ]


def test_non_codex_generation_is_rejected() -> None:
    event = CodexGenerationEvent(
        provider="deepseek",
        mode="codex_exec",
        cli_version="codex-cli test",
        generated_at="2026-08-17T00:00:00+08:00",
        kind="hotspot",
    )

    with pytest.raises(RuntimeError, match="只允许 Codex"):
        draft_cli._assert_article_provenance(
            (event,),
            codex_draft_supplied=False,
        )


def test_manual_codex_draft_requires_a_source_event() -> None:
    with pytest.raises(RuntimeError, match="缺少生成来源"):
        draft_cli._assert_article_provenance((), codex_draft_supplied=True)


def test_generation_events_do_not_leak_between_kinds(monkeypatch) -> None:
    monkeypatch.setattr(
        draft_cli,
        "_build_for_kind",
        lambda kind, **kwargs: {"title": f"{kind}-title"},
    )

    _, first = draft_cli._build_with_codex_provenance(
        "hotspot",
        codex_draft=object(),
        **BUILD_KWARGS,
    )
    _, second = draft_cli._build_with_codex_provenance(
        "market",
        codex_draft=None,
        **BUILD_KWARGS,
    )

    assert [event.kind for event in first] == ["hotspot"]
    assert second == ()
