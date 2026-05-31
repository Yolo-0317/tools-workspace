#!/usr/bin/env python3
"""解析 investment-agent/持仓执行卡.md → 持仓、账户、盘中监控规则。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


@dataclass
class CardPosition:
    name: str
    code: str
    shares: int
    cost: float
    price: float | None
    status: str
    action: str
    asset_type: str = "stock"


@dataclass
class CardAccount:
    total_assets: float | None
    available_cash: float | None
    market_value: float | None
    fund_value: float | None
    position_ratio: float | None
    holding_pnl: float | None
    daily_pnl: float | None
    snapshot_date: date | None


def _cell(line: str, idx: int) -> str:
    parts = [p.strip() for p in line.split("|")]
    if len(parts) <= idx:
        return ""
    return parts[idx].strip("* ").replace(",", "")


def _parse_num(text: str) -> float | None:
    m = re.search(r"([\d,.]+)", text.replace(",", ""))
    return float(m.group(1)) if m else None


def _parse_int(text: str) -> int:
    m = re.search(r"(\d+)", text.replace(",", ""))
    return int(m.group(1)) if m else 0


def _extract_section(text: str, heading_prefix: str) -> str:
    lines: list[str] = []
    capturing = False
    for line in text.splitlines():
        if line.startswith("## ") and capturing:
            break
        if line.startswith(heading_prefix):
            capturing = True
            lines.append(line)
            continue
        if capturing:
            lines.append(line)
    return "\n".join(lines).strip()


def parse_stock_positions(text: str) -> list[CardPosition]:
    positions: list[CardPosition] = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("| 股票 | 代码 |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            if line.startswith("|------"):
                continue
            code = _cell(line, 2)
            if not re.fullmatch(r"\d{6}", code):
                continue
            positions.append(
                CardPosition(
                    name=_cell(line, 1),
                    code=code,
                    shares=_parse_int(_cell(line, 3)),
                    cost=_parse_num(_cell(line, 4)) or 0.0,
                    price=_parse_num(_cell(line, 5)),
                    status=_cell(line, 8),
                    action=_cell(line, 9),
                    asset_type="stock",
                )
            )
    return positions


def parse_account(text: str) -> CardAccount:
    section = _extract_section(text, "## 账户概览")
    body = section or text
    total = available = market = fund = position = holding = daily = None
    snapshot_date: date | None = None

    m = re.search(r"最后更新[：:]\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        snapshot_date = date.fromisoformat(m.group(1))
    m = re.search(r"当前持仓[（(](\d{1,2}/\d{1,2})", text)
    if m and snapshot_date is None:
        month, day = m.group(1).split("/")
        snapshot_date = date(date.today().year, int(month), int(day))

    for line in body.splitlines():
        if "**总资产**" in line:
            total = _parse_num(line)
        elif "**可用资金**" in line:
            available = _parse_num(line)
        elif "**证券市值**" in line:
            market = _parse_num(line)
        elif "**基金市值**" in line:
            fund = _parse_num(line)
        elif line.startswith("- **仓位**"):
            pm = re.search(r"([\d.]+)%", line)
            if pm:
                position = float(pm.group(1)) / 100.0
        elif "**持仓盈亏**" in line:
            holding = _parse_num(line)
        elif "**当日盈亏**" in line:
            daily = _parse_num(line)

    return CardAccount(
        total_assets=total,
        available_cash=available,
        market_value=market,
        fund_value=fund,
        position_ratio=position,
        holding_pnl=holding,
        daily_pnl=daily,
        snapshot_date=snapshot_date,
    )


def _rule_id(code: str, rtype: str, **kw: float) -> str:
    if rtype == "price_in_range":
        return f"hold_{code}_range_{int(kw['low'] * 100)}_{int(kw['high'] * 100)}"
    if rtype == "daily_pct_above":
        return f"hold_{code}_pct_{int(kw['pct'])}"
    key = "price" if "price" in kw else "pct"
    return f"hold_{code}_{rtype}_{int(kw[key] * 100)}"


def _msg_price_below(name: str, code: str, price: float, hint: str) -> str:
    return f"⚠️ {name}({code}) 跌破 {price:.2f} 元保护线，现价 {{price}} 元。{hint}"


def _msg_price_above(name: str, code: str, price: float, hint: str) -> str:
    return f"📌 {name}({code}) 涨至 {{price}} 元（≥{price:.2f}）。{hint}"


def _msg_range(name: str, code: str, low: float, high: float, hint: str) -> str:
    return f"📌 {name}({code}) 在 {{price}} 元（{low:.1f}~{high:.1f} 换仓区）。{hint}"


def _msg_pct(name: str, code: str) -> str:
    return f"⛔ {name}({code}) 当日涨幅 {{pct}}%（>5%）。纪律：严禁追高，不加仓。"


def _rules_from_block(
    block: str,
    *,
    code: str,
    name: str,
    hints: dict[str, str] | None = None,
) -> list[dict]:
    hints = hints or {}
    rules: list[dict] = []

    for m in re.finditer(r"(?:反弹\s*)?\*?\*?≥([\d.]+)\s*元", block):
        price = float(m.group(1))
        rid = _rule_id(code, "price_above", price=price)
        rules.append(
            {
                "id": rid,
                "code": code,
                "name": name,
                "type": "price_above",
                "price": price,
                "message": _msg_price_above(name, code, price, hints.get("above", "评估减仓或锁利。")),
            }
        )

    for m in re.finditer(r"跌破\s*\*?\*?([\d.]+)\s*元", block):
        price = float(m.group(1))
        rid = _rule_id(code, "price_below", price=price)
        hint = hints.get("below", "评估保护性操作。")
        if price <= 9.01 and code == "600873":
            hint = "纪律：清仓止损，严禁补仓。"
            rid = "meihua_stop_9"
        rules.append(
            {
                "id": rid,
                "code": code,
                "name": name,
                "type": "price_below",
                "price": price,
                "message": _msg_price_below(name, code, price, hint),
            }
        )

    for m in re.finditer(r"≤([\d.]+)\s*元", block):
        price = float(m.group(1))
        rid = _rule_id(code, "price_below", price=price)
        rules.append(
            {
                "id": rid,
                "code": code,
                "name": name,
                "type": "price_below",
                "price": price,
                "message": _msg_price_below(
                    name,
                    code,
                    price,
                    hints.get("dip", "若仓位允许，可小步评估加仓（勿追高）。"),
                ),
            }
        )

    for m in re.finditer(r"([\d.]+)[～~]([\d.]+)\s*元", block):
        low, high = float(m.group(1)), float(m.group(2))
        rid = _rule_id(code, "price_in_range", low=low, high=high)
        rules.append(
            {
                "id": rid,
                "code": code,
                "name": name,
                "type": "price_in_range",
                "low": low,
                "high": high,
                "message": _msg_range(name, code, low, high, hints.get("range", "已盈利，可评估减仓或换仓。")),
            }
        )

    if re.search(r"单日涨幅\s*>\s*5", block):
        rules.append(
            {
                "id": f"hold_{code}_pct_5",
                "code": code,
                "name": name,
                "type": "daily_pct_above",
                "pct": 5.0,
                "message": _msg_pct(name, code),
            }
        )

    return rules


_NAME_CODE = {
    "梅花生物": "600873",
    "广州发展": "600098",
    "南网储能": "600995",
    "宝新能源": "000690",
    "中国广核": "003816",
    "中国核电": "601985",
}

_HINTS: dict[str, dict[str, str]] = {
    "600873": {
        "above": "可考虑减仓 200 股（2手），严禁补仓。",
        "below": "纪律：清仓止损，严禁补仓。",
    },
    "600995": {
        "above": "可考虑再减 200 股锁定利润。",
        "below": "600股浮盈需保护，评估是否减仓。",
    },
    "600098": {
        "range": "已盈利，可评估减 200/400 股（整手）换南网或保留。",
        "above": "优先锁定利润，评估减仓或换仓南网。",
    },
    "000690": {
        "dip": "若仓位允许，可小步评估加仓 100 股（勿追高）。",
    },
    "003816": {"below": "收息股保护：评估减仓 500 股。"},
    "601985": {"below": "收息股保护：评估减仓 300 股。"},
}


def parse_holdings_alert_rules(text: str, positions: list[CardPosition] | None = None) -> list[dict]:
    """从 P0～P4 触发条件生成 holdings 监控规则。"""
    plan = _extract_section(text, "## 进行中计划")
    if not plan:
        return []

    name_to_code = dict(_NAME_CODE)
    for p in positions or []:
        name_to_code[p.name] = p.code

    rules: list[dict] = []
    seen_ids: set[str] = set()

    sections = re.split(r"(?=###\s*[🔴🟡🟢]\s*P\d)", plan)
    for section in sections:
        if not section.strip():
            continue
        title_m = re.search(r"P\d[：:]([^（\n]+)", section)
        if title_m:
            title = title_m.group(1).strip()
            for name, code in name_to_code.items():
                if name in title:
                    for rule in _rules_from_block(section, code=code, name=name, hints=_HINTS.get(code)):
                        if rule["id"] not in seen_ids:
                            seen_ids.add(rule["id"])
                            rules.append(rule)
                    break

        for m in re.finditer(r"^-\s+\*\*([^*]+)\*\*（", section, re.MULTILINE):
            sub_name = m.group(1).strip()
            code = name_to_code.get(sub_name)
            if not code:
                continue
            start = m.start()
            next_m = re.search(r"^-\s+\*\*([^*]+)\*\*（", section[m.end() :], re.MULTILINE)
            end = m.end() + next_m.start() if next_m else len(section)
            sub_block = section[start:end]
            for rule in _rules_from_block(
                sub_block,
                code=code,
                name=sub_name,
                hints=_HINTS.get(code),
            ):
                if rule["id"] not in seen_ids:
                    seen_ids.add(rule["id"])
                    rules.append(rule)

    # 稳定 id（与历史 monitor state 兼容）
    legacy_ids = {
        ("600873", "price_below", 9.0): "meihua_stop_9",
        ("600873", "price_above", 10.5): "meihua_reduce_105",
        ("600995", "price_below", 14.0): "nangwang_stop_14",
        ("600995", "price_above", 16.0): "nangwang_reduce_16",
        ("600098", "price_in_range", 7.8, 8.3): "guangfa_swap_zone",
        ("600098", "price_above", 8.5): "guangfa_lock_85",
        ("000690", "price_below", 5.5): "baoxin_add_55",
        ("000690", "daily_pct_above", 5.0): "baoxin_no_chase",
        ("003816", "price_below", 4.3): "guanghe_stop_430",
        ("601985", "price_below", 8.6): "hedian_stop_860",
    }
    for rule in rules:
        code = rule["code"]
        rtype = rule["type"]
        if rtype == "price_in_range":
            key = (code, rtype, rule["low"], rule["high"])
        elif rtype == "daily_pct_above":
            key = (code, rtype, rule["pct"])
        else:
            key = (code, rtype, rule["price"])
        if key in legacy_ids:
            rule["id"] = legacy_ids[key]

    return rules


def parse_card(text: str) -> tuple[list[CardPosition], CardAccount, list[dict]]:
    positions = parse_stock_positions(text)
    account = parse_account(text)
    rules = parse_holdings_alert_rules(text, positions)
    return positions, account, rules
