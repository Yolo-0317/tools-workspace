#!/usr/bin/env python3
"""东方财富 SOP 数据采集（OpenCLI），供 Top5 并发分析使用。"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.tools.fetch_eastmoney_quotes import (
    fetch_full_sop_batch,
    fetch_full_sop_data,
    fetch_technical_summaries_batch_opencli,
)


def fetch_sop_data(code: str) -> dict[str, str]:
    """OpenCLI 采集东财 8 个维度，返回原始文本字典。"""
    return fetch_full_sop_data(code)


def build_preliminary_report(code: str, data: dict[str, str]) -> str:
    code = str(code).split(".")[0].zfill(6)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""# {code} 初步分析报告（SOP 版）

**采集时间**: {now}
**股票代码**: {code}
**数据来源**: OpenCLI 东财浏览器采集

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

## 八、委比委差买卖盘

```
{data.get("委比委差买卖盘", "未获取")}
```
"""


def extract_and_save(code: str, output_dir: str | Path) -> str:
    """采集并保存初步报告，返回文件路径。"""
    code = str(code).split(".")[0].zfill(6)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data = fetch_sop_data(code)
    report = build_preliminary_report(code, data)
    out_path = output_dir / f"{code}_初步报告_SOP版.md"
    out_path.write_text(report, encoding="utf-8")
    return str(out_path)


def extract_and_save_batch(
    codes: list[str],
    output_dir: str | Path,
    *,
    chain_technical: bool = False,
) -> dict[str, str] | tuple[dict[str, str], dict[str, str]]:
    """批量 SOP 采集（单 OpenCLI 会话），返回 code -> 报告路径。

    chain_technical=True 时在同一浏览器会话内续拉 K 线，并返回 (paths, technical_map)。
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_map = fetch_full_sop_batch(codes, close_browser=not chain_technical)
    paths: dict[str, str] = {}
    for code, data in data_map.items():
        report = build_preliminary_report(code, data)
        out_path = output_dir / f"{code}_初步报告_SOP版.md"
        out_path.write_text(report, encoding="utf-8")
        paths[code] = str(out_path)

    if not chain_technical:
        return paths

    tech_map = fetch_technical_summaries_batch_opencli(
        list(paths.keys()),
        reset_browser=False,
        close_browser=True,
    )
    return paths, tech_map


def _extract_worker(args: tuple[str, str]) -> tuple[str, str, str | None]:
    """兼容多进程 worker（OpenCLI 建议单会话；保留接口供旧调用）。"""
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
