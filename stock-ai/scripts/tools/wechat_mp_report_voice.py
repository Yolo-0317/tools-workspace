#!/usr/bin/env python3
"""热点/话题稿：分析报告腔扫描（读者转述 vs 行业观察）。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

# (pattern, 简短说明)
REPORT_VOICE_RULES: tuple[tuple[str, str], ...] = (
    (r"风向.{0,6}松", "政策风向归纳"),
    (r"政策.{0,4}松", "政策解读口吻"),
    (r"松绑", "行业报告词"),
    (r"拟放开|拟适当放开", "公文/研报用语"),
    (r"与其说", "作文对照结构"),
    (r"不如说", "作文对照结构"),
    (r"是一回事", "分论点腔"),
    (r"更常听见", "作者在归纳读者"),
    (r"对.{0,8}来说", "分析报告主语"),
    (r"不等于", "论文对照句"),
    (r"预期天然", "行业术语"),
    (r"不补叙事|调节奏", "制片行业术语"),
    (r"外部条件", "分析报告词"),
    (r"一拨问|另一拨|两拨人", "分论点腔"),
    (r"底下其实是|先说为什么", "提纲腔"),
    (r"硬盘里|排期轮不上|播出许可", "技术隐喻"),
    (r"沉没库存|库存去化|选择疲劳", "行业术语"),
    (r"陆续会.{0,8}冒出来|留得下来的", "展望总结腔"),
    (r"看不见背后", "报告腔"),
    (r"真正卡住的，往往不是", "专栏金句"),
    (r"评论区也好懂|担心很具体", "meta 点评读者"),
    (r"厂里另算|厂子那边另算", "分线分析"),
    (r"排期这条路上", "行业路线比喻"),
    (r"有人举", "分论点举例腔"),
    (r"服化道", "制片行业术语"),
    (r"一眼五年前|一眼\d+年前", "压缩怪句"),
    (r"那种压了", "分析报告举例腔"),
)


def scan_report_voice(text: str) -> list[tuple[str, str, str]]:
    """返回 (pattern说明, 正则, 命中片段)。"""
    hits: list[tuple[str, str, str]] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(">"):
            continue
        for pattern, label in REPORT_VOICE_RULES:
            m = re.search(pattern, stripped)
            if m:
                hits.append((label, pattern, stripped[:80]))
                break
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描正文分析报告腔")
    parser.add_argument("--text", default="", help="直接传正文")
    parser.add_argument("--file", default="", help="JSON 缓存或 .md，取 body_core 字段或全文")
    args = parser.parse_args()

    body = args.text
    if args.file:
        path = Path(args.file)
        raw = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            data = json.loads(raw)
            body = str(data.get("body_core") or "")
        else:
            body = raw

    hits = scan_report_voice(body)
    if not hits:
        print("OK 无分析报告腔命中")
        return 0
    print(f"FAIL {len(hits)} 处分析报告腔：")
    for label, pattern, snippet in hits:
        print(f"  · [{label}] /{pattern}/ …{snippet}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
