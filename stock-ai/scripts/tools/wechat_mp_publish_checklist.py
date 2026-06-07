#!/usr/bin/env python3
"""发布前五步人工审清单（终端打印，API 无法代做）。"""

from __future__ import annotations

MANUAL_PUBLISH_STEPS: tuple[tuple[str, str], ...] = (
    ("预览", "mp.weixin.qq.com 打开草稿 → 手机预览排版/插图"),
    ("标题", "标题与正文数字一致；无普跌/暴涨等与盘面不符的词"),
    ("开头", "首段 2 句结论可见（在「盘面速览」之前）"),
    ("原创", "发布时勾选原创，分类选财经/科技"),
    ("话题", "正文文末已含 # 行；原创发布后可在后台 # 再确认；可选引导「推荐 ♡」"),
)


def format_manual_publish_checklist() -> str:
    lines = ["【发布前五步】"]
    for i, (name, detail) in enumerate(MANUAL_PUBLISH_STEPS, 1):
        lines.append(f"  {i}. {name}：{detail}")
    return "\n".join(lines)


def print_manual_publish_checklist() -> None:
    print(format_manual_publish_checklist())
