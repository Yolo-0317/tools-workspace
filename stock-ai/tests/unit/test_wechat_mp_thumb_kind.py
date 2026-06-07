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
    assert "牛马品牌" in _DEFAULT_KIND_THUMB_NAMES["sector"]
    assert "交易所屏" in _DEFAULT_KIND_THUMB_NAMES["market"]
    assert "财经亮屏" in _DEFAULT_KIND_THUMB_NAMES["top5"]
    assert "多屏亮行情" in _DEFAULT_KIND_THUMB_NAMES["dragons"]
    assert "显示器走势" in _DEFAULT_KIND_THUMB_NAMES["news"]


def test_finance_thumb_excludes_avatar_material() -> None:
    from scripts.tools.wechat_mp_client import _is_finance_thumb_material

    assert not _is_finance_thumb_material({"name": "avatar.png", "name_raw": "avatar.png"})
    assert _is_finance_thumb_material(
        {"name": "封面-显示器走势-双封面.jpg", "name_raw": "封面-显示器走势-双封面.jpg"}
    )


def test_pick_thumb_for_kind_uses_distinct_env(monkeypatch) -> None:
    monkeypatch.delenv("WECHAT_MP_THUMB_MEDIA_ID", raising=False)
    monkeypatch.delenv("WECHAT_MP_THUMB_NAME_TOP5", raising=False)
    monkeypatch.delenv("WECHAT_MP_THUMB_NAME_DRAGONS", raising=False)
    monkeypatch.setenv("WECHAT_MP_KIND_THUMB_FROM_ASSETS", "0")
    calls: list[str] = []

    def _fake_pick(*, name_sub=None, media_id_preset=None, use_global_preset=True, **kwargs):
        del media_id_preset, use_global_preset, kwargs
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
    assert "财经亮屏" in calls[1]


def test_pick_sector_falls_back_to_banner_upload(monkeypatch, tmp_path) -> None:
    banner = tmp_path / "banner.png"
    banner.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 32)

    monkeypatch.setenv("WECHAT_MP_SECTOR_THUMB_FROM_BANNER", "1")
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_client._sector_banner_thumb_path",
        lambda: banner,
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_client.pick_thumb_from_material_library",
        lambda **kwargs: (None, {"errmsg": "miss"}),
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_client.add_permanent_image",
        lambda path: ("media-banner-1", None),
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_client.SECTOR_BANNER_THUMB_CACHE",
        tmp_path / "sector_thumb.json",
    )

    mid, err = pick_thumb_for_draft_kind("sector")
    assert err is None
    assert mid == "media-banner-1"


def test_pick_top5_prefers_local_bright_asset(monkeypatch, tmp_path) -> None:
    cover = ROOT / "assets" / "wechat_mp" / "cover-financial-screen-dual.jpg"
    if not cover.is_file():
        return
    cache = tmp_path / "top5_thumb.json"
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_client._KIND_THUMB_ASSET_CACHE",
        {"top5": cache, "dragons": tmp_path / "dragons_thumb.json"},
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_client.pick_thumb_from_material_library",
        lambda **kwargs: (None, {"errmsg": "miss"}),
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_client.add_permanent_image",
        lambda path: ("media-top5-bright", None),
    )

    mid, err = pick_thumb_for_draft_kind("top5")
    assert err is None
    assert mid == "media-top5-bright"
