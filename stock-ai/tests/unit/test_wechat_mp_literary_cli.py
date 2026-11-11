from scripts.tools import wechat_mp_draft as draft_cli
from scripts.tools import wechat_mp_draft_slots as draft_slots


def test_literary_uses_tv_cover_assets_but_independent_slot() -> None:
    assert draft_cli._resolve_cover_kind("literary") == "tv_review"
    assert draft_cli._resolve_draft_slot_key("literary", None) == "literary"
    assert "literary" in draft_slots.managed_slot_keys()
