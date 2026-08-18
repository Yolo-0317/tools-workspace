from __future__ import annotations

import pytest

from scripts.tools import wechat_mp_role_card as role_card
from scripts.tools.wechat_mp_codex_client import _assert_prompt_safe


VALID_CARD = """# 栀夏未完成账号角色卡

## 运行时关键边界
- 隐形作者人格
- 普通人生活成本：时间、金钱、尊严和选择成本
- 事实与推断分开
- 禁止虚构亲历
- 禁止显性自称栀夏
"""


def test_load_account_role_card_returns_non_empty_text(tmp_path, monkeypatch) -> None:
    path = tmp_path / "account-role-card.md"
    path.write_text(VALID_CARD, encoding="utf-8")
    monkeypatch.setattr(role_card, "ACCOUNT_ROLE_CARD_PATH", path)

    assert role_card.load_account_role_card() == VALID_CARD.strip()


def test_account_role_prompt_block_has_stable_heading(tmp_path, monkeypatch) -> None:
    path = tmp_path / "account-role-card.md"
    path.write_text(VALID_CARD, encoding="utf-8")
    monkeypatch.setattr(role_card, "ACCOUNT_ROLE_CARD_PATH", path)

    block = role_card.account_role_prompt_block()

    assert block.startswith("## 账号角色卡（最先遵守）\n")
    assert "隐形作者人格" in block
    _assert_prompt_safe(block)


def test_load_account_role_card_rejects_missing_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(role_card, "ACCOUNT_ROLE_CARD_PATH", tmp_path / "missing.md")

    with pytest.raises(RuntimeError, match="角色卡文件不存在"):
        role_card.load_account_role_card()


@pytest.mark.parametrize("content", ["", "# 只有标题\n隐形作者人格"])
def test_load_account_role_card_rejects_empty_or_incomplete(
    content: str, tmp_path, monkeypatch
) -> None:
    path = tmp_path / "account-role-card.md"
    path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(role_card, "ACCOUNT_ROLE_CARD_PATH", path)

    with pytest.raises(RuntimeError, match="角色卡为空|角色卡缺少关键边界"):
        role_card.load_account_role_card()
