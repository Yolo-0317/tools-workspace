#!/usr/bin/env python3
"""从东方财富行情页抓取现价（OpenCLI Browser，单会话批量）。"""

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
  infoText: document.querySelector('.brief_info_c')?.innerText || ''
})
"""


@dataclass
class EastmoneyQuote:
    code: str
    name: str
    price: float
    change_amt: float
    change_pct: float
    source: str = "eastmoney-opencli"


def code_to_prefix(code: str) -> str:
    code = str(code).split(".")[0].zfill(6)
    return "sh" if code.startswith(("6", "5")) else "sz"


def quote_url(code: str) -> str:
    code = str(code).split(".")[0].zfill(6)
    return f"https://quote.eastmoney.com/{code_to_prefix(code)}{code}.html"


def _opencli_bin() -> str:
    return os.getenv("OPENCLI_BIN", str(DEFAULT_OPENCLI))


def _run_opencli(args: list[str], *, timeout: float = 45) -> tuple[str, str, int]:
    bin_path = _opencli_bin()
    if not Path(bin_path).exists():
        raise FileNotFoundError(f"未找到 opencli: {bin_path}")

    env = os.environ.copy()
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


def _parse_label_value(text: str, label: str) -> str | None:
    match = re.search(rf"{re.escape(label)}[：:]\s*([^\t\n]+)", text)
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

    # 负涨幅带双负号，如 -0.26-2.69%
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

    # 无分隔拼接，如 0.376.36% / 1.329.23%：用「去掉末尾涨幅数字」反推涨跌额
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
    code = str(code).split(".")[0].zfill(6)
    name = (payload.get("name") or code).strip() or code
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
        code=code,
        name=name,
        price=price,
        change_amt=change_amt,
        change_pct=change_pct,
    )


def _open_quote_page(code: str, url: str) -> None:
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
    raise RuntimeError(f"打开东财行情页失败 {code}: {last_err}")


def fetch_quotes_opencli(
    codes: list[str],
    *,
    wait_seconds: float = 2.0,
    close_browser: bool = True,
) -> dict[str, EastmoneyQuote]:
    """在同一 OpenCLI 会话中依次打开东财行情页并解析现价。"""
    if not codes:
        return {}

    unique_codes = sorted({str(c).split(".")[0].zfill(6) for c in codes})
    quotes: dict[str, EastmoneyQuote] = {}

    _run_opencli(["browser", "close"], timeout=15)

    for code in unique_codes:
        url = quote_url(code)
        _open_quote_page(code, url)

        wait_arg = str(max(1, int(round(wait_seconds))))
        _run_opencli(["browser", "wait", "time", wait_arg], timeout=10)

        stdout, stderr, rc = _run_opencli(["browser", "eval", EXTRACT_QUOTE_JS])
        if rc != 0:
            raise RuntimeError(f"读取东财行情失败 {code}: {stderr or stdout}")

        raw = stdout.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"解析东财行情 JSON 失败 {code}: {raw[:200]}") from exc

        quote = parse_quote_payload(code, payload)
        if quote:
            quotes[code] = quote

    if close_browser:
        _run_opencli(["browser", "close"], timeout=15)

    return quotes


def fetch_quotes(
    codes: list[str],
    *,
    wait_seconds: float = 2.0,
) -> dict[str, EastmoneyQuote]:
    """抓取东财现价（OpenCLI 打开 quote.eastmoney.com 行情页）。"""
    return fetch_quotes_opencli(codes, wait_seconds=wait_seconds)


if __name__ == "__main__":
    import sys

    codes = sys.argv[1:] or ["600873", "600995", "003816"]
    result = fetch_quotes(codes)
    for code, q in sorted(result.items()):
        print(f"{q.name}({code}): {q.price} ({q.change_pct:+.2f}%) [{q.source}]")
