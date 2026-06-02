"""按槽位匹配公众号封面素材。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import (
    _DEFAULT_KIND_THUMB_NAMES,
    pick_thumb_for_draft_kind,
    pick_thumb_from_material_library,
)


def test_default_kind_thumb_names() -> None:
    assert "交易所屏" in _DEFAULT_KIND_THUMB_NAMES["market"]
    assert "手机看盘" in _DEFAULT_KIND_THUMB_NAMES["top5"]


def test_pick_thumb_for_kind_uses_distinct_env(monkeypatch) -> None:
    monkeypatch.delenv("WECHAT_MP_THUMB_MEDIA_ID", raising=False)
    calls: list[str] = []

    def _fake_pick(*, name_sub=None, media_id_preset=None, use_global_preset=True):
        del media_id_preset, use_global_preset
        calls.append(name_sub or "")
        return f"id-{name_sub}", None

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_client.pick_thumb_from_material_library",
        _fake_pick,
    )
    pick_thumb_for_draft_kind("market")
    pick_thumb_for_draft_kind("top5")
    assert calls[0] != calls[1]
    assert "交易所屏" in calls[0]
    assert "手机看盘" in calls[1]
