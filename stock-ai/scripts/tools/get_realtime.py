"""指定交易日行情：OpenCLI 东财 K 线（禁止 HTTP API 直联）。"""

from __future__ import annotations

import re
import sys
from datetime import datetime

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.fetch_eastmoney_quotes import fetch_kline_rows_opencli


def normalize_code(code: str) -> str:
    digits = re.sub(r"\D", "", str(code))
    if len(digits) < 6:
        raise ValueError(f"无法解析证券代码: {code}")
    return digits[:6].zfill(6)


def get_realtime_info(code: str, trade_date: str) -> dict:
    code6 = normalize_code(code)
    target = datetime.strptime(trade_date, "%Y%m%d").strftime("%Y-%m-%d")
    rows = fetch_kline_rows_opencli(code6, limit=240, close_browser=True)
    for r in rows:
        if r and r[0] == target:
            return {
                "trade_date": r[0],
                "今开": float(r[1]),
                "当前": float(r[2]),
                "最高": float(r[3]),
                "最低": float(r[4]),
                "成交量": float(r[5]),
                "成交额": float(r[6]),
                "涨跌幅": float(r[8]) if len(r) > 8 and r[8] else 0.0,
                "source": "eastmoney-opencli",
            }
    raise ValueError(f"{code} 未找到指定交易日 {trade_date} 的行情数据")


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "873527"
    d = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y%m%d")
    print(get_realtime_info(c, d))
