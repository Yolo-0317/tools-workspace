"""User-input validation with no database or account dependencies."""

from __future__ import annotations

import math
import re

from .models import HoldingInput


_SUPPORTED_PREFIXES = ("00", "30", "60", "68")


def normalize_code(value: str) -> str:
    raw = str(value).strip()
    raw = re.sub(r"^(?:sh|sz)", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\.(?:SH|SZ)$", "", raw, flags=re.IGNORECASE)
    if not re.fullmatch(r"\d{6}", raw):
        raise ValueError("证券代码必须是六位数字")
    if not raw.startswith(_SUPPORTED_PREFIXES):
        raise ValueError("共享版仅支持沪深 A 股普通股票")
    return raw


def market_for_code(code: str) -> str:
    normalized = normalize_code(code)
    return "SH" if normalized.startswith(("60", "68")) else "SZ"


def validate_holding(
    shares: int | None,
    cost_price: float | None,
    available_shares: int | None,
) -> HoldingInput | None:
    if shares is None and cost_price is None and available_shares is None:
        return None
    if shares is None or cost_price is None:
        raise ValueError("持仓诊断必须同时提供 shares 和 cost_price")
    if isinstance(shares, bool) or not isinstance(shares, int) or shares < 0:
        raise ValueError("shares 必须是非负整数")
    if shares % 100 != 0:
        raise ValueError("shares 必须是 100 股的整数倍")
    if not math.isfinite(float(cost_price)) or float(cost_price) <= 0:
        raise ValueError("cost_price 必须是正的有限数")
    if available_shares is not None:
        if (
            isinstance(available_shares, bool)
            or not isinstance(available_shares, int)
            or available_shares < 0
            or available_shares > shares
            or available_shares % 100 != 0
        ):
            raise ValueError("available_shares 必须是 0..shares 内的整百股")
    return HoldingInput(
        shares=shares,
        cost_price=float(cost_price),
        available_shares=available_shares,
    )
