"""hotspot 节名清洗：去掉旧模板节名。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_prose import normalize_hotspot_legacy_labels


def test_normalize_hotspot_legacy_labels_strips_rigid_sections():
    raw = "\n".join(
        [
            "> 今天深写什么",
            "霍尔木兹牵动油运链。",
            "",
            "> 霍尔木兹海峡",
            "发生了什么：伊朗称海峡暂闭。",
            "",
            "> 向后看要验证什么",
            "盯 Brent 与油服竞价。",
        ]
    )
    out = normalize_hotspot_legacy_labels(raw)
    assert "今天深写什么" not in out
    assert "向后看要验证什么" not in out
    assert "为啥盯这条" not in out
    assert "明天盯什么" not in out
    assert "伊朗称海峡暂闭" in out
