from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.tools import wechat_mp_tv_review_article as tv


NOW = datetime(2026, 8, 18, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def _topic(mode: str = "review") -> dict[str, object]:
    return {
        "title_zh": "测试电影",
        "title_en": "Test Film",
        "platform": "院线",
        "type": "film",
        "year": "2026",
        "hook": "一个普通人不得不重新选择的故事",
        "content_mode": "discussion" if mode == "discussion" else "review",
        "trend_title": "测试电影里的选择为什么引发争议",
        "reference_angles": [],
        "sources": [],
        "from_trend": False,
    }


def _capture_prompt(monkeypatch, response: str) -> list[str]:
    captured: list[str] = []
    monkeypatch.setattr(tv, "is_wechat_mp_llm_configured", lambda: True)
    monkeypatch.setattr(
        tv,
        "call_wechat_mp_llm",
        lambda messages, **_: captured.append(messages[-1]["content"]) or response,
    )
    return captured


def test_tv_review_prompt_starts_with_account_role_card(monkeypatch) -> None:
    from scripts.tools import wechat_mp_tv_review_template as template

    captured = _capture_prompt(monkeypatch, "> 第一节\n" + "正文。" * 500)
    monkeypatch.setenv("WECHAT_MP_TV_RESEARCH", "0")
    monkeypatch.setattr(template, "template_prompt_block", lambda: "五节模板规则")
    monkeypatch.setattr(template, "template_system_message", lambda: "影视稿系统规则")
    monkeypatch.setattr(template, "tv_depth_prompt_block", lambda: "剧情深度规则")

    tv.generate_tv_review_body(_topic(), now=NOW)

    assert captured[0].index("## 账号角色卡（最先遵守）") < captured[0].index(
        "## 稿型任务：影视长文"
    )


def test_tv_discussion_prompt_starts_with_account_role_card(monkeypatch) -> None:
    captured = _capture_prompt(monkeypatch, "正文。" * 900)
    monkeypatch.setenv("WECHAT_MP_TV_RESEARCH", "0")

    tv.generate_tv_discussion_body(_topic("discussion"), now=NOW)

    assert captured[0].index("## 账号角色卡（最先遵守）") < captured[0].index(
        "## 稿型任务：影视话题讨论"
    )


def test_tv_reference_rewrite_keeps_account_role_card(monkeypatch) -> None:
    captured = _capture_prompt(monkeypatch, "正文。" * 900)

    tv._rewrite_discussion_against_references("初稿。" * 900, reference_block="参考报道")

    assert "## 账号角色卡（最先遵守）" in captured[0]
    assert captured[0].index("## 账号角色卡（最先遵守）") < captured[0].index(
        "【参考文章】"
    )
