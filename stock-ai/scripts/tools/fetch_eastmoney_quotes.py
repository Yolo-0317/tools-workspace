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
import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_OPENCLI = Path.home() / ".nvm/versions/node/v24.14.1/bin/opencli"

EXTRACT_QUOTE_JS = r"""
JSON.stringify({
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
    const text = (a?.innerText || '').replace(/\s+/g, ' ').trim();
    const href = a?.href || '';
    if (text && href) items.push({ time, text, href });
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


def _strip_proxy_env(env: dict[str, str]) -> dict[str, str]:
    for key in (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
        "http_proxy", "https_proxy", "all_proxy",
    ):
        env.pop(key, None)
    env["NO_PROXY"] = "*"
    return env


def _opencli_bin() -> str:
    return os.getenv("OPENCLI_BIN", str(DEFAULT_OPENCLI))


def _run_opencli(args: list[str], *, timeout: float = 60) -> tuple[str, str, int]:
    bin_path = _opencli_bin()
    if not Path(bin_path).exists():
        raise FileNotFoundError(f"未找到 opencli: {bin_path}")

    env = _strip_proxy_env(os.environ.copy())
    nvm_bin = str(Path(bin_path).parent)
    env["PATH"] = f"{nvm_bin}:{env.get('PATH', '')}"

    proc = subprocess.run(
        [bin_path, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return proc.stdout.strip(), proc.stderr.strip(), proc.returncode


def _reset_browser() -> None:
    _run_opencli(["browser", "close"], timeout=15)


def _close_browser_if(enabled: bool) -> None:
    if enabled:
        _run_opencli(["browser", "close"], timeout=15)


def _reset_browser_if(enabled: bool) -> None:
    if enabled:
        _reset_browser()


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


def _open_page(url: str, *, label: str = "") -> None:
    last_err = ""
    for attempt in range(2):
        if attempt:
            _run_opencli(["browser", "close"], timeout=15)
        stdout, stderr, rc = _run_opencli(["browser", "open", url])
        if rc == 0:
            return
        last_err = stderr or stdout
        if "stale page" not in last_err.lower():
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
        _run_opencli(["browser", "close"], timeout=15)

    if not raw:
        return []
    try:
        klines = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"解析 K 线 JSON 失败 {c}: {raw[:200]}") from exc
    if not isinstance(klines, list):
        return []
    return kline_strings_to_rows([str(x) for x in klines])


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
        _run_opencli(["browser", "close"], timeout=15)
    return out


def fetch_opencli_latest_kline_row(code: str) -> list[str] | None:
    rows = fetch_kline_rows_opencli(code, limit=2, close_browser=True)
    return rows[-1] if rows else None


def fetch_fund_flow_text_opencli(code: str, *, close_browser: bool = True) -> str:
    c = code6(code)
    _run_opencli(["browser", "close"], timeout=15)
    _open_page(fund_flow_url(c), label=c)
    _run_opencli(["browser", "wait", "time", "2"], timeout=10)
    raw = _eval_js(EXTRACT_ZJLX_JS)
    if close_browser:
        _run_opencli(["browser", "close"], timeout=15)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


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
        _open_page(quote_url(c), label=c)
        _wait_page_ready(fallback_seconds=wait_seconds)
        raw = _eval_js(EXTRACT_QUOTE_JS)
        if not raw:
            continue
        payload = json.loads(raw)
        snap = parse_sop_snapshot(c, payload)
        if not snap:
            continue

        if include_fund_flow_page:
            _open_page(fund_flow_url(c), label=f"{c}-zjlx")
            _run_opencli(["browser", "wait", "time", "2"], timeout=10)
            ff_raw = _eval_js(EXTRACT_ZJLX_JS)
            try:
                ff_text = json.loads(ff_raw)
            except json.JSONDecodeError:
                ff_text = ff_raw
            if ff_text:
                snap.fund_flow_text = ff_text

        snapshots[c] = snap

    if close_browser:
        _run_opencli(["browser", "close"], timeout=15)

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
    if reset_browser:
        _reset_browser()
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
    _run_opencli(["browser", "close"], timeout=15)
    _open_page(kuaixun_url(), label="kuaixun")
    _run_opencli(["browser", "wait", "time", "3"], timeout=15)
    raw = _eval_js(EXTRACT_KUAIXUN_JS, timeout=30)
    if close_browser:
        _run_opencli(["browser", "close"], timeout=15)
    if not raw:
        return []
    items = json.loads(raw)
    return items[:limit] if isinstance(items, list) else []


BREADTH_PAGE_URL = "https://quote.eastmoney.com/zs000001.html"

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
]

WTI_OIL_INDEX_URL = "https://data.eastmoney.com/cjsj/hyzs_EMI01508580.html"


def unify_quote_url(code: str) -> str:
    return f"https://quote.eastmoney.com/unify/r/{code}"


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
        _run_opencli(["browser", "close"], timeout=15)

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

    _run_opencli(["browser", "close"], timeout=15)

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
        _run_opencli(["browser", "close"], timeout=15)

    return out


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if not args:
        args = ["600873", "600995", "003816"]
    result = fetch_quotes(args)
    for c, q in sorted(result.items()):
        print(f"{q.name}({c}): {q.price} ({q.change_pct:+.2f}%) [{q.source}]")
