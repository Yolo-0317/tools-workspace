"""参考文素材抓取。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()


def test_extract_opening_paragraphs_filters_noise() -> None:
    from scripts.tools.wechat_mp_reference_fetch import _extract_opening_paragraphs

    html = (
        "<p>来源：央视 编辑：张三</p>"
        "<p>倪大红演的伏生抱着竹简嚎啕大哭，身边人劝他书毁了可以再写。</p>"
        "<p>他嘶哑着回了一句，我妻我子我全家舍命护它啊。</p>"
    )
    paras = _extract_opening_paragraphs(html, max_paras=3)
    assert len(paras) == 1
    assert "嚎啕大哭" in paras[0]
    assert "来源" not in paras[0]
