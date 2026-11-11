"""Frozen V3 five-factor arithmetic; no DB, network, dotenv or legacy runtime imports.
Source: stock-ai/core_v3/stock_selection_five_factor_mysql.py
Source SHA256: 7b83925cceeca736aabd960f2c369d12bb550b472ba60ddaffee7d10b3dad127
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import pandas as pd
MIN_PRICE = 3.0

MAX_PRICE = 200.0

MIN_AMOUNT_WAN = 5000.0

LOOKBACK_DAYS = 450

MIN_BARS = 130

DEFAULT_MIN_SCORE = 70.0

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


def normalize(payload):
    """Accept normalized complete Tushare or Miaoxiang daily bars."""
    import math
    import re
    if payload.get('source') not in {'mx-finance-data', 'tushare-daily'} or not payload.get('source_file'):
        raise ValueError('需要Tushare或妙想原始数据来源')
    if payload.get('adjustment') != 'unadjusted' or payload.get('history_complete') is not True:
        raise ValueError('需要已核验的不复权完整历史；不能用部分展示数据')
    code = payload.get('code', '')
    if not re.fullmatch(r'(?:60\d{4}|68\d{4})\.SH|(?:00\d{4}|30\d{4})\.SZ', code):
        raise ValueError('只接受沪深 A 股标准代码')
    try:
        end = pd.Timestamp(payload['as_of'])
        frame = pd.DataFrame(payload['bars']).rename(columns={
            'date':'trade_date','volume_shares':'vol','amount_yuan':'amount','pct_change':'pct_chg'})
        needed=['open','high','low','close','vol','amount','pct_chg']
        frame['trade_date'] = pd.to_datetime(frame['trade_date'], errors='raise')
        if frame['trade_date'].isna().any() or frame['trade_date'].duplicated().any():
            raise ValueError('日线日期为空或重复')
        if pd.isna(end) or (frame['trade_date'] > end).any() or frame['trade_date'].max()!=end:
            raise ValueError('日线截止日期不一致')
        for c in needed:
            frame[c] = pd.to_numeric(frame[c], errors='raise')
            if not frame[c].map(math.isfinite).all():
                raise ValueError('指标缺失或非有限值')
        if (frame[['open','high','low','close']]<=0).any().any() or (frame[['vol','amount']]<0).any().any():
            raise ValueError('价格或量额无效')
        if (frame['high'] < frame[['open','close','low']].max(axis=1)).any() or (frame['low'] > frame[['open','close']].min(axis=1)).any():
            raise ValueError('OHLC 不一致')
        frame=frame[frame['trade_date']>=end-pd.Timedelta(days=LOOKBACK_DAYS)].sort_values('trade_date').copy()
        if len(frame)<MIN_BARS:
            raise ValueError('450 个自然日范围内不足130根日线')
        # Legacy stock_daily stores thousand yuan; do not use misleading WAN label.
        frame['amount'] /= 1000.0
        frame['ts_code']=code
        return frame
    except (KeyError,TypeError) as exc:
        raise ValueError('缺少有效日线字段') from exc


def evaluate(payload):
    frame=normalize(payload)
    score=score_one_stock(frame,strict_bottom=False,strict_breakout=True)
    result={'code':payload['code'],'as_of':payload['as_of'],'source_file':payload['source_file'],
            'rules':'core_v3-five-factor-miaoxiang-v1','score':None,'eligible':False}
    if score is not None:
        detail=asdict(score)
        detail['metrics'].pop('成交额(万)',None)
        detail['metrics']['成交额(元)']=float(frame.iloc[-1]['amount'])*1000
        detail['total']=score.total
        result.update(score=detail,eligible=score.total>=DEFAULT_MIN_SCORE)
    return result


def main():
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser(description='用已核验日线复现 V3 五因子；计算过程不访问数据库或网络')
    parser.add_argument('input',help='JSON: {"stocks": [单股数据对象]}')
    args=parser.parse_args()
    data=json.loads(Path(args.input).read_text())
    results=[]
    for payload in data['stocks']:
        try:
            results.append(evaluate(payload))
        except (ValueError,TypeError) as exc:
            results.append({'code':payload.get('code'),'eligible':False,'score':None,'error':str(exc)})
    def ranking(item):
        s=item['score'];return (s['pattern'],s['volume'],s['momentum'],s['metrics']['涨幅%'],s['total'])
    selected=sorted([r for r in results if r['eligible']],key=ranking,reverse=True)
    print(json.dumps({'selected':selected,'review':results,'scope':'input universe only'},ensure_ascii=False,indent=2,allow_nan=False))

if __name__=='__main__':
    main()
