#!/usr/bin/env python3
"""东方财富 SOP 数据采集（Playwright），供 Top5 并发分析使用。"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
F10_MAX_LEN = 5000
ROOT = Path(__file__).resolve().parents[2]


def get_market_prefix(code: str) -> tuple[str, str]:
    code = str(code).split(".")[0].zfill(6)
    if code.startswith(("60", "68")):
        return "sh", "SH"
    return "sz", "SZ"


def fetch_sop_data(code: str) -> dict[str, str]:
    """用 Playwright 采集东财 8 个维度，返回原始文本字典。"""
    from playwright.sync_api import sync_playwright

    code = str(code).split(".")[0].zfill(6)
    prefix_lower, prefix_upper = get_market_prefix(code)
    results: dict[str, str] = {}

    chrome = os.getenv("CHROME_EXECUTABLE", CHROME_PATH)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=chrome)
        page = browser.new_page()

        quote_url = f"https://quote.eastmoney.com/{prefix_lower}{code}.html"
        try:
            page.goto(quote_url, timeout=15000)
            page.wait_for_selector(".brief_info_c", timeout=10000)
            page.wait_for_timeout(1500)
            results["基本面"] = (
                page.evaluate('document.querySelector(".brief_info_c")?.innerText') or "未找到基本面数据"
            )
            results["资金面"] = (
                page.evaluate('document.querySelector(".zjl_charts")?.innerText') or "未找到资金面数据"
            )
            results["委比委差买卖盘"] = (
                page.evaluate('document.querySelector(".sider_quote_price2")?.innerText')
                or "未找到委比/委差数据"
            )
        except Exception as exc:  # noqa: BLE001
            err = f"获取失败: {exc}"
            results["基本面"] = err
            results["资金面"] = err
            results["委比委差买卖盘"] = err

        f10_base = (
            f"https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html"
            f"?type=web&code={prefix_upper}{code}&color=b"
        )
        for name, path in {
            "财务面": "#/cwfx",
            "消息面": "#/zxgg",
            "研报面": "#/yjbg",
            "所属板块": "#/hxtc",
            "盈利预测": "#/ylyc",
        }.items():
            try:
                page.goto(f10_base + path, timeout=15000)
                page.wait_for_selector("#app", timeout=10000)
                page.wait_for_timeout(2500)
                text = page.evaluate('document.querySelector("#app")?.innerText || ""') or ""
                if len(text) > F10_MAX_LEN:
                    text = text[:F10_MAX_LEN] + "\n\n...[内容过长已截断]..."
                results[name] = text.strip() or "页面为空或未加载出数据"
            except Exception as exc:  # noqa: BLE001
                results[name] = f"获取失败: {exc}"

        browser.close()
    return results


def build_preliminary_report(code: str, data: dict[str, str]) -> str:
    code = str(code).split(".")[0].zfill(6)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""# {code} 初步分析报告（SOP 版）

**采集时间**: {now}
**股票代码**: {code}
**数据来源**: Playwright 实时采集

---

## 一、基本面（3.1 行情页）

```
{data.get("基本面", "未获取")}
```

## 二、资金面（3.2 资金流向）

```
{data.get("资金面", "未获取")}
```

## 三、财务面（3.4 F10财务分析）

```
{data.get("财务面", "未获取")}
```

## 四、消息面（3.5 资讯公告）

```
{data.get("消息面", "未获取")}
```

## 五、研报面（3.6 研究报告）

```
{data.get("研报面", "未获取")}
```

## 六、所属板块（3.7 核心题材）

```
{data.get("所属板块", "未获取")}
```

## 七、盈利预测（3.8 盈利预测）

```
{data.get("盈利预测", "未获取")}
```
"""


def extract_and_save(code: str, output_dir: str | Path) -> str:
    """采集并保存初步报告，返回文件路径。"""
    code = str(code).split(".")[0].zfill(6)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        import playwright  # noqa: F401
    except ImportError:
        return _extract_via_system_python(code, output_dir)

    data = fetch_sop_data(code)
    report = build_preliminary_report(code, data)
    out_path = output_dir / f"{code}_初步报告_SOP版.md"
    out_path.write_text(report, encoding="utf-8")
    return str(out_path)


def _extract_via_system_python(code: str, output_dir: Path) -> str:
    """当前解释器无 playwright 时，回退到系统 python3。"""
    cmd = [
        "python3",
        str(Path(__file__).resolve()),
        str(code),
        str(output_dir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=str(ROOT))
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "子进程 SOP 采集失败").strip()[:500])
    out_path = output_dir / f"{code}_初步报告_SOP版.md"
    if not out_path.exists():
        raise RuntimeError(f"SOP 报告未生成: {out_path}")
    return str(out_path)


def _extract_worker(args: tuple[str, str]) -> tuple[str, str, str | None]:
    """多进程 worker：(code, output_dir) -> (code, path, error)."""
    code, output_dir = args
    try:
        path = extract_and_save(code, output_dir)
        return code, path, None
    except Exception as exc:  # noqa: BLE001
        return code, "", str(exc)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 eastmoney_sop_extract.py <code> <output_dir>", file=sys.stderr)
        raise SystemExit(1)
    print(extract_and_save(sys.argv[1], sys.argv[2]))
