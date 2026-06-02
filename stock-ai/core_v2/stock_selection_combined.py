#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合选股策略：全周期牛股捕捉系统
集成三个核心逻辑：
1. 3年大底箱体突破 (Macro Breakout) - 宏观趋势反转
2. 低位放量三连阳 (Volume Surge) - 主力建仓异动
3. 空中加油 (MA20 Pullback) - 强势股二次拉升
"""

import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径（须在 fetch_opencli_sop / scripts 导入之前）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from fetch_opencli_sop import get_market_sentiment

load_dotenv()

# ============================================
# 策略参数
# ============================================

# 1. 3年大底参数
BOX_PERIOD = 700
BOX_WIDTH_MAX = 80
DIST_FROM_250D_HIGH_MAX = -2
DIST_FROM_250D_LOW_MAX = 100

# 2. 三连阳参数
THREE_UP_MIN_CHG = 1.0           # 每日最小涨幅
THREE_UP_TOTAL_CHG_MAX = 15.0    # 3日累计最大涨幅（避免追高）
THREE_UP_VOL_RATIO = 1.5         # 成交额相对于5日均值的倍数

# 3. 空中加油参数
PULLBACK_MA20_DIST = 3.0         # 距离MA20的最大距离（%）
PULLBACK_PREV_STRENGTH = 20.0    # 前期20日涨幅要求（%）
PULLBACK_VOL_DECREASE = 0.8      # 回调时成交量相对于5日均值的比例（缩量）

# 4. 早埋伏参数（新增，不影响原策略）
AMBUSH_NEAR_BOX_TOP_MIN = -8.0   # 距离箱顶下方不超过8%
AMBUSH_NEAR_BOX_TOP_MAX = -1.0   # 距离箱顶至少1%（尚未突破）
AMBUSH_BOX_WIDTH_MAX = 100       # 允许更宽箱体
AMBUSH_MA20_SLOPE_MIN = 0.0      # MA20斜率不为负
AMBUSH_VOL_RATIO_MIN = 0.9       # 成交量不萎缩过度
AMBUSH_VOL_RATIO_MAX = 1.6       # 也不要求放巨量

# 5. 基本面红线参数
ROE_MIN = 3.0                   # 最小 ROE (%)
NET_PROFIT_GROWTH_MIN = -20.0   # 最小净利润增长率 (%)
EXCLUDE_ST = True               # 是否剔除 ST/*ST

# 基础过滤（MySQL amount = Tushare 千元）
MIN_PRICE = 5
MAX_PRICE = 20
MIN_AMOUNT_QIAN = 50_000  # 5000 万元 = 50000 千元
LIQUIDITY_SCORE_CAP_WAN = 200_000  # 流动性分满分对应 20 亿元成交额

# Top5 / 候选池可执行动作（与 pick_selection_top 默认一致）
BUY_ACTIONS = frozenset({"强势关注", "观察买入", "小仓埋伏"})
TOP5_ELIGIBLE_ACTIONS = BUY_ACTIONS | {"持有"}

# 执行卡硬过滤（与 investment-agent/持仓执行卡 对齐）
CHASE_PCT_MAX = 5.0          # 单日涨幅 >5% 不追高
DROP_EXCLUDE_PCT = -7.0      # 大跌剔除
LIMIT_DOWN_PCT = -9.5        # 接近跌停剔除
POSITION_NO_BUY_PCT = 75.0       # >75%：买入类动作 → 继续观察（对齐执行卡 A 档）
POSITION_PROBE_ONLY_PCT = 60.0   # 60–75%：仅保留「小仓埋伏」（B 档试探）
HIGH_POSITION_PCT = POSITION_NO_BUY_PCT  # 兼容旧名
EXCLUDE_BJ = True            # 剔除北交所 92xxxx
TOP5_MAX_PER_INDUSTRY = 2

# 突破 K 线：收盘在当日振幅中的位置（越高越好，过滤长上影假突破）
BREAKOUT_CLOSE_STRENGTH_MIN = 0.55

# 早埋伏允许小幅回踩（%）
AMBUSH_SOFT_DIP_PCT = -1.5

# 震荡市评分门槛（neutral 用默认；weak 抬高买入门槛）
SCORE_STRONG_WEAK = 85
SCORE_BUY_WEAK = 70
SCORE_AMBUSH_WEAK = 58


def amount_qian_to_wan(amount_qian: float) -> float:
    """Tushare/MySQL 成交额（千元）→ 万元。"""
    return float(amount_qian) / 10.0


def liquidity_score_from_wan(amount_wan: float) -> float:
    """0–10 分；20 亿元成交额封顶。"""
    if amount_wan <= 0:
        return 0.0
    return min(10.0, amount_wan / (LIQUIDITY_SCORE_CAP_WAN / 10))


def _normalize_position_pct(ratio: float | None) -> float:
    if ratio is None:
        return 0.0
    val = float(ratio)
    return val * 100 if val <= 1.0 else val


def _cap_action_for_redlines(action: str, pct_chg: float, account_position_pct: float) -> str:
    """执行卡买入档位：>75% 禁买；60–75% 仅小仓埋伏；≤60% 按评分动作（仍受禁追高约束）。"""
    if pct_chg > CHASE_PCT_MAX and action in BUY_ACTIONS:
        return "继续观察"
    if account_position_pct > POSITION_NO_BUY_PCT:
        if action in BUY_ACTIONS:
            return "继续观察"
        return action
    if account_position_pct > POSITION_PROBE_ONLY_PCT:
        if action in ("强势关注", "观察买入"):
            return "小仓埋伏"
    return action


def _position_suggestion(action: str, close_price: float) -> tuple[int, float, int]:
    """返回 (position_ratio%, buy_shares, buy_amount_yuan)。"""
    ratio_map = {
        "强势关注": 0.20,
        "观察买入": 0.15,
        "继续观察": 0.08,
        "小仓埋伏": 0.05,
    }
    position_ratio = ratio_map.get(action, 0.0)
    total_capital = 100000
    buy_amount_yuan = total_capital * position_ratio
    buy_shares = 0
    if close_price > 0 and buy_amount_yuan > 0:
        buy_shares = int(buy_amount_yuan / close_price / 100) * 100
    return int(position_ratio * 100), buy_shares, int(buy_shares * close_price)


def _resolve_industry(ts_code: str, industry_map: dict[str, str]) -> str:
    code_str = str(ts_code).split(".")[0].zfill(6)
    return industry_map.get(code_str) or industry_map.get(str(ts_code)) or "N/A"


def _sector_matches(industry: str, hot_sectors: list[str]) -> bool:
    if industry in {"", "N/A", "-", "--"} or not hot_sectors:
        return False
    return any(industry in s or s in industry for s in hot_sectors)


def classify_market_regime(up_ratio: float | None) -> str:
    """weak / neutral / strong，用于震荡市动态门槛。"""
    if up_ratio is None:
        return "neutral"
    if up_ratio < 0.45:
        return "weak"
    if up_ratio > 0.60:
        return "strong"
    return "neutral"


def close_strength_ratio(high: float, low: float, close: float) -> float:
    """收盘在当日振幅中的相对位置 0~1。"""
    span = float(high) - float(low)
    if span <= 0:
        return 1.0
    return (float(close) - float(low)) / span


def action_thresholds_for_regime(regime: str) -> dict[str, float]:
    """返回各建议动作最低总分。"""
    if regime == "weak":
        return {
            "强势关注": SCORE_STRONG_WEAK,
            "观察买入": SCORE_BUY_WEAK,
            "继续观察": 52.0,
            "小仓埋伏": SCORE_AMBUSH_WEAK,
        }
    if regime == "strong":
        return {"强势关注": 78.0, "观察买入": 63.0, "继续观察": 48.0, "小仓埋伏": 53.0}
    return {"强势关注": 80.0, "观察买入": 65.0, "继续观察": 50.0, "小仓埋伏": 55.0}


def assign_action(
    total_score: float,
    *,
    is_ambush_only: bool,
    regime: str,
) -> str:
    th = action_thresholds_for_regime(regime)
    if is_ambush_only:
        if total_score >= th["小仓埋伏"]:
            return "小仓埋伏"
        if total_score >= th["继续观察"]:
            return "继续观察"
        return "谨慎回避"
    if total_score >= th["强势关注"]:
        return "强势关注"
    if total_score >= th["观察买入"]:
        return "观察买入"
    if total_score >= th["继续观察"]:
        return "继续观察"
    return "谨慎回避"


def _market_score_from_sentiment(market_sentiment: dict | None) -> tuple[int, list[str]]:
    """返回 (大盘调整分, 热门板块列表)。"""
    if not market_sentiment:
        return 0, []
    hot_sectors = list(market_sentiment.get("热门板块") or [])
    up_ratio = market_sentiment.get("up_ratio")
    if up_ratio is None:
        breadth = market_sentiment.get("breadth") or {}
        if isinstance(breadth, dict):
            total = int(breadth.get("up", 0)) + int(breadth.get("down", 0)) + int(
                breadth.get("flat", 0)
            )
            if total > 0:
                up_ratio = int(breadth.get("up", 0)) / total
    adj = 0
    if up_ratio is not None:
        if up_ratio > 0.6:
            adj = 5
        elif up_ratio < 0.4:
            adj = -5
    return adj, hot_sectors


def get_db_engine():
    mysql_url = os.getenv("MYSQL_URL", "").replace("host.docker.internal", "127.0.0.1")
    return create_engine(mysql_url)

def get_latest_trade_date(engine):
    query = "SELECT MAX(trade_date) FROM stock_daily"
    with engine.connect() as conn:
        return conn.execute(text(query)).scalar().strftime("%Y%m%d")

def main(target_date=None):
    engine = get_db_engine()
    if target_date:
        trade_date = target_date
    else:
        trade_date = get_latest_trade_date(engine)
    print(f"🚀 开始综合选股扫描，基准日期：{trade_date}")
    
    skip_sentiment = os.getenv("SKIP_MARKET_SENTIMENT", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    market_sentiment = None
    market_score_adj = 0
    hot_sectors: list[str] = []
    market_regime = "neutral"
    if skip_sentiment:
        print("📡 跳过大盘情绪（SKIP_MARKET_SENTIMENT=1）")
    else:
        print("📡 正在获取大盘实时情绪…")
        try:
            market_sentiment = get_market_sentiment()
            market_score_adj, hot_sectors = _market_score_from_sentiment(market_sentiment)
            market_regime = classify_market_regime(market_sentiment.get("up_ratio"))
            if market_sentiment.get("up_ratio") is not None:
                print(
                    f"📊 大盘赚钱效应：{market_sentiment['up_ratio'] * 100:.1f}%，"
                    f"环境={market_regime}，风险调整：{market_score_adj}"
                )
            if hot_sectors:
                print(f"🔥 当前热门板块：{', '.join(hot_sectors[:3])}…")
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ 大盘情绪获取失败（{exc}），跳过板块/大盘加分")
    
    # 获取1100天数据以支持3年大底计算
    end_date_obj = datetime.strptime(trade_date, "%Y%m%d")
    start_date_obj = end_date_obj - timedelta(days=1100)
    start_date = start_date_obj.strftime("%Y-%m-%d")
    end_date = end_date_obj.strftime("%Y-%m-%d")
    
    query = f"""
        SELECT ts_code, trade_date, open, high, low, close, pct_chg, vol, amount
        FROM stock_daily
        WHERE trade_date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY ts_code, trade_date
    """
    df_all = pd.read_sql(text(query), engine)
    print(f"✓ 已加载 {len(df_all)} 条记录")

    industry_map: dict[str, str] = {}
    try:
        from scripts.tools.portfolio_db import load_industry_map

        industry_map = load_industry_map(engine=engine)
        n_ind = len({k for k in industry_map if re.fullmatch(r"\d{6}", str(k))})
        print(f"✓ 行业映射 {n_ind} 只（OpenCLI stock_profile）")
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未能加载行业映射（{exc}）")

    st_codes: set[str] = set()
    if EXCLUDE_ST:
        try:
            from scripts.tools.portfolio_db import ensure_market_name_cache, load_st_codes

            ensure_market_name_cache()
            st_codes = load_st_codes(engine=engine)
            print(f"🛡️ ST 剔除：{len(st_codes)} 只")
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ ST 名单加载失败（{exc}）")

    holdings_codes: set[str] = set()
    account_position_pct = 0.0
    try:
        from scripts.tools.portfolio_db import load_account, load_holding_codes

        holdings_codes = load_holding_codes()
        acct = load_account()
        account_position_pct = _normalize_position_pct(
            acct.position_ratio if acct else None
        )
        print(
            f"📋 账户约束：持仓 {len(holdings_codes)} 只，"
            f"仓位 {account_position_pct:.1f}%（>{POSITION_NO_BUY_PCT:.0f}% 不买；"
            f"{POSITION_PROBE_ONLY_PCT:.0f}–{POSITION_NO_BUY_PCT:.0f}% 仅小仓埋伏）"
        )
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未读取持仓/仓位（{exc}），跳过执行卡过滤")

    excluded_crash = 0
    excluded_bj = 0
    excluded_st = 0
    signal_hits = {"大底突破": 0, "三连阳": 0, "空中加油": 0, "早埋伏": 0}
    results = []
    for ts_code, group in df_all.groupby('ts_code'):
        group = group.sort_values('trade_date')
        if len(group) < 60: continue
        
        latest = group.iloc[-1]
        close_today = latest['close']
        amount_today = latest['amount']
        code_str = str(ts_code).split(".")[0].zfill(6)
        pct_chg_today = float(latest['pct_chg'])

        if EXCLUDE_ST and code_str in st_codes:
            excluded_st += 1
            continue
        if EXCLUDE_BJ and code_str.startswith("92"):
            excluded_bj += 1
            continue
        if pct_chg_today <= DROP_EXCLUDE_PCT or pct_chg_today <= LIMIT_DOWN_PCT:
            excluded_crash += 1
            continue
        
        # 基础过滤
        if not (MIN_PRICE <= close_today <= MAX_PRICE): continue
        if amount_today < MIN_AMOUNT_QIAN:
            continue
        amount_wan = amount_qian_to_wan(amount_today)
        
        # 均线计算
        ma5 = group['close'].tail(5).mean()
        ma10 = group['close'].tail(10).mean()
        ma20 = group['close'].tail(20).mean()
        ma60 = group['close'].tail(60).mean()
        
        # --- 策略1: 3年大底突破 ---
        is_breakout = False
        box_width = 0
        breakout_ratio = 0
        if len(group) >= BOX_PERIOD:
            box_data = group.iloc[-BOX_PERIOD:-10]
            box_high = box_data['high'].max()
            box_low = box_data['low'].min()
            box_width = (box_high - box_low) / box_low * 100
            breakout_ratio = (close_today - box_high) / box_high * 100
            
            high_250d = group['high'].tail(250).max()
            low_250d = group['low'].tail(250).min()
            dist_from_high = (close_today - high_250d) / high_250d * 100
            dist_from_low = (close_today - low_250d) / low_250d * 100
            
            day_high = float(latest["high"])
            day_low = float(latest["low"])
            close_str = close_strength_ratio(day_high, day_low, close_today)
            if (box_width <= BOX_WIDTH_MAX and breakout_ratio >= 0 and 
                dist_from_high <= DIST_FROM_250D_HIGH_MAX and dist_from_low <= DIST_FROM_250D_LOW_MAX and
                ma5 > ma10 > ma20 and
                pct_chg_today > 0 and
                close_today > float(latest['open']) and
                close_str >= BREAKOUT_CLOSE_STRENGTH_MIN):
                is_breakout = True

        # --- 策略2: 低位放量三连阳 ---
        is_three_up = False
        if len(group) >= 10:
            recent_3 = group.tail(3)
            avg_amount_5 = group['amount'].iloc[-8:-3].mean()
            
            cond1 = (recent_3['pct_chg'] >= THREE_UP_MIN_CHG).all()
            cond2 = (recent_3['close'] > recent_3['open']).all()
            cond3 = (recent_3['amount'] > avg_amount_5 * THREE_UP_VOL_RATIO).any()
            cond4 = (close_today - group['close'].iloc[-4]) / group['close'].iloc[-4] * 100 <= THREE_UP_TOTAL_CHG_MAX
            
            # 确保是在相对低位（距250日高点跌幅超过30%）
            high_250d = group['high'].tail(250).max()
            is_low = (close_today - high_250d) / high_250d * 100 < -30
            
            if cond1 and cond2 and cond3 and cond4 and is_low:
                is_three_up = True

        # --- 策略3: 空中加油 (MA20回踩) ---
        is_pullback = False
        if len(group) >= 30:
            prev_20d_chg = (group['close'].iloc[-5] - group['close'].iloc[-25]) / group['close'].iloc[-25] * 100
            dist_to_ma20 = abs(close_today - ma20) / ma20 * 100
            avg_amount_5 = group['amount'].iloc[-10:-5].mean()
            vol_ratio = amount_today / avg_amount_5
            
            if (prev_20d_chg >= PULLBACK_PREV_STRENGTH and 
                dist_to_ma20 <= PULLBACK_MA20_DIST and 
                vol_ratio <= PULLBACK_VOL_DECREASE and
                close_today >= ma20 and
                close_today >= ma5 and
                close_today > float(latest['open']) and
                pct_chg_today > 0):
                is_pullback = True

        # --- 策略4: 早埋伏（接近突破但未突破） ---
        is_ambush = False
        if len(group) >= max(BOX_PERIOD, 40):
            box_data2 = group.iloc[-BOX_PERIOD:-5]
            box_high2 = box_data2['high'].max()
            box_low2 = box_data2['low'].min()
            box_width2 = (box_high2 - box_low2) / box_low2 * 100 if box_low2 > 0 else 999
            near_box_top = (close_today - box_high2) / box_high2 * 100 if box_high2 > 0 else -999

            # MA20近5日斜率（简化）
            ma20_series = group['close'].rolling(20).mean()
            ma20_slope_5d = (ma20_series.iloc[-1] - ma20_series.iloc[-6]) / ma20_series.iloc[-6] * 100 if len(group) >= 26 and ma20_series.iloc[-6] > 0 else -999

            avg_amount_5b = group['amount'].iloc[-10:-5].mean()
            vol_ratio_b = amount_today / avg_amount_5b if avg_amount_5b > 0 else 0

            ambush_ok = (
                AMBUSH_NEAR_BOX_TOP_MIN <= near_box_top <= AMBUSH_NEAR_BOX_TOP_MAX and
                box_width2 <= AMBUSH_BOX_WIDTH_MAX and
                ma20_slope_5d >= AMBUSH_MA20_SLOPE_MIN and
                AMBUSH_VOL_RATIO_MIN <= vol_ratio_b <= AMBUSH_VOL_RATIO_MAX and
                close_today >= ma20
            )
            if ambush_ok and pct_chg_today >= 0 and close_today > float(latest["open"]):
                is_ambush = True
            elif ambush_ok and AMBUSH_SOFT_DIP_PCT <= pct_chg_today < 0:
                is_ambush = True

        # --- 策略5: 主力异动（已弃用 capital_flow 表；资金面改 OpenCLI SOP） ---
        is_surge = False
        big_net = 0
        big_pct = 0

        # 记录结果 + 评分
        if is_breakout:
            signal_hits["大底突破"] += 1
        if is_three_up:
            signal_hits["三连阳"] += 1
        if is_pullback:
            signal_hits["空中加油"] += 1
        if is_ambush:
            signal_hits["早埋伏"] += 1

        if is_breakout or is_three_up or is_pullback or is_ambush or is_surge:
            # --- 暂时跳过自动基本面过滤，由 Agent 通过浏览器手动校验 ---
            # print(f"  🔍 校验基本面红线: {ts_code}...")
            # fundamental = get_stock_fundamental(ts_code)
            
            # 记录技术面候选
            tags = []
            if is_breakout: tags.append("大底突破")
            if is_three_up: tags.append("三连阳")
            if is_pullback: tags.append("空中加油")
            if is_ambush: tags.append("早埋伏")
            if is_surge: tags.append("主力异动")

            # === 评分体系（0-100）===
            # 1) 信号分（0-45）
            signal_score = 0
            if is_breakout:
                signal_score += 18
            if is_three_up:
                signal_score += 14
            if is_pullback:
                signal_score += 13
            if is_ambush:
                signal_score += 12
            if is_surge:
                signal_score += 15

            # 2) 趋势分（0-25）
            trend_score = 0
            if ma5 > ma10:
                trend_score += 8
            if ma10 > ma20:
                trend_score += 8
            if close_today >= ma20:
                trend_score += 9

            # 3) 动量分（0-20） + 5) 风险惩罚（0~-15）
            risk_penalty = 0
            momentum_score = 0
            if -2 <= pct_chg_today <= CHASE_PCT_MAX:
                momentum_score += 8
            elif CHASE_PCT_MAX < pct_chg_today <= 6:
                momentum_score += 2
            elif pct_chg_today > 6:
                risk_penalty -= 4

            if len(group) >= 25:
                prev_20d_chg_for_score = (group['close'].iloc[-1] - group['close'].iloc[-21]) / group['close'].iloc[-21] * 100
                if 5 <= prev_20d_chg_for_score <= 30:
                    momentum_score += 12
                elif prev_20d_chg_for_score > 30:
                    momentum_score += 6

            # 4) 流动性分（0-10）
            liquidity_score = liquidity_score_from_wan(amount_wan)

            if abs(pct_chg_today) > 8:
                risk_penalty -= 6
            if len(group) >= 10:
                recent_vol = group['pct_chg'].tail(10).std()
                if recent_vol > 5:
                    risk_penalty -= 5
            if is_ambush and AMBUSH_SOFT_DIP_PCT <= pct_chg_today < 0:
                risk_penalty -= 2
            if len(group) >= 4:
                chg_3d = (close_today / float(group['close'].iloc[-4]) - 1) * 100
                if chg_3d > 12:
                    risk_penalty -= 4

            # 6) 大盘调整
            total_score = max(0, min(100, round(signal_score + trend_score + momentum_score + liquidity_score + risk_penalty + market_score_adj, 1)))

            # 7) 板块调整
            sector_score_adj = 0
            industry = _resolve_industry(str(ts_code), industry_map)
            if _sector_matches(industry, hot_sectors):
                sector_score_adj = 5
                total_score = min(100, total_score + sector_score_adj)

            # 8) 三力合一共振 (Market + Sector + Stock)
            resonance_score = 0
            # 条件：大盘环境好 + 属于热门板块 + 个股有强信号(标签数>1 或 信号分高)
            if market_score_adj > 0 and sector_score_adj > 0 and (len(tags) > 1 or signal_score >= 18):
                resonance_score = 10
                total_score = min(100, total_score + resonance_score)
                tags.append("三力合一")

            is_ambush_only = is_ambush and not (
                is_breakout or is_three_up or is_pullback or is_surge
            )
            action = assign_action(
                total_score,
                is_ambush_only=is_ambush_only,
                regime=market_regime,
            )

            if code_str in holdings_codes:
                action = "持有" if action in BUY_ACTIONS else action
            else:
                action = _cap_action_for_redlines(action, pct_chg_today, account_position_pct)
                if pct_chg_today > CHASE_PCT_MAX and action in BUY_ACTIONS:
                    action = "继续观察"
                if pct_chg_today < 0 and action not in BUY_ACTIONS:
                    action = "谨慎回避"

            if code_str not in holdings_codes and action == "谨慎回避":
                continue

            _, buy_shares, buy_amount_yuan = _position_suggestion(action, close_today)

            results.append({
                '代码': code_str,
                '收盘价': close_today,
                '涨幅%': latest['pct_chg'],
                '成交额(万)': round(amount_wan, 2),
                '策略标签': ",".join(tags),
                '标签数': len(tags),
                '总分': total_score,
                '信号分': signal_score,
                '趋势分': trend_score,
                '动量分': momentum_score,
                '流动性分': round(liquidity_score, 1),
                '风险调整': risk_penalty,
                '大盘调整': market_score_adj,
                '板块调整': sector_score_adj,
                '共振加分': resonance_score,
                '大盘环境': market_regime,
                '所属行业': industry,
                '建议动作': action,
                '建议买入(股)': buy_shares,
                '预计金额(元)': buy_amount_yuan,
                '超大单净流入(万)': big_net,
                '超大单占比%': big_pct
            })

    print(
        "📈 信号命中："
        + "，".join(f"{k} {v}" for k, v in signal_hits.items())
        + f"；A轨入池 {len(results)} 只（环境={market_regime}）"
    )
    project_root = os.getenv(
        "PROJECT_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    # —— B 轨观察池（宽松，strategy=watch，不进 Top5/SOP）——
    try:
        from selection_watch_track import run_watch_track

        watch_results = run_watch_track(
            df_all,
            trade_date=trade_date,
            industry_map=industry_map,
            st_codes=st_codes,
            market_regime=market_regime,
            holdings_codes=holdings_codes,
            account_position_pct=account_position_pct,
        )
        if watch_results is not None:
            from scripts.tools.execution_card_buys import (
                apply_execution_card_b_tier,
                ensure_card_probe_in_watch,
            )
            from scripts.tools.portfolio_db import save_selection_daily_results

            latest_by_code: dict[str, dict] = {}
            for ts_code, group in df_all.groupby("ts_code"):
                g = group.sort_values("trade_date")
                if g.empty:
                    continue
                last = g.iloc[-1]
                code_str = str(ts_code).split(".")[0].zfill(6)
                latest_by_code[code_str] = {
                    "close": float(last["close"]),
                    "pct_chg": float(last["pct_chg"]),
                    "amount_wan": amount_qian_to_wan(float(last["amount"])),
                }
            n_card_watch = ensure_card_probe_in_watch(
                watch_results,
                results,
                latest_by_code,
                account_position_pct,
                market_regime=market_regime,
            )
            if n_card_watch:
                print(f"📌 执行卡关注补入 watch：{n_card_watch} 只（P-买1/买2 未入信号池）")
            apply_execution_card_b_tier(watch_results, account_position_pct)
            wn = save_selection_daily_results(
                trade_date, watch_results, strategy="watch"
            ) if watch_results else 0
            watch_path = (
                Path(project_root) / "output" / f"stock_selection_watch_{trade_date}.csv"
            )
            watch_path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(watch_results).to_csv(
                watch_path, index=False, encoding="utf-8-sig"
            )
            print(f"👀 B轨观察池 {len(watch_results)} 只 → MySQL strategy=watch ({wn} 条)")
            print(f"📄 {watch_path}")
        else:
            print("👀 B轨观察池：0 只")
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ B轨观察池失败：{exc}")

    try:
        from scripts.tools.execution_card_buys import apply_execution_card_b_tier

        n_card = apply_execution_card_b_tier(results, account_position_pct)
        if n_card:
            print(f"📌 执行卡 B 档试探：{n_card} 只升为「小仓埋伏」（P-买1/买2）")
        for row in results:
            action = row.get("建议动作")
            close_today = float(row.get("收盘价") or 0)
            if action and close_today > 0:
                _, buy_shares, buy_amount_yuan = _position_suggestion(
                    str(action), close_today
                )
                row["建议买入(股)"] = buy_shares
                row["预计金额(元)"] = buy_amount_yuan
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 执行卡 B 档对齐失败：{exc}")

    if not results:
        print("❌ A轨（combined）未筛选出符合任何策略的股票")
        return

    if excluded_crash or excluded_bj or excluded_st:
        print(
            f"🛡️ 硬过滤剔除：大跌/跌停 {excluded_crash} 只，"
            f"北交所 {excluded_bj} 只，ST {excluded_st} 只"
        )

    res_df = pd.DataFrame(results).sort_values(by=['总分', '标签数', '成交额(万)'], ascending=False)
    buyable = res_df[res_df["建议动作"].isin(BUY_ACTIONS)] if not res_df.empty else res_df
    if not buyable.empty:
        print(f"🎯 可执行买入类 {len(buyable)} 只（Top5 优先从此筛选）")
    
    output_dir = Path(project_root) / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / f"stock_selection_combined_{trade_date}.csv"
    res_df.to_csv(str(output_path), index=False, encoding='utf-8-sig')

    try:
        from scripts.tools.portfolio_db import save_selection_daily_results

        db_n = save_selection_daily_results(trade_date, results)
        print(f"💾 MySQL selection_daily_results: {db_n} 条")
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ MySQL 入库失败: {exc}")
    
    print("\n" + "="*50)
    print(f"✅ 综合选股完成！共筛选出 {len(res_df)} 只股票")
    print(f"📄 结果已保存至：{output_path}")
    print("="*50)
    print(res_df.head(20))

if __name__ == "__main__":
    # 如果想跑历史某一天，可以在这里指定，例如：
    # main("20260120")
    main()
