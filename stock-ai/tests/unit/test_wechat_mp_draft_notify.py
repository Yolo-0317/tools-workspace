"""草稿推送通知文案。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_draft_notify import (
    DraftPushResult,
    format_batch_message,
)


def test_format_batch_message_ok() -> None:
    text = format_batch_message(
        "evening",
        [
            DraftPushResult(kind="market", title="A股收盘复盘", action="updated", ok=True),
            DraftPushResult(kind="top5", title="今日五只", action="created", ok=True),
        ],
    )
    assert "交易日 19:00" in text
    assert "[market]" in text
    assert "更新" in text
    assert "[top5]" in text
    assert "新建" in text
    assert "mp.weixin.qq.com" in text


def test_format_batch_message_with_failures() -> None:
    text = format_batch_message(
        "weekend",
        [DraftPushResult(kind="news", title="", action="", ok=False, error="合规")],
        failed_kinds=["news"],
    )
    assert "休市日 19:00" in text
    assert "跳过/失败" in text
