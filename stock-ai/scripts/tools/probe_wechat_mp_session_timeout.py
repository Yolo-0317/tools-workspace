#!/usr/bin/env python3
"""每隔 N 分钟用 OpenCLI 刷新公众号后台并检测是否仍登录（会话超时实验）。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.fetch_eastmoney_quotes import _eval_js, _open_page, _run_opencli  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TZ = ZoneInfo("Asia/Shanghai")

HOME_URL = (
    "https://mp.weixin.qq.com/cgi-bin/home?t=home/index&token=655713719&lang=zh_CN"
)

PROBE_JS = r"""
JSON.stringify((() => {
  const t = document.body.innerText || "";
  const href = location.href || "";
  const logged_out =
    t.includes("请重新登录") ||
    t.includes("扫码登录") ||
    href.includes("/login") ||
    href.includes("action=login");
  return {
    logged_in: !logged_out,
    url: href,
    title: document.title,
    account_hint: (t.match(/通知中心\s*\n([^\n]+)/) || [])[1] || null,
    has_dashboard: !!document.querySelector("#js_index_menu"),
  };
})())
"""


def _now() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")


def _probe(*, url: str, click_home: bool) -> dict:
    _open_page(url, label="mp home")
    _run_opencli(["browser", "wait", "time", "3"], timeout=10)
    if click_home:
        _run_opencli(["browser", "click", "9"], timeout=15)
        _run_opencli(["browser", "wait", "time", "2"], timeout=10)
    raw = _eval_js(PROBE_JS, timeout=30)
    return json.loads(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenCLI 轮询公众号后台登录态")
    parser.add_argument("--url", default=HOME_URL, help="后台首页 URL（含 token）")
    parser.add_argument("--interval-min", type=float, default=5.0, help="探测间隔（分钟）")
    parser.add_argument("--max-hours", type=float, default=48.0, help="最长运行小时数")
    parser.add_argument("--log", default=str(ROOT / "output" / "wechat_mp_session_probe.log"))
    parser.add_argument("--no-click", action="store_true", help="仅刷新，不点侧边栏首页")
    args = parser.parse_args()

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    interval_sec = max(60.0, args.interval_min * 60.0)
    deadline = time.time() + max(1.0, args.max_hours * 3600.0)
    start_mono = time.monotonic()
    start_wall = _now()
    probe_n = 0

    def log(line: str) -> None:
        msg = f"[{_now()}] {line}"
        print(msg, flush=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(msg + "\n")

    log(f"SESSION_PROBE_START url={args.url} interval={args.interval_min}min")
    log(f"SESSION_PROBE_START wall={start_wall}")

    while time.time() < deadline:
        probe_n += 1
        elapsed_min = (time.monotonic() - start_mono) / 60.0
        try:
            st = _probe(url=args.url, click_home=not args.no_click)
        except Exception as exc:
            log(f"probe#{probe_n} elapsed={elapsed_min:.1f}min ERROR {exc}")
            time.sleep(min(60.0, interval_sec))
            continue

        logged_in = bool(st.get("logged_in"))
        account = st.get("account_hint") or "?"
        log(
            f"probe#{probe_n} elapsed={elapsed_min:.1f}min "
            f"logged_in={logged_in} account={account} url={st.get('url', '')[:120]}"
        )

        if not logged_in:
            log(
                f"SESSION_LOGGED_OUT after={elapsed_min:.1f}min "
                f"probes={probe_n} start={start_wall}"
            )
            return 0

        sleep_until = time.time() + interval_sec
        while time.time() < sleep_until:
            time.sleep(min(30.0, sleep_until - time.time()))

    log(f"SESSION_PROBE_TIMEOUT max_hours={args.max_hours} probes={probe_n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
