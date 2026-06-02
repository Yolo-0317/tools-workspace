"""公众号公开稿：与作者个人持仓/账户隔离。"""

from __future__ import annotations

import re

# 注入各篇 LLM prompt / system
PUBLIC_MP_WRITER_RULE = """
【公众号公开稿】面向不特定读者发布，与作者个人无关。严禁出现：
作者持仓、已持仓/非持仓、我的仓位、个人账户、执行卡、P0～P4、结合持仓、第一人称「我」的仓位配置。
可将纪律写成「短线选手」「观望者」的通用规则；仓位用「情绪周期风控参考」等市场语言。
严禁出现：翻墙、代理订阅、Clash、Mihomo、机场节点、substore 等敏感网络工具描述。
"""

# 成稿后兜底清洗（humanize 末尾调用）
_LINE_DROP_RE = re.compile(
    r"^(.*(?:结合持仓|执行卡|P[0-4]\s|我的持仓|作者持仓|个人仓位|"
    r"clash|mihomo|substore|机场|订阅合并).*)$",
    re.I,
)

_INLINE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"（已持仓）", ""),
    (r"（非持仓）", ""),
    (r"📌已持仓", ""),
    (r"已持仓", ""),
    (r"非持仓标的", "观察标的"),
    (r"非持仓", ""),
    (r"结合持仓", "结合盘面"),
    (r"持仓与计划", "观察与纪律"),
    (r"以执行卡为准", "按技术纪律"),
    (r"持仓标的", "观察标的"),
    (r"不与新信号冲突加仓", "不与原策略冲突追高"),
    (r"已写入次日盘中监控", "纳入次日观察池"),
    (r"个人研究笔记", "研究笔记"),
    (r"仓位上限", "情绪风控仓位参考"),
    (r"是否持仓、", ""),
    (r"是否持仓", ""),
    (r"已持仓如何处理", "标的优先级如何排序"),
    (r"仍遵守不追高、不满仓新开仓", "仍建议不追高、控制单票仓位"),
    (r"执行卡", "规则文件"),
    (r"hub\.yoloworld\.site[^\s]*", "自有看板"),
    (r"yoloworld\.site", "自有域名"),
)


def sanitize_public_mp_text(text: str) -> str:
    """公开稿终稿清洗（三篇通用）。"""
    if not text:
        return text
    lines_out: list[str] = []
    for line in text.splitlines():
        if _LINE_DROP_RE.match(line.strip()):
            continue
        s = line
        for pat, repl in _INLINE_REPLACEMENTS:
            s = re.sub(pat, repl, s)
        s = re.sub(r"P[0-5][^\n]*", "", s)
        s = re.sub(r"\s{2,}", " ", s).strip()
        if s or not line.strip():
            lines_out.append(s)
    merged = "\n".join(lines_out)
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    return merged.strip()
