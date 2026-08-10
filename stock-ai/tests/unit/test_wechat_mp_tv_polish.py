"""影视稿纯段落排版。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_tv_polish import finalize_tv_review_body


def test_finalize_tv_review_strips_subheadings():
    raw = """> 散场时有人在问彩蛋

7月29日内地上映，我买的晚场。

> 没看过《英雄无归》也能进场，但会少一层心酸

国内没上《英雄无归》，剧情梗概你应该听过。

· 开篇送外卖：彼得翻窗进巷战。

· 地铁里救人：镜头贴近。
"""
    out = finalize_tv_review_body(raw)
    assert ">" not in out
    assert "没看过《英雄无归》也能进场，但会少一层心酸" not in out.split("\n\n")[0]
    assert "送外卖" in out
    assert "地铁" in out
    assert out.count("\n\n") >= 2


def test_tv_review_public_finalize_keeps_multi_sentence_paragraphs():
    from scripts.tools.wechat_mp_public import finalize_public_body_text

    body = (
        "第一句写上映和场面，字数要够长才能测出拆句问题。"
        "第二句写人物和表演，霍兰德疲惫写在脸上。"
        "第三句写主题和镜头，冷清但不煽情。"
        "第四句收束到观感判断。"
    )
    out = finalize_public_body_text(body, kind="tv_review")
    blocks = [b.strip() for b in out.split("\n\n") if b.strip()]
    assert len(blocks) == 1
    assert out.count("。") >= 3
