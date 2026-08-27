"""DeepSeek 公众号写稿。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()


def test_parse_writer_json() -> None:
    from scripts.tools.wechat_mp_deepseek_writer import _parse_writer_response

    raw = json.dumps({"title": "测试标题", "body": "第一段。\n\n第二段。"})
    out = _parse_writer_response(raw)
    assert out["title"] == "测试标题"
    assert "第一段" in out["body"]


def test_build_prompt_minimal() -> None:
    from scripts.tools.wechat_mp_deepseek_writer import build_deepseek_writer_prompt

    p = build_deepseek_writer_prompt("典籍里的中国 尚书")
    assert "爆款标题" in p
    assert "钩子" in p
    assert "语料库" not in p
    assert "场面" in p or "对白" in p


def test_build_prompt_non_dianji() -> None:
    from scripts.tools.wechat_mp_deepseek_writer import build_deepseek_writer_prompt

    p = build_deepseek_writer_prompt("暑期档票房破70亿")
    assert "场面" not in p


def test_build_prompt_dianji_user_has_nail() -> None:
    from scripts.tools.wechat_mp_deepseek_writer import build_deepseek_dianji_user_prompt

    p = build_deepseek_dianji_user_prompt(
        "典籍里的中国 尚书 伏生",
        topic_key="dianji-shangshu",
    )
    assert "场记" not in p  # system 侧
    assert "钉子" in p or "伏生护书" in p
    assert "画面钉子" in p


def test_parse_body_array() -> None:
    from scripts.tools.wechat_mp_deepseek_writer import _parse_writer_response

    raw = json.dumps({"title": "测试", "body": ["第一段。", "第二段。"]})
    out = _parse_writer_response(raw)
    assert "第一段" in out["body"]
    assert "第二段" in out["body"]


def test_protect_opening_paragraph() -> None:
    from scripts.tools.wechat_mp_deepseek_polish import protect_opening_paragraph

    before = "倪大红抱着竹简嚎啕大哭。「书毁了可以再写。」\n\n第二段内容。"
    after = "2021年大年初一节目开播。\n\n第二段被改过。"
    out = protect_opening_paragraph(before, after)
    assert "嚎啕大哭" in out
    assert "2021年" not in out.split("\n\n")[0]
