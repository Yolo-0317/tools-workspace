#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纯技术面选股策略：筑底 + 放量突破

说明：
- 仅基于 MySQL `stock_daily` 日线进行筛选
- 不包含浏览器抓取、财务/资金/消息二次分析
- 保留 main(target_date, max_enrich) 签名，兼容现有 MCP 调用
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()
load_dotenv()

from stock_ai.market_codes import is_sh_sz_a_share

# ============================================
# 技术面参数（筑底 + 放量突破）
# ============================================
BOTTOM_MA60_BAND_LOW = 0.95
BOTTOM_MA60_BAND_HIGH = 1.05
BOTTOM_MA60_SLOPE_MIN = -0.01
BOTTOM_VOL_SHRINK_MAX = 0.7
BOTTOM_AMP_10D_MAX = 15.0

BREAKOUT_VOL_RATIO_MIN = 1.5
BREAKOUT_CLOSE_RATIO_MIN = 1.03
PLATFORM_WINDOW = 20
PLATFORM_TOUCH_MIN = 10
PLATFORM_BAND = 0.03

MIN_PRICE = 4.0
MAX_PRICE = 30.0
MIN_AMOUNT = 5000.0  # 万


def get_db_engine():
    mysql_url = os.getenv("MYSQL_URL")
    if not mysql_url:
        raise RuntimeError("MYSQL_URL 未设置，无法从 MySQL 读取日线数据")
    return create_engine(mysql_url)


def get_latest_trade_date(engine) -> str:
    query = "SELECT MAX(trade_date) FROM stock_daily"
    with engine.connect() as conn:
        latest = conn.execute(text(query)).scalar()
    if latest is None:
        raise RuntimeError("stock_daily 没有数据")
    return latest.strftime("%Y%m%d")


def normalize_code_6(ts_code: str) -> str:
    digits = "".join(filter(str.isdigit, str(ts_code)))
    return digits[:6]


def load_daily_data(engine, trade_date: str) -> pd.DataFrame:
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
    return pd.read_sql(text(query), engine)


def select_technical_candidates(df_all: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    for ts_code, group in df_all.groupby("ts_code"):
        if not is_sh_sz_a_share(str(ts_code)):
            continue
        group = group.sort_values("trade_date")
        if len(group) < 130:
            continue

        latest = group.iloc[-1]
        close_today = float(latest["close"])
        amount_today = float(latest["amount"])
        pct_chg_today = float(latest["pct_chg"])

        if not (MIN_PRICE <= close_today <= MAX_PRICE):
            continue
        if amount_today < MIN_AMOUNT:
            continue

        close_series = group["close"]
        vol_series = group["vol"]
        high_series = group["high"]
        low_series = group["low"]

        ma60_series = close_series.rolling(60).mean()
        ma60_today = float(ma60_series.iloc[-1]) if pd.notna(ma60_series.iloc[-1]) else None
        ma60_prev = float(ma60_series.iloc[-6]) if pd.notna(ma60_series.iloc[-6]) else None
        if ma60_today is None or ma60_prev is None or ma60_prev <= 0:
            continue

        # -------------------------
        # 1) 筑底条件
        # -------------------------
        price_vs_ma60 = close_today / ma60_today if ma60_today > 0 else 999.0
        ma60_slope = (ma60_today - ma60_prev) / ma60_prev

        avg_vol_20 = float(vol_series.tail(20).mean())
        avg_vol_prev_60 = float(vol_series.iloc[-80:-20].mean()) if len(vol_series) >= 80 else 0.0
        vol_shrink_ratio = avg_vol_20 / avg_vol_prev_60 if avg_vol_prev_60 > 0 else 999.0

        high_10 = float(high_series.tail(10).max())
        low_10 = float(low_series.tail(10).min())
        amp_10d = (high_10 - low_10) / low_10 * 100 if low_10 > 0 else 999.0

        bottom_cond = (
            BOTTOM_MA60_BAND_LOW <= price_vs_ma60 <= BOTTOM_MA60_BAND_HIGH
            and ma60_slope > BOTTOM_MA60_SLOPE_MIN
            and vol_shrink_ratio < BOTTOM_VOL_SHRINK_MAX
            and amp_10d < BOTTOM_AMP_10D_MAX
        )
        if not bottom_cond:
            continue

        # -------------------------
        # 2) 放量突破条件
        # -------------------------
        avg_vol_5 = float(vol_series.tail(5).mean())
        vol_ratio_5 = float(vol_series.iloc[-1]) / avg_vol_5 if avg_vol_5 > 0 else 0.0
        prev_close = float(close_series.iloc[-2])
        close_ratio = close_today / prev_close if prev_close > 0 else 0.0

        high_20 = float(high_series.tail(20).max())
        breakout_ma60 = close_today > ma60_today
        breakout_20d_high = close_today > high_20
        near_current_cnt = int((close_series.tail(PLATFORM_WINDOW).between(close_today * (1 - PLATFORM_BAND), close_today * (1 + PLATFORM_BAND))).sum())
        breakout_platform = near_current_cnt >= PLATFORM_TOUCH_MIN

        breakout_cond = (
            vol_ratio_5 >= BREAKOUT_VOL_RATIO_MIN
            and close_ratio >= BREAKOUT_CLOSE_RATIO_MIN
            and (breakout_ma60 or breakout_20d_high or breakout_platform)
        )
        if not breakout_cond:
            continue

        signal_score = 45.0
        bottom_score = 25.0
        breakout_score = 0.0
        breakout_score += 12 if vol_ratio_5 < 2.0 else 18
        breakout_score += 12 if close_ratio < 1.05 else 17
        if breakout_20d_high:
            breakout_score += 13
        elif breakout_ma60:
            breakout_score += 9
        else:
            breakout_score += 7
        technical_score = round(min(100.0, signal_score + bottom_score + breakout_score), 1)

        tags = ["筑底", "放量突破"]
        if breakout_20d_high:
            tags.append("突破20日高点")
        if breakout_ma60:
            tags.append("突破MA60")
        if breakout_platform:
            tags.append("突破平台")
        if vol_ratio_5 >= 2.0:
            tags.append("显著放量")

        rows.append(
            {
                "代码": ts_code,
                "代码6位": normalize_code_6(ts_code),
                "收盘价": round(close_today, 2),
                "涨幅%": round(pct_chg_today, 2),
                "成交额(万)": round(amount_today, 1),
                "股价/MA60": round(price_vs_ma60, 4),
                "MA60斜率": round(ma60_slope, 4),
                "近20量/前60量": round(vol_shrink_ratio, 4),
                "近10日振幅%": round(amp_10d, 2),
                "今日量/5日量": round(vol_ratio_5, 2),
                "今收/昨收": round(close_ratio, 4),
                "近20日高点": round(high_20, 2),
                "平台触达天数": near_current_cnt,
                "策略标签": ",".join(tags),
                "技术分": technical_score,
                "信号分": signal_score,
                "趋势分": bottom_score,
                "突破分": breakout_score,
                "位置分": 0.0,
            }
        )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        by=["技术分", "今日量/5日量", "今收/昨收"],
        ascending=False,
    )


def save_outputs(technical_df: pd.DataFrame, trade_date: str) -> Dict[str, Path]:
    project_root = os.getenv("PROJECT_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_dir = Path(project_root) / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    technical_path = output_dir / f"technical_candidates_{trade_date}.csv"
    final_path = output_dir / f"stock_selection_bottom_breakout_eastmoney_{trade_date}.csv"

    if not technical_df.empty:
        technical_df.to_csv(str(technical_path), index=False, encoding="utf-8-sig")
        technical_df.to_csv(str(final_path), index=False, encoding="utf-8-sig")

    return {"technical": technical_path, "final": final_path}


def main(target_date: Optional[str] = None, max_enrich: int = 20):
    # max_enrich 保留仅用于兼容既有 MCP 调用，纯技术策略不使用此参数
    _ = max_enrich

    engine = get_db_engine()
    trade_date = target_date or get_latest_trade_date(engine)
    print(f"🚀 纯技术面策略启动，基准日期：{trade_date}")
    print("正在执行 MySQL 技术面筛选（筑底+放量突破）...")

    df_all = load_daily_data(engine, trade_date)
    print(f"✓ 已加载日线记录: {len(df_all)}")

    technical_df = select_technical_candidates(df_all)
    if technical_df.empty:
        print("❌ 技术面未筛到候选股票")
        return None, trade_date

    paths = save_outputs(technical_df, trade_date)

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        from scripts.tools.selection_strategy_bridge import (
            bottom_breakout_rows_for_db,
            persist_strategy_rows,
        )

        persist_strategy_rows(
            trade_date,
            bottom_breakout_rows_for_db(technical_df),
            "bottom_breakout",
            csv_stem="stock_selection_bottom_breakout_eastmoney",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ bottom_breakout MySQL 入库失败：{exc}")

    print("\n" + "=" * 60)
    print(f"✅ 技术面选股完成，输出: {len(technical_df)} 只")
    print(f"📄 技术中间文件: {paths['technical']}")
    print(f"📄 最终结果文件: {paths['final']}")
    print("=" * 60)
    print(technical_df.head(20))
    return technical_df, trade_date


if __name__ == "__main__":
    arg_date = sys.argv[1] if len(sys.argv) > 1 else None
    arg_max = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    main(arg_date, arg_max)
