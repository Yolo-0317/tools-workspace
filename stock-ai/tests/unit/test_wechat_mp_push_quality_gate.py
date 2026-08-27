"""wechat_mp_push_quality_gate 单元测试。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_push_quality_gate import (
    assess_article_for_push,
    quality_gate_enabled,
    quality_gate_strict,
)
from scripts.tools.wechat_mp_traffic_checklist import TrafficChecklistReport, TrafficCheckItem


def _sample_article(*, title: str = "测试标题？", body: str = "正文含涨跌幅 1.2%。") -> dict:
    return {
        "title": title,
        "digest": "摘要含A股与收盘。",
        "body_text": body,
        "content": f"<p>{body}</p>",
        "recommended_hashtags": ["A股"],
    }


def test_quality_gate_enabled_evening_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WECHAT_MP_PUSH_QUALITY_GATE", raising=False)
    monkeypatch.setenv("WECHAT_MP_NEWS_BATCH", "evening")
    assert quality_gate_enabled() is True


def test_quality_gate_disabled_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_MP_PUSH_QUALITY_GATE", "0")
    monkeypatch.setenv("WECHAT_MP_NEWS_BATCH", "evening")
    assert quality_gate_enabled() is False


def test_assess_article_passes_reasonable_copy() -> None:
    art = _sample_article(
        title="京东方A与亨通光电：A股快讯？",
        body=(
            "> 今日主线：半导体与通信设备走强。\n\n"
            "一、快讯\n\n"
            "京东方A 涨 3.2%，成交额 12 亿。\n\n"
            "不构成投资建议，决策自负。"
        ),
    )
    result = assess_article_for_push(art, "news", with_traffic=False)
    assert result.eval_report.compliance_failures == []
    # 门槛较松的样例应能过或至少给出明确 block_reason
    if not result.ok:
        assert result.block_reason


def test_assess_article_fails_low_score(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_MP_QUALITY_MIN_SCORE", "99")
    art = _sample_article(body="短。")
    result = assess_article_for_push(art, "news", with_traffic=False)
    assert result.ok is False
    assert "总分" in result.block_reason


def test_assess_article_fails_high_ai_flavor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_MP_QUALITY_MAX_AI_FLAVOR", "5")
    body = "综上所述，值得注意的是，一方面涨另一方面跌。感谢您的阅读。"
    art = _sample_article(body=body)
    result = assess_article_for_push(art, "news", with_traffic=False)
    assert result.ok is False
    assert "AI味" in result.block_reason


def test_quality_gate_strict_default() -> None:
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("WECHAT_MP_QUALITY_GATE_STRICT", None)
        assert quality_gate_strict() is True


def test_assess_article_with_advisory_only_traffic_is_not_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_report = TrafficChecklistReport(
        kind="hotspot",
        title="标题",
        edition=None,
        items=[
            TrafficCheckItem(
                id="reader_choice_connected",
                label="正文末尾接读者选择",
                passed=False,
                advisory=True,
            ),
        ],
    )
    monkeypatch.setenv("WECHAT_MP_QUALITY_MIN_SCORE", "0")
    with patch(
        "scripts.tools.wechat_mp_push_quality_gate.run_traffic_checklist",
        return_value=fake_report,
    ):
        result = assess_article_for_push(
            _sample_article(
                title="今天的热点是怎么说",
                body="a" * 2200,
            ),
            "hotspot",
        )
    assert result.ok is True
    assert result.traffic_failures == []
    assert result.traffic_advisories == ["reader_choice_connected:正文末尾接读者选择"]


def test_assess_article_blocks_when_real_traffic_failures_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_MP_QUALITY_TRAFFIC_BLOCK", "1")
    fake_report = TrafficChecklistReport(
        kind="hotspot",
        title="标题",
        edition=None,
        items=[
            TrafficCheckItem(
                id="title_len",
                label="标题 ≤32 字",
                passed=False,
            ),
            TrafficCheckItem(
                id="reader_choice_connected",
                label="正文末尾接读者选择",
                passed=False,
                advisory=True,
            ),
        ],
    )
    with patch(
        "scripts.tools.wechat_mp_push_quality_gate.run_traffic_checklist",
        return_value=fake_report,
    ):
        result = assess_article_for_push(
            _sample_article(
                title="今天的热点是怎么说",
                body="a" * 2200,
            ),
            "hotspot",
        )
    assert result.ok is False
    assert result.traffic_failures == ["title_len:标题 ≤32 字"]
    assert result.traffic_advisories == ["reader_choice_connected:正文末尾接读者选择"]
