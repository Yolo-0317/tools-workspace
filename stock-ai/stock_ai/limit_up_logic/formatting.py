from __future__ import annotations

from datetime import date, datetime

from .models import LimitUpResult


IDENTITY_LABELS = {
    "DATA_INSUFFICIENT": "数据不足",
    "RISK_VETOED": "风险否决",
    "RELAY_FAILED": "接力失败",
    "SECOND_WAVE_CANDIDATE": "二波加速候选",
    "POST_LIMIT_HOLDING": "首板后承接",
    "FIRST_BOARD_SETUP": "首板预备",
    "NORMAL_TREND": "普通趋势",
}

GENE_LABELS = {
    "STRONG": "强",
    "MEDIUM": "中",
    "WEAK": "弱",
    "UNKNOWN": "未知",
}

MISSING_LABELS = {
    "daily_bars_10": "至少10根完整日线",
    "daily_bars_20": "20日趋势与压力",
    "turnover_rate": "换手率",
    "active_themes": "已验证活跃题材",
    "sector_change_pct": "实时板块涨幅",
    "sector_limit_up_count": "板块涨停家数",
    "sector_leader_strength": "板块领涨股强度",
    "main_net_inflow_ratio": "当日主力净流入占比",
    "consecutive_inflow_days": "连续资金流向",
    "auction_strength": "竞价强度",
    "seal_quality": "封单质量",
    "reopen_count": "炸板回封次数",
}


def _joined(items: tuple[str, ...], fallback: str) -> str:
    return "；".join(items[:4]) if items else fallback


def _cutoff(value: datetime | date | None) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    return "未知"


def format_limit_up_logic_card(result: LimitUpResult) -> str:
    identity = IDENTITY_LABELS[result.identity]
    gene = GENE_LABELS[result.gene]
    paths = result.paths
    missing = tuple(MISSING_LABELS.get(item, item) for item in result.missing_fields)
    return "\n".join(
        (
            f"【涨停逻辑】{identity}｜涨停基因：{gene}｜评分：{result.score.total}/100",
            f"- 封板驱动：{_joined(result.drivers, '未形成可验证的封板驱动组合')}",
            f"- 封板前提：{_joined(result.prerequisites, '需要盘中重新验证')}",
            f"- 压制因素：{_joined(result.suppressors, '暂无结构性压制证据')}",
            f"- 三路径：涨停加速{paths.acceleration}% / 趋势延续{paths.continuation}% / 接力失败{paths.failure}%",
            f"- 数据缺口：{'；'.join(missing) if missing else '无'}",
            f"- 数据截止：{_cutoff(result.data_cutoff)}",
        )
    )
