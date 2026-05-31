#!/usr/bin/env python3
"""从持仓执行卡同步 portfolio_positions / portfolio_account / alert_rules 到 MySQL。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.holdings_card_parser import parse_card
from scripts.tools.holdings_context import AGENT_HOLDINGS, DEFAULT_HOLDINGS
from scripts.tools.portfolio_db import sync_from_card


def resolve_card(path: Path | None) -> Path:
    if path is not None:
        return path
    if AGENT_HOLDINGS.exists():
        return AGENT_HOLDINGS
    return DEFAULT_HOLDINGS


def main() -> int:
    parser = argparse.ArgumentParser(description="从持仓执行卡同步 MySQL 持仓与监控规则")
    parser.add_argument("--card", type=Path, default=None, help="执行卡路径")
    parser.add_argument("--dry-run", action="store_true", help="只解析不写入")
    args = parser.parse_args()

    card_path = resolve_card(args.card)
    if not card_path.exists():
        print(f"❌ 未找到执行卡: {card_path}", file=sys.stderr)
        return 1

    text = card_path.read_text(encoding="utf-8")
    positions, account, rules = parse_card(text)

    if not positions:
        print("❌ 执行卡未解析到股票持仓", file=sys.stderr)
        return 1

    print(f"执行卡: {card_path}")
    print(f"持仓: {len(positions)} 条")
    for p in positions:
        print(f"  {p.name}({p.code}) {p.shares}股 @ {p.cost:.3f}")
    print(f"账户: 总资产={account.total_assets} 可用={account.available_cash} 仓位={account.position_ratio}")
    print(f"监控规则: {len(rules)} 条")

    if args.dry_run:
        return 0

    stats = sync_from_card(positions, account, rules)
    print(
        f"✅ 已同步 MySQL: positions={stats['positions']} "
        f"account={stats['account']} rules={stats['rules']}"
    )
    try:
        from scripts.tools.portfolio_db import save_portfolio_daily_snapshot

        snap = save_portfolio_daily_snapshot(snapshot_slot="sync")
        print(
            f"📸 持仓快照 sync/{snap['snapshot_date']} positions={snap['positions']}"
        )
    except Exception as exc:  # noqa: BLE001
        from scripts.tools.dashboard_data import log_snapshot_alert

        log_snapshot_alert(f"FAIL slot=sync error={exc}")
        print(f"⚠️ 持仓快照失败: {exc}", file=sys.stderr)
        print("   已写入 logs/snapshot_alerts.log", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
