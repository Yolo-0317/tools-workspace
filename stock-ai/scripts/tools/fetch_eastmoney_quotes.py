#!/usr/bin/env python3
"""
东方财富数据采集（唯一入口：OpenCLI Browser）。

禁止 Python 侧 HTTP/API 直联东财；所有行情、K 线、指数、资金、快讯均在浏览器上下文中采集。
K 线历史通过页面 JSONP 注入（与东财网页同机制），不经 requests/urllib。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

EXTRACT_QUOTE_JS = r"""
JSON.stringify({
  pathCode: ((document.location.pathname.match(/(\d{6})/) || [])[1] || ''),
  name: (document.querySelector('.quote_title_name')?.innerText || '').trim(),
  priceText: (document.querySelector('.zxj')?.innerText || '').trim(),
  zdfText: (document.querySelector('.zd')?.innerText || '').trim(),
  infoText: document.querySelector('.brief_info_c')?.innerText || '',
  fundFlowText: document.querySelector('.zjl_charts')?.innerText || '',
  orderBookText: document.querySelector('.sider_quote_price2')?.innerText || ''
})
"""

EXTRACT_ZJLX_JS = r"""
JSON.stringify((document.body.innerText.match(/主力净流入[\s\S]{0,600}/) || [''])[0])
"""

EXTRACT_KUAIXUN_JS = r"""
(() => {
  const items = [];
  document.querySelectorAll('.news_item').forEach(el => {
    const time = el.querySelector('.news_time')?.innerText?.trim() || '';
    const a = el.querySelector('a[href*="/a/"]');
    const text = (el.querySelector('.news_detail_text')?.innerText || a?.innerText || '')
      .replace(/\s+/g, ' ').trim();
    const href = a?.href || '';
    const ct = el.querySelector('.comment_text')?.innerText?.trim() || '';
    const cm = ct.match(/评论\s*(\d+)/);
    const comment = cm ? parseInt(cm[1], 10) : 0;
    if (text && href) items.push({ time, text, href, comment });
  });
  const seen = new Set();
  return JSON.stringify(items.filter(x => {
    if (seen.has(x.href)) return false;
    seen.add(x.href);
    return true;
  }));
})()
"""


@dataclass
class EastmoneyQuote:
    code: str
    name: str
    price: float
    change_amt: float
    change_pct: float
    source: str = "eastmoney-opencli"


@dataclass
class EastmoneySopSnapshot:
    code: str
    name: str
    price: float
    change_amt: float
    change_pct: float
    info_text: str
    fund_flow_text: str
    source: str = "eastmoney-opencli-sop"

    def label(self, key: str) -> str | None:
        return _parse_label_value(self.info_text, key)

    def to_kline_row(self, date_str: str | None = None) -> list[str]:
        from datetime import date

        d = date_str or date.today().isoformat()
        open_ = _parse_float(self.label("今开")) or self.price
        high = _parse_float(self.label("最高")) or self.price
        low = _parse_float(self.label("最低")) or self.price
        vol = _parse_float(self.label("成交量")) or 0.0
        amount = _parse_float(self.label("成交额")) or 0.0
        return [
            d,
            str(open_),
            str(self.price),
            str(high),
            str(low),
            str(vol),
            str(amount),
            "",
            str(self.change_pct),
        ]


def code6(code: str) -> str:
    return re.sub(r"\D", "", str(code))[:6].zfill(6)


def code_to_prefix(code: str) -> str:
    c = code6(code)
    return "sh" if c.startswith(("6", "5")) else "sz"


def quote_url(code: str) -> str:
    c = code6(code)
    return f"https://quote.eastmoney.com/{code_to_prefix(c)}{c}.html"


def index_url(code: str) -> str:
    """指数页：zs000001 / zs399001。"""
    return f"https://quote.eastmoney.com/zs{code6(code)}.html"


def fund_flow_url(code: str) -> str:
    return f"https://data.eastmoney.com/zjlx/{code6(code)}.html"


def kuaixun_url() -> str:
    return "https://kuaixun.eastmoney.com/"


def secid(code: str) -> str:
    c = code6(code)
    if c.startswith(("00", "30", "301", "002", "15", "16", "18", "8")):
        return f"0.{c}"
    if c.startswith(("60", "688", "50", "51", "56", "58")):
        return f"1.{c}"
    raise ValueError(f"无法识别证券代码的市场类型: {code}")


_INDEX_SECIDS = {
    "000001": "1.000001",
    "399001": "0.399001",
    "000688": "1.000688",
}


def index_secid(code: str) -> str:
    c = code6(code)
    try:
        return _INDEX_SECIDS[c]
    except KeyError as exc:
        raise ValueError(f"不支持的大盘指数: {c}") from exc


def _strip_proxy_env(env: dict[str, str]) -> dict[str, str]:
    for key in (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
        "http_proxy", "https_proxy", "all_proxy",
    ):
        env.pop(key, None)
    env["NO_PROXY"] = "*"
    return env


def _node_version(path: Path) -> tuple[int, ...]:
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", path.name)
    if match is None:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def resolve_opencli_bin(*, nvm_root: Path | None = None) -> str:
    """Resolve OpenCLI from explicit config, PATH, then installed nvm versions."""

    configured = os.getenv("OPENCLI_BIN")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        raise FileNotFoundError(f"OPENCLI_BIN 不可执行: {candidate}")

    path_candidate = shutil.which("opencli")
    if path_candidate:
        return path_candidate

    root = nvm_root or Path.home() / ".nvm" / "versions" / "node"
    candidates = [
        version / "bin" / "opencli"
        for version in root.glob("v*")
        if _node_version(version)
        and (version / "bin" / "opencli").is_file()
        and os.access(version / "bin" / "opencli", os.X_OK)
    ]
    if candidates:
        return str(max(candidates, key=lambda item: _node_version(item.parents[1])))
    raise FileNotFoundError(
        "未找到 opencli；请运行 npm install -g @jackwener/opencli，或配置 OPENCLI_BIN"
    )


def _opencli_bin() -> str:
    return resolve_opencli_bin()


_BROWSER_SUBCOMMANDS = frozenset(
    {
        "analyze",
        "back",
        "bind",
        "check",
        "click",
        "close",
        "console",
        "dblclick",
        "dialog",
        "drag",
        "eval",
        "extract",
        "fill",
        "find",
        "focus",
        "frames",
        "get",
        "hover",
        "init",
        "keys",
        "network",
        "open",
        "screenshot",
        "scroll",
        "select",
        "state",
        "tab",
        "type",
        "unbind",
        "uncheck",
        "upload",
        "verify",
        "wait",
    }
)


def _opencli_browser_session() -> str:
    """统一自动化会话名，复用同一 Chrome 窗口（默认 stock）。"""
    return os.getenv("OPENCLI_BROWSER_SESSION", "stock")


def _browser_reuse_tab() -> bool:
    return os.getenv("OPENCLI_BROWSER_REUSE_TAB", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _browser_new_tab() -> bool:
    return os.getenv("OPENCLI_BROWSER_NEW_TAB", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _browser_if_exists_mode() -> str:
    """已有自动化窗时如何导航：navigate=同标签跳转（默认）；tab=新标签（易堆 Chrome 分组）。"""
    mode = (os.getenv("OPENCLI_BROWSER_IF_EXISTS") or "navigate").strip().lower()
    if mode in ("navigate", "reuse", "same", "open"):
        return "navigate"
    if mode in ("tab", "new_tab", "new-tab"):
        return "tab"
    return "tab"


def _browser_close_prev_tab() -> bool:
    return os.getenv("OPENCLI_BROWSER_CLOSE_PREV_TAB", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _tab_list_timeout() -> float:
    try:
        return max(12.0, float(os.getenv("OPENCLI_TAB_LIST_TIMEOUT", "45")))
    except ValueError:
        return 45.0


def _list_browser_tabs() -> list[dict]:
    stdout, _, rc = _run_opencli(["browser", "tab", "list"], timeout=_tab_list_timeout())
    if rc != 0 or not stdout:
        return []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _browser_session_has_tabs() -> bool:
    return any(isinstance(t, dict) and t.get("page") for t in _list_browser_tabs())


def _active_tab_target_id(tabs: list[dict]) -> str | None:
    for tab in tabs:
        if tab.get("active") and tab.get("page"):
            return str(tab["page"])
    for tab in tabs:
        if tab.get("page"):
            return str(tab["page"])
    return None


def _browser_window_args() -> list[str]:
    mode = (os.getenv("OPENCLI_BROWSER_WINDOW") or "background").strip().lower()
    if mode in ("", "none", "off", "default"):
        return []
    if mode not in ("foreground", "background"):
        return []
    return ["--window", mode]


def _cleanup_browser_sessions() -> list[str]:
    raw = os.getenv("OPENCLI_BROWSER_CLEANUP_SESSIONS", "stock,default,mp")
    return [s.strip() for s in raw.split(",") if s.strip()]


def _with_browser_session(args: list[str]) -> list[str]:
    """OpenCLI 1.8+：browser <session> [--window mode] <cmd>；1.7 为 browser <cmd>。"""
    if len(args) < 2 or args[0] != "browser":
        return args
    win = _browser_window_args()

    def _wrap(session: str, rest: list[str]) -> list[str]:
        cmd = rest[0] if rest else ""
        use_win = win and cmd in _BROWSER_SUBCOMMANDS and cmd not in ("bind", "unbind")
        if use_win:
            return ["browser", session, *win, *rest]
        return ["browser", session, *rest]

    if args[1] in _BROWSER_SUBCOMMANDS:
        return _wrap(_opencli_browser_session(), args[1:])
    if len(args) >= 3 and args[2] in _BROWSER_SUBCOMMANDS:
        return _wrap(args[1], args[2:])
    return args


def _run_opencli(args: list[str], *, timeout: float = 60) -> tuple[str, str, int]:
    bin_path = _opencli_bin()
    if not Path(bin_path).exists():
        raise FileNotFoundError(f"未找到 opencli: {bin_path}")

    env = _strip_proxy_env(os.environ.copy())
    nvm_bin = str(Path(bin_path).parent)
    env["PATH"] = f"{nvm_bin}:{env.get('PATH', '')}"

    proc = subprocess.run(
        [bin_path, *_with_browser_session(args)],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return proc.stdout.strip(), proc.stderr.strip(), proc.returncode


def _browser_close_tabs_on_release() -> bool:
    return os.getenv("OPENCLI_BROWSER_CLOSE_TABS_ON_RELEASE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def close_all_session_tabs(*, session: str | None = None) -> None:
    """关闭会话内全部 OpenCLI 托管标签（减轻 Chrome「标签分组」堆积）。"""
    sess = (session or _opencli_browser_session()).strip()
    for _ in range(12):
        stdout, _, rc = _run_opencli(["browser", sess, "tab", "list"], timeout=_tab_list_timeout())
        if rc != 0 or not stdout:
            break
        try:
            tabs = json.loads(stdout)
        except json.JSONDecodeError:
            break
        if not isinstance(tabs, list) or not tabs:
            break
        for tab in tabs:
            if not isinstance(tab, dict):
                continue
            page_id = tab.get("page")
            if not page_id:
                continue
            try:
                _run_opencli(
                    ["browser", sess, "tab", "close", str(page_id)],
                    timeout=10,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired, RuntimeError):
                pass


def release_browser_session(
    *,
    session: str | None = None,
    close_tabs: bool | None = None,
) -> None:
    """用完释放：先关全部 tab，再 browser close 释放 lease。"""
    sess = (session or _opencli_browser_session()).strip()
    if close_tabs if close_tabs is not None else _browser_close_tabs_on_release():
        close_all_session_tabs(session=sess)
    try:
        _run_opencli(["browser", sess, "close"], timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired, RuntimeError):
        pass


def force_close_opencli_browser(*, rounds: int = 3) -> None:
    """关闭各会话全部 tab + lease（可多轮）。不关 Chrome 本体；见 opencli_browser_cleanup.sh。"""
    import time

    sessions = _cleanup_browser_sessions()
    for _ in range(max(1, rounds)):
        for sess in sessions:
            release_browser_session(session=sess, close_tabs=True)
        time.sleep(0.25)


def _reset_browser() -> None:
    force_close_opencli_browser(rounds=2)


def _close_browser_if(enabled: bool) -> None:
    if enabled:
        force_close_opencli_browser(rounds=3)


def _reset_browser_if(enabled: bool) -> None:
    if not enabled:
        return
    if _browser_reuse_tab() and os.getenv("OPENCLI_BROWSER_FORCE_RESET", "0").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return
    _reset_browser()


def _maybe_close_before_nav() -> None:
    """复用标签时跳过 close，避免每次导航都新开自动化窗。"""
    if not _browser_reuse_tab():
        release_browser_session(close_tabs=True)


def _wait_page_ready(*, fallback_seconds: float = 2.0, selector: str = ".brief_info_c") -> None:
    """优先等元素，失败则回退固定等待。"""
    _, _, rc = _run_opencli(
        ["browser", "wait", "selector", selector, "8"],
        timeout=12,
    )
    if rc != 0:
        wait_arg = str(max(1, int(round(fallback_seconds))))
        _run_opencli(["browser", "wait", "time", wait_arg], timeout=10)


def _parse_label_value(text: str, label: str) -> str | None:
    match = re.search(rf"{re.escape(label)}[：:\s]*([^\t\n]+)", text)
    if not match:
        return None
    value = match.group(1).strip()
    if value in {"", "-", "--"}:
        return None
    return value


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.replace(",", "").replace("%", "").replace("+", "").strip()
    if cleaned in {"", "-", "--"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_zdf(zdf_text: str) -> tuple[float | None, float | None]:
    text = (zdf_text or "").replace(" ", "")
    if not text or text in {"-", "--"}:
        return None, None

    neg_match = re.fullmatch(r"(-?\d+(?:\.\d+)?)(-(\d+(?:\.\d+)?))%", text)
    if neg_match and neg_match.group(1).startswith("-"):
        return float(neg_match.group(1)), -float(neg_match.group(3))

    pct_match = re.search(r"(-?\d+(?:\.\d+)?)%$", text)
    if not pct_match:
        return None, None
    change_pct = float(pct_match.group(1))
    amt_part = text[: pct_match.start()]
    if not amt_part:
        return None, change_pct

    pct_num = pct_match.group(1).lstrip("-")
    if pct_num and amt_part.endswith(pct_num):
        amt_part = amt_part[: -len(pct_num)]
    amt_match = re.search(r"(-?\d+(?:\.\d+)?)$", amt_part)
    change_amt = float(amt_match.group(1)) if amt_match else None
    return change_amt, change_pct


def _compute_change(price: float, prev_close: float | None) -> tuple[float, float]:
    if prev_close is None or prev_close <= 0:
        return 0.0, 0.0
    change_amt = round(price - prev_close, 4)
    change_pct = round(change_amt / prev_close * 100, 2)
    return change_amt, change_pct


def parse_quote_payload(code: str, payload: dict[str, str]) -> EastmoneyQuote | None:
    c = code6(code)
    name = (payload.get("name") or c).strip() or c
    info_text = payload.get("infoText") or ""

    price = _parse_float(payload.get("priceText"))
    if price is None:
        for label in ("最新", "最新价"):
            price = _parse_float(_parse_label_value(info_text, label))
            if price is not None:
                break
    if price is None:
        return None

    prev_close = _parse_float(_parse_label_value(info_text, "昨收"))
    if prev_close is not None and prev_close > 0:
        change_amt, change_pct = _compute_change(price, prev_close)
    else:
        change_amt, change_pct = 0.0, 0.0
        parsed_amt, parsed_pct = _parse_zdf(payload.get("zdfText") or "")
        if parsed_pct is not None:
            change_pct = parsed_pct
        if parsed_amt is not None:
            change_amt = parsed_amt

    return EastmoneyQuote(
        code=c,
        name=name,
        price=price,
        change_amt=change_amt,
        change_pct=change_pct,
    )


def parse_sop_snapshot(code: str, payload: dict[str, str]) -> EastmoneySopSnapshot | None:
    quote = parse_quote_payload(code, payload)
    if quote is None:
        return None
    return EastmoneySopSnapshot(
        code=quote.code,
        name=quote.name,
        price=quote.price,
        change_amt=quote.change_amt,
        change_pct=quote.change_pct,
        info_text=payload.get("infoText") or "",
        fund_flow_text=payload.get("fundFlowText") or "",
    )


def parse_fund_flow_text(text: str) -> dict[str, float | None]:
    main_net = None
    main_pct = None
    m = re.search(r"主力净流入[：:\s]*([\-]?\d+(?:\.\d+)?)", text)
    if m:
        main_net = float(m.group(1))
    m2 = re.search(r"主力净比[：:\s]*([\-]?\d+(?:\.\d+)?)", text)
    if m2:
        main_pct = float(m2.group(1))
    return {"main_net_inflow": main_net, "main_net_pct": main_pct}


def _resolve_page_nav_mode(*, new_tab: bool | None) -> str:
    """open=首窗或当前标签跳转；tab_new=已有窗时新开标签。"""
    if new_tab is True:
        return "tab_new"
    if new_tab is False:
        return "open"
    if _browser_new_tab():
        return "tab_new" if _browser_session_has_tabs() else "open"
    if _browser_if_exists_mode() == "navigate":
        return "navigate"
    return "tab_new" if _browser_session_has_tabs() else "open"


def _navigate_browser_url(url: str, mode: str) -> tuple[str, str, int]:
    if mode in ("open", "navigate"):
        return _run_opencli(["browser", "open", url])

    tabs_before = _list_browser_tabs()
    prev_target = _active_tab_target_id(tabs_before)
    stdout, stderr, rc = _run_opencli(["browser", "tab", "new", url])
    if rc == 0 and prev_target and _browser_close_prev_tab():
        _run_opencli(["browser", "tab", "close", prev_target], timeout=10)
    return stdout, stderr, rc


def _open_page(url: str, *, label: str = "", new_tab: bool | None = None) -> None:
    """同会话 navigate 打开 URL；默认不 tab new，任务结束由 release_browser_session 关 tab。"""
    last_err = ""
    retry_markers = ("stale page", "detached")
    for attempt in range(3):
        if attempt:
            release_browser_session(close_tabs=True)
        mode = _resolve_page_nav_mode(new_tab=new_tab)
        stdout, stderr, rc = _navigate_browser_url(url, mode)
        if rc == 0:
            return
        last_err = stderr or stdout
        if not any(marker in last_err.lower() for marker in retry_markers):
            break
    raise RuntimeError(f"打开东财页面失败 {label or url}: {last_err}")


def _eval_js(js: str, *, timeout: float = 60) -> str:
    stdout, stderr, rc = _run_opencli(["browser", "eval", js], timeout=timeout)
    if rc != 0:
        raise RuntimeError(f"OpenCLI eval 失败: {stderr or stdout}")
    return stdout.strip()


def _kline_jsonp_js(secid_val: str, limit: int) -> str:
    return f"""
new Promise((resolve) => {{
  const cb = "jQuery_oc_" + Date.now();
  window[cb] = (data) => {{
    try {{
      const klines = (data.data && data.data.klines) ? data.data.klines : [];
      resolve(JSON.stringify(klines.slice(-{int(limit)})));
    }} catch (e) {{ resolve(JSON.stringify([])); }}
  }};
  const s = document.createElement("script");
  s.src = "https://push2his.eastmoney.com/api/qt/stock/kline/get?cb=" + cb
    + "&secid={secid_val}&ut=fa5fd1943c7b386f172d6893dbfba10b"
    + "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
    + "&klt=101&fqt=0&end=20500101&lmt={int(limit)}&_=" + Date.now();
  s.onerror = () => resolve(JSON.stringify([]));
  document.head.appendChild(s);
  setTimeout(() => resolve(JSON.stringify([])), 12000);
}})
"""


def kline_strings_to_rows(klines: list[str]) -> list[list[str]]:
    return [line.split(",") for line in klines if line]


def fetch_kline_rows_opencli(
    code: str,
    *,
    limit: int = 120,
    wait_seconds: float = 2.0,
    close_browser: bool = True,
    reset_browser: bool = True,
) -> list[list[str]]:
    """OpenCLI 打开东财行情页，在浏览器上下文中 JSONP 拉取日 K。"""
    c = code6(code)
    sid = secid(c)
    _reset_browser_if(reset_browser)
    _open_page(quote_url(c), label=c)

    _wait_page_ready(fallback_seconds=wait_seconds)

    raw = _eval_js(_kline_jsonp_js(sid, limit), timeout=90)
    if close_browser:
        release_browser_session(close_tabs=True)

    if not raw:
        return []
    try:
        klines = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"解析 K 线 JSON 失败 {c}: {raw[:200]}") from exc
    if not isinstance(klines, list):
        return []
    return kline_strings_to_rows([str(x) for x in klines])


def fetch_chip_kline_rows_opencli(
    code: str,
    *,
    limit: int = 210,
    wait_seconds: float = 2.0,
    close_browser: bool = True,
    reset_browser: bool = True,
) -> list[list[str]]:
    """Fetch unadjusted daily rows including f61 turnover for CYQ calculation."""

    return fetch_kline_rows_opencli(
        code,
        limit=limit,
        wait_seconds=wait_seconds,
        close_browser=close_browser,
        reset_browser=reset_browser,
    )


def fetch_kline_rows_batch_opencli(
    codes: list[str],
    *,
    limit: int = 120,
    wait_seconds: float = 2.0,
    close_browser: bool = True,
    reset_browser: bool = True,
) -> dict[str, list[list[str]]]:
    """批量 K 线：单 OpenCLI 会话顺序采集。"""
    if not codes:
        return {}

    unique = [code6(c) for c in dict.fromkeys(code6(c) for c in codes)]
    out: dict[str, list[list[str]]] = {}
    _reset_browser_if(reset_browser)

    for c in unique:
        try:
            _open_page(quote_url(c), label=f"{c}-kline")
            _wait_page_ready(fallback_seconds=wait_seconds)
            raw = _eval_js(_kline_jsonp_js(secid(c), limit), timeout=90)
            if not raw:
                out[c] = []
                continue
            klines = json.loads(raw)
            if not isinstance(klines, list):
                out[c] = []
            else:
                out[c] = kline_strings_to_rows([str(x) for x in klines])
        except Exception:  # noqa: BLE001
            out[c] = []

    if close_browser:
        release_browser_session(close_tabs=True)
    return out


def fetch_index_kline_rows_opencli(
    index_codes: list[str] | None = None,
    *,
    limit: int = 30,
    wait_seconds: float = 2.0,
    close_browser: bool = True,
    reset_browser: bool = True,
) -> dict[str, list[list[str]]]:
    """Fetch configured domestic index daily rows inside the OpenCLI browser."""
    codes = [code6(code) for code in (index_codes or list(_INDEX_SECIDS))]
    out: dict[str, list[list[str]]] = {}
    _reset_browser_if(reset_browser)
    for code in dict.fromkeys(codes):
        try:
            sid = index_secid(code)
            _open_page(index_url(code), label=f"index-{code}-kline")
            _wait_page_ready(fallback_seconds=wait_seconds)
            raw = _eval_js(_kline_jsonp_js(sid, limit), timeout=90)
            values = json.loads(raw) if raw else []
            out[code] = (
                kline_strings_to_rows([str(item) for item in values])
                if isinstance(values, list)
                else []
            )
        except Exception:  # noqa: BLE001
            out[code] = []
    if close_browser:
        release_browser_session(close_tabs=True)
    return out


def fetch_opencli_latest_kline_row(code: str) -> list[str] | None:
    rows = fetch_kline_rows_opencli(code, limit=2, close_browser=True)
    return rows[-1] if rows else None


def fetch_fund_flow_text_opencli(code: str, *, close_browser: bool = True) -> str:
    c = code6(code)
    _maybe_close_before_nav()
    _open_page(fund_flow_url(c), label=c)
    _run_opencli(["browser", "wait", "time", "2"], timeout=10)
    raw = _eval_js(EXTRACT_ZJLX_JS)
    if close_browser:
        release_browser_session(close_tabs=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _quote_page_code(payload: dict[str, str], expected: str) -> str | None:
    path_code = str(payload.get("pathCode") or "").strip()
    if len(path_code) == 6 and path_code.isdigit():
        return path_code.zfill(6)
    info = payload.get("infoText") or ""
    match = re.search(r"\b(\d{6})\b", info)
    if match:
        return match.group(1)
    return None


def _read_quote_payload(code: str, *, wait_seconds: float) -> dict[str, str] | None:
    """读取行情页 DOM；校验 URL 代码，避免上一页残留。"""
    c = code6(code)
    for attempt in range(3):
        if attempt:
            _run_opencli(["browser", "wait", "time", "1"], timeout=10)
        raw = _eval_js(EXTRACT_QUOTE_JS)
        if not raw:
            continue
        payload = json.loads(raw)
        page_code = _quote_page_code(payload, c)
        if page_code is None or page_code == c:
            return payload
        print(
            f"{c} 页面代码不匹配(page={page_code})，重试 {attempt + 1}/3",
            file=sys.stderr,
        )
    return None


def fetch_sop_snapshots(
    codes: list[str],
    *,
    wait_seconds: float = 2.0,
    close_browser: bool = True,
    reset_browser: bool = True,
    include_fund_flow_page: bool = True,
) -> dict[str, EastmoneySopSnapshot]:
    """SOP：行情页基本面 + 资金页主力流向（同一 OpenCLI 会话）。"""
    if not codes:
        return {}

    unique_codes = sorted({code6(c) for c in codes})
    snapshots: dict[str, EastmoneySopSnapshot] = {}

    _reset_browser_if(reset_browser)

    for c in unique_codes:
        try:
            _open_page(quote_url(c), label=c)
            _wait_page_ready(fallback_seconds=wait_seconds)
            payload = _read_quote_payload(c, wait_seconds=wait_seconds)
            if not payload:
                continue
            snap = parse_sop_snapshot(c, payload)
            if not snap:
                continue

            if include_fund_flow_page:
                try:
                    _open_page(fund_flow_url(c), label=f"{c}-zjlx")
                    _run_opencli(["browser", "wait", "time", "2"], timeout=10)
                    ff_raw = _eval_js(EXTRACT_ZJLX_JS)
                    try:
                        ff_text = json.loads(ff_raw)
                    except json.JSONDecodeError:
                        ff_text = ff_raw
                    if ff_text:
                        snap.fund_flow_text = ff_text
                except Exception as exc:  # noqa: BLE001
                    print(f"{c} 资金页采集失败: {exc}", file=sys.stderr)

            snapshots[c] = snap
        except Exception as exc:  # noqa: BLE001
            print(f"{c} 行情页采集失败: {exc}", file=sys.stderr)
            continue

    if close_browser:
        release_browser_session(close_tabs=True)

    return snapshots


def fetch_quotes_opencli(
    codes: list[str],
    *,
    wait_seconds: float = 2.0,
    close_browser: bool = True,
    reset_browser: bool = True,
) -> dict[str, EastmoneyQuote]:
    snaps = fetch_sop_snapshots(
        codes,
        wait_seconds=wait_seconds,
        close_browser=close_browser,
        reset_browser=reset_browser,
        include_fund_flow_page=False,
    )
    return {
        c: EastmoneyQuote(
            code=s.code,
            name=s.name,
            price=s.price,
            change_amt=s.change_amt,
            change_pct=s.change_pct,
        )
        for c, s in snaps.items()
    }


def fetch_quotes(
    codes: list[str],
    *,
    wait_seconds: float = 2.0,
) -> dict[str, EastmoneyQuote]:
    return fetch_quotes_opencli(codes, wait_seconds=wait_seconds)


def fetch_index_snapshots(
    index_codes: list[str],
    *,
    wait_seconds: float = 2.0,
    close_browser: bool = True,
    reset_browser: bool = True,
) -> dict[str, EastmoneyQuote]:
    """采集指数（上证/深证/创业板等）。"""
    if not index_codes:
        return {}

    unique = sorted({code6(c) for c in index_codes})
    out: dict[str, EastmoneyQuote] = {}
    _reset_browser_if(reset_browser)
    wait_arg = str(max(1, int(round(wait_seconds))))

    for c in unique:
        _open_page(index_url(c), label=c)
        _run_opencli(["browser", "wait", "time", wait_arg], timeout=10)
        raw = _eval_js(EXTRACT_QUOTE_JS)
        if not raw:
            continue
        payload = json.loads(raw)
        quote = parse_quote_payload(c, payload)
        if quote:
            out[c] = quote

    _close_browser_if(close_browser)
    return out


def fetch_macro_news_opencli(*, limit: int = 15, close_browser: bool = True) -> list[dict[str, str]]:
    """东财 7×24 快讯（OpenCLI）。"""
    _maybe_close_before_nav()
    _open_page(kuaixun_url(), label="kuaixun")
    _run_opencli(["browser", "wait", "time", "3"], timeout=15)
    raw = _eval_js(EXTRACT_KUAIXUN_JS, timeout=30)
    if close_browser:
        release_browser_session(close_tabs=True)
    if not raw:
        return []
    items = json.loads(raw)
    return items[:limit] if isinstance(items, list) else []


def _normalize_news_href(href: str) -> str:
    href = (href or "").strip()
    if href.startswith("//"):
        return f"https:{href}"
    return href


def fetch_kuaixun_engagement_opencli(
    *,
    limit: int = 80,
    close_browser: bool = True,
) -> dict[str, dict[str, int]]:
    """快讯列表页评论数（OpenCLI）。返回 href -> {comment, read}。"""
    _maybe_close_before_nav()
    _open_page(kuaixun_url(), label="kuaixun")
    _run_opencli(["browser", "wait", "time", "4"], timeout=15)
    raw = _eval_js(EXTRACT_KUAIXUN_JS, timeout=30)
    if close_browser:
        release_browser_session(close_tabs=True)
    if not raw:
        return {}
    items = json.loads(raw)
    if not isinstance(items, list):
        return {}
    out: dict[str, dict[str, int]] = {}
    for row in items[:limit]:
        href = _normalize_news_href(str(row.get("href") or ""))
        if not href:
            continue
        try:
            comment = int(row.get("comment") or 0)
        except (TypeError, ValueError):
            comment = 0
        out[href] = {"comment": max(comment, 0), "read": 0}
    return out


BREADTH_PAGE_URL = "https://quote.eastmoney.com/zs000001.html"
ZTB_PAGE_URL = "https://quote.eastmoney.com/ztb/detail"
ZT_POOL_UT = "7eea3edcaed734bea9cbfc24409ed989"
ZT_POOL_ENDPOINTS: dict[str, str] = {
    "zt": "getTopicZTPool",
    "zb": "getTopicZBPool",
    "dt": "getTopicDTPool",
}
A_SHARE_LIST_URL = "https://quote.eastmoney.com/center/gridlist.html#hs_a_board"
# 沪深京 A 股列表页 webguest clist（与页面 Network 一致）
A_SHARE_CLIST_FS = (
    "m:0+t:6+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,"
    "m:1+t:23+f:!2,m:0+t:81+s:262144+f:!2"
)
A_SHARE_CLIST_FIELDS = "f12,f14"
A_SHARE_LIST_PAGE_SIZE = 20
A_SHARE_JSONP_TIMEOUT_MS = 20000
A_SHARE_CLIST_UT = "fa5fd1943c7b386f172d6893dbfba10b"
A_SHARE_CLIST_WBP2U = "|0|0|0|web"

INDUSTRY_BOARD_URL = "https://quote.eastmoney.com/center/gridlist.html#industry_board"
# 东财 App 人气榜（A 股）；公众号 top5 流量优先候选池
HOT_STOCK_RANK_URL = (
    "https://vipmoney.eastmoney.com/collect/stockranking/pages/ranking9_3/list.html"
)

EXTRACT_HOT_STOCKS_JS = r"""
JSON.stringify((() => {
  const skip = /现价|涨跌幅|相关|排名|隐藏|一览|热股|板块|ETF|飙升/;
  const rows = [];
  const seen = new Set();
  const text = document.body.innerText || "";
  const re = /([\u4e00-\u9fa5A-Za-zＡ-Ｚａ-ｚ\*ST\s]{2,16})\s*\n+\s*(\d{6})\s*\n+[\s\S]{0,140}?([+-]?\d+\.\d+)%/g;
  let m;
  while ((m = re.exec(text)) !== null && rows.length < 30) {
    const name = m[1].replace(/\s+/g, " ").trim();
    const code = m[2];
    if (skip.test(name) || seen.has(code)) continue;
    seen.add(code);
    rows.push({
      rank: rows.length + 1,
      code,
      name,
      change_pct: parseFloat(m[3]),
    });
  }
  return rows;
})())
"""


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _jsonp_clist_page_js(pn: int, pz: int, *, fs: str, fields: str) -> str:
    fs_json = json.dumps(fs, ensure_ascii=False)
    wbp2u_json = json.dumps(A_SHARE_CLIST_WBP2U, ensure_ascii=False)
    return f"""
new Promise((resolve) => {{
  const cb = "jQuery_oc_" + Date.now();
  window[cb] = (data) => {{
    try {{
      const payload = (data && data.data) ? data.data : {{}};
      const diff = payload.diff;
      const list = Array.isArray(diff) ? diff : Object.values(diff || {{}});
      const rows = list.map((x) => ({{
        code: String(x.f12 || "").replace(/\\D/g, "").slice(-6).padStart(6, "0"),
        name: String(x.f14 || "").trim(),
      }})).filter((x) => /^\\d{{6}}$/.test(x.code) && x.name);
      resolve(JSON.stringify({{ total: Number(payload.total) || 0, rows: rows }}));
    }} catch (e) {{
      resolve(JSON.stringify({{ total: 0, rows: [], error: String(e) }}));
    }}
  }};
  const s = document.createElement("script");
  s.src = "https://push2.eastmoney.com/webguest/api/qt/clist/get?timil=1&np=1&fltt=1&invt=2&cb=" + cb
    + "&fs=" + encodeURIComponent({fs_json})
    + "&fields={fields}&fid=f3&pn={int(pn)}&pz={int(pz)}&po=1&dect=1"
    + "&ut={A_SHARE_CLIST_UT}&wbp2u=" + encodeURIComponent({wbp2u_json})
    + "&_=" + Date.now();
  s.onerror = () => resolve(JSON.stringify({{ total: 0, rows: [], error: "script" }}));
  document.head.appendChild(s);
  setTimeout(
    () => resolve(JSON.stringify({{ total: 0, rows: [], error: "timeout" }})),
    {int(A_SHARE_JSONP_TIMEOUT_MS)}
  );
}})
"""


def _read_a_share_total_pages_js() -> str:
    return r"""
JSON.stringify((() => {
  const nums = [...document.querySelectorAll('a, span, li')]
    .map((el) => (el.innerText || '').trim())
    .filter((x) => /^\d+$/.test(x))
    .map((x) => parseInt(x, 10))
    .filter((n) => n > 0 && n < 500);
  if (!nums.length) return 0;
  return Math.max(...nums);
})())
"""


def _fetch_market_names_jsonp_head(
    *,
    wait_seconds: float = 3.0,
    page_size: int = 20,
    max_pages: int = 10,
) -> dict[str, str]:
    """JSONP 仅可取前 ~10 页（约 200 条），作 DOM 全量前的快速预热。"""
    wait_arg = str(max(1, int(round(wait_seconds))))
    _open_page(A_SHARE_LIST_URL, label="hs-a-jsonp")
    _run_opencli(["browser", "wait", "time", wait_arg], timeout=15)

    out: dict[str, str] = {}
    for pn in range(1, max_pages + 1):
        if pn > 1:
            _run_opencli(["browser", "wait", "time", "0.5"], timeout=10)
        raw = _eval_js(
            _jsonp_clist_page_js(
                pn,
                page_size,
                fs=A_SHARE_CLIST_FS,
                fields=A_SHARE_CLIST_FIELDS,
            ),
            timeout=max(35.0, A_SHARE_JSONP_TIMEOUT_MS / 1000 + 5),
        )
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            break
        rows = payload.get("rows") or []
        if not rows:
            break
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = code6(str(row.get("code") or ""))
            name = str(row.get("name") or "").strip()
            if re.fullmatch(r"\d{6}", code) and name and _has_cjk(name):
                out[code] = name
    return out


def fetch_market_names_opencli(
    *,
    page_size: int = A_SHARE_LIST_PAGE_SIZE,
    wait_seconds: float = 3.0,
    close_browser: bool = True,
    reset_browser: bool = True,
    max_pages: int = 320,
    use_jsonp_head: bool = False,
) -> dict[str, str]:
    """东财 A 股列表 DOM 翻页全量（单 OpenCLI 会话，约 6～8 分钟）。"""
    _ = page_size, use_jsonp_head
    if reset_browser:
        _reset_browser()
    return _fetch_market_names_opencli_dom(
        wait_seconds=max(0.8, wait_seconds * 0.35),
        close_browser=close_browser,
        reset_browser=False,
        max_pages=max_pages,
        progress=True,
    )


def _extract_a_share_table_rows_js() -> str:
    return r"""
JSON.stringify((() => {
  const out = [];
  for (const tr of document.querySelectorAll('table tbody tr')) {
    const tds = [...tr.querySelectorAll('td')];
    if (tds.length < 3) continue;
    const code = (tds[1].innerText || '').trim();
    let name = (tds[2].innerText || '').trim().split(/\s/)[0];
    if (/^\d{6}$/.test(code) && name) out.push({ code, name });
  }
  return out;
})())
"""


def _qtpager_links_js() -> str:
    return r"""
JSON.stringify((() => {
  const root = document.querySelector('.qtpager');
  if (!root) return [];
  return [...root.querySelectorAll('a')].map((a) => (a.innerText || '').trim());
})())
"""


def _click_qtpager_link_js(label: str) -> str:
    text = json.dumps(str(label), ensure_ascii=False)
    return f"""
JSON.stringify((() => {{
  const root = document.querySelector('.qtpager');
  if (!root) return {{ ok: false, error: 'no pager' }};
  const target = {text};
  const link = [...root.querySelectorAll('a')].find(
    (a) => (a.innerText || '').trim() === target
  );
  if (!link) return {{ ok: false, error: 'missing ' + target }};
  link.click();
  return {{ ok: true, label: target }};
}})())
"""


def _wait_for_qtpager_ready(*, max_seconds: float = 30.0) -> bool:
    attempts = max(3, int(max_seconds))
    for _ in range(attempts):
        try:
            links = json.loads(_eval_js(_qtpager_links_js(), timeout=15) or "[]")
        except json.JSONDecodeError:
            links = []
        if isinstance(links, list) and links:
            return True
        _run_opencli(["browser", "wait", "time", "1"], timeout=10)
    return False


def _fetch_market_names_opencli_dom(
    *,
    wait_seconds: float = 1.2,
    close_browser: bool = True,
    reset_browser: bool = True,
    max_pages: int = 400,
    progress: bool = False,
) -> dict[str, str]:
    """`.qtpager` 区块翻页全量（东财 A 股列表页，约 6～9 分钟）。"""
    import sys

    if reset_browser:
        _reset_browser()
    wait_arg = str(max(1, int(round(wait_seconds))))
    _open_page(A_SHARE_LIST_URL, label="hs-a-list-dom")
    if not _wait_for_qtpager_ready(max_seconds=30.0):
        _close_browser_if(close_browser)
        raise RuntimeError("东财 A 股列表分页器未加载（.qtpager 为空）")

    out: dict[str, str] = {}
    seen_pages: set[int] = set()
    idle_rounds = 0
    max_idle_rounds = 4

    while len(seen_pages) < max_pages and idle_rounds < max_idle_rounds:
        try:
            links = json.loads(_eval_js(_qtpager_links_js(), timeout=15) or "[]")
        except json.JSONDecodeError:
            links = []
        if not isinstance(links, list):
            links = []

        round_added = 0
        for label in links:
            if label == ">":
                continue
            if not str(label).isdigit():
                continue
            page_no = int(label)
            if page_no in seen_pages or page_no > max_pages:
                continue
            _eval_js(_click_qtpager_link_js(str(page_no)), timeout=15)
            _run_opencli(["browser", "wait", "time", wait_arg], timeout=15)
            raw = _eval_js(_extract_a_share_table_rows_js(), timeout=20)
            try:
                rows = json.loads(raw) if raw else []
            except json.JSONDecodeError:
                rows = []
            if not rows:
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                code = code6(str(row.get("code") or ""))
                name = str(row.get("name") or "").strip()
                if re.fullmatch(r"\d{6}", code) and name and _has_cjk(name):
                    out[code] = name
            seen_pages.add(page_no)
            round_added += 1
            if progress and (
                page_no == 1 or page_no % 25 == 0 or len(seen_pages) % 25 == 0
            ):
                print(
                    f"  … A 股列表 {page_no} 页，已采集 {len(out)} 只（{len(seen_pages)} 页）",
                    file=sys.stderr,
                )

        if ">" in links:
            _eval_js(_click_qtpager_link_js(">"), timeout=15)
            _run_opencli(["browser", "wait", "time", wait_arg], timeout=15)
        else:
            break

        if round_added:
            idle_rounds = 0
        else:
            idle_rounds += 1

    _close_browser_if(close_browser)
    return out


INDUSTRY_BOARD_FS = "m:90+t:2"
INDUSTRY_BOARD_JSONP_FIELDS = "f12,f14,f3,f128,f136,f140"


def _jsonp_industry_board_rows_js(*, pn: int = 1, pz: int = 20) -> str:
    wbp2u_json = json.dumps(A_SHARE_CLIST_WBP2U, ensure_ascii=False)
    return f"""
new Promise((resolve) => {{
  const cb = "jQuery_ib_" + Date.now();
  window[cb] = (data) => {{
    try {{
      const diff = data?.data?.diff;
      const list = Array.isArray(diff) ? diff : Object.values(diff || {{}});
      const rows = list.map((x, i) => ({{
        rank: {int(pn - 1) * int(pz)} + i + 1,
        sector: String(x.f14 || "").trim(),
        sector_chg: Number(x.f3),
        leader_name: String(x.f128 || "").trim(),
        leader_chg: Number(x.f136),
        code: String(x.f140 || "").replace(/\\D/g, "").slice(-6).padStart(6, "0"),
        board_code: String(x.f12 || "").trim(),
      }})).filter((r) => /^\\d{{6}}$/.test(r.code) && r.sector && r.leader_name);
      resolve(JSON.stringify({{ rc: data?.rc, rows }}));
    }} catch (e) {{
      resolve(JSON.stringify({{ rc: -1, rows: [], error: String(e) }}));
    }}
  }};
  const s = document.createElement("script");
  s.src = "https://push2.eastmoney.com/api/qt/clist/get?cb=" + cb
    + "&fs=" + encodeURIComponent("{INDUSTRY_BOARD_FS}")
    + "&fields={INDUSTRY_BOARD_JSONP_FIELDS}"
    + "&fid=f3&po=1&pn={int(pn)}&pz={int(pz)}&np=1"
    + "&ut={A_SHARE_CLIST_UT}&fltt=2&invt=2&wbp2u=" + encodeURIComponent({wbp2u_json})
    + "&_=" + Date.now();
  s.onerror = () => resolve(JSON.stringify({{ rc: -1, rows: [], error: "script" }}));
  document.head.appendChild(s);
  setTimeout(
    () => resolve(JSON.stringify({{ rc: -1, rows: [], error: "timeout" }})),
    {int(A_SHARE_JSONP_TIMEOUT_MS)}
  );
}})
"""


EXTRACT_HOT_INDUSTRY_JS = r"""
JSON.stringify((() => {
  const names = [];
  const seen = new Set();
  const bad = /资金流|排行|沪深京|概念|地区|龙虎|今日|5日|10日|更多|全部|自选|板块榜/;
  const push = (text) => {
    const name = (text || '').trim().replace(/\s+/g, '');
    if (!name || name.length < 2 || name.length > 12 || seen.has(name)) return;
    if (/^(序号|名称|代码|最新|涨跌幅|涨跌额|总手|换手|领涨股)/.test(name)) return;
    if (bad.test(name)) return;
    seen.add(name);
    names.push(name);
  };
  for (const row of document.querySelectorAll('table tbody tr')) {
    const tds = row.querySelectorAll('td');
    if (tds.length < 2) continue;
    const rank = (tds[0].innerText || '').trim();
    if (!/^\d{1,3}$/.test(rank)) continue;
    const link = row.querySelector('a[href*="bk"], a[href*="/bk/"]');
    if (link) push(link.innerText);
    if (names.length >= 12) break;
  }
  return names;
})())
"""

EXTRACT_BREADTH_JS = r"""
JSON.stringify((() => {
  const t = (document.body.innerText || '').replace(/\u00a0/g, ' ');
  const blocks = [...t.matchAll(/涨:(\d+)\s*平:(\d+)\s*跌:(\d+)/g)].map(m => ({
    up: +m[1], flat: +m[2], down: +m[3]
  }));
  if (!blocks.length) return null;
  const sh = blocks[0];
  const sz = blocks[1] || { up: 0, flat: 0, down: 0 };
  return {
    shanghai: sh,
    shenzhen: sz,
    total: {
      up: sh.up + sz.up,
      flat: sh.flat + sz.flat,
      down: sh.down + sz.down
    },
    source: 'eastmoney-opencli'
  };
})())
"""

EXTRACT_UNIFY_QUOTE_JS = r"""
JSON.stringify((() => {
  const name = (document.querySelector('.quote_title_name')?.innerText || document.title.split('(')[0] || '').trim();
  const text = document.body.innerText || '';
  const idx = name ? text.indexOf(name) : -1;
  const slice = idx >= 0 ? text.slice(idx, idx + 500) : text.slice(0, 600);
  const priceMatch = slice.match(/\n(\d[\d,]*\.\d+)\n/);
  const price = priceMatch ? parseFloat(priceMatch[1].replace(/,/g, '')) : null;
  let zdfText = '';
  if (priceMatch) {
    const afterPrice = slice.slice(priceMatch.index + priceMatch[0].length);
    const zdfLine = afterPrice.match(/^\s*([^\n]+)/);
    zdfText = zdfLine ? zdfLine[1].trim() : '';
  }
  const infoMatch = slice.match(/今开:[^\n]+/);
  const infoText = infoMatch ? infoMatch[0] : '';
  return {
    name,
    price,
    zdfText,
    infoText,
    source: 'eastmoney-opencli-unify'
  };
})())
"""

EXTRACT_OIL_INDEX_JS = r"""
JSON.stringify((() => {
  for (const row of document.querySelectorAll('table tr')) {
    const cells = [...row.querySelectorAll('td')].map(c => c.innerText.trim());
    if (cells.length < 3 || !/^\d{4}-\d{2}-\d{2}$/.test(cells[0])) continue;
    const price = parseFloat(cells[1].replace(/,/g, ''));
    const changePct = parseFloat(String(cells[2]).replace(/,/g, '').replace('%', ''));
    if (Number.isNaN(price) || Number.isNaN(changePct)) continue;
    const prev = price / (1 + changePct / 100);
    return {
      date: cells[0],
      price,
      change: +(price - prev).toFixed(2),
      changePct,
      source: 'eastmoney-opencli-data'
    };
  }
  return null;
})())
"""

INTERNATIONAL_INDEX_SPECS: list[tuple[str, str]] = [
    ("道琼斯", "100.DJIA"),
    ("纳斯达克", "100.NDX"),
    ("标普500", "100.SPX"),
    ("恒生指数", "100.HSI"),
    ("日经225", "100.N225"),
    ("韩国KOSPI", "100.KS11"),
    ("韩国KOSDAQ", "100.KQ11"),
]

WTI_OIL_INDEX_URL = "https://data.eastmoney.com/cjsj/hyzs_EMI01508580.html"


def unify_quote_url(code: str) -> str:
    return f"https://quote.eastmoney.com/unify/r/{code}"


def _jsonp_board_constituents_js(board_code: str, *, pz: int = 12) -> str:
    bk = (board_code or "").strip().upper()
    return f"""
new Promise((resolve) => {{
  const cb = "jQuery_bc_" + Date.now();
  window[cb] = (data) => {{
    try {{
      const diff = data?.data?.diff;
      const list = Array.isArray(diff) ? diff : Object.values(diff || {{}});
      const rows = list.map((x) => ({{
        code: String(x.f12 || "").replace(/\\D/g, "").slice(-6).padStart(6, "0"),
        name: String(x.f14 || "").trim(),
        change_pct: Number(x.f3),
      }})).filter((r) => /^\\d{{6}}$/.test(r.code) && r.name);
      resolve(JSON.stringify({{ rc: data?.rc, rows }}));
    }} catch (e) {{
      resolve(JSON.stringify({{ rc: -1, rows: [], error: String(e) }}));
    }}
  }};
  const s = document.createElement("script");
  s.src = "https://push2.eastmoney.com/api/qt/clist/get?cb=" + cb
    + "&fs=" + encodeURIComponent("b:{bk}")
    + "&fields=f12,f14,f3"
    + "&fid=f3&po=1&pn=1&pz={int(pz)}&np=1"
    + "&fltt=2&invt=2&ut={A_SHARE_CLIST_UT}&_=" + Date.now();
  s.onerror = () => resolve(JSON.stringify({{ rc: -1, rows: [], error: "script" }}));
  document.head.appendChild(s);
  setTimeout(
    () => resolve(JSON.stringify({{ rc: -1, rows: [], error: "timeout" }})),
    {int(A_SHARE_JSONP_TIMEOUT_MS)}
  );
}})
"""


def fetch_industry_board_constituents(
    board_code: str,
    *,
    top_n: int = 8,
    close_browser: bool = False,
    reset_browser: bool = False,
) -> list[dict]:
    """东财板块 BK 成分股（OpenCLI JSONP，按涨跌幅）。"""
    bk = (board_code or "").strip().upper()
    if not bk.startswith("BK") or top_n <= 0:
        return []
    if reset_browser:
        _reset_browser()
    pz = max(top_n, 8)
    _open_page(INDUSTRY_BOARD_URL, label="industry-board-const")
    _run_opencli(["browser", "wait", "time", "1"], timeout=10)
    raw = _eval_js(_jsonp_board_constituents_js(bk, pz=pz), timeout=45)
    _close_browser_if(close_browser)
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    rows = payload.get("rows") or []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)][:top_n]


def fetch_hot_industry_board_rows_opencli(
    *,
    top_n: int = 12,
    wait_seconds: float = 3.0,
    close_browser: bool = True,
    reset_browser: bool = True,
) -> list[dict]:
    """行业板块涨幅榜 + 领涨股（OpenCLI 页面内 JSONP，fs=m:90+t:2）。"""
    if top_n <= 0:
        return []
    if reset_browser:
        _reset_browser()
    wait_arg = str(max(1, int(round(wait_seconds))))
    pz = max(top_n, 20)
    _open_page(INDUSTRY_BOARD_URL, label="industry-board")
    _run_opencli(["browser", "wait", "time", wait_arg], timeout=15)
    raw = _eval_js(_jsonp_industry_board_rows_js(pn=1, pz=pz), timeout=45)
    _close_browser_if(close_browser)
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    rows = payload.get("rows") or []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)][:top_n]


def fetch_hot_industry_sectors_opencli(
    *,
    top_n: int = 5,
    wait_seconds: float = 3.0,
    close_browser: bool = True,
    reset_browser: bool = True,
) -> list[str]:
    """行业板块涨幅榜前 N 名称（JSONP 优先，失败回退 DOM 解析）。"""
    if top_n <= 0:
        return []
    rows = fetch_hot_industry_board_rows_opencli(
        top_n=max(top_n, 8),
        wait_seconds=wait_seconds,
        close_browser=close_browser,
        reset_browser=reset_browser,
    )
    out: list[str] = []
    for row in rows:
        name = str(row.get("sector") or "").strip()
        if name and name not in out:
            out.append(name)
        if len(out) >= top_n:
            return out
    if out:
        return out
    if reset_browser:
        _reset_browser()
    wait_arg = str(max(1, int(round(wait_seconds))))
    _open_page(INDUSTRY_BOARD_URL, label="industry-board-dom")
    _run_opencli(["browser", "wait", "time", wait_arg], timeout=15)
    raw = _eval_js(EXTRACT_HOT_INDUSTRY_JS, timeout=30)
    _close_browser_if(close_browser)
    if not raw or raw == "null":
        return []
    try:
        names = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(names, list):
        return []
    for item in names:
        name = str(item).strip()
        if name and name not in out:
            out.append(name)
        if len(out) >= top_n:
            break
    return out


def fetch_hot_stocks_opencli(
    *,
    top_n: int = 10,
    wait_seconds: float = 5.0,
    close_browser: bool = True,
    reset_browser: bool = True,
    url: str | None = None,
) -> list[dict]:
    """东财 A 股人气榜前 N（OpenCLI；vipmoney 飙升/人气页）。

    休市周末页面多为**上一交易日收盘快照**，非盘中实时排名。
    """
    if top_n <= 0:
        return []
    if reset_browser:
        _reset_browser()
    wait_arg = str(max(2, int(round(wait_seconds))))
    page_url = (url or os.getenv("WECHAT_MP_HOT_STOCK_URL") or HOT_STOCK_RANK_URL).strip()
    _open_page(page_url, label="hot-stock-rank")
    _run_opencli(["browser", "wait", "time", wait_arg], timeout=20)
    raw = _eval_js(EXTRACT_HOT_STOCKS_JS, timeout=45)
    _close_browser_if(close_browser)
    if not raw or raw == "null":
        return []
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").zfill(6)[-6:]
        name = str(item.get("name") or "").strip()
        if not re.fullmatch(r"\d{6}", code) or len(name) < 2:
            continue
        out.append(
            {
                "rank": int(item.get("rank") or len(out) + 1),
                "code": code,
                "name": name,
                "change_pct": float(item.get("change_pct") or 0.0),
            }
        )
        if len(out) >= top_n:
            break
    return out


def _topic_pool_jsonp_js(
    endpoint: str,
    trade_date: str,
    *,
    pageindex: int = 0,
    pagesize: int = 200,
) -> str:
    return f"""
new Promise((resolve) => {{
  const cb = "jQuery_zt_" + Date.now() + "_{pageindex}";
  window[cb] = (data) => {{
    try {{
      const pool = (data && data.data && data.data.pool) ? data.data.pool : [];
      resolve(JSON.stringify({{ rc: data && data.rc, pool: pool }}));
    }} catch (e) {{
      resolve(JSON.stringify({{ rc: -1, pool: [], error: String(e) }}));
    }}
  }};
  const s = document.createElement("script");
  s.src = "https://push2ex.eastmoney.com/{endpoint}?ut={ZT_POOL_UT}&dpt=wz.ztzt"
    + "&Pageindex={pageindex}&pagesize={pagesize}&sort=fbt:asc&date={trade_date}&cb=" + cb
    + "&_=" + Date.now();
  s.onerror = () => resolve(JSON.stringify({{ rc: -1, pool: [], error: "script" }}));
  document.head.appendChild(s);
  setTimeout(
    () => resolve(JSON.stringify({{ rc: -1, pool: [], error: "timeout" }})),
    20000
  );
}})
"""


def _fetch_topic_pool_pages_opencli(
    endpoint: str,
    trade_date: str,
    *,
    pagesize: int = 200,
    max_pages: int = 10,
) -> list[dict]:
    out: list[dict] = []
    for page in range(max_pages):
        raw = _eval_js(
            _topic_pool_jsonp_js(endpoint, trade_date, pageindex=page, pagesize=pagesize),
            timeout=35,
        )
        if not raw:
            break
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            break
        pool = payload.get("pool") or []
        if not isinstance(pool, list) or not pool:
            break
        out.extend([x for x in pool if isinstance(x, dict)])
        if len(pool) < pagesize:
            break
    return out


def fetch_emotion_topic_pools_opencli(
    trade_date: str | None = None,
    *,
    close_browser: bool = True,
    reset_browser: bool = True,
) -> dict[str, list[dict]]:
    """盘中涨停/炸板/跌停池（OpenCLI JSONP，单会话）。"""
    from datetime import date

    d = (trade_date or date.today().isoformat())[:10].replace("-", "")
    if reset_browser:
        _reset_browser()
    _open_page(ZTB_PAGE_URL, label="ztb")
    _run_opencli(["browser", "wait", "time", "2"], timeout=25)
    pools: dict[str, list[dict]] = {}
    for kind, endpoint in ZT_POOL_ENDPOINTS.items():
        pools[kind] = _fetch_topic_pool_pages_opencli(endpoint, d)
    _close_browser_if(close_browser)
    return pools


def fetch_market_breadth_opencli(
    *,
    close_browser: bool = True,
    reset_browser: bool = True,
) -> dict[str, object] | None:
    """全 A 涨跌家数：上证+深证行情条（涨/平/跌）汇总。"""
    if reset_browser:
        _reset_browser()
    _open_page(BREADTH_PAGE_URL, label="breadth")
    _run_opencli(["browser", "wait", "time", "3"], timeout=10)
    raw = _eval_js(EXTRACT_BREADTH_JS, timeout=30)
    _close_browser_if(close_browser)
    if not raw or raw == "null":
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _parse_compact_prev_close(info_text: str) -> float | None:
    match = re.search(r"昨收[:：]([\d,.]+)", info_text or "")
    return _parse_float(match.group(1)) if match else None


def _parse_unify_zdf(zdf_text: str) -> tuple[float | None, float | None]:
    text = (zdf_text or "").replace(" ", "").strip()
    if not text:
        return None, None
    compact = re.fullmatch(r"(-?\d+\.\d{2})(-?\d+\.\d{2})%", text)
    if compact:
        return float(compact.group(1)), float(compact.group(2))
    return _parse_zdf(text)


def _parse_unify_quote_payload(payload: dict) -> EastmoneyQuote | None:
    name = str(payload.get("name") or "").strip()
    price = payload.get("price")
    if price is None:
        return None
    price = float(price)
    info_text = str(payload.get("infoText") or "")
    prev_close = _parse_compact_prev_close(info_text)
    if prev_close is not None and prev_close > 0:
        change_amt, change_pct = _compute_change(price, prev_close)
    else:
        change_amt, change_pct = 0.0, 0.0
        parsed_amt, parsed_pct = _parse_unify_zdf(str(payload.get("zdfText") or ""))
        if parsed_pct is not None:
            change_pct = parsed_pct
        if parsed_amt is not None:
            change_amt = parsed_amt
    return EastmoneyQuote(
        code=name,
        name=name,
        price=price,
        change_amt=change_amt,
        change_pct=change_pct,
        source=str(payload.get("source") or "eastmoney-opencli-unify"),
    )


def _parse_oil_index_payload(payload: dict) -> EastmoneyQuote | None:
    price = payload.get("price")
    if price is None:
        return None
    change = payload.get("change")
    change_pct = payload.get("changePct")
    return EastmoneyQuote(
        code="WTI",
        name="WTI原油",
        price=float(price),
        change_amt=float(change or 0),
        change_pct=float(change_pct or 0),
        source=str(payload.get("source") or "eastmoney-opencli-data"),
    )


def fetch_domestic_market_opencli(
    index_codes: list[str] | None = None,
    *,
    include_breadth: bool = True,
    wait_seconds: float = 2.0,
) -> tuple[dict[str, EastmoneyQuote], dict[str, object] | None]:
    """A 股指数 + 全 A 涨跌：单 OpenCLI 会话，结束时关闭浏览器。"""
    codes = index_codes or ["000001", "399001", "399006", "000300", "000688"]
    snaps = fetch_index_snapshots(
        codes,
        wait_seconds=wait_seconds,
        close_browser=not include_breadth,
        reset_browser=True,
    )
    breadth = None
    if include_breadth:
        breadth = fetch_market_breadth_opencli(close_browser=True, reset_browser=False)
    return snaps, breadth


def fetch_international_briefing_opencli(
    specs: list[tuple[str, str]] | None = None,
    *,
    include_wti: bool = True,
    wait_seconds: float = 2.0,
) -> tuple[dict[str, EastmoneyQuote], EastmoneyQuote | None]:
    """全球指数 + WTI 原油：单 OpenCLI 会话，结束时关闭浏览器。"""
    items = specs or INTERNATIONAL_INDEX_SPECS
    out: dict[str, EastmoneyQuote] = {}
    wait_arg = str(max(1, int(round(wait_seconds))))
    oil: EastmoneyQuote | None = None

    _reset_browser()
    try:
        for label, code in items:
            url = unify_quote_url(code)
            try:
                _open_page(url, label=label)
                _run_opencli(["browser", "wait", "time", wait_arg], timeout=10)
                raw = _eval_js(EXTRACT_UNIFY_QUOTE_JS, timeout=30)
                if not raw:
                    continue
                payload = json.loads(raw)
                quote = _parse_unify_quote_payload(payload)
                if quote:
                    quote.name = label
                    out[label] = quote
            except Exception:
                continue

        if include_wti:
            try:
                _open_page(WTI_OIL_INDEX_URL, label="wti-oil")
                _run_opencli(["browser", "wait", "time", "3"], timeout=10)
                raw = _eval_js(EXTRACT_OIL_INDEX_JS, timeout=30)
                if raw and raw != "null":
                    payload = json.loads(raw)
                    if isinstance(payload, dict):
                        oil = _parse_oil_index_payload(payload)
            except Exception:
                oil = None
    finally:
        _close_browser_if(True)

    return out, oil


def fetch_international_quotes_opencli(
    specs: list[tuple[str, str]] | None = None,
    *,
    wait_seconds: float = 2.0,
    close_browser: bool = True,
    reset_browser: bool = True,
) -> dict[str, EastmoneyQuote]:
    """国际市场指数：东财 unify/r 全球指数页（替代原腾讯 gtimg）。"""
    if reset_browser and close_browser:
        quotes, _ = fetch_international_briefing_opencli(
            specs,
            include_wti=False,
            wait_seconds=wait_seconds,
        )
        return quotes

    items = specs or INTERNATIONAL_INDEX_SPECS
    out: dict[str, EastmoneyQuote] = {}
    wait_arg = str(max(1, int(round(wait_seconds))))
    if reset_browser:
        _reset_browser()
    for label, code in items:
        url = unify_quote_url(code)
        try:
            _open_page(url, label=label)
            _run_opencli(["browser", "wait", "time", wait_arg], timeout=10)
            raw = _eval_js(EXTRACT_UNIFY_QUOTE_JS, timeout=30)
            if not raw:
                continue
            payload = json.loads(raw)
            quote = _parse_unify_quote_payload(payload)
            if quote:
                quote.name = label
                out[label] = quote
        except Exception:
            continue
    _close_browser_if(close_browser)
    return out


def fetch_wti_oil_opencli(
    *,
    close_browser: bool = True,
    reset_browser: bool = True,
) -> EastmoneyQuote | None:
    """WTI 原油：东财行业指数 CONC 最新一行（data 页，非 HTTP API）。"""
    if reset_browser:
        _reset_browser()
    try:
        _open_page(WTI_OIL_INDEX_URL, label="wti-oil")
        _run_opencli(["browser", "wait", "time", "3"], timeout=10)
        raw = _eval_js(EXTRACT_OIL_INDEX_JS, timeout=30)
        if not raw or raw == "null":
            return None
        payload = json.loads(raw)
        return _parse_oil_index_payload(payload) if isinstance(payload, dict) else None
    except Exception:
        return None
    finally:
        _close_browser_if(close_browser)


def format_international_market_lines(quotes: dict[str, EastmoneyQuote] | None = None) -> list[str]:
    """格式化为战报「四、国际市场」段落行（指数 + WTI，不含布伦特）。"""
    if quotes is not None:
        index_quotes = quotes
        oil = None
    else:
        index_quotes, oil = fetch_international_briefing_opencli(include_wti=True)
    if not index_quotes and oil is None:
        return ["国际市场：OpenCLI 采集失败"]
    lines: list[str] = []
    for label, _ in INTERNATIONAL_INDEX_SPECS:
        q = index_quotes.get(label)
        if not q:
            continue
        lines.append(f"{label}: {q.price} ({q.change_amt:+.2f}, {q.change_pct:+.2f}%)")
    if oil:
        lines.append(f"WTI原油: {oil.price} ({oil.change_amt:+.2f}, {oil.change_pct:+.2f}%)")
    return lines or ["国际市场：暂无数据"]


EXTRACT_F10_APP_JS = r"""
JSON.stringify((document.querySelector('#app')?.innerText || '').slice(0, 5000))
"""

F10_MAX_LEN = 5000
F10_SECTIONS: dict[str, str] = {
    "财务面": "#/cwfx",
    "消息面": "#/zxgg",
    "研报面": "#/yjbg",
    "所属板块": "#/hxtc",
    "盈利预测": "#/ylyc",
}


def market_prefix_upper(code: str) -> str:
    c = code6(code)
    return "SH" if c.startswith(("60", "68")) else "SZ"


def f10_url(code: str, hash_path: str) -> str:
    c = code6(code)
    return (
        "https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html"
        f"?type=web&code={market_prefix_upper(c)}{c}&color=b{hash_path}"
    )


def _truncate(text: str, limit: int = F10_MAX_LEN) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text or "页面为空或未加载出数据"
    return text[:limit] + "\n\n...[内容过长已截断]..."


def fetch_full_sop_data(
    code: str,
    *,
    wait_seconds: float = 2.0,
    close_browser: bool = True,
    reset_browser: bool = True,
) -> dict[str, str]:
    """单股 8 维度 SOP（OpenCLI 单会话）。"""
    return fetch_full_sop_batch(
        [code],
        wait_seconds=wait_seconds,
        close_browser=close_browser,
        reset_browser=reset_browser,
    ).get(code6(code), {})


def fetch_full_sop_batch(
    codes: list[str],
    *,
    wait_seconds: float = 2.0,
    close_browser: bool = True,
    reset_browser: bool = True,
) -> dict[str, dict[str, str]]:
    """批量 8 维度 SOP：同一 OpenCLI 会话顺序采集（Top5 分析用）。"""
    if not codes:
        return {}

    unique = [code6(c) for c in dict.fromkeys(code6(c) for c in codes)]
    out: dict[str, dict[str, str]] = {}
    wait_arg = str(max(1, int(round(wait_seconds))))

    _reset_browser_if(reset_browser)

    for c in unique:
        results: dict[str, str] = {}
        try:
            _open_page(quote_url(c), label=c)
            _wait_page_ready(fallback_seconds=wait_seconds)
            raw = _eval_js(EXTRACT_QUOTE_JS)
            payload = json.loads(raw) if raw else {}
            results["基本面"] = _truncate(payload.get("infoText") or "未找到基本面数据")
            results["资金面"] = _truncate(payload.get("fundFlowText") or "")
            results["委比委差买卖盘"] = _truncate(
                payload.get("orderBookText") or "未找到委比/委差数据"
            )

            _open_page(fund_flow_url(c), label=f"{c}-zjlx")
            _run_opencli(["browser", "wait", "time", "2"], timeout=10)
            ff_raw = _eval_js(EXTRACT_ZJLX_JS)
            try:
                ff_text = json.loads(ff_raw)
            except json.JSONDecodeError:
                ff_text = ff_raw
            if ff_text:
                results["资金面"] = _truncate(str(ff_text))

            for name, hash_path in F10_SECTIONS.items():
                try:
                    _open_page(f10_url(c, hash_path), label=f"{c}-{name}")
                    _run_opencli(["browser", "wait", "time", "3"], timeout=15)
                    app_raw = _eval_js(EXTRACT_F10_APP_JS, timeout=30)
                    try:
                        app_text = json.loads(app_raw)
                    except json.JSONDecodeError:
                        app_text = app_raw
                    results[name] = _truncate(str(app_text or ""))
                except Exception as exc:  # noqa: BLE001
                    results[name] = f"获取失败: {exc}"

            out[c] = results
        except Exception as exc:  # noqa: BLE001
            err = f"获取失败: {exc}"
            out[c] = {
                "基本面": err,
                "资金面": err,
                "委比委差买卖盘": err,
                **{k: err for k in F10_SECTIONS},
            }

    if close_browser:
        release_browser_session(close_tabs=True)

    return out


def technical_summary_from_kline_rows(rows: list[list[str]]) -> str:
    """从 OpenCLI K 线行计算 MA/量比摘要。"""
    if not rows:
        return "（OpenCLI 无 K 线数据）"
    closes, vols, dates = [], [], []
    for r in rows:
        if len(r) < 6:
            continue
        try:
            dates.append(r[0])
            closes.append(float(r[2]))
            vols.append(float(r[5]))
        except ValueError:
            continue
    if not closes:
        return "（K 线解析失败）"

    n = len(closes)
    ma5 = sum(closes[-5:]) / min(5, n)
    ma20 = sum(closes[-20:]) / min(20, n)
    ma60 = sum(closes[-60:]) / min(60, n)
    vol20 = sum(vols[-20:]) / min(20, len(vols)) if vols else 0
    vol_ratio = vols[-1] / vol20 if vol20 else 0
    pct = float(rows[-1][8]) if len(rows[-1]) > 8 and rows[-1][8] else 0.0

    return (
        f"收盘 {closes[-1]:.2f}元 ({pct:+.2f}%) | "
        f"MA5={ma5:.2f} MA20={ma20:.2f} MA60={ma60:.2f} | "
        f"量比(相对20日均量)={vol_ratio:.2f}x | 交易日={dates[-1]}"
    )


def fetch_technical_summary_opencli(
    code: str,
    *,
    limit: int = 60,
    reset_browser: bool = True,
    close_browser: bool = True,
) -> str:
    rows = fetch_kline_rows_opencli(
        code,
        limit=limit,
        close_browser=close_browser,
        reset_browser=reset_browser,
    )
    return technical_summary_from_kline_rows(rows)


def fetch_technical_summaries_batch_opencli(
    codes: list[str],
    *,
    limit: int = 60,
    reset_browser: bool = True,
    close_browser: bool = True,
) -> dict[str, str]:
    """批量技术面摘要（单 OpenCLI 会话）。"""
    rows_map = fetch_kline_rows_batch_opencli(
        codes,
        limit=limit,
        reset_browser=reset_browser,
        close_browser=close_browser,
    )
    out: dict[str, str] = {}
    for c, rows in rows_map.items():
        if rows:
            out[c] = technical_summary_from_kline_rows(rows)
        else:
            out[c] = "（OpenCLI 无 K 线数据）"
    return out


@dataclass
class SelectionProfileSnapshot:
    code: str
    name: str
    industry: str | None
    concepts: list[str]
    profile_text: str
    info_text: str
    sectors_text: str


def parse_industry_from_info(info_text: str) -> str | None:
    for label in ("所属行业", "行业", "行业分类", "板块"):
        value = _parse_label_value(info_text or "", label)
        if value:
            cleaned = re.split(r"[\s/|]+", value.strip())[0]
            if cleaned and cleaned not in {"-", "--"}:
                return cleaned
    return None


def parse_industry_from_sectors(sectors_text: str) -> str | None:
    text = (sectors_text or "").strip()
    if not text:
        return None

    highlight = text
    start = text.find("题材亮点")
    if start >= 0:
        end_candidates = [
            text.find("题材详情", start),
            text.find("所属板块", start),
            text.find("概念题材", start + 8),
        ]
        end = min((e for e in end_candidates if e > start), default=start + 600)
        highlight = text[start:end]

    m = re.search(r"行业背景\s*([^\n]+)", highlight)
    if m:
        raw = m.group(1).strip().strip("：:")
        if 2 <= len(raw) <= 80:
            first = raw.split(",")[0].strip()
            if first and first not in {"-", "--"}:
                return first

    block_idx = text.find("所属板块")
    if block_idx >= 0:
        block = text[block_idx : block_idx + 240]
        for level in ("三级", "二级", "一级"):
            m2 = re.search(rf"{level}\s*\n\s*([^\n]+)", block)
            if m2:
                val = m2.group(1).strip()
                if 2 <= len(val) <= 32 and val not in {"所属板块", "地区"}:
                    return val
    return None


def parse_concepts_from_sectors(sectors_text: str) -> list[str]:
    text = (sectors_text or "").strip()
    if not text:
        return []

    concepts: list[str] = []
    seen: set[str] = set()
    noise = {
        "概念题材",
        "题材",
        "题材亮点",
        "题材详情",
        "入选理由",
        "人气龙头",
        "所属板块",
        "一级",
        "二级",
        "三级",
        "地区",
    }

    for line in text.splitlines():
        line = line.strip()
        if not line or line in noise:
            continue
        m = re.match(r"^(.+?)\s+[-+]?\d+(?:\.\d+)?%$", line)
        if not m:
            continue
        name = m.group(1).strip()
        if len(name) < 2 or len(name) > 20:
            continue
        if name in seen or name in noise:
            continue
        if re.fullmatch(r"[\d.%]+", name):
            continue
        seen.add(name)
        concepts.append(name)
    return concepts[:24]


def build_selection_profile_text(
    info_text: str,
    sectors_text: str,
    *,
    max_len: int = 900,
) -> str:
    parts: list[str] = []
    text = sectors_text or ""

    bg = re.search(r"行业背景\s*([^\n]+)", text)
    if bg:
        parts.append(f"行业背景：{bg.group(1).strip()}")

    core = re.search(r"核心竞争力\s*([^\n]{10,260})", text)
    if core:
        parts.append(f"核心竞争力：{core.group(1).strip()}")

    block_idx = text.find("所属板块")
    if block_idx >= 0:
        block = text[block_idx : block_idx + 280].strip()
        if block:
            parts.append(block)

    reason = re.search(r"入选理由\s*\n+([^\n]{10,260})", text)
    if reason:
        parts.append(f"入选理由：{reason.group(1).strip()}")

    if not parts and info_text:
        parts.append(info_text.strip()[:400])

    merged = "\n\n".join(parts).strip()
    if len(merged) <= max_len:
        return merged or ""
    return merged[:max_len] + "\n\n...[已截断]..."


def selection_profile_from_payload(
    code: str,
    *,
    name: str,
    info_text: str,
    sectors_text: str,
) -> SelectionProfileSnapshot:
    c = code6(code)
    industry = parse_industry_from_sectors(sectors_text) or parse_industry_from_info(info_text)
    concepts = parse_concepts_from_sectors(sectors_text)
    profile_text = build_selection_profile_text(info_text, sectors_text)
    return SelectionProfileSnapshot(
        code=c,
        name=(name or c).strip() or c,
        industry=industry,
        concepts=concepts,
        profile_text=profile_text,
        info_text=info_text or "",
        sectors_text=sectors_text or "",
    )


def fetch_selection_profiles_batch(
    codes: list[str],
    *,
    wait_seconds: float = 2.0,
    close_browser: bool = True,
) -> dict[str, SelectionProfileSnapshot]:
    """轻量档案：行情 brief_info + F10 所属板块（入选股 enrich，约 2 页/股）。"""
    if not codes:
        return {}

    unique = [code6(c) for c in dict.fromkeys(code6(c) for c in codes)]
    out: dict[str, SelectionProfileSnapshot] = {}
    wait_arg = str(max(1, int(round(wait_seconds))))

    _maybe_close_before_nav()

    for c in unique:
        info_text = ""
        sectors_text = ""
        name = c
        try:
            _open_page(quote_url(c), label=c)
            _run_opencli(["browser", "wait", "time", wait_arg], timeout=10)
            raw = _eval_js(EXTRACT_QUOTE_JS)
            payload = json.loads(raw) if raw else {}
            name = (payload.get("name") or c).strip() or c
            info_text = payload.get("infoText") or ""

            _open_page(f10_url(c, "#/hxtc"), label=f"{c}-所属板块")
            _run_opencli(["browser", "wait", "time", "3"], timeout=15)
            app_raw = _eval_js(EXTRACT_F10_APP_JS, timeout=30)
            try:
                sectors_text = json.loads(app_raw) if app_raw else ""
            except json.JSONDecodeError:
                sectors_text = app_raw or ""
            if not isinstance(sectors_text, str):
                sectors_text = str(sectors_text)

            out[c] = selection_profile_from_payload(
                c,
                name=name,
                info_text=info_text,
                sectors_text=_truncate(sectors_text, F10_MAX_LEN),
            )
        except Exception as exc:  # noqa: BLE001
            out[c] = SelectionProfileSnapshot(
                code=c,
                name=name,
                industry=parse_industry_from_info(info_text),
                concepts=parse_concepts_from_sectors(sectors_text),
                profile_text=build_selection_profile_text(info_text, sectors_text)
                or f"获取失败: {exc}",
                info_text=info_text,
                sectors_text=sectors_text or f"获取失败: {exc}",
            )

    if close_browser:
        release_browser_session(close_tabs=True)

    return out


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if not args:
        args = ["600873", "600995", "003816"]
    result = fetch_quotes(args)
    for c, q in sorted(result.items()):
        print(f"{q.name}({c}): {q.price} ({q.change_pct:+.2f}%) [{q.source}]")
