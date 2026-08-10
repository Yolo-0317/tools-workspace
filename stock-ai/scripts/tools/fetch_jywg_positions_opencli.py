#!/usr/bin/env python3
"""
东方财富证券网页持仓（jywg.18.cn）— OpenCLI 采集。

会话模型（与站点「在线时间」一致，最长约 3 小时）：
  1. 首次或过期：在 OpenCLI 自动化窗口手动登录（须选「3小时」在线时间 + 图形验证码）。
  2. 登录成功后本脚本拉取持仓；并写入 ~/.cache/stock-ai/jywg_session.json 记录过期时间。
  3. 过期后再次执行会提示重新登录；可用 --wait-login 轮询等待你完成登录。

禁止 HTTP 直联；仅 browser open + eval（与 fetch_eastmoney_quotes 一致）。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]

from scripts.tools.fetch_eastmoney_quotes import (  # noqa: E402
    _close_browser_if,
    _eval_js,
    _open_page,
    _run_opencli,
)

JYWG_POSITION_URL = "https://jywg.18.cn/Search/Position"
JYWG_LOGIN_URL = "https://jywg.18.cn/Login"
JYWG_LOGOUT_URL = "https://jywg.18.cn/Login?el=1&clear=1"
SESSION_TTL = timedelta(hours=3)
SESSION_CACHE = Path.home() / ".cache" / "stock-ai" / "jywg_session.json"

CHECK_PAGE_JS = r"""
JSON.stringify((() => {
  const path = location.pathname || "";
  if (/\/Login/i.test(path) || document.getElementById("txtZjzh")) {
    return { logged_in: false, page: "login", url: location.href };
  }
  if (/\/Search\/Position/i.test(path)) {
    const body = document.body.innerText || "";
    const hasHeader = body.includes("证券代码") || body.includes("证券名称");
    const hasRow = [...document.querySelectorAll("table tr")].some(tr => {
      const cells = [...tr.querySelectorAll("td")].map(td => (td.innerText || "").trim());
      return cells.length >= 11 && /^\\d{6}$/.test(cells[0]);
    });
    return { logged_in: hasHeader || hasRow, page: "position", url: location.href };
  }
  return { logged_in: false, page: path, url: location.href };
})())
"""

EXTRACT_POSITIONS_JS = r"""
JSON.stringify((() => {
  const account = {};
  document.querySelectorAll("#assest_cont td").forEach(td => {
    const t = (td.innerText || "").replace(/\s+/g, " ").trim();
    const parts = t.split(/\s+/);
    if (parts.length >= 2) {
      const val = parts[parts.length - 1];
      const key = parts.slice(0, -1).join("");
      if (/^[\d,.+-]+$/.test(val)) account[key] = val;
    }
  });
  const positions = [];
  document.querySelectorAll("table tr").forEach(tr => {
    const cells = [...tr.querySelectorAll("td")].map(td =>
      (td.innerText || "").replace(/\s+/g, " ").trim()
    );
    if (cells.length >= 11 && /^\d{6}$/.test(cells[0])) {
      positions.push({
        code: cells[0], name: cells[1], qty: cells[2], available: cells[3],
        cost: cells[4], price: cells[5], market_value: cells[6], pnl: cells[7],
        pnl_pct: cells[8], day_pnl: cells[9], day_pnl_pct: cells[10],
        action: cells[11] || ""
      });
    }
  });
  const user = (document.body.innerText.match(/([\u4e00-\u9fa5]+\(\d+\*+\d+\))/) || [])[1] || null;
  return {
    source: "jywg.18.cn-opencli",
    url: location.href,
    fetched_at: new Date().toISOString(),
    user,
    account,
    positions
  };
})())
"""


@dataclass
class SessionInfo:
    logged_in_at: datetime
    expires_at: datetime
    user: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "logged_in_at": self.logged_in_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "user": self.user,
            "ttl_hours": SESSION_TTL.total_seconds() / 3600,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionInfo | None:
        try:
            logged_in_at = datetime.fromisoformat(str(data["logged_in_at"]))
            expires_at = datetime.fromisoformat(str(data["expires_at"]))
            if logged_in_at.tzinfo is None:
                logged_in_at = logged_in_at.astimezone()
            if expires_at.tzinfo is None:
                expires_at = expires_at.astimezone()
            return cls(logged_in_at=logged_in_at, expires_at=expires_at, user=data.get("user"))
        except (KeyError, ValueError):
            return None


def _now() -> datetime:
    return datetime.now().astimezone()


def load_session_cache() -> SessionInfo | None:
    if not SESSION_CACHE.is_file():
        return None
    try:
        data = json.loads(SESSION_CACHE.read_text(encoding="utf-8"))
        return SessionInfo.from_dict(data)
    except (json.JSONDecodeError, OSError):
        return None


def save_session_cache(info: SessionInfo) -> None:
    SESSION_CACHE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_CACHE.write_text(
        json.dumps(info.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def clear_session_cache() -> None:
    if SESSION_CACHE.is_file():
        SESSION_CACHE.unlink()


def read_page_state() -> dict[str, Any]:
    raw = _eval_js(CHECK_PAGE_JS)
    return json.loads(raw)


def fetch_positions_payload() -> dict[str, Any]:
    raw = _eval_js(EXTRACT_POSITIONS_JS)
    return json.loads(raw)


def print_manual_login_help() -> None:
    print(
        """
请在 OpenCLI 弹出的浏览器窗口完成登录：
  1. 资金账号 + 交易密码
  2. 图形验证码（须人工输入，Agent 无法代填）
  3. 「在线时间」请选择 3小时（最长会话；15/30 分钟会更早掉线）
  4. 点击「登录」

勿用带 clear=1 的退出链接，除非你想清空会话。
登录成功后本脚本会自动继续；或另开终端执行（无 --wait-login）拉持仓。
""".strip(),
        file=sys.stderr,
    )


def session_status_message(info: SessionInfo | None) -> str:
    if info is None:
        return "本地无会话记录（尚未成功拉取或已清除）。"
    now = _now()
    if now >= info.expires_at:
        return f"会话可能已过期（记录过期于 {info.expires_at.astimezone().strftime('%Y-%m-%d %H:%M %Z')}）。"
    left = info.expires_at - now
    mins = int(left.total_seconds() // 60)
    return (
        f"会话记录有效约还剩 {mins} 分钟"
        f"（登录于 {info.logged_in_at.astimezone().strftime('%H:%M')}，"
        f"假定最长 {int(SESSION_TTL.total_seconds() // 3600)} 小时）。"
    )


def wait_until_logged_in(
    *,
    timeout_sec: float,
    poll_sec: float,
    open_login_first: bool,
) -> bool:
    url = JYWG_LOGIN_URL if open_login_first else JYWG_POSITION_URL
    _open_page(url)
    print_manual_login_help()
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        state = read_page_state()
        if state.get("logged_in"):
            if state.get("page") != "position":
                _open_page(JYWG_POSITION_URL)
                time.sleep(1)
                state = read_page_state()
            if state.get("logged_in"):
                return True
        time.sleep(poll_sec)
    return False


def run_fetch(
    *,
    wait_login: bool,
    wait_timeout: float,
    poll_sec: float,
    close_browser: bool,
    open_login_first: bool,
) -> dict[str, Any]:
    cached = load_session_cache()
    if cached and _now() >= cached.expires_at:
        print(f"警告：{session_status_message(cached)}", file=sys.stderr)

    _open_page(JYWG_POSITION_URL)
    time.sleep(1.5)
    state = read_page_state()

    if not state.get("logged_in"):
        clear_session_cache()
        if wait_login:
            if not wait_until_logged_in(
                timeout_sec=wait_timeout,
                poll_sec=poll_sec,
                open_login_first=open_login_first,
            ):
                raise RuntimeError(
                    f"等待登录超时（{wait_timeout:.0f}s）。请在 OpenCLI 窗口完成登录后重试。"
                )
        else:
            print_manual_login_help()
            raise RuntimeError(
                "未登录或会话已失效。请执行：\n"
                f"  uv run python -m scripts.tools.fetch_jywg_positions_opencli --wait-login\n"
                f"或在 OpenCLI 窗口打开 {JYWG_LOGIN_URL} 手动登录后再运行本脚本。"
            )

    payload = fetch_positions_payload()
    if not payload.get("positions"):
        raise RuntimeError("已登录但未解析到持仓表，页面结构可能变更。")

    now = _now()
    save_session_cache(
        SessionInfo(
            logged_in_at=now,
            expires_at=now + SESSION_TTL,
            user=payload.get("user"),
        )
    )
    payload["session"] = load_session_cache().to_dict() if load_session_cache() else {}
    _close_browser_if(close_browser)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="东方财富证券网页持仓（jywg.18.cn · OpenCLI）；首次手动登录，会话最长约 3 小时。"
    )
    parser.add_argument(
        "--wait-login",
        action="store_true",
        help="打开登录页并轮询，直到你在 OpenCLI 窗口完成登录",
    )
    parser.add_argument(
        "--wait-timeout",
        type=float,
        default=600,
        help="--wait-login 最长等待秒数（默认 600）",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=5,
        help="轮询间隔秒数（默认 5）",
    )
    parser.add_argument(
        "--open-login",
        action="store_true",
        help="--wait-login 时先打开 /Login 而非持仓页",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="仅打印本地会话缓存状态",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="删除本地 jywg_session.json",
    )
    parser.add_argument(
        "--close-browser",
        action="store_true",
        help="结束后关闭 OpenCLI 浏览器",
    )
    parser.add_argument("-o", "--output", type=Path, help="将 JSON 写入文件")
    parser.add_argument(
        "--sync-db",
        action="store_true",
        help="拉取成功后写入 MySQL portfolio_positions / portfolio_account（不改 alert_rules）",
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="与 --sync-db 联用：再写入 slot=sync 的每日快照",
    )
    args = parser.parse_args()

    if args.clear_cache:
        clear_session_cache()
        print(f"已清除 {SESSION_CACHE}")
        return 0

    if args.status:
        info = load_session_cache()
        print(session_status_message(info))
        if info:
            print(json.dumps(info.to_dict(), ensure_ascii=False, indent=2))
        return 0

    try:
        payload = run_fetch(
            wait_login=args.wait_login,
            wait_timeout=args.wait_timeout,
            poll_sec=args.poll,
            close_browser=args.close_browser,
            open_login_first=args.open_login,
        )
    except (RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"失败：{exc}", file=sys.stderr)
        return 2

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    out_path = args.output or (ROOT / "output" / "jywg_positions_latest.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text + "\n", encoding="utf-8")
    print(f"已写入 {out_path}", file=sys.stderr)

    n = len(payload.get("positions") or [])
    print(f"持仓 {n} 条；{session_status_message(load_session_cache())}", file=sys.stderr)

    if args.sync_db:
        from scripts.tools.jywg_portfolio_sync import sync_jywg_payload

        stats = sync_jywg_payload(payload)
        print(
            f"MySQL: positions={stats['positions']} account={stats['account']} (东方财富证券)",
            file=sys.stderr,
        )
        if args.snapshot:
            from scripts.tools.portfolio_db import save_portfolio_daily_snapshot

            for slot in ("sync", "eod"):
                snap = save_portfolio_daily_snapshot(snapshot_slot=slot)
                print(
                    f"快照 {slot}/{snap['snapshot_date']} "
                    f"positions={snap['positions']}",
                    file=sys.stderr,
                )

    if not args.sync_db:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
