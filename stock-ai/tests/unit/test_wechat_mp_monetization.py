"""流量主成稿优化。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_monetization import (
    append_recommend_hook,
    polish_for_traffic,
    split_disclaimer,
)


def test_polish_for_traffic_no_ad_marker_by_default() -> None:
    body = "> 盘面速览\n指数涨0.4%\n\n> 外围与资金\n美股小涨"
    out = polish_for_traffic(body, kind="market")
    assert "· · ·" not in out


def test_append_recommend_hook() -> None:
    body = "> 盘面速览\n内容"
    out = append_recommend_hook(body, kind="market")
    assert "推荐 ♡" in out


def test_engagement_before_disclaimer() -> None:
    disc = "本文为作者个人投资日记与信息整理，不构成投资建议。市场有风险，决策自负。"
    body = f"> 盘面速览\n内容\n\n{disc}"
    core, tail = split_disclaimer(body)
    polished = polish_for_traffic(core, kind="market")
    merged = f"{polished}\n\n{tail}"
    assert ("留言" in merged) or ("交流" in merged)
    assert "推荐 ♡" in merged
    assert merged.index("交流" if "交流" in merged else "留言") < merged.index("本文为作者")
    assert merged.index("推荐 ♡") < merged.index("本文为作者")
