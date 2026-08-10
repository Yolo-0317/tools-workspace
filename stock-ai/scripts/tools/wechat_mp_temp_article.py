#!/usr/bin/env python3
"""公众号「临时稿」槽：单篇可覆写，不占用 workspace 日更总览。"""

from __future__ import annotations

import os
from collections.abc import Callable
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

# 注册变体：uv run python -m scripts.tools.wechat_mp_draft --kind temp --variant lark_cli
TempArticleFns = tuple[Callable[[], str], Callable[[], str], Callable[[], str]]

_VARIANTS: dict[str, TempArticleFns] = {}


def _register(name: str, fns: TempArticleFns) -> None:
    _VARIANTS[name.strip().lower()] = fns


def list_temp_variants() -> tuple[str, ...]:
    return tuple(sorted(_VARIANTS))


def resolve_temp_variant(name: str | None = None) -> str:
    raw = (name or os.getenv("WECHAT_MP_TEMP_VARIANT", "lark_cli")).strip().lower()
    if raw not in _VARIANTS:
        opts = ", ".join(list_temp_variants()) or "(无)"
        raise ValueError(f"未知 temp variant={raw!r}，可选: {opts}")
    return raw


def temp_article_title(*, variant: str | None = None) -> str:
    v = resolve_temp_variant(variant)
    return _VARIANTS[v][0]()


def temp_article_digest(*, variant: str | None = None) -> str:
    v = resolve_temp_variant(variant)
    return _VARIANTS[v][1]()


def generate_temp_article_body(*, variant: str | None = None) -> str:
    v = resolve_temp_variant(variant)
    return _VARIANTS[v][2]()


def _load_lark_cli_variant() -> None:
    from scripts.tools.wechat_mp_lark_cli_article import (
        generate_lark_cli_article_body,
        lark_cli_article_digest,
        lark_cli_article_title,
    )

    _register(
        "lark_cli",
        (lark_cli_article_title, lark_cli_article_digest, generate_lark_cli_article_body),
    )


def _load_english_buddy_variant() -> None:
    from scripts.tools.wechat_mp_english_buddy_article import (
        english_buddy_article_digest,
        english_buddy_article_title,
        generate_english_buddy_article_body,
    )

    _register(
        "english_buddy",
        (
            english_buddy_article_title,
            english_buddy_article_digest,
            generate_english_buddy_article_body,
        ),
    )


def _load_harryputter_variant() -> None:
    from scripts.tools.wechat_mp_harryputter_article import (
        generate_harryputter_article_body,
        harryputter_article_digest,
        harryputter_article_title,
    )

    _register(
        "harryputter",
        (
            harryputter_article_title,
            harryputter_article_digest,
            generate_harryputter_article_body,
        ),
    )


def _load_world_cup_variant() -> None:
    from scripts.tools.wechat_mp_world_cup_article import (
        generate_world_cup_article_body,
        world_cup_article_digest,
        world_cup_article_title,
    )

    _register(
        "world_cup",
        (
            world_cup_article_title,
            world_cup_article_digest,
            generate_world_cup_article_body,
        ),
    )


_load_lark_cli_variant()
_load_english_buddy_variant()
_load_harryputter_variant()
_load_world_cup_variant()
