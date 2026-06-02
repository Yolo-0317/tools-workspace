"""执行卡「买入决策 2.0」候选队列 — 与 investment-agent/持仓执行卡.md 同步。"""

from __future__ import annotations

from typing import Any

# 解析失败时的兜底（勿与 md 长期双轨维护）
_FALLBACK_PROBE_BUYS: dict[str, dict[str, str]] = {
    "603697": {
        "name": "有友食品",
        "priority": "P-买2",
        "trigger": "回踩 10.70～10.90，单日涨幅 <3%",
        "shares": "100",
        "stop": "10.30",
    },
}

_FALLBACK_TRIM_HINTS: dict[str, dict[str, str]] = {
    "600098": {
        "name": "广州发展",
        "priority": "P1",
        "trigger": "7.75～8.20",
        "action": "减 200 股（腾现金、降仓位）",
    },
}


def _execution_card_path():
    from scripts.tools.holdings_context import AGENT_HOLDINGS, DEFAULT_HOLDINGS

    if AGENT_HOLDINGS.exists():
        return AGENT_HOLDINGS
    return DEFAULT_HOLDINGS


def _read_execution_card_text() -> str:
    path = _execution_card_path()
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_execution_card_probe_buys() -> dict[str, dict[str, str]]:
    """读持仓执行卡.md「候选买入队列」。"""
    text = _read_execution_card_text()
    if not text:
        return dict(_FALLBACK_PROBE_BUYS)
    try:
        from scripts.tools.holdings_card_parser import parse_execution_card_probe_buys

        parsed = parse_execution_card_probe_buys(text)
        if parsed:
            return parsed
    except Exception:
        pass
    return dict(_FALLBACK_PROBE_BUYS)


def load_execution_card_trim_hints() -> dict[str, dict[str, str]]:
    text = _read_execution_card_text()
    if not text:
        return dict(_FALLBACK_TRIM_HINTS)
    try:
        from scripts.tools.holdings_card_parser import parse_execution_card_trim_hints

        parsed = parse_execution_card_trim_hints(text)
        if parsed:
            return parsed
    except Exception:
        pass
    return dict(_FALLBACK_TRIM_HINTS)


def _code6(code: str) -> str:
    return str(code).split(".")[0].zfill(6)


def _row_code(row: dict[str, Any]) -> str:
    return _code6(str(row.get("代码") or row.get("code") or row.get("ts_code") or ""))


def _row_score(row: dict[str, Any]) -> float:
    try:
        return float(row.get("总分") or row.get("score") or 0)
    except (TypeError, ValueError):
        return 0.0


BUY_ACTIONS = frozenset({"强势关注", "观察买入", "小仓埋伏"})


def _selection_probe_trigger(row: dict[str, Any]) -> str:
    card = str(row.get("执行卡触发") or "").strip()
    if card:
        return card
    action = str(row.get("建议动作") or "").strip()
    tags = str(row.get("策略标签") or "").strip()
    if tags and action:
        return f"{action} · {tags}"
    return action or tags or "—"


def _selection_row_to_probe(row: dict[str, Any], rank: int) -> dict[str, str]:
    code = _row_code(row)
    md = load_execution_card_probe_buys().get(code, {})
    trigger = str(row.get("执行卡触发") or md.get("trigger") or "").strip()
    if not trigger:
        trigger = _selection_probe_trigger(row)
    priority = str(row.get("执行卡优先级") or md.get("priority") or f"选股#{rank}")
    stop = str(row.get("执行卡止损") or md.get("stop") or "—")
    shares = str(row.get("执行卡股数") or md.get("shares") or "100")
    name = str(row.get("名称") or row.get("name") or md.get("name") or code)
    payload: dict[str, str] = {
        "code": code,
        "name": name,
        "kind": "probe_buy",
        "priority": priority,
        "trigger": trigger,
        "shares": shares,
        "stop": stop,
        "strategy": str(row.get("strategy") or ""),
        "score": str(_row_score(row)),
        "action": str(row.get("建议动作") or ""),
    }
    status = str(row.get("执行卡状态") or "").strip()
    if status:
        payload["status"] = status
    return payload


def execution_card_buys_from_selection(
    rows: list[dict[str, Any]],
    *,
    holding_codes: set[str] | list[str] | None = None,
    top_n: int = 8,
) -> list[dict[str, str]]:
    """
    执行卡试探买入：从当日选股列表挑候选（按分数，去重，排除已持仓）。
    减仓提示仍读 md P1。
    """
    holdings = {_code6(c) for c in (holding_codes or [])}
    md_probe = load_execution_card_probe_buys()
    best_by_code: dict[str, dict[str, Any]] = {}

    for row in rows:
        code = _row_code(row)
        if len(code) != 6 or code in holdings:
            continue
        action = str(row.get("建议动作") or "")
        has_card = bool(row.get("执行卡触发") or row.get("执行卡优先级"))
        if action not in BUY_ACTIONS and not has_card and code not in md_probe:
            continue
        prev = best_by_code.get(code)
        if prev is None or _row_score(row) > _row_score(prev):
            best_by_code[code] = row

    ranked = sorted(
        best_by_code.values(),
        key=lambda row: (
            1 if (
                row.get("执行卡触发")
                or row.get("执行卡优先级")
                or _row_code(row) in md_probe
            ) else 0,
            _row_score(row),
        ),
        reverse=True,
    )[:top_n]
    probes = [_selection_row_to_probe(row, i) for i, row in enumerate(ranked, 1)]
    trims = [{**meta, "code": code, "kind": "trim"} for code, meta in load_execution_card_trim_hints().items()]
    return probes + trims


def execution_card_buys_payload() -> list[dict[str, str]]:
    """Home Hub / API：当前执行卡可试探买入与减仓提示（读持仓执行卡.md）。"""
    probe = load_execution_card_probe_buys()
    trim = load_execution_card_trim_hints()
    buys = [{**meta, "code": code, "kind": "probe_buy"} for code, meta in probe.items()]
    trims = [{**meta, "code": code, "kind": "trim"} for code, meta in trim.items()]
    return buys + trims


def apply_execution_card_b_tier(
    rows: list[dict[str, Any]],
    account_position_pct: float,
    *,
    probe_only_pct: float = 60.0,
    no_buy_pct: float = 75.0,
    chase_pct_max: float = 5.0,
    buy_actions: frozenset[str] | None = None,
) -> int:
    """
    B 档（60%～75%）：执行卡 P-买1/买2 在池内且未禁追高 → 建议动作升为「小仓埋伏」。
    返回被提升的条数。
    """
    if buy_actions is None:
        buy_actions = frozenset({"强势关注", "观察买入", "小仓埋伏"})

    if not (probe_only_pct < account_position_pct <= no_buy_pct):
        return 0

    probe_buys = load_execution_card_probe_buys()
    n = 0
    for row in rows:
        code = _code6(str(row.get("代码") or row.get("code") or ""))
        meta = probe_buys.get(code)
        if not meta:
            continue
        pct = float(row.get("涨幅%") or row.get("pct_chg") or 0)
        action = str(row.get("建议动作") or "")
        if pct > chase_pct_max:
            row["执行卡优先级"] = meta["priority"]
            row["执行卡触发"] = meta["trigger"]
            row["执行卡止损"] = meta["stop"]
            row["执行卡股数"] = meta["shares"]
            row["执行卡状态"] = f"等回踩（当日涨幅>{chase_pct_max:.0f}% 禁建仓）"
            continue
        if action == "谨慎回避":
            continue
        if action in buy_actions and action == "小仓埋伏":
            row.setdefault("执行卡优先级", meta["priority"])
            row.setdefault("执行卡触发", meta["trigger"])
            row.setdefault("执行卡止损", meta["stop"])
            row.setdefault("执行卡股数", meta["shares"])
            continue
        row["建议动作"] = "小仓埋伏"
        row["执行卡优先级"] = meta["priority"]
        row["执行卡触发"] = meta["trigger"]
        row["执行卡止损"] = meta["stop"]
        row["执行卡股数"] = meta["shares"]
        row["名称"] = row.get("名称") or meta["name"]
        n += 1
    return n


def reapply_position_tier_actions(
    rows: list[dict[str, Any]],
    account_position_pct: float,
    *,
    assign_action_fn: Any,
    cap_action_fn: Any,
    chase_pct_max: float = 5.0,
    buy_actions: frozenset[str] | None = None,
    holdings_codes: set[str] | None = None,
) -> None:
    """按当前仓位重算建议动作（需 combined 行含 总分、策略标签、大盘环境）。"""
    if buy_actions is None:
        buy_actions = frozenset({"强势关注", "观察买入", "小仓埋伏"})
    holdings_codes = holdings_codes or set()

    for row in rows:
        code = _code6(str(row.get("代码") or ""))
        tags = str(row.get("策略标签") or "")
        tag_set = {t.strip() for t in tags.split(",") if t.strip()}
        has_signal = bool(
            tag_set
            & {"大底突破", "三连阳", "空中加油", "早埋伏", "三力合一"}
            | {t for t in tag_set if t.startswith("观察-")}
        )
        if not has_signal:
            continue

        score = float(row.get("总分") or 0)
        regime = str(row.get("大盘环境") or "neutral")
        is_ambush_only = "早埋伏" in tag_set and not (
            tag_set & {"大底突破", "三连阳", "空中加油"}
        )
        pct = float(row.get("涨幅%") or 0)

        action = assign_action_fn(score, is_ambush_only=is_ambush_only, regime=regime)
        if code in holdings_codes:
            action = "持有" if action in buy_actions else action
        else:
            action = cap_action_fn(action, pct, account_position_pct)
            if pct > chase_pct_max and action in buy_actions:
                action = "继续观察"
            if pct < 0 and action not in buy_actions:
                action = "谨慎回避"

        row["建议动作"] = action


def ensure_card_probe_in_watch(
    watch_rows: list[dict[str, Any]],
    combined_rows: list[dict[str, Any]],
    latest_by_code: dict[str, dict[str, Any]],
    account_position_pct: float,
    *,
    market_regime: str = "neutral",
    chase_pct_max: float = 5.0,
) -> int:
    """
    执行卡 P-买1/买2 若未进 A/B 轨，补一条 watch 行（仅行情摘要 + 执行卡条件）。
    """
    probe_buys = load_execution_card_probe_buys()
    in_pool = {
        _code6(str(r.get("代码") or ""))
        for r in (*watch_rows, *combined_rows)
    }
    added = 0
    for code, meta in probe_buys.items():
        if code in in_pool:
            continue
        bar = latest_by_code.get(code)
        if not bar:
            continue
        pct = float(bar.get("pct_chg") or 0)
        close = float(bar.get("close") or 0)
        amount_wan = float(bar.get("amount_wan") or 0)
        action = "继续观察"
        if 60.0 < account_position_pct <= 75.0 and pct <= chase_pct_max:
            action = "小仓埋伏"
        row: dict[str, Any] = {
            "代码": code,
            "名称": meta["name"],
            "收盘价": close,
            "涨幅%": pct,
            "成交额(万)": round(amount_wan, 2),
            "策略标签": "执行卡关注",
            "标签数": 1,
            "总分": 0,
            "大盘环境": market_regime,
            "建议动作": action,
            "执行卡优先级": meta["priority"],
            "执行卡触发": meta["trigger"],
            "执行卡止损": meta["stop"],
            "执行卡股数": meta["shares"],
        }
        if pct > chase_pct_max:
            row["执行卡状态"] = f"等回踩（当日涨幅>{chase_pct_max:.0f}% 禁建仓）"
        watch_rows.append(row)
        added += 1
    if added and 60.0 < account_position_pct <= 75.0:
        apply_execution_card_b_tier(watch_rows, account_position_pct, chase_pct_max=chase_pct_max)
    return added
