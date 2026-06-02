"""公众号正文去 emoji。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_prose import humanize_mp_text


def test_humanize_strips_emoji_and_ai_header() -> None:
    raw = """【AI 综合解读】

📊 大盘与外围
指数震荡。

📰 国内要闻
· 某政策出台

【000725 京东方A · 分69 · 暂不操作】
理由：观望。
"""
    out = humanize_mp_text(raw)
    assert "📊" not in out
    assert "【AI 综合解读】" not in out
    assert "一、盘面与外围" in out
    assert "京东方A（69分）：暂不操作" in out
