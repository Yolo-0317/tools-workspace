#!/usr/bin/env python3
"""要闻稿完读钩子。"""

from __future__ import annotations

import re

from scripts.tools.wechat_mp_read_hooks import (
    BRIDGE_MARK,
    apply_if_enabled,
    has_reader_hook,
    inject_transitions_in_section,
    insert_after_section_title,
    read_hooks_enabled,
)
from scripts.tools.wechat_mp_prose import NEWS_SECTION_TITLES

_SECTION = NEWS_SECTION_TITLES[0]
_NEWS_ITEM_RE = re.compile(r"^\d+\.\s+")

_TRANSITIONS = (
    f"{BRIDGE_MARK}下一条对板块的传导，可能和这一条完全不是同一条路。",
    f"{BRIDGE_MARK}别被标题带走，盯它能不能落到量价。",
    f"{BRIDGE_MARK}这一条和上一条的验证点，本来就不在同一维度。",
    f"{BRIDGE_MARK}再往后，资金会不会用脚投票，会更说明问题。",
)


def finalize_news_body(body: str) -> str:
    if not read_hooks_enabled("news"):
        return body

    def _run(text: str) -> str:
        head = text[:700]
        if has_reader_hook(head) and re.search(r"\d", head):
            return inject_transitions_in_section(
                text,
                _SECTION,
                line_re=_NEWS_ITEM_RE,
                transitions=_TRANSITIONS,
            )
        from scripts.tools.wechat_mp_weekend_news import build_news_time_context

        intro = build_news_time_context().intro_lede
        if not has_reader_hook(text[:500]):
            text = insert_after_section_title(
                text,
                _SECTION,
                [
                    "",
                    intro,
                    "",
                ],
            )
        return inject_transitions_in_section(
            text,
            _SECTION,
            line_re=_NEWS_ITEM_RE,
            transitions=_TRANSITIONS,
        )

    return apply_if_enabled("news", body, _run)
