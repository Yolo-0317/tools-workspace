"""Codex 单剧推广稿交接 JSON。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.tools import wechat_mp_codex_short_drama as codex_mod


def valid_data() -> dict[str, object]:
    fact_ids = ["character-1", "relationship-1", "conflict-1", "reversal-1"]
    paragraph = (
        "李建军失去原来的工作后进入工厂，摆在他面前的是一台让众人束手无策的机床。"
        "他没有急着证明自己，只是盯着故障一步步排查。"
        "周围人的怀疑没有消失，维修结果却开始改变他们的判断。"
    ) * 3
    return {
        "drama_id": "1713873",
        "drama_name": "修好铁疙瘩转身踏青云",
        "title": "下岗技师进厂第一天，就接下没人敢碰的机床",
        "digest": "一台故障机床，把一个下岗技师逼到了必须证明自己的位置。",
        "title_fact_ids": ["character-1", "conflict-1"],
        "digest_fact_ids": ["character-1", "conflict-1"],
        "paragraphs": [
            {"text": paragraph, "fact_ids": fact_ids}
            for _ in range(6)
        ],
        "sources": [
            {
                "source_id": "source-1",
                "url": "https://news.example.test/drama-1713873",
                "title": "短剧剧情介绍",
                "source_name": "测试媒体",
                "source_type": "report",
                "excerpt": "李建军进入工厂，靠维修机床证明自己的技术。",
            }
        ],
        "facts": [
            {
                "fact_id": "character-1",
                "fact_type": "character",
                "claim": "主角名叫李建军。",
                "source_ids": ["platform", "source-1"],
            },
            {
                "fact_id": "relationship-1",
                "fact_type": "relationship",
                "claim": "李建军进入一家工厂工作。",
                "source_ids": ["platform", "source-1"],
            },
            {
                "fact_id": "conflict-1",
                "fact_type": "conflict",
                "claim": "故障机床成为他的技术考验。",
                "source_ids": ["platform", "source-1"],
            },
            {
                "fact_id": "reversal-1",
                "fact_type": "reversal",
                "claim": "维修结果改变了旁人对他的判断。",
                "source_ids": ["platform", "source-1"],
            },
        ],
        "rejected_claims": ["李建军最终获得某项国家奖项"],
        "slot_key": "short_drama_feature",
    }


def test_load_codex_short_drama_draft_preserves_fact_bindings() -> None:
    draft = codex_mod.load_codex_short_drama_draft_data(valid_data())

    assert draft.drama_id == "1713873"
    assert draft.slot_key == "short_drama_feature"
    assert len(draft.paragraphs) == 6
    assert draft.facts[2].source_ids == ("platform", "source-1")
    assert draft.sources[0].source_id == "source-1"


def test_codex_short_drama_draft_rejects_reserved_platform_source() -> None:
    data = valid_data()
    data["sources"] = [
        {
            "source_id": "platform",
            "url": "https://fake.example/platform",
            "title": "伪造平台来源",
            "source_name": "未知",
            "source_type": "report",
            "excerpt": "内容",
        }
    ]

    with pytest.raises(ValueError, match="platform 来源由系统注入"):
        codex_mod.load_codex_short_drama_draft_data(data)


def test_codex_short_drama_draft_requires_boolean_official_flag() -> None:
    data = valid_data()
    data["sources"][0]["official"] = "false"

    with pytest.raises(ValueError, match="official 必须是布尔值"):
        codex_mod.load_codex_short_drama_draft_data(data)
