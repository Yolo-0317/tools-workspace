"""Load and validate the single account-level writing persona for WeChat."""

from __future__ import annotations

from pathlib import Path


ACCOUNT_ROLE_CARD_PATH = (
    Path(__file__).resolve().parents[3]
    / ".cursor"
    / "skills"
    / "wechat-mp-writing"
    / "account-role-card.md"
)

_REQUIRED_BOUNDARIES = (
    "隐形作者人格",
    "时间、金钱、尊严和选择成本",
    "事实与推断分开",
    "禁止虚构亲历",
    "禁止显性自称栀夏",
)


def load_account_role_card() -> str:
    path = ACCOUNT_ROLE_CARD_PATH
    if not path.is_file():
        raise RuntimeError(f"公众号账号角色卡文件不存在: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"公众号账号角色卡为空: {path}")
    missing = [marker for marker in _REQUIRED_BOUNDARIES if marker not in text]
    if missing:
        raise RuntimeError(f"公众号账号角色卡缺少关键边界: {'、'.join(missing)}")
    return text


def account_role_prompt_block() -> str:
    return f"## 账号角色卡（最先遵守）\n{load_account_role_card()}"
