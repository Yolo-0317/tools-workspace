#!/usr/bin/env python3
"""财经快讯利好/利空分类（关键词打分，供 sync_macro_news 每 15 分钟落库）。"""

from __future__ import annotations

from typing import Literal

NewsSentiment = Literal["bullish", "bearish", "neutral"]

SENTIMENT_LABEL: dict[NewsSentiment, str] = {
    "bullish": "利好",
    "bearish": "利空",
    "neutral": "中性",
}

# 长词优先匹配（按长度降序在运行时排序）
_BULLISH_KEYWORDS = (
    "业绩预增",
    "净利润增长",
    "超预期",
    "估值修复",
    "政策利好",
    "中标",
    "获批",
    "签约",
    "扩产",
    "回购",
    "增持",
    "举牌",
    "降准",
    "降息",
    "刺激",
    "宽松",
    "复苏",
    "回暖",
    "景气",
    "向好",
    "改善",
    "涨停",
    "大涨",
    "突破",
    "新高",
    "上涨",
    "增长",
    "盈利",
    "利好",
)

_BEARISH_KEYWORDS = (
    "不及预期",
    "业绩预亏",
    "净利润下滑",
    "风险提示",
    "立案调查",
    "行政处罚",
    "减持",
    "解禁",
    "违约",
    "退市",
    "制裁",
    "收紧",
    "加息",
    "暂停",
    "暴雷",
    "亏损",
    "预亏",
    "跌停",
    "大跌",
    "破位",
    "新低",
    "下跌",
    "下滑",
    "放缓",
    "萎缩",
    "抛售",
    "杀跌",
    "利空",
)

_SORTED_BULLISH = tuple(sorted(_BULLISH_KEYWORDS, key=len, reverse=True))
_SORTED_BEARISH = tuple(sorted(_BEARISH_KEYWORDS, key=len, reverse=True))


def _score_keywords(blob: str, keywords: tuple[str, ...]) -> int:
    score = 0
    for kw in keywords:
        if kw in blob:
            score += max(2, len(kw) // 2)
    return score


def classify_news_sentiment(title: str, summary: str = "") -> NewsSentiment:
    """基于标题+摘要关键词判断 A 股语境下的利好/利空/中性。"""
    blob = f"{title or ''} {summary or ''}".strip()
    if not blob:
        return "neutral"

    if "利好" in blob and "利空" not in blob:
        return "bullish"
    if "利空" in blob and "利好" not in blob:
        return "bearish"

    bull = _score_keywords(blob, _SORTED_BULLISH)
    bear = _score_keywords(blob, _SORTED_BEARISH)

    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"


def sentiment_label(sentiment: str | None) -> str:
    key = sentiment if sentiment in SENTIMENT_LABEL else "neutral"
    return SENTIMENT_LABEL[key]  # type: ignore[index]
