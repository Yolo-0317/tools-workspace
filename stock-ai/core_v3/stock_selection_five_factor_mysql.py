#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于 MySQL `stock_daily` 的 A 股技术面五因子选股脚本。

策略来源：core_v3/strategy.md
五因子：趋势 + 形态 + 动量 + 量能 + 支撑压力
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# 尽量兼容项目已有 .env 加载方式
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)
load_dotenv()

# -----------------------------
# 基础过滤参数
# -----------------------------
MIN_PRICE = 3.0
MAX_PRICE = 200.0
MIN_AMOUNT_WAN = 5000.0
LOOKBACK_DAYS = 450
MIN_BARS = 130
DEFAULT_MIN_SCORE = 70.0
# 放宽版筑底硬过滤（在“严格筑底”基础上保留风控，同时提升候选覆盖）
STRICT_BOTTOM_MA60_BAND_LOW = 0.93
STRICT_BOTTOM_MA60_BAND_HIGH = 1.08
STRICT_BOTTOM_MA60_SLOPE_MIN = -0.015
STRICT_BOTTOM_VOL_SHRINK_MAX = 0.9
STRICT_BOTTOM_AMP20_MAX = 18.0
STRICT_BREAKOUT_VOL_RATIO_MIN = 1.5
STRICT_BREAKOUT_PCT_MIN = 3.0


@dataclass
class FactorScore:
    trend: float
    pattern: float
    momentum: float
    volume: float
    support_pressure: float
    tags: List[str]
    metrics: Dict[str, float]

    @property
    def total(self) -> float:
        return round(
            self.trend + self.pattern + self.momentum + self.volume + self.support_pressure, 1
        )


def get_db_engine():
    mysql_url = os.getenv("MYSQL_URL")
    if not mysql_url:
        raise RuntimeError("MYSQL_URL 未设置，无法从 MySQL 读取数据")
    return create_engine(mysql_url, pool_pre_ping=True, pool_recycle=3600)


def parse_trade_date(target_date: Optional[str], engine) -> str:
    if target_date:
        fmt = "%Y%m%d" if "-" not in target_date else "%Y-%m-%d"
        d = datetime.strptime(target_date, fmt)
        return d.strftime("%Y%m%d")

    with engine.connect() as conn:
        latest = conn.execute(text("SELECT MAX(trade_date) FROM stock_daily")).scalar()
    if latest is None:
        raise RuntimeError("stock_daily 没有可用数据")
    return latest.strftime("%Y%m%d")


def load_daily_data(engine, trade_date: str) -> pd.DataFrame:
    end_dt = datetime.strptime(trade_date, "%Y%m%d")
    start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
    query = text(
        """
        SELECT ts_code, trade_date, open, high, low, close, pct_chg, vol, amount
        FROM stock_daily
        WHERE trade_date BETWEEN :start_date AND :end_date
        ORDER BY ts_code, trade_date
        """
    )
    df = pd.read_sql(
        query,
        engine,
        params={
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "end_date": end_dt.strftime("%Y-%m-%d"),
        },
    )
    if df.empty:
        return df
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss_safe = avg_loss.where(avg_loss > 0, 1e-12)
    rs = avg_gain / avg_loss_safe
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0).astype(float)


def calc_kdj(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    low_n = low.rolling(n).min()
    high_n = high.rolling(n).max()
    denominator = (high_n - low_n).replace(0, pd.NA)
    rsv = ((close - low_n) / denominator * 100).fillna(50.0)
    k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    d = k.ewm(alpha=1 / 3, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def calc_obv(close: pd.Series, vol: pd.Series) -> pd.Series:
    direction = close.diff().fillna(0).apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return (direction * vol).cumsum()


def choose_support_pressure(
    close: float, low20: float, high20: float, high60: float, ma20: float, ma60: float
) -> Tuple[float, str, float, str, int]:
    support_candidates = [
        ("low20", low20),
        ("ma60", ma60),
        ("ma20", ma20),
        ("round", float(int(close))),
    ]
    supports_valid = [(name, v) for name, v in support_candidates if pd.notna(v) and v > 0 and v <= close]
    if supports_valid:
        support_name, support = max(supports_valid, key=lambda x: x[1])
    else:
        support_name, support = "low20", low20

    pressure_candidates = [
        ("high20", high20),
        ("high60", high60),
        ("round", float(int(close) + 1)),
    ]
    pressures_valid = [(name, v) for name, v in pressure_candidates if pd.notna(v) and v > close]
    if pressures_valid:
        pressure_name, pressure = min(pressures_valid, key=lambda x: x[1])
    else:
        pressure_name, pressure = "high60", high60

    overlap_count = 0
    for _, val in support_candidates:
        if pd.notna(val) and support > 0 and abs(val - support) / support <= 0.02:
            overlap_count += 1

    return support, support_name, pressure, pressure_name, overlap_count


def score_one_stock(
    group: pd.DataFrame,
    strict_bottom: bool = False,
    strict_breakout: bool = True,
) -> Optional[FactorScore]:
    group = group.sort_values("trade_date").copy()
    if len(group) < MIN_BARS:
        return None

    close = group["close"].astype(float)
    high = group["high"].astype(float)
    low = group["low"].astype(float)
    vol = group["vol"].astype(float)
    pct_chg = group["pct_chg"].astype(float)
    amount = group["amount"].astype(float)

    ma5 = close.rolling(5).mean()
    ma10 = close.rolling(10).mean()
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()

    macd_fast = ema(close, 12)
    macd_slow = ema(close, 26)
    macd_line = macd_fast - macd_slow
    macd_signal = ema(macd_line, 9)
    macd_hist = macd_line - macd_signal
    rsi = calc_rsi(close, 14)
    k, d, j = calc_kdj(high, low, close, 9)
    obv = calc_obv(close, vol)

    latest = group.iloc[-1]
    idx = len(group) - 1

    close_today = float(close.iloc[idx])
    amount_today = float(amount.iloc[idx])
    pct_today = float(pct_chg.iloc[idx])
    prev_close = float(close.iloc[idx - 1])

    if not (MIN_PRICE <= close_today <= MAX_PRICE):
        return None
    if amount_today < MIN_AMOUNT_WAN:
        return None
    if any(pd.isna(v) for v in [ma20.iloc[idx], ma60.iloc[idx], ma20.iloc[idx - 5], ma60.iloc[idx - 10]]):
        return None

    ma5_today = float(ma5.iloc[idx])
    ma10_today = float(ma10.iloc[idx])
    ma20_today = float(ma20.iloc[idx])
    ma60_today = float(ma60.iloc[idx])
    ma20_5d = float(ma20.iloc[idx - 5])
    ma60_10d = float(ma60.iloc[idx - 10])
    ma60_prev = float(ma60.iloc[idx - 1])
    ma20_slope = (ma20_today - ma20_5d) / ma20_5d if ma20_5d > 0 else 0.0
    ma60_slope = (ma60_today - ma60_10d) / ma60_10d if ma60_10d > 0 else 0.0

    # 形态相关
    high20 = float(high.iloc[idx - 19 : idx + 1].max())
    low20 = float(low.iloc[idx - 19 : idx + 1].min())
    high20_prev = float(high.iloc[idx - 20 : idx].max())
    high60 = float(high.iloc[idx - 59 : idx + 1].max())
    amp20 = (high20 - low20) / low20 * 100 if low20 > 0 else 0.0
    avg_vol_20 = float(vol.iloc[idx - 19 : idx + 1].mean())
    avg_vol_prev_60 = float(vol.iloc[idx - 79 : idx - 19].mean()) if idx >= 80 else 0.0
    vol_shrink = avg_vol_20 / avg_vol_prev_60 if avg_vol_prev_60 > 0 else 0.0
    vol5 = float(vol.iloc[idx - 4 : idx + 1].mean())
    vol_ratio = float(vol.iloc[idx]) / vol5 if vol5 > 0 else 0.0
    price_vs_ma60 = close_today / ma60_today if ma60_today > 0 else 999.0
    breakout_ma60 = close_today > ma60_today and prev_close <= ma60_prev
    breakout_20high = close_today > high20_prev

    # 严格筑底：作为硬过滤条件，不满足则直接剔除
    strict_bottom_ok = (
        STRICT_BOTTOM_MA60_BAND_LOW <= price_vs_ma60 <= STRICT_BOTTOM_MA60_BAND_HIGH
        and ma60_slope >= STRICT_BOTTOM_MA60_SLOPE_MIN
        and 0 < vol_shrink < STRICT_BOTTOM_VOL_SHRINK_MAX
        and amp20 < STRICT_BOTTOM_AMP20_MAX
    )
    if strict_bottom and not strict_bottom_ok:
        return None

    # 严格放量突破：作为硬过滤条件，保证输出更偏“启动池”而非“防守池”
    strict_breakout_ok = (
        (breakout_ma60 or breakout_20high)
        and vol_ratio >= STRICT_BREAKOUT_VOL_RATIO_MIN
        and pct_today >= STRICT_BREAKOUT_PCT_MIN
    )
    if strict_breakout and not strict_breakout_ok:
        return None

    # 动量相关
    macd_today = float(macd_line.iloc[idx])
    macd_sig_today = float(macd_signal.iloc[idx])
    macd_hist_today = float(macd_hist.iloc[idx])
    macd_hist_prev = float(macd_hist.iloc[idx - 1])
    rsi_today = float(rsi.iloc[idx])
    k_today, d_today, j_today = float(k.iloc[idx]), float(d.iloc[idx]), float(j.iloc[idx])
    k_prev, d_prev, j_prev = float(k.iloc[idx - 1]), float(d.iloc[idx - 1]), float(j.iloc[idx - 1])

    obv_today = float(obv.iloc[idx])
    obv_5d = float(obv.iloc[idx - 5])
    obv_high20_prev = float(obv.iloc[idx - 20 : idx].max()) if idx >= 20 else obv_today

    tags: List[str] = []
    metrics: Dict[str, float] = {
        "量比": round(vol_ratio, 3),
        "20日振幅%": round(amp20, 2),
        "20日均量/前60日均量": round(vol_shrink, 3),
        "RSI14": round(rsi_today, 2),
        "MACD": round(macd_today, 4),
        "MACD_SIGNAL": round(macd_sig_today, 4),
        "K": round(k_today, 2),
        "D": round(d_today, 2),
    }

    # -----------------------------
    # 1) 趋势因子（满分 25）
    # -----------------------------
    trend = 0.0
    if close_today > ma60_today:
        trend += 5
    if close_today > ma20_today:
        trend += 5
    if ma20_today > ma20_5d * 1.01:
        trend += 5
    if ma60_today >= ma60_10d * 0.99:
        trend += 5
    if ma5_today > ma10_today > ma20_today > ma60_today:
        trend += 5

    if ma20_slope > 0.02:
        trend += 2
    if close_today > ma5_today and close_today > ma10_today and close_today > ma20_today and close_today > ma60_today:
        trend += 3
    if close_today < ma20_today:
        trend -= 5
    if ma60_slope < -0.01:
        trend -= 3
    if ma5_today < ma10_today < ma20_today:
        trend -= 5
    trend = max(0.0, min(25.0, trend))

    # -----------------------------
    # 2) 形态因子（满分 25）
    # -----------------------------
    pattern = 0.0
    if amp20 < 15:
        pattern += 5
    if 0 < vol_shrink < 0.7:
        pattern += 5
    if vol_ratio >= 1.5:
        pattern += 5
    if pct_today >= 3:
        pattern += 5

    if breakout_ma60:
        pattern += 3
    if breakout_20high:
        pattern += 2

    if amp20 < 10:
        pattern += 2
    if vol_ratio >= 2.0:
        pattern += 2
    if pct_today >= 5.0:
        pattern += 2
    if pct_today >= 9.7:
        pattern += 3

    if vol_ratio >= 1.5 and pct_today < 1.0:
        pattern -= 5
    if (breakout_ma60 or breakout_20high) and vol_ratio < 1.2:
        pattern -= 3

    pattern = max(0.0, min(25.0, pattern))

    # -----------------------------
    # 3) 动量因子（满分 20）
    # -----------------------------
    momentum = 0.0
    if macd_today > macd_sig_today:
        momentum += 4
    if macd_hist_today > macd_hist_prev and macd_hist_today > 0:
        momentum += 4

    if 50 <= rsi_today <= 80:
        momentum += 6
    elif 30 <= rsi_today < 50:
        momentum += 3

    if k_today > d_today and k_prev <= d_prev:
        momentum += 6
    elif k_today > d_today:
        momentum += 3

    if macd_today > macd_sig_today and macd_today > 0:
        momentum += 2
    if 60 <= rsi_today <= 75:
        momentum += 2
    if k_today > k_prev and d_today > d_prev and j_today > j_prev:
        momentum += 2

    if macd_today < macd_sig_today:
        momentum -= 5
    if rsi_today > 85:
        momentum -= 3
    if rsi_today < 25:
        momentum -= 2
    if k_today < d_today and k_prev >= d_prev:
        momentum -= 4

    momentum = max(0.0, min(20.0, momentum))

    # -----------------------------
    # 4) 量能因子（满分 15）
    # -----------------------------
    volume_score = 0.0
    if vol_ratio >= 2.0:
        volume_score += 5
    elif vol_ratio >= 1.5:
        volume_score += 3

    if obv_today > obv_5d:
        volume_score += 5

    if pct_today > 0 and vol_ratio >= 1.0:
        volume_score += 5
    elif pct_today > 0 and vol_ratio < 1.0:
        volume_score += 2

    if vol_ratio >= 3.0:
        volume_score += 2
    if obv_today > obv_high20_prev:
        volume_score += 3

    if idx >= 2:
        pct3 = pct_chg.iloc[idx - 2 : idx + 1]
        vol_ratio_series = vol / vol.rolling(5).mean().replace(0, pd.NA)
        vr3 = vol_ratio_series.iloc[idx - 2 : idx + 1].fillna(0)
        if bool((pct3 > 0).all()) and bool((vr3 >= 1.0).all()):
            volume_score += 3

    if pct_today > 0 and vol_ratio < 0.8:
        volume_score -= 2
    if pct_today < 0 and vol_ratio > 1.0:
        volume_score -= 5
    if vol_ratio < 0.5:
        volume_score -= 2

    volume_score = max(0.0, min(15.0, volume_score))

    # -----------------------------
    # 5) 支撑压力因子（满分 15）
    # -----------------------------
    support_pressure = 0.0
    support, support_name, pressure, pressure_name, overlap_count = choose_support_pressure(
        close_today, low20, high20, high60, ma20_today, ma60_today
    )

    support_dist = (close_today - support) / support if support > 0 else 1.0
    pressure_dist = (pressure - close_today) / close_today if close_today > 0 else 0.0

    if support_dist <= 0.03:
        support_pressure += 8
    elif support_dist <= 0.05:
        support_pressure += 5
    elif support_dist <= 0.08:
        support_pressure += 3

    if pressure_dist >= 0.10:
        support_pressure += 7
    elif pressure_dist >= 0.05:
        support_pressure += 4
    elif pressure_dist >= 0.03:
        support_pressure += 2

    if support_name == "ma60" and abs(close_today - ma60_today) / ma60_today <= 0.03:
        support_pressure += 2
    if overlap_count >= 2:
        support_pressure += 3
    if pressure_name == "round" and close_today > ma20_today:
        support_pressure += 2

    if close_today < min(low20, ma20_today, ma60_today):
        support_pressure -= 5
    if pressure_dist < 0.03:
        support_pressure -= 3

    support_pressure = max(0.0, min(15.0, support_pressure))

    if breakout_ma60:
        tags.append("突破MA60")
    if breakout_20high:
        tags.append("突破20日高点")
    if vol_ratio >= 2.0:
        tags.append("显著放量")
    if ma5_today > ma10_today > ma20_today > ma60_today:
        tags.append("均线多头")
    if 60 <= rsi_today <= 75:
        tags.append("强势动量")
    if support_dist <= 0.05:
        tags.append("靠近支撑")
    if pressure_dist >= 0.10:
        tags.append("上方空间较大")
    if strict_bottom_ok:
        tags.append("严格筑底")
    if strict_breakout_ok:
        tags.append("严格放量突破")

    metrics.update(
        {
            "支撑位": round(support, 2),
            "压力位": round(pressure, 2),
            "距支撑%": round(support_dist * 100, 2),
            "距压力%": round(pressure_dist * 100, 2),
            "MA20斜率%": round(ma20_slope * 100, 2),
            "MA60斜率%": round(ma60_slope * 100, 2),
            "收盘价": round(close_today, 2),
            "涨幅%": round(pct_today, 2),
            "成交额(万)": round(amount_today, 1),
        }
    )

    return FactorScore(
        trend=round(trend, 1),
        pattern=round(pattern, 1),
        momentum=round(momentum, 1),
        volume=round(volume_score, 1),
        support_pressure=round(support_pressure, 1),
        tags=tags,
        metrics=metrics,
    )


def normalize_code_6(ts_code: str) -> str:
    digits = "".join(filter(str.isdigit, str(ts_code)))
    return digits[:6] if len(digits) >= 6 else str(ts_code)


def run_selection(
    df_all: pd.DataFrame,
    min_score: float,
    strict_bottom: bool = False,
    strict_breakout: bool = True,
) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for ts_code, group in df_all.groupby("ts_code"):
        scored = score_one_stock(group, strict_bottom=strict_bottom, strict_breakout=strict_breakout)
        if not scored:
            continue
        if scored.total < min_score:
            continue

        rows.append(
            {
                "代码": ts_code,
                "代码6位": normalize_code_6(ts_code),
                "收盘价": scored.metrics["收盘价"],
                "涨幅%": scored.metrics["涨幅%"],
                "成交额(万)": scored.metrics["成交额(万)"],
                "总分": scored.total,
                "趋势分(25)": scored.trend,
                "形态分(25)": scored.pattern,
                "动量分(20)": scored.momentum,
                "量能分(15)": scored.volume,
                "支撑压力分(15)": scored.support_pressure,
                "量比": scored.metrics["量比"],
                "20日振幅%": scored.metrics["20日振幅%"],
                "20日均量/前60日均量": scored.metrics["20日均量/前60日均量"],
                "RSI14": scored.metrics["RSI14"],
                "MACD": scored.metrics["MACD"],
                "MACD_SIGNAL": scored.metrics["MACD_SIGNAL"],
                "K": scored.metrics["K"],
                "D": scored.metrics["D"],
                "支撑位": scored.metrics["支撑位"],
                "压力位": scored.metrics["压力位"],
                "距支撑%": scored.metrics["距支撑%"],
                "距压力%": scored.metrics["距压力%"],
                "MA20斜率%": scored.metrics["MA20斜率%"],
                "MA60斜率%": scored.metrics["MA60斜率%"],
                "策略标签": ",".join(scored.tags),
            }
        )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values(
        by=["形态分(25)", "量能分(15)", "动量分(20)", "涨幅%", "总分"],
        ascending=False,
    )


def save_outputs(df: pd.DataFrame, trade_date: str) -> Dict[str, Path]:
    project_root = Path(__file__).resolve().parents[1]
    output_dir = project_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    technical_path = output_dir / f"technical_candidates_five_factor_{trade_date}.csv"
    final_path = output_dir / f"stock_selection_five_factor_{trade_date}.csv"

    if not df.empty:
        df.to_csv(technical_path, index=False, encoding="utf-8-sig")
        df.to_csv(final_path, index=False, encoding="utf-8-sig")

    return {"technical": technical_path, "final": final_path}


def main(target_date: Optional[str] = None, min_score: float = DEFAULT_MIN_SCORE):
    engine = get_db_engine()
    trade_date = parse_trade_date(target_date, engine)

    print(f"🚀 五因子技术选股启动，目标日期：{trade_date}")
    print(f"筛选阈值：总分 >= {min_score}")
    print("严格筑底硬过滤：关闭")
    print("严格放量突破硬过滤：开启")

    df_all = load_daily_data(engine, trade_date)
    if df_all.empty:
        print("❌ 未读取到 stock_daily 数据")
        return

    print(f"✓ 已加载日线记录：{len(df_all)}")
    result = run_selection(df_all, min_score=min_score, strict_bottom=False, strict_breakout=True)
    if result.empty:
        print("❌ 未筛选到满足条件的候选股票")
        return

    paths = save_outputs(result, trade_date)
    print("\n" + "=" * 60)
    print(f"✅ 五因子选股完成，候选数量：{len(result)}")
    print(f"📄 技术中间文件：{paths['technical']}")
    print(f"📄 最终结果文件：{paths['final']}")
    print("=" * 60)
    print(result.head(20))


if __name__ == "__main__":
    arg_date = sys.argv[1] if len(sys.argv) > 1 else None
    arg_score = float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_MIN_SCORE
    main(arg_date, arg_score)
