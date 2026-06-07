import os

from services.free_chat_access import (
    free_chat_enabled_for_username,
    free_chat_users_public,
)


def test_empty_env_disables_free_chat(monkeypatch):
    monkeypatch.delenv("ENGLISH_BUDDY_FREE_CHAT_USERS", raising=False)
    assert free_chat_enabled_for_username("yueyue") is False
    assert free_chat_users_public() == []


def test_whitelist_users(monkeypatch):
    monkeypatch.setenv("ENGLISH_BUDDY_FREE_CHAT_USERS", "yueyue, dingdang")
    assert free_chat_enabled_for_username("yueyue") is True
    assert free_chat_enabled_for_username("YueYue") is True
    assert free_chat_enabled_for_username("dingdang") is True
    assert free_chat_enabled_for_username("guest") is False
    assert free_chat_enabled_for_username(None) is False
    assert free_chat_users_public() == ["dingdang", "yueyue"]
