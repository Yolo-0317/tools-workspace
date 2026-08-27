from __future__ import annotations

import pytest

from scripts.tools.wechat_mp_browser_prompt import build_browser_prompt


def test_hotspot_prompt_contains_fact_pack_and_no_internal_secrets() -> None:
    prompt = build_browser_prompt(
        kind="hotspot",
        topic="具体公共事件",
        thesis="组织者没有动手，也可能因为没有制止危险行为而承担安全保障责任。",
        fact_lines=("法院判决新人承担40%责任｜来源：光明网",),
        research_urls=(
            "https://m.gmw.cn/example",
            "https://www.thepaper.cn/example",
            "https://www.chinanews.com.cn/example",
        ),
    )

    assert "一句话钉子" in prompt
    assert "法院判决新人承担40%责任" in prompt
    assert "第一行标题" in prompt
    assert "虚构采访" in prompt
    assert "token=" not in prompt.lower()


def test_literary_prompt_requires_scene_opening_and_verified_quotes() -> None:
    prompt = build_browser_prompt(
        kind="literary",
        topic="《典籍里的中国·史记》",
        thesis="司马迁最重要的选择不是忍辱本身，而是让写作目标压过同时代人的评价。",
        fact_lines=("《史记》共130篇｜来源：中国国家博物馆",),
        research_urls=(
            "https://www.chnmuseum.cn/example",
            "https://tv.cctv.com/example",
            "https://www.nlc.cn/example",
        ),
    )

    assert "作品场面、原文细节或节目动作" in prompt
    assert "不得虚构观看经历" in prompt
    assert "直接引文" in prompt
    assert "《史记》共130篇" in prompt


def test_prompt_rejects_fewer_than_three_source_domains() -> None:
    with pytest.raises(ValueError, match="3 个不同来源域"):
        build_browser_prompt(
            kind="hotspot",
            topic="事件",
            thesis="这是一个长度足够且可以被公开事实反驳和检验的原创判断。",
            fact_lines=("事实",),
            research_urls=("https://a.example/1", "https://a.example/2"),
        )


def test_prompt_rejects_credential_shaped_text() -> None:
    with pytest.raises(ValueError, match="敏感字段"):
        build_browser_prompt(
            kind="hotspot",
            topic="事件",
            thesis="这是一个长度足够且可以被公开事实反驳和检验的原创判断。",
            fact_lines=("WECHAT_MP_SECRET=secret",),
            research_urls=(
                "https://a.example/1",
                "https://b.example/2",
                "https://c.example/3",
            ),
        )
