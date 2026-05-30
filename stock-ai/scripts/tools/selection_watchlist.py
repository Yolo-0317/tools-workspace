#!/usr/bin/env python3
"""综合选股 Top5 导出、战报段落与次日监控规则。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "output"
AGENT_ROOT = ROOT / "investment-agent"
WATCH_FILE = AGENT_ROOT / "config" / "selection_watch_alerts.json"
ARTIFACT_JSON = OUTPUT_DIR / "daily_selection_top5.json"
ARTIFACT_FULL = OUTPUT_DIR / "daily_selection_full_latest.txt"
ARTIFACT_AI = OUTPUT_DIR / "daily_selection_ai_latest.txt"
SOP_JSON_LATEST = OUTPUT_DIR / "sop_review_latest.json"
TOP_N = 5
TZ = ZoneInfo("Asia/Shanghai")


@dataclass
class SelectionPick:
    code: str
    name: str
    close: float
    change_pct: float
    score: float
    label: str
    action: str
    in_holdings: bool = False


def next_trading_day(d: date) -> date:
    nd = d + timedelta(days=1)
    while nd.weekday() >= 5:
        nd += timedelta(days=1)
    return nd


def parse_trade_date_from_csv(path: Path) -> date:
    m = re.search(r"(\d{8})$", path.stem)
    if not m:
        return datetime.now(TZ).date()
    return datetime.strptime(m.group(1), "%Y%m%d").date()


def find_latest_selection_csv(output_dir: Path | None = None) -> Path | None:
    output_dir = output_dir or OUTPUT_DIR
    files = sorted(output_dir.glob("stock_selection_combined_*.csv"))
    return files[-1] if files else None


def load_top_picks(
    csv_path: Path | None = None,
    *,
    top_n: int = TOP_N,
    holdings_codes: set[str] | None = None,
) -> tuple[date, list[SelectionPick]]:
    from scripts.tools.holdings_context import load_holdings_card

    path = csv_path or find_latest_selection_csv()
    if path is None or not path.exists():
        raise FileNotFoundError("未找到 stock_selection_combined_*.csv")

    import pandas as pd

    df = pd.read_csv(path, encoding="utf-8-sig")
    if df.empty:
        raise ValueError("选股 CSV 为空")
    if "总分" in df.columns:
        df = df.sort_values(by=["总分", "标签数", "成交额(万)"], ascending=False)

    if holdings_codes is None:
        holdings_codes, _, _ = load_holdings_card()

    trade_date = parse_trade_date_from_csv(path)
    picks: list[SelectionPick] = []
    for _, row in df.head(top_n).iterrows():
        code = str(row["代码"]).split(".")[0].zfill(6)
        picks.append(
            SelectionPick(
                code=code,
                name="",
                close=float(row["收盘价"]),
                change_pct=float(row["涨幅%"]),
                score=float(row.get("总分", 0)),
                label=str(row.get("策略标签", "")),
                action=str(row.get("建议动作", "")),
                in_holdings=code in holdings_codes,
            )
        )
    return trade_date, picks


def _load_names(codes: list[str]) -> dict[str, str]:
    import os

    from sqlalchemy import create_engine, text

    url = os.getenv("MYSQL_URL", "").replace("host.docker.internal", "127.0.0.1")
    if not url:
        return {}
    placeholders = ", ".join(f":c{i}" for i in range(len(codes)))
    params = {f"c{i}": c for i, c in enumerate(codes)}
    names: dict[str, str] = {}
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT ts_code, name FROM stock_basic WHERE ts_code IN ({placeholders})"),
                params,
            ).fetchall()
        for row in rows:
            names[str(row.ts_code).split(".")[0].zfill(6)] = row.name
    except Exception:
        pass
    return names


def enrich_pick_names(picks: list[SelectionPick]) -> list[SelectionPick]:
    names = _load_names([p.code for p in picks])
    out: list[SelectionPick] = []
    for p in picks:
        out.append(
            SelectionPick(
                **{**asdict(p), "name": names.get(p.code, p.name or p.code)}
            )
        )
    return out


def format_briefing_section(
    picks: list[SelectionPick],
    *,
    trade_date: date,
    watch_date: date,
    ai_excerpt: str = "",
    sop_reviews: list[dict] | None = None,
) -> list[str]:
    sop_reviews = sop_reviews if sop_reviews is not None else load_sop_reviews()
    worthy = _sop_watch_map(sop_reviews)
    review_by_code = {str(r["code"]).zfill(6): r for r in sop_reviews}
    use_sop = bool(sop_reviews)
    td = f"{trade_date.month}月{trade_date.day}日"
    wd = f"{watch_date.month}月{watch_date.day}日"
    lines = [
        f"五、今日选股 Top{len(picks)}（{td} 收盘后）· 次日 {wd} 观察",
        "",
    ]
    if not picks:
        lines.append("- 暂无选股结果（17:30 选股可能未运行）")
        return lines

    for i, p in enumerate(picks, 1):
        held = " 📌已持仓" if p.in_holdings else ""
        lines.append(
            f"{i}. {p.name}({p.code}){held}\n"
            f"   {p.label} · 分{p.score:.0f} · {p.close:.2f} ({p.change_pct:+.2f}%) · {p.action}"
        )
        if p.in_holdings:
            continue
        if use_sop:
            sop = review_by_code.get(p.code, {})
            if worthy.get(p.code):
                decision = sop.get("decision") or "买入观察"
                supports = sop.get("support") or []
                stop = sop.get("stop")
                targets = sop.get("targets") or []
                extra = []
                if supports:
                    extra.append(f"支撑{min(map(float, supports)):.2f}")
                if stop:
                    extra.append(f"止损{float(stop):.2f}")
                if targets:
                    extra.append(f"目标{min(map(float, targets)):.2f}")
                hint = " · ".join(extra) if extra else ""
                lines.append(f"   ✅ SOP值得关注（{decision}）{' · ' + hint if hint else ''} → 次日5分钟监控")
            else:
                decision = sop.get("decision") or "暂不操作"
                lines.append(f"   ⏸ SOP暂不监控（{decision}）")
        else:
            dip = round(p.close * 0.97, 2)
            lines.append(f"   次日监控：涨>5%不追；回调≤{dip}元观察区")

    if ai_excerpt.strip():
        lines.extend(["", "── SOP / AI 投资决策 ──", "", ai_excerpt.strip(), ""])
    watch_count = len([p for p in picks if not p.in_holdings and p.code in worthy])
    if use_sop:
        monitor_note = (
            f"说明：SOP 判定「值得关注」{watch_count} 只（非持仓）已写入次日 5 分钟盘中监控；"
            "含支撑/止损/目标位提醒。红线仍适用（禁追高、禁满仓新开仓）。"
        )
    else:
        monitor_note = (
            "说明：Top5 已写入次日盘中监控（非持仓标的）；红线仍适用（禁追高、禁满仓新开仓）。"
        )
    lines.extend(["", monitor_note])
    return lines


def load_ai_excerpt() -> str:
    """读取选股 SOP / DeepSeek 微信摘要（优先干净产物，不含运行日志）。"""
    from scripts.tools.wechat_format import extract_sop_ai_section, format_sop_wechat_summary

    if ARTIFACT_AI.exists():
        text = ARTIFACT_AI.read_text(encoding="utf-8").strip()
        if text:
            return format_sop_wechat_summary(text)

    for path in (ARTIFACT_FULL, OUTPUT_DIR / "daily_selection_push_latest.txt"):
        if not path.exists():
            continue
        extracted = extract_sop_ai_section(path.read_text(encoding="utf-8"))
        if extracted:
            return extracted
    return ""


def load_sop_reviews(path: Path | None = None, *, refresh: bool = True) -> list[dict]:
    path = path or SOP_JSON_LATEST
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    from scripts.tools.sop_watch_parse import reparse_watch_meta

    raw = list(data.get("reviews") or [])
    reviews = [reparse_watch_meta(r) for r in raw]
    if refresh and reviews != raw:
        data["reviews"] = reviews
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return reviews


def _sop_watch_map(reviews: list[dict]) -> dict[str, dict]:
    return {str(r["code"]).zfill(6): r for r in reviews if r.get("watch_worthy")}


def build_watch_rules(
    picks: list[SelectionPick],
    *,
    watch_date: date,
    sop_reviews: list[dict] | None = None,
) -> list[dict]:
    sop_reviews = sop_reviews if sop_reviews is not None else load_sop_reviews()
    worthy = _sop_watch_map(sop_reviews)
    use_sop = bool(sop_reviews)

    rules: list[dict] = []
    wd = watch_date.isoformat()
    for p in picks:
        if p.in_holdings:
            continue
        code = p.code
        sop = worthy.get(code)
        if use_sop and not sop:
            continue

        dip = round(p.close * 0.97, 2)
        name = p.name or code
        rules.append(
            {
                "code": code,
                "name": name,
                "id": f"sel_{code}_no_chase",
                "type": "daily_pct_above",
                "pct": 5.0,
                "watch_date": wd,
                "source": "sop" if sop else "selection",
                "message": (
                    f"📊 选股池 {name}({code}) 当日涨 {{pct}}%（>5%）。"
                    f"SOP 观察标的，严禁追高（{wd}）。"
                    if sop
                    else f"📊 选股池 {name}({code}) 当日涨 {{pct}}%（>5%）。"
                    f"次日观察标的，严禁追高（{wd}）。"
                ),
            }
        )

        if sop:
            supports = sop.get("support") or []
            if supports:
                support = float(min(supports))
                rules.append(
                    {
                        "code": code,
                        "name": name,
                        "id": f"sel_{code}_sop_support",
                        "type": "price_below",
                        "price": support,
                        "watch_date": wd,
                        "source": "sop",
                        "message": (
                            f"📊 SOP观察 {name}({code}) 回踩支撑区 {{price}} 元"
                            f"（≤{support:.2f}）。可结合战报评估试探，非持仓。"
                        ),
                    }
                )
            stop = sop.get("stop")
            if stop:
                stop_f = float(stop)
                rules.append(
                    {
                        "code": code,
                        "name": name,
                        "id": f"sel_{code}_sop_stop",
                        "type": "price_below",
                        "price": stop_f,
                        "watch_date": wd,
                        "source": "sop",
                        "message": (
                            f"⚠️ SOP观察 {name}({code}) 跌破止损 {{price}} 元"
                            f"（<{stop_f:.2f}）。观察逻辑失效，勿盲目介入。"
                        ),
                    }
                )
            targets = sop.get("targets") or []
            if targets:
                target = float(min(targets))
                rules.append(
                    {
                        "code": code,
                        "name": name,
                        "id": f"sel_{code}_sop_target",
                        "type": "price_above",
                        "price": target,
                        "watch_date": wd,
                        "source": "sop",
                        "message": (
                            f"📈 SOP观察 {name}({code}) 触及目标/压力 {{price}} 元"
                            f"（≥{target:.2f}）。勿追高，评估是否放弃新开仓。"
                        ),
                    }
                )
        else:
            rules.append(
                {
                    "code": code,
                    "name": name,
                    "id": f"sel_{code}_dip",
                    "type": "price_below",
                    "price": dip,
                    "watch_date": wd,
                    "source": "selection",
                    "message": (
                        f"📊 选股池 {name}({code}) 回调至 {{price}} 元（≤{dip}，选股价 {p.close:.2f} 的 -3%）。"
                        f"可结合战报与仓位评估观察，非持仓。"
                    ),
                }
            )
    return rules


def sync_watch_alerts(
    csv_path: Path | None = None,
    *,
    watch_file: Path = WATCH_FILE,
) -> dict:
    from scripts.tools.holdings_context import load_holdings_card

    holdings_codes, _, _ = load_holdings_card()
    trade_date, picks = load_top_picks(csv_path, holdings_codes=holdings_codes)
    picks = enrich_pick_names(picks)
    sop_reviews = load_sop_reviews()
    worthy = _sop_watch_map(sop_reviews)
    pick_codes = {p.code for p in picks}
    watch_codes = sorted(code for code in worthy if code in pick_codes and not any(
        p.in_holdings for p in picks if p.code == code
    ))
    watch_date = next_trading_day(trade_date)

    payload = {
        "version": 2,
        "description": "SOP 值得关注标的 · 次日 5 分钟盘中监控（非持仓）",
        "selection_trade_date": trade_date.isoformat(),
        "watch_date": watch_date.isoformat(),
        "sop_available": bool(sop_reviews),
        "watch_codes": watch_codes,
        "picks": [asdict(p) for p in picks],
        "sop_reviews": sop_reviews,
        "rules": build_watch_rules(picks, watch_date=watch_date, sop_reviews=sop_reviews),
    }
    watch_file.parent.mkdir(parents=True, exist_ok=True)
    watch_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    artifact = {
        "trade_date": trade_date.isoformat(),
        "watch_date": watch_date.isoformat(),
        "picks": [asdict(p) for p in picks],
        "synced_at": datetime.now(TZ).isoformat(timespec="seconds"),
    }
    ARTIFACT_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_JSON.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def load_active_selection_rules(
    watch_file: Path = WATCH_FILE,
    *,
    today: date | None = None,
) -> list[dict]:
    today = today or datetime.now(TZ).date()
    if not watch_file.exists():
        return []
    data = json.loads(watch_file.read_text(encoding="utf-8"))
    watch_date = data.get("watch_date")
    rules: list[dict] = []
    for rule in data.get("rules") or []:
        if rule.get("persistent"):
            rules.append(rule)
        elif watch_date == today.isoformat():
            rules.append(rule)
    return rules


def export_ai_artifact(ai_text: str) -> None:
    """保存选股 AI/SOP 微信摘要（供战报引用，不含 stderr 日志）。"""
    from scripts.tools.wechat_format import format_sop_wechat_summary

    ARTIFACT_AI.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_AI.write_text(format_sop_wechat_summary(ai_text.strip()) + "\n", encoding="utf-8")


def export_artifact_from_text(full_text: str) -> None:
    ARTIFACT_FULL.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_FULL.write_text(full_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="选股 Top5 战报/监控工具")
    parser.add_argument("--sync", action="store_true", help="从最新 CSV 同步次日监控规则")
    parser.add_argument("--csv", type=Path, default=None)
    args = parser.parse_args()

    if not args.sync:
        parser.print_help()
        return 0

    try:
        payload = sync_watch_alerts(args.csv)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 同步失败: {exc}", file=sys.stderr)
        return 1

    n_rules = len(payload.get("rules") or [])
    n_watch = len(payload.get("watch_codes") or [])
    print(
        f"✅ 选股监控已更新 watch_date={payload['watch_date']} "
        f"watch={n_watch} rules={n_rules} sop={'是' if payload.get('sop_available') else '否'}"
    )
    print(f"   文件: {WATCH_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
