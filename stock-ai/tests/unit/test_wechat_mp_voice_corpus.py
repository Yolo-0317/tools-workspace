"""写稿语料库 prompt 加载。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_voice_corpus import load_discussion_voice_prompt


def test_load_discussion_base_contains_corpus_phrases() -> None:
    text = load_discussion_voice_prompt(dianji=False)
    assert "读者转述者" in text
    assert "鼻头一酸" in text
    assert "节目旨在" in text


def test_load_dianji_overlay() -> None:
    text = load_discussion_voice_prompt(dianji=True)
    assert "典籍专栏" in text
    assert "一集一颗钉子" in text
