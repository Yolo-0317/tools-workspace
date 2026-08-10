"""分板块基础过滤与风控阈值（主板 / 科创板 / 创业板）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BoardKind(str, Enum):
    MAIN = "main"
    KCB = "kcb"  # 科创板 688/689
    GEM = "gem"  # 创业板 300/301
    BJ = "bj"  # 北交所 92


@dataclass(frozen=True)
class BoardFilterParams:
    min_price: float
    max_price: float
    min_amount_qian: float  # MySQL amount = Tushare 千元
    chase_pct_max: float
    drop_exclude_pct: float
    limit_down_pct: float
    three_up_total_chg_max: float
    pullback_prev_strength: float
    liquidity_score_cap_wan: float
    momentum_risk_pct: float  # |pct| 超过此值额外风险扣分
    enable_three_up: bool = True  # 科创板回测显示三连阳胜率 ~39%，默认关闭
    signal_day_pct_max: float = 99.0  # 信号日涨幅上限（防追高）
    # 科创板专用动作门槛（None = 沿用全局 regime 门槛）
    action_strong_threshold: float | None = None
    action_buy_threshold: float | None = None
    action_buy_threshold_neutral: float | None = None  # 震荡市更高买入门槛
    action_observe_threshold: float | None = None
    action_ambush_threshold: float | None = None
    pullback_score_bonus: float = 0.0  # 空中加油额外加分
    block_on_weak_market: bool = False  # 弱势市场禁止新开仓信号
    block_on_neutral_market: bool = False  # 震荡市禁止（科创板回测：strong 67% vs neutral 40%）
    max_entry_score: float | None = None  # 总分超过此值不入场（防过热）
    max_signals_per_day: int | None = None  # 同日最多保留 N 只（按总分，科创板）


# 主板 / 中小板 / 深市主板（5–20 元 + 流动性；回测见 backtest_selection_combined --board main）
MAIN_BOARD = BoardFilterParams(
    min_price=5.0,
    max_price=20.0,
    min_amount_qian=50_000,  # 5000 万
    chase_pct_max=5.0,
    drop_exclude_pct=-7.0,
    limit_down_pct=-9.5,
    three_up_total_chg_max=15.0,
    pullback_prev_strength=20.0,
    liquidity_score_cap_wan=200_000,
    momentum_risk_pct=8.0,
    enable_three_up=True,
    signal_day_pct_max=6.0,
    max_signals_per_day=5,
)

# 科创板：空中加油为主；震荡市可开仓；略降买入门槛以提高信号频率（回测 2023–2026）
KCB_BOARD = BoardFilterParams(
    min_price=12.0,
    max_price=800.0,
    min_amount_qian=30_000,  # 3000 万
    chase_pct_max=5.0,
    drop_exclude_pct=-14.0,
    limit_down_pct=-19.5,
    three_up_total_chg_max=12.0,
    pullback_prev_strength=25.0,
    liquidity_score_cap_wan=500_000,
    momentum_risk_pct=10.0,
    enable_three_up=False,
    signal_day_pct_max=6.0,
    action_strong_threshold=72.0,
    action_buy_threshold=55.0,
    action_buy_threshold_neutral=58.0,
    action_observe_threshold=48.0,
    action_ambush_threshold=50.0,
    pullback_score_bonus=10.0,
    block_on_weak_market=True,
    block_on_neutral_market=False,
    max_entry_score=None,
    max_signals_per_day=3,
)

# 创业板：参数介于主板与科创板之间（便于后续扩展）
GEM_BOARD = BoardFilterParams(
    min_price=8.0,
    max_price=120.0,
    min_amount_qian=30_000,  # 3000 万
    chase_pct_max=6.0,
    drop_exclude_pct=-10.0,
    limit_down_pct=-19.5,
    three_up_total_chg_max=18.0,
    pullback_prev_strength=24.0,
    liquidity_score_cap_wan=300_000,
    momentum_risk_pct=10.0,
)

_BOARD_MAP: dict[BoardKind, BoardFilterParams] = {
    BoardKind.MAIN: MAIN_BOARD,
    BoardKind.KCB: KCB_BOARD,
    BoardKind.GEM: GEM_BOARD,
    BoardKind.BJ: MAIN_BOARD,
}


def code6(ts_code: str) -> str:
    return str(ts_code).split(".")[0].zfill(6)


def detect_board(ts_code: str) -> BoardKind:
    c = code6(ts_code)
    if c.startswith(("688", "689")):
        return BoardKind.KCB
    if c.startswith(("300", "301")):
        return BoardKind.GEM
    if c.startswith("92"):
        return BoardKind.BJ
    return BoardKind.MAIN


def is_main_board_code(ts_code: str) -> bool:
    """沪深主板 A 股（含原中小板 002/003），不含科创/创业/北交所。"""
    return detect_board(ts_code) == BoardKind.MAIN


_MAIN_BOARD_PREFIXES = ("600", "601", "603", "605", "000", "001", "002", "003")


def sql_universe_clause(board: str) -> str:
    """回测 SQL WHERE 片段：kcb / main / all。"""
    b = board.lower()
    if b == "kcb":
        return "(ts_code LIKE '688%' OR ts_code LIKE '689%')"
    if b == "main":
        parts = " OR ".join(f"ts_code LIKE '{p}%'" for p in _MAIN_BOARD_PREFIXES)
        return f"(({parts}) AND ts_code NOT LIKE '688%' AND ts_code NOT LIKE '689%')"
    return "1=1"


def max_signals_for_code(ts_code: str, *, legacy_unified: bool = False) -> int | None:
    p = get_board_params(ts_code, legacy_unified=legacy_unified)
    return p.max_signals_per_day


def get_board_params(ts_code: str, *, legacy_unified: bool = False) -> BoardFilterParams:
    """legacy_unified=True 时全市场沿用主板 5–20 元（用于回测对照）。"""
    if legacy_unified:
        return MAIN_BOARD
    return _BOARD_MAP[detect_board(ts_code)]


def passes_base_filter(
    ts_code: str,
    close: float,
    amount_qian: float,
    *,
    legacy_unified: bool = False,
) -> bool:
    p = get_board_params(ts_code, legacy_unified=legacy_unified)
    return p.min_price <= float(close) <= p.max_price and float(amount_qian) >= p.min_amount_qian


def liquidity_score_from_wan(amount_wan: float, params: BoardFilterParams) -> float:
    if amount_wan <= 0:
        return 0.0
    cap = params.liquidity_score_cap_wan / 10.0
    return min(10.0, amount_wan / cap) if cap > 0 else 0.0


def board_action_threshold_overrides(
    board: BoardFilterParams,
    *,
    market_regime: str | None = None,
) -> dict[str, float] | None:
    """板块自定义动作门槛；震荡市可提高买入门槛。"""
    mapping = {
        "强势关注": board.action_strong_threshold,
        "观察买入": board.action_buy_threshold,
        "继续观察": board.action_observe_threshold,
        "小仓埋伏": board.action_ambush_threshold,
    }
    if all(v is None for v in mapping.values()) and board.action_buy_threshold_neutral is None:
        return None
    overrides = {k: v for k, v in mapping.items() if v is not None}
    if market_regime == "neutral" and board.action_buy_threshold_neutral is not None:
        overrides["观察买入"] = board.action_buy_threshold_neutral
    return overrides or None


def should_block_weak_market(
    board: BoardFilterParams,
    *,
    market_regime: str,
    board_market_regime: str | None = None,
) -> bool:
    """板块级市场过滤：弱势/震荡市可禁止新开仓信号。"""
    regime = board_market_regime or market_regime
    if board.block_on_weak_market and regime == "weak":
        return True
    if board.block_on_neutral_market and regime == "neutral":
        return True
    return False


def passes_crash_filter(ts_code: str, pct_chg: float, *, legacy_unified: bool = False) -> bool:
    """True = 未触发大跌/跌停剔除。"""
    p = get_board_params(ts_code, legacy_unified=legacy_unified)
    pct = float(pct_chg)
    return pct > p.drop_exclude_pct and pct > p.limit_down_pct
