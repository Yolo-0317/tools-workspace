#!/usr/bin/env python3
"""持仓与监控规则 MySQL 读写（权威数据源；选股见 selection_daily_results）。"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[2]
STOCK_AI = ROOT
AGENT = STOCK_AI / "investment-agent"


@dataclass
class DbPosition:
    code: str
    name: str
    shares: int
    cost: float
    status: str = ""
    action: str = ""


@dataclass
class DbAccount:
    total_assets: float | None
    available_cash: float | None
    market_value: float | None
    position_ratio: float | None
    holding_pnl: float | None
    snapshot_date: date | None


def _load_dotenv() -> None:
    for path in (STOCK_AI / ".env", ROOT.parent / "stock-mysql" / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def mysql_url() -> str:
    _load_dotenv()
    url = os.environ.get("MYSQL_URL", "")
    if not url:
        user = os.environ.get("MYSQL_USER", "stock")
        password = os.environ.get("MYSQL_PASSWORD", "")
        db = os.environ.get("MYSQL_DATABASE", "stock_data")
        url = f"mysql+pymysql://{user}:{password}@127.0.0.1:3306/{db}"
    return url.replace("host.docker.internal", "127.0.0.1")


def get_engine() -> Engine | None:
    url = mysql_url()
    if not url or "://" not in url:
        return None
    try:
        return create_engine(url, pool_pre_ping=True)
    except Exception:
        return None


def _row_to_rule(row: Any) -> dict:
    rule: dict[str, Any] = {
        "id": row.rule_id,
        "code": str(row.ts_code).zfill(6),
        "name": row.name or "",
        "type": row.rule_type,
        "message": row.message_template or "",
    }
    if row.price is not None:
        rule["price"] = float(row.price)
    if row.low_price is not None:
        rule["low"] = float(row.low_price)
    if row.high_price is not None:
        rule["high"] = float(row.high_price)
    if row.pct_threshold is not None:
        rule["pct"] = float(row.pct_threshold)
    return rule


def load_positions(*, engine: Engine | None = None) -> list[DbPosition]:
    engine = engine or get_engine()
    if engine is None:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT ts_code, name, shares, cost_price, status_note, action_note
                    FROM portfolio_positions
                    WHERE is_active = 1
                    ORDER BY ts_code
                    """
                )
            ).fetchall()
    except Exception:
        return []

    out: list[DbPosition] = []
    for row in rows:
        code = str(row.ts_code).zfill(6)
        if not re.fullmatch(r"\d{6}", code):
            continue
        out.append(
            DbPosition(
                code=code,
                name=str(row.name or code),
                shares=int(row.shares or 0),
                cost=float(row.cost_price or 0),
                status=str(row.status_note or ""),
                action=str(row.action_note or ""),
            )
        )
    return out


def load_holding_codes(*, engine: Engine | None = None) -> set[str]:
    return {p.code for p in load_positions(engine=engine)}


def load_account(*, engine: Engine | None = None) -> DbAccount | None:
    engine = engine or get_engine()
    if engine is None:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT total_assets, available_cash, market_value, position_ratio,
                           holding_pnl, snapshot_date
                    FROM portfolio_account
                    WHERE id = 1
                    """
                )
            ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    snap = row.snapshot_date
    return DbAccount(
        total_assets=float(row.total_assets) if row.total_assets is not None else None,
        available_cash=float(row.available_cash) if row.available_cash is not None else None,
        market_value=float(row.market_value) if row.market_value is not None else None,
        position_ratio=float(row.position_ratio) if row.position_ratio is not None else None,
        holding_pnl=float(row.holding_pnl) if row.holding_pnl is not None else None,
        snapshot_date=snap if isinstance(snap, date) else None,
    )


def load_latest_closes(codes: list[str], *, engine: Engine | None = None) -> dict[str, float]:
    """从东财 OpenCLI 采集最新价（禁止 HTTP API / MySQL 行情兜底）。"""
    _ = engine
    if not codes:
        return {}
    try:
        from scripts.tools.fetch_eastmoney_quotes import fetch_quotes

        quotes = fetch_quotes([str(c).zfill(6) for c in codes])
        return {c: q.price for c, q in quotes.items() if q.price is not None}
    except Exception:
        return {}


def load_alert_rules(
    *,
    source: str | None = None,
    engine: Engine | None = None,
) -> list[dict]:
    engine = engine or get_engine()
    if engine is None:
        return []
    sql = """
        SELECT rule_id, ts_code, name, rule_type, price, low_price, high_price,
               pct_threshold, message_template
        FROM alert_rules
        WHERE is_enabled = 1
    """
    params: dict[str, Any] = {}
    if source:
        sql += " AND source = :source"
        params["source"] = source
    sql += " ORDER BY rule_id"
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
    except Exception:
        return []
    return [_row_to_rule(r) for r in rows]


def load_active_selection_rules(
    *,
    today: date | None = None,
    engine: Engine | None = None,
) -> list[dict]:
    today = today or date.today()
    engine = engine or get_engine()
    if engine is None:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT ar.rule_id, ar.ts_code, ar.name, ar.rule_type, ar.price,
                           ar.low_price, ar.high_price, ar.pct_threshold, ar.message_template
                    FROM alert_rules ar
                    INNER JOIN selection_watch_picks swp
                      ON swp.ts_code = ar.ts_code
                     AND swp.watch_date = :today
                     AND swp.is_active = 1
                    WHERE ar.source = 'selection'
                      AND ar.is_enabled = 1
                    ORDER BY ar.rule_id
                    """
                ),
                {"today": today.isoformat()},
            ).fetchall()
    except Exception:
        return []
    rules = [_row_to_rule(r) for r in rows]
    for rule in rules:
        rule["watch_date"] = today.isoformat()
    return rules


def load_all_monitor_rules(*, today: date | None = None) -> list[dict]:
    """持仓规则 + 当日选股监控规则（仅 MySQL）。"""
    today = today or date.today()
    engine = get_engine()
    holdings = load_alert_rules(source="holdings", engine=engine)
    for rule in holdings:
        rule["source"] = "holdings"
    selection = load_active_selection_rules(today=today, engine=engine)
    for rule in selection:
        rule["source"] = "selection"
    return holdings + selection


def sync_from_card(positions, account, rules: list[dict]) -> dict[str, int]:
    """写入 portfolio_positions / portfolio_account / alert_rules（source=holdings）。"""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法同步")

    active_codes = [p.code for p in positions]
    rule_ids = [str(r["id"]) for r in rules]

    with engine.begin() as conn:
        if active_codes:
            placeholders = ", ".join(f":c{i}" for i in range(len(active_codes)))
            params = {f"c{i}": c for i, c in enumerate(active_codes)}
            conn.execute(
                text(
                    f"UPDATE portfolio_positions SET is_active = 0 "
                    f"WHERE ts_code NOT IN ({placeholders})"
                ),
                params,
            )
        else:
            conn.execute(text("UPDATE portfolio_positions SET is_active = 0"))

        pos_n = 0
        for p in positions:
            conn.execute(
                text(
                    """
                    INSERT INTO portfolio_positions
                      (ts_code, name, asset_type, shares, cost_price,
                       status_note, action_note, source, is_active)
                    VALUES
                      (:code, :name, :atype, :shares, :cost, :status, :action, 'card', 1)
                    ON DUPLICATE KEY UPDATE
                      name = VALUES(name),
                      asset_type = VALUES(asset_type),
                      shares = VALUES(shares),
                      cost_price = VALUES(cost_price),
                      status_note = VALUES(status_note),
                      action_note = VALUES(action_note),
                      source = 'card',
                      is_active = 1
                    """
                ),
                {
                    "code": p.code,
                    "name": p.name,
                    "atype": getattr(p, "asset_type", "stock"),
                    "shares": p.shares,
                    "cost": p.cost,
                    "status": p.status,
                    "action": p.action,
                },
            )
            pos_n += 1

        acct_n = 0
        if account.total_assets is not None or account.available_cash is not None:
            conn.execute(
                text(
                    """
                    INSERT INTO portfolio_account
                      (id, total_assets, available_cash, market_value, position_ratio,
                       holding_pnl, snapshot_date)
                    VALUES
                      (1, :total, :cash, :market, :pos, :pnl, :snap)
                    ON DUPLICATE KEY UPDATE
                      total_assets = VALUES(total_assets),
                      available_cash = VALUES(available_cash),
                      market_value = VALUES(market_value),
                      position_ratio = VALUES(position_ratio),
                      holding_pnl = VALUES(holding_pnl),
                      snapshot_date = VALUES(snapshot_date)
                    """
                ),
                {
                    "total": account.total_assets,
                    "cash": account.available_cash,
                    "market": account.market_value,
                    "pos": account.position_ratio,
                    "pnl": account.holding_pnl,
                    "snap": account.snapshot_date,
                },
            )
            acct_n = 1

        if rule_ids:
            placeholders = ", ".join(f":r{i}" for i in range(len(rule_ids)))
            params = {f"r{i}": rid for i, rid in enumerate(rule_ids)}
            conn.execute(
                text(
                    f"UPDATE alert_rules SET is_enabled = 0 "
                    f"WHERE source = 'holdings' AND rule_id NOT IN ({placeholders})"
                ),
                params,
            )
        else:
            conn.execute(text("UPDATE alert_rules SET is_enabled = 0 WHERE source = 'holdings'"))

        rule_n = upsert_alert_rules(rules, source="holdings", conn=conn)

    return {"positions": pos_n, "account": acct_n, "rules": rule_n}


def upsert_alert_rules(rules: list[dict], *, source: str, conn) -> int:
    n = 0
    for r in rules:
        rid = str(r.get("id") or f"{source}_{r.get('code')}_{n}")
        conn.execute(
            text(
                """
                INSERT INTO alert_rules
                  (rule_id, ts_code, name, rule_type, price, low_price, high_price,
                   pct_threshold, message_template, source, is_enabled)
                VALUES
                  (:rid, :code, :name, :rtype, :price, :low, :high, :pct, :msg, :src, 1)
                ON DUPLICATE KEY UPDATE
                  ts_code = VALUES(ts_code),
                  name = VALUES(name),
                  rule_type = VALUES(rule_type),
                  price = VALUES(price),
                  low_price = VALUES(low_price),
                  high_price = VALUES(high_price),
                  pct_threshold = VALUES(pct_threshold),
                  message_template = VALUES(message_template),
                  source = VALUES(source),
                  is_enabled = 1
                """
            ),
            {
                "rid": rid,
                "code": str(r.get("code", "")),
                "name": str(r.get("name", "")),
                "rtype": str(r.get("type", "")),
                "price": r.get("price"),
                "low": r.get("low"),
                "high": r.get("high"),
                "pct": r.get("pct"),
                "msg": str(r.get("message", "")),
                "src": source,
            },
        )
        n += 1
    return n


def sync_selection_payload(payload: dict) -> dict[str, int]:
    """将选股监控结构写入 DB（selection_watch_picks + alert_rules）。"""
    engine = get_engine()
    if engine is None:
        return {"alert_rules": 0, "selection_watch_picks": 0}

    trade_date = payload.get("selection_trade_date") or date.today().isoformat()
    watch_date = payload.get("watch_date") or trade_date
    picks = payload.get("picks") or []
    rules = payload.get("rules") or []

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE selection_watch_picks SET is_active = 0 WHERE watch_date = :wd"),
            {"wd": watch_date},
        )
        pick_n = 0
        for p in picks:
            code = str(p.get("code", ""))
            if not re.fullmatch(r"\d{6}", code):
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO selection_watch_picks
                      (selection_trade_date, watch_date, ts_code, name, close_price,
                       change_pct, score, label, action_hint, in_holdings, raw_json, is_active)
                    VALUES
                      (:td, :wd, :code, :name, :close, :pct, :score, :label, :action,
                       :held, :raw, 1)
                    """
                ),
                {
                    "td": trade_date,
                    "wd": watch_date,
                    "code": code,
                    "name": str(p.get("name", code)),
                    "close": p.get("close"),
                    "pct": p.get("change_pct"),
                    "score": p.get("score"),
                    "label": p.get("label"),
                    "action": p.get("action"),
                    "held": 1 if p.get("in_holdings") else 0,
                    "raw": json.dumps(p, ensure_ascii=False),
                },
            )
            pick_n += 1
        rule_n = upsert_alert_rules(rules, source="selection", conn=conn)

    return {"alert_rules": rule_n, "selection_watch_picks": pick_n}


def _parse_selection_trade_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    s = str(value).strip().replace("-", "")
    if len(s) >= 8 and s[:8].isdigit():
        return datetime.strptime(s[:8], "%Y%m%d").date()
    return datetime.fromisoformat(str(value)[:10]).date()


def _code6(code: str) -> str:
    return str(code).split(".")[0].zfill(6)


def _to_ts_code(code: str) -> str:
    code_str = _code6(code)
    if code_str.startswith(("60", "68")):
        return f"{code_str}.SH"
    return f"{code_str}.SZ"


_STOCK_NAME_CACHE: dict[str, str] | None = None
_NAME_CACHE_FILE = STOCK_AI / "output" / "cache" / "stock_name_map.json"
_OPENCLI_NAME_LOOKUP_LIMIT = 128
_MARKET_NAME_CACHE_MIN = 500
_BULK_WARM_ATTEMPTED = False


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _name_needs_enrich(name: str, code: str) -> bool:
    n = (name or "").strip()
    if not n or n == code:
        return True
    if n.isdigit() and len(n) == 6:
        return True
    return not _has_cjk(n)


def _read_disk_name_cache() -> dict[str, str]:
    if not _NAME_CACHE_FILE.is_file():
        return {}
    try:
        data = json.loads(_NAME_CACHE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {
                _code6(k): str(v).strip()
                for k, v in data.items()
                if _has_cjk(str(v))
            }
    except Exception:
        pass
    return {}


def _write_disk_name_cache(extra: dict[str, str]) -> None:
    if not extra:
        return
    merged = _read_disk_name_cache()
    for code, cn in extra.items():
        c = _code6(code)
        if cn and _has_cjk(cn):
            merged[c] = cn.strip()
    _NAME_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _NAME_CACHE_FILE.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _fetch_eastmoney_market_name_cache(*, force: bool = False) -> dict[str, str]:
    """东财 clist 全市场代码→名称，写入本地缓存（Tushare 不可用时的主来源）。"""
    cache = _read_disk_name_cache()
    if len(cache) >= _MARKET_NAME_CACHE_MIN and not force:
        return cache
    try:
        import requests
    except ImportError:
        return cache

    fs = "m:1+t:2,m:1+t:23,m:0+t:6,m:0+t:80,m:0+t:81,m:0+t:82,m:0+t:83"
    prev_no_proxy = os.environ.get("NO_PROXY")
    os.environ["NO_PROXY"] = "*"
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
    merged = dict(cache)
    pn = 1
    pz = 500
    try:
        while pn <= 80:
            try:
                resp = session.get(
                    "https://push2.eastmoney.com/api/qt/clist/get",
                    params={"pn": pn, "pz": pz, "fs": fs, "fields": "f12,f14"},
                    timeout=30,
                )
                resp.raise_for_status()
                payload = resp.json()
            except Exception:
                break
            block = (payload.get("data") or {}).get("diff") or []
            if not block:
                break
            for item in block:
                if not isinstance(item, dict):
                    continue
                code = _code6(str(item.get("f12") or ""))
                name = str(item.get("f14") or "").strip()
                if code and name and _has_cjk(name):
                    merged[code] = name
            total = int((payload.get("data") or {}).get("total") or 0)
            if pn * pz >= total:
                break
            pn += 1
    finally:
        if prev_no_proxy is None:
            os.environ.pop("NO_PROXY", None)
        else:
            os.environ["NO_PROXY"] = prev_no_proxy
    if len(merged) > len(cache):
        _write_disk_name_cache(merged)
    global _STOCK_NAME_CACHE
    _STOCK_NAME_CACHE = None
    return merged


def _fetch_opencli_market_name_cache(*, force: bool = False) -> dict[str, str]:
    """OpenCLI 东财 A 股列表 JSONP 分页（clist HTTP 不可用时的全量兜底）。"""
    cache = _read_disk_name_cache()
    if len(cache) >= _MARKET_NAME_CACHE_MIN and not force:
        return cache
    try:
        from scripts.tools.fetch_eastmoney_quotes import fetch_market_names_opencli

        print(
            "⏳ OpenCLI 东财 A 股列表 DOM 翻页（约 6～8 分钟）…",
            file=sys.stderr,
        )
        fetched = fetch_market_names_opencli(close_browser=True)
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ OpenCLI A 股列表失败: {exc}", file=sys.stderr)
        return cache

    merged = dict(cache)
    merged.update(fetched)
    if len(merged) > len(cache):
        _write_disk_name_cache(merged)
    global _STOCK_NAME_CACHE
    _STOCK_NAME_CACHE = None
    print(
        f"✓ OpenCLI A 股列表: +{len(fetched)} 条，合计 {len(merged)} 条",
        file=sys.stderr,
    )
    return merged


def ensure_market_name_cache(*, force: bool = False) -> int:
    """预热代码→中文名缓存（东财 clist → OpenCLI A 股列表 → 逐股补缺）。"""
    _load_dotenv()
    _fetch_eastmoney_market_name_cache(force=force)
    cache = _read_disk_name_cache()
    if len(cache) < _MARKET_NAME_CACHE_MIN:
        cache = _fetch_opencli_market_name_cache(force=force)
    global _STOCK_NAME_CACHE
    _STOCK_NAME_CACHE = cache
    return len(cache)


def _fetch_opencli_names(codes: list[str]) -> dict[str, str]:
    if not codes:
        return {}
    try:
        from scripts.tools.fetch_eastmoney_quotes import fetch_quotes_opencli

        quotes = fetch_quotes_opencli(codes, close_browser=True)
    except Exception:
        return {}
    out: dict[str, str] = {}
    for code, quote in quotes.items():
        cn = (quote.name or "").strip()
        c = _code6(code)
        if cn and _has_cjk(cn) and cn != c:
            out[c] = cn
    return out


def _fetch_tushare_name_cache(*, refresh: bool = False) -> dict[str, str]:
    """本地名称缓存（Tushare 仅有行情权限，不调用 stock_basic）。"""
    global _STOCK_NAME_CACHE
    if _STOCK_NAME_CACHE is not None and not refresh:
        return _STOCK_NAME_CACHE
    _load_dotenv()
    cache: dict[str, str] = dict(_read_disk_name_cache())
    _STOCK_NAME_CACHE = cache
    return cache


def load_stock_names_by_codes(
    codes: list[str],
    *,
    engine: Engine | None = None,
) -> dict[str, str]:
    """6 位代码 → 中文名（持仓 → 东财全市场缓存 → OpenCLI 补缺）。"""
    normalized: list[str] = []
    for raw in codes:
        code = _code6(raw)
        if re.fullmatch(r"\d{6}", code) and code not in normalized:
            normalized.append(code)
    if not normalized:
        return {}

    global _BULK_WARM_ATTEMPTED
    if not _BULK_WARM_ATTEMPTED and len(_read_disk_name_cache()) < _MARKET_NAME_CACHE_MIN:
        _BULK_WARM_ATTEMPTED = True
        ensure_market_name_cache()

    out: dict[str, str] = {}
    engine = engine or get_engine()
    if engine is not None:
        placeholders = ", ".join(f":c{i}" for i in range(len(normalized)))
        params = {f"c{i}": c for i, c in enumerate(normalized)}
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        f"SELECT ts_code, name FROM portfolio_positions "
                        f"WHERE is_active = 1 AND ts_code IN ({placeholders})"
                    ),
                    params,
                ).fetchall()
            for row in rows:
                code = _code6(row.ts_code)
                cn = str(row.name or "").strip()
                if cn and _has_cjk(cn):
                    out[code] = cn
        except Exception:
            pass

    try:
        from stock_ai.symbols import CODE_NAMES

        for code in normalized:
            if code in out:
                continue
            cn = (CODE_NAMES.get(code) or "").strip()
            if cn and _has_cjk(cn):
                out[code] = cn
    except Exception:
        pass

    tushare_names = _fetch_tushare_name_cache()
    for code in normalized:
        if code in out:
            continue
        cn = tushare_names.get(code) or tushare_names.get(_to_ts_code(code), "")
        if cn:
            out[code] = cn

    missing = [c for c in normalized if c not in out]
    if missing and len(missing) <= _OPENCLI_NAME_LOOKUP_LIMIT:
        opencli = _fetch_opencli_names(missing)
        out.update(opencli)
        _write_disk_name_cache(opencli)
    return out


def enrich_sop_review_bundle(
    bundle: dict[str, Any] | None,
    *,
    names: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    if not bundle or not bundle.get("items"):
        return bundle
    items = bundle["items"]
    if names is None:
        codes = [_code6(str(it.get("ts_code", ""))) for it in items]
        names = load_stock_names_by_codes(codes)
    for item in items:
        code = _code6(str(item.get("ts_code", item.get("code", ""))))
        item["code"] = code
        cur = str(item.get("name") or "").strip()
        cn = (names or {}).get(code, "")
        if cn and _name_needs_enrich(cur, code):
            item["name"] = cn
    return bundle


def enrich_selection_row_names(
    rows: list[dict[str, Any]],
    *,
    names: dict[str, str] | None = None,
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    if not rows:
        return rows
    if names is None:
        codes = [_selection_row_code(r) for r in rows]
        names = load_stock_names_by_codes(codes, engine=engine)
    for row in rows:
        code = _selection_row_code(row)
        cur = str(row.get("名称") or row.get("name") or "").strip()
        cn = (names or {}).get(code, "")
        if cn and _name_needs_enrich(cur, code):
            row["名称"] = cn
    return rows


def _selection_row_code(row: dict[str, Any]) -> str:
    return _code6(str(row.get("代码", row.get("code", ""))))


def _json_safe_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:  # NaN / inf
            return None
        return value
    if hasattr(value, "item"):
        try:
            return _json_safe_value(value.item())
        except Exception:
            return str(value)
    if isinstance(value, (int, str, bool)):
        return value
    return str(value)


def _json_safe_selection_row(row: dict[str, Any]) -> dict[str, Any]:
    clean = {str(k): _json_safe_value(v) for k, v in row.items()}
    if "代码" in clean and clean["代码"] is not None:
        clean["代码"] = _selection_row_code(clean)
    return clean


def save_selection_daily_results(
    trade_date: date | str,
    rows: list[dict[str, Any]],
    *,
    strategy: str = "combined",
) -> int:
    """写入选股全量结果：同日 + 同 strategy 先删后插（覆盖）；不同日期或策略保留。"""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法写入 selection_daily_results")

    td = _parse_selection_trade_date(trade_date)
    strat = (strategy or "combined").strip() or "combined"
    if rows:
        enrich_selection_row_names(rows, engine=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM selection_daily_results "
                "WHERE trade_date = :d AND strategy = :s"
            ),
            {"d": td.isoformat(), "s": strat},
        )
        n = 0
        for rank_no, row in enumerate(rows, 1):
            safe = _json_safe_selection_row(row)
            code = _selection_row_code(safe)
            if not re.fullmatch(r"\d{6}", code):
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO selection_daily_results
                      (trade_date, strategy, ts_code, rank_no, close_price, change_pct, total_score,
                       label_count, amount_wan, strategy_label, action_hint, raw_json)
                    VALUES
                      (:td, :strat, :code, :rank, :close, :pct, :score, :lc, :amt, :label, :action, :raw)
                    """
                ),
                {
                    "td": td.isoformat(),
                    "strat": strat,
                    "code": code,
                    "rank": rank_no,
                    "close": safe.get("收盘价"),
                    "pct": safe.get("涨幅%"),
                    "score": safe.get("总分"),
                    "lc": safe.get("标签数"),
                    "amt": safe.get("成交额(万)"),
                    "label": safe.get("策略标签"),
                    "action": safe.get("建议动作"),
                    "raw": json.dumps(safe, ensure_ascii=False),
                },
            )
            n += 1
    return n


def list_selection_trade_dates(
    *,
    strategy: str = "combined",
    engine: Engine | None = None,
) -> list[date]:
    engine = engine or get_engine()
    if engine is None:
        return []
    strat = (strategy or "combined").strip() or "combined"
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT DISTINCT trade_date
                    FROM selection_daily_results
                    WHERE strategy = :s
                    ORDER BY trade_date DESC
                    """
                ),
                {"s": strat},
            ).fetchall()
    except Exception:
        return []
    out: list[date] = []
    for row in rows:
        val = row.trade_date
        if isinstance(val, date):
            out.append(val)
        else:
            out.append(datetime.fromisoformat(str(val)[:10]).date())
    return out


def list_selection_strategies(*, engine: Engine | None = None) -> list[str]:
    engine = engine or get_engine()
    if engine is None:
        return ["combined"]
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT DISTINCT strategy
                    FROM selection_daily_results
                    ORDER BY strategy
                    """
                )
            ).fetchall()
    except Exception:
        return ["combined"]
    out = [str(r[0]) for r in rows if r[0]]
    return out or ["combined"]


def latest_selection_trade_date(
    *,
    strategy: str = "combined",
    engine: Engine | None = None,
) -> date | None:
    engine = engine or get_engine()
    if engine is None:
        return None
    strat = (strategy or "combined").strip() or "combined"
    try:
        with engine.connect() as conn:
            value = conn.execute(
                text(
                    "SELECT MAX(trade_date) FROM selection_daily_results "
                    "WHERE strategy = :s"
                ),
                {"s": strat},
            ).scalar()
    except Exception:
        return None
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:10]).date()


def load_selection_daily_results(
    trade_date: date | str | None = None,
    *,
    strategy: str = "combined",
    engine: Engine | None = None,
) -> tuple[date | None, list[dict[str, Any]]]:
    """读取选股结果，返回与 CSV 列一致的字典列表。"""
    engine = engine or get_engine()
    if engine is None:
        return None, []

    td = _parse_selection_trade_date(trade_date) if trade_date else None
    strat = (strategy or "combined").strip() or "combined"
    sql = """
        SELECT trade_date, raw_json
        FROM selection_daily_results
        WHERE strategy = :strat
    """
    params: dict[str, Any] = {"strat": strat}
    if td is not None:
        sql += " AND trade_date = :d"
        params["d"] = td.isoformat()
    else:
        sql += (
            " AND trade_date = ("
            "SELECT MAX(trade_date) FROM selection_daily_results WHERE strategy = :strat2"
            ")"
        )
        params["strat2"] = strat
    sql += " ORDER BY rank_no"

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
    except Exception:
        return None, []

    if not rows:
        return td, []

    out: list[dict[str, Any]] = []
    resolved = td
    for row in rows:
        if resolved is None and row.trade_date is not None:
            resolved = (
                row.trade_date
                if isinstance(row.trade_date, date)
                else datetime.fromisoformat(str(row.trade_date)[:10]).date()
            )
        raw = row.raw_json
        if isinstance(raw, str):
            raw = json.loads(raw)
        if isinstance(raw, dict):
            out.append(raw)
    return resolved, enrich_selection_row_names(out, engine=engine)


def _profile_row_from_dict(item: dict[str, Any]) -> dict[str, Any]:
    code = str(item.get("ts_code") or item.get("code") or "").split(".")[0].zfill(6)
    concepts = item.get("concepts")
    if isinstance(concepts, str):
        try:
            concepts = json.loads(concepts)
        except json.JSONDecodeError:
            concepts = [c.strip() for c in concepts.split(",") if c.strip()]
    if not isinstance(concepts, list):
        concepts = []
    return {
        "code": code,
        "name": (item.get("name") or "").strip() or None,
        "industry": ((item.get("industry") or item.get("所属行业") or "").strip() or None)[:128]
        if (item.get("industry") or item.get("所属行业"))
        else None,
        "concepts": [str(c).strip() for c in concepts if str(c).strip()],
        "profile_text": (item.get("profile_text") or item.get("公司简介") or "").strip() or None,
        "info_text": (item.get("info_text") or "").strip() or None,
        "sectors_text": (item.get("sectors_text") or "").strip() or None,
        "source": (item.get("source") or "eastmoney-opencli").strip() or "eastmoney-opencli",
    }


def upsert_stock_profiles(
    profiles: list[dict[str, Any]],
    *,
    engine: Engine | None = None,
) -> int:
    engine = engine or get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法写入 stock_profile")
    if not profiles:
        return 0

    n = 0
    with engine.begin() as conn:
        for raw in profiles:
            row = _profile_row_from_dict(raw)
            code = row["code"]
            if not re.fullmatch(r"\d{6}", code):
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO stock_profile
                      (ts_code, name, industry, concepts, profile_text, info_text, sectors_text, source)
                    VALUES
                      (:code, :name, :industry, :concepts, :profile_text, :info_text, :sectors_text, :source)
                    ON DUPLICATE KEY UPDATE
                      name = VALUES(name),
                      industry = COALESCE(VALUES(industry), industry),
                      concepts = COALESCE(VALUES(concepts), concepts),
                      profile_text = COALESCE(VALUES(profile_text), profile_text),
                      info_text = COALESCE(VALUES(info_text), info_text),
                      sectors_text = COALESCE(VALUES(sectors_text), sectors_text),
                      source = VALUES(source),
                      updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {
                    "code": code,
                    "name": row["name"],
                    "industry": row["industry"],
                    "concepts": json.dumps(row["concepts"], ensure_ascii=False)
                    if row["concepts"]
                    else None,
                    "profile_text": row["profile_text"],
                    "info_text": row["info_text"],
                    "sectors_text": row["sectors_text"],
                    "source": row["source"],
                },
            )
            n += 1
    return n


def load_stock_profiles_by_codes(
    codes: list[str],
    *,
    engine: Engine | None = None,
) -> dict[str, dict[str, Any]]:
    engine = engine or get_engine()
    if engine is None or not codes:
        return {}

    uniq = [
        str(c).split(".")[0].zfill(6)
        for c in dict.fromkeys(str(c).split(".")[0].zfill(6) for c in codes)
    ]
    placeholders = ", ".join(f":c{i}" for i in range(len(uniq)))
    params = {f"c{i}": c for i, c in enumerate(uniq)}
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT ts_code, name, industry, concepts, profile_text, info_text, sectors_text, source, updated_at
                    FROM stock_profile
                    WHERE ts_code IN ({placeholders})
                    """
                ),
                params,
            ).fetchall()
    except Exception:
        return {}

    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.ts_code).zfill(6)
        concepts = row.concepts
        if isinstance(concepts, str):
            try:
                concepts = json.loads(concepts)
            except json.JSONDecodeError:
                concepts = []
        out[code] = {
            "ts_code": code,
            "name": row.name,
            "industry": row.industry,
            "concepts": concepts or [],
            "profile_text": row.profile_text,
            "info_text": row.info_text,
            "sectors_text": row.sectors_text,
            "source": row.source,
            "updated_at": str(row.updated_at) if row.updated_at else None,
        }
    return out


def load_industry_map(*, engine: Engine | None = None) -> dict[str, str]:
    """6 位代码 / ts_code → 行业名（OpenCLI enrich 写入的 stock_profile）。"""
    engine = engine or get_engine()
    if engine is None:
        return {}

    out: dict[str, str] = {}

    def _put(code: str, industry: str | None) -> None:
        ind = (industry or "").strip()
        if not ind or ind in {"N/A", "-", "--"}:
            return
        c6 = _code6(code)
        out[c6] = ind
        out[_to_ts_code(c6)] = ind

    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT ts_code, industry FROM stock_profile
                    WHERE industry IS NOT NULL AND industry != ''
                    """
                )
            ).fetchall()
        for row in rows:
            _put(str(row.ts_code), str(row.industry))
    except Exception:
        pass

    return out


def is_st_stock_name(name: str) -> bool:
    """ST / *ST 名称识别。"""
    n = (name or "").strip()
    if not n:
        return False
    return bool(re.match(r"^\*?ST", n, re.IGNORECASE))


def load_st_codes_from_names(name_map: dict[str, str] | None = None) -> set[str]:
    """从代码→名称映射中提取 ST 代码集合。"""
    if name_map is None:
        name_map = _fetch_tushare_name_cache()
    st: set[str] = set()
    for code, name in name_map.items():
        if not re.fullmatch(r"\d{6}", str(code)):
            continue
        if is_st_stock_name(str(name)):
            st.add(str(code))
    return st


def load_st_codes(*, engine: Engine | None = None) -> set[str]:
    """ST 代码：东财全市场名称缓存（OpenCLI enrich 前兜底）。"""
    _ = engine
    ensure_market_name_cache()
    return load_st_codes_from_names(_read_disk_name_cache())


def merge_profile_fields_into_selection_row(
    row: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(row)
    industry = profile.get("industry")
    if industry:
        merged["所属行业"] = industry
    concepts = profile.get("concepts") or []
    if concepts:
        merged["概念板块"] = concepts
        merged["概念板块文本"] = "、".join(str(c) for c in concepts)
    profile_text = profile.get("profile_text")
    if profile_text:
        merged["公司简介"] = profile_text
    if profile.get("name") and not merged.get("名称"):
        merged["名称"] = profile["name"]
    merged["档案来源"] = profile.get("source") or "eastmoney-opencli"
    return merged


def patch_selection_daily_profiles(
    trade_date: date | str,
    profiles_by_code: dict[str, dict[str, Any]],
    *,
    strategy: str = "combined",
    engine: Engine | None = None,
) -> int:
    """将档案字段写回 selection_daily_results.raw_json（按 ts_code 匹配）。"""
    engine = engine or get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法更新 selection_daily_results")
    if not profiles_by_code:
        return 0

    td = _parse_selection_trade_date(trade_date)
    strat = (strategy or "combined").strip() or "combined"
    updated = 0
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT ts_code, raw_json
                FROM selection_daily_results
                WHERE trade_date = :d AND strategy = :s
                ORDER BY rank_no
                """
            ),
            {"d": td.isoformat(), "s": strat},
        ).fetchall()
        for row in rows:
            code = str(row.ts_code).zfill(6)
            profile = profiles_by_code.get(code)
            if not profile:
                continue
            raw = row.raw_json
            if isinstance(raw, str):
                raw = json.loads(raw)
            if not isinstance(raw, dict):
                continue
            merged = merge_profile_fields_into_selection_row(raw, profile)
            conn.execute(
                text(
                    """
                    UPDATE selection_daily_results
                    SET raw_json = :raw
                    WHERE trade_date = :d AND strategy = :s AND ts_code = :code
                    """
                ),
                {
                    "raw": json.dumps(merged, ensure_ascii=False),
                    "d": td.isoformat(),
                    "s": strat,
                    "code": code,
                },
            )
            updated += 1
    return updated


def enrich_selection_profiles_for_date(
    trade_date: date | str | None = None,
    *,
    strategy: str = "combined",
    profiles_by_code: dict[str, dict[str, Any]] | None = None,
    engine: Engine | None = None,
) -> dict[str, Any]:
    """upsert stock_profile + 回写当日 selection raw_json。"""
    engine = engine or get_engine()
    td, rows = load_selection_daily_results(trade_date, strategy=strategy, engine=engine)
    if td is None or not rows:
        return {"trade_date": None, "codes": [], "upserted": 0, "patched": 0}

    if profiles_by_code is None:
        return {
            "trade_date": td.isoformat(),
            "codes": [_selection_row_code(r) for r in rows],
            "upserted": 0,
            "patched": 0,
            "error": "profiles_by_code required",
        }

    profile_rows = list(profiles_by_code.values())
    upserted = upsert_stock_profiles(profile_rows, engine=engine)
    patched = patch_selection_daily_profiles(td, profiles_by_code, strategy=strategy, engine=engine)
    return {
        "trade_date": td.isoformat(),
        "codes": sorted(profiles_by_code.keys()),
        "upserted": upserted,
        "patched": patched,
    }


def _best_ts_code_for_daily(code6: str, *, engine: Engine) -> str:
    """stock_daily 存在 6 位与 .SH/.SZ 两套 ts_code 时，取最新交易日更靠后的一套。"""
    seen: set[str] = set()
    candidates: list[str] = []
    for cand in (code6, _to_ts_code(code6)):
        if cand not in seen:
            seen.add(cand)
            candidates.append(cand)
    best = code6
    best_max: date | None = None
    with engine.connect() as conn:
        for cand in candidates:
            mx = conn.execute(
                text("SELECT MAX(trade_date) FROM stock_daily WHERE ts_code = :c"),
                {"c": cand},
            ).scalar()
            if mx is None:
                continue
            if isinstance(mx, str):
                mx_d = datetime.fromisoformat(mx[:10]).date()
            elif isinstance(mx, date):
                mx_d = mx
            else:
                mx_d = datetime.fromisoformat(str(mx)[:10]).date()
            if best_max is None or mx_d > best_max:
                best_max = mx_d
                best = cand
    return best


def load_stock_daily_bars(
    code: str,
    *,
    end_date: date | str | None = None,
    limit: int = 60,
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """MySQL stock_daily 日线 K 线（按交易日升序）。"""
    engine = engine or get_engine()
    if engine is None:
        return []

    ts = _code6(code)
    if not re.fullmatch(r"\d{6}", ts):
        return []

    n = max(5, min(int(limit), 250))
    end_d = _parse_selection_trade_date(end_date) if end_date else None
    ts_key = _best_ts_code_for_daily(ts, engine=engine)
    sql = """
        SELECT trade_date, open, high, low, close, pct_chg, vol, amount
        FROM stock_daily
        WHERE ts_code = :code
    """
    params: dict[str, Any] = {"code": ts_key, "n": n}
    if end_d is not None:
        sql += " AND trade_date <= :end"
        params["end"] = end_d.isoformat()
    sql += " ORDER BY trade_date DESC LIMIT :n"

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
    except Exception:
        return []

    bars: list[dict[str, Any]] = []
    for row in reversed(rows):
        td = row.trade_date
        if isinstance(td, date):
            td_str = td.isoformat()
        else:
            td_str = str(td)[:10]
        bars.append(
            {
                "trade_date": td_str,
                "open": float(row.open) if row.open is not None else None,
                "high": float(row.high) if row.high is not None else None,
                "low": float(row.low) if row.low is not None else None,
                "close": float(row.close) if row.close is not None else None,
                "pct_chg": float(row.pct_chg) if row.pct_chg is not None else None,
                "vol": int(row.vol) if row.vol is not None else None,
                "amount": float(row.amount) if row.amount is not None else None,
            }
        )
    return bars


def latest_stock_daily_trade_date(*, engine: Engine | None = None) -> date | None:
    """stock_daily 全市场最新交易日。"""
    engine = engine or get_engine()
    if engine is None:
        return None
    try:
        with engine.connect() as conn:
            value = conn.execute(text("SELECT MAX(trade_date) FROM stock_daily")).scalar()
    except Exception:
        return None
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:10]).date()


def resolve_selection_kline_end_date(
    selection_trade_date: date | str,
    *,
    engine: Engine | None = None,
) -> date:
    """选股 K 线截止日：至少覆盖选股日，并延伸至已同步的最新交易日。"""
    sel_d = _parse_selection_trade_date(selection_trade_date)
    latest = latest_stock_daily_trade_date(engine=engine)
    if latest is not None and latest > sel_d:
        return latest
    return sel_d


def _snapshot_date(value: date | str | None = None) -> date:
    if value is None:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Asia/Shanghai")).date()
    return _parse_selection_trade_date(value)


def save_portfolio_daily_snapshot(
    *,
    snapshot_date: date | str | None = None,
    snapshot_slot: str = "eod",
    fetch_market_prices: bool = True,
) -> dict[str, Any]:
    """写入账户 + 持仓每日快照（同日同 slot 覆盖）。"""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法写入持仓快照")

    snap = _snapshot_date(snapshot_date)
    slot = (snapshot_slot or "eod").strip() or "eod"
    positions = load_positions(engine=engine)
    account = load_account(engine=engine)
    if not positions:
        raise RuntimeError("无活跃持仓，跳过快照")

    closes: dict[str, float] = {}
    if fetch_market_prices:
        closes = load_latest_closes([p.code for p in positions], engine=engine)

    total_mv = 0.0
    total_pnl = 0.0
    pos_rows: list[dict[str, Any]] = []
    for p in positions:
        mp = closes.get(p.code)
        mv = (mp * p.shares) if mp is not None and p.shares else None
        pnl_amt = ((mp - p.cost) * p.shares) if mp is not None and p.shares else None
        pnl_pct = ((mp / p.cost - 1) * 100) if mp is not None and p.cost else None
        if mv is not None:
            total_mv += mv
        if pnl_amt is not None:
            total_pnl += pnl_amt
        pos_rows.append(
            {
                "code": p.code,
                "name": p.name,
                "shares": p.shares,
                "cost": p.cost,
                "mp": mp,
                "mv": mv,
                "pnl_amt": pnl_amt,
                "pnl_pct": pnl_pct,
                "status": p.status,
                "action": p.action,
            }
        )

    acct_total = account.total_assets if account else None
    acct_cash = account.available_cash if account else None
    acct_ratio = account.position_ratio if account else None
    acct_pnl = account.holding_pnl if account else total_pnl

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO portfolio_account_daily
                  (snapshot_date, snapshot_slot, total_assets, available_cash,
                   market_value, position_ratio, holding_pnl)
                VALUES
                  (:d, :slot, :total, :cash, :mv, :ratio, :pnl)
                ON DUPLICATE KEY UPDATE
                  total_assets = VALUES(total_assets),
                  available_cash = VALUES(available_cash),
                  market_value = VALUES(market_value),
                  position_ratio = VALUES(position_ratio),
                  holding_pnl = VALUES(holding_pnl)
                """
            ),
            {
                "d": snap.isoformat(),
                "slot": slot,
                "total": acct_total,
                "cash": acct_cash,
                "mv": total_mv if total_mv else (account.market_value if account else None),
                "ratio": acct_ratio,
                "pnl": acct_pnl,
            },
        )
        conn.execute(
            text(
                "DELETE FROM portfolio_positions_daily "
                "WHERE snapshot_date = :d AND snapshot_slot = :slot"
            ),
            {"d": snap.isoformat(), "slot": slot},
        )
        n = 0
        for row in pos_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO portfolio_positions_daily
                      (snapshot_date, snapshot_slot, ts_code, name, shares, cost_price,
                       market_price, market_value, pnl_amount, pnl_pct, status_note, action_note)
                    VALUES
                      (:d, :slot, :code, :name, :shares, :cost, :mp, :mv, :pnl, :pct, :st, :act)
                    """
                ),
                {
                    "d": snap.isoformat(),
                    "slot": slot,
                    "code": row["code"],
                    "name": row["name"],
                    "shares": row["shares"],
                    "cost": row["cost"],
                    "mp": row["mp"],
                    "mv": row["mv"],
                    "pnl": row["pnl_amt"],
                    "pct": row["pnl_pct"],
                    "st": row["status"],
                    "act": row["action"],
                },
            )
            n += 1
    return {"account": 1, "positions": n, "snapshot_date": snap.isoformat(), "slot": slot}


def save_sop_review_daily(
    trade_date: date | str,
    *,
    strategy: str = "combined",
    selection_source: str | None = None,
    generated_at: datetime | str | None = None,
    wechat_summary: str = "",
    report_path: str | None = None,
    items: list[dict[str, Any]],
) -> dict[str, int]:
    """写入 SOP 审查批次 + 逐股明细（同日同 strategy 覆盖）。"""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法写入 sop_review")

    td = _parse_selection_trade_date(trade_date)
    strat = (strategy or "combined").strip() or "combined"
    if generated_at is None:
        gen = datetime.now()
    elif isinstance(generated_at, datetime):
        gen = generated_at
    else:
        gen = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00")[:19])

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM sop_review_items WHERE trade_date = :d AND strategy = :s"),
            {"d": td.isoformat(), "s": strat},
        )
        conn.execute(
            text(
                """
                INSERT INTO sop_review_daily
                  (trade_date, strategy, selection_source, generated_at,
                   wechat_summary, report_path)
                VALUES
                  (:d, :s, :src, :gen, :wx, :rp)
                ON DUPLICATE KEY UPDATE
                  selection_source = VALUES(selection_source),
                  generated_at = VALUES(generated_at),
                  wechat_summary = VALUES(wechat_summary),
                  report_path = VALUES(report_path)
                """
            ),
            {
                "d": td.isoformat(),
                "s": strat,
                "src": selection_source,
                "gen": gen.strftime("%Y-%m-%d %H:%M:%S"),
                "wx": wechat_summary,
                "rp": report_path,
            },
        )
        n = 0
        for item in items:
            code = str(item.get("code", "")).split(".")[0].zfill(6)
            if not re.fullmatch(r"\d{6}", code):
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO sop_review_items
                      (trade_date, strategy, rank_no, ts_code, name, score, decision,
                       watch_worthy, close_price, change_pct, strategy_label, action_hint,
                       support_prices, stop_price, target_prices, in_holdings, review_md, raw_json)
                    VALUES
                      (:d, :s, :rank, :code, :name, :score, :dec, :watch, :close, :pct,
                       :label, :action, :sup, :stop, :tgt, :held, :md, :raw)
                    """
                ),
                {
                    "d": td.isoformat(),
                    "s": strat,
                    "rank": int(item.get("rank_no", n + 1)),
                    "code": code,
                    "name": str(item.get("name", code)),
                    "score": item.get("score"),
                    "dec": item.get("decision"),
                    "watch": 1 if item.get("watch_worthy") else 0,
                    "close": item.get("close_price"),
                    "pct": item.get("change_pct"),
                    "label": item.get("strategy_label"),
                    "action": item.get("action_hint"),
                    "sup": json.dumps(item.get("support") or [], ensure_ascii=False),
                    "stop": item.get("stop"),
                    "tgt": json.dumps(item.get("targets") or [], ensure_ascii=False),
                    "held": 1 if item.get("in_holdings") else 0,
                    "md": item.get("review_md"),
                    "raw": json.dumps(item.get("raw_json") or {}, ensure_ascii=False),
                },
            )
            n += 1
    return {"items": n, "trade_date": td.isoformat(), "strategy": strat}


def load_portfolio_snapshot_series(
    *,
    date_from: date | str | None = None,
    date_to: date | str | None = None,
    snapshot_slot: str = "eod",
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """看板：账户快照时间序列。"""
    engine = engine or get_engine()
    if engine is None:
        return []
    slot = (snapshot_slot or "eod").strip() or "eod"
    sql = """
        SELECT snapshot_date, snapshot_slot, total_assets, available_cash,
               market_value, position_ratio, holding_pnl, created_at
        FROM portfolio_account_daily
        WHERE snapshot_slot = :slot
    """
    params: dict[str, Any] = {"slot": slot}
    if date_from:
        sql += " AND snapshot_date >= :df"
        params["df"] = _parse_selection_trade_date(date_from).isoformat()
    if date_to:
        sql += " AND snapshot_date <= :dt"
        params["dt"] = _parse_selection_trade_date(date_to).isoformat()
    sql += " ORDER BY snapshot_date"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    return [dict(r._mapping) for r in rows]


def load_portfolio_positions_on_date(
    snapshot_date: date | str,
    *,
    snapshot_slot: str = "eod",
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    engine = engine or get_engine()
    if engine is None:
        return []
    snap = _parse_selection_trade_date(snapshot_date)
    slot = (snapshot_slot or "eod").strip() or "eod"
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT ts_code, name, shares, cost_price, market_price, market_value,
                       pnl_amount, pnl_pct, status_note, action_note
                FROM portfolio_positions_daily
                WHERE snapshot_date = :d AND snapshot_slot = :slot
                ORDER BY ts_code
                """
            ),
            {"d": snap.isoformat(), "slot": slot},
        ).fetchall()
    return [dict(r._mapping) for r in rows]


def load_sop_review_bundle(
    trade_date: date | str | None = None,
    *,
    strategy: str = "combined",
    engine: Engine | None = None,
) -> dict[str, Any] | None:
    engine = engine or get_engine()
    if engine is None:
        return None
    strat = (strategy or "combined").strip() or "combined"
    with engine.connect() as conn:
        if trade_date:
            td = _parse_selection_trade_date(trade_date)
            header = conn.execute(
                text(
                    """
                    SELECT trade_date, strategy, selection_source, generated_at,
                           wechat_summary, report_path
                    FROM sop_review_daily
                    WHERE trade_date = :d AND strategy = :s
                    """
                ),
                {"d": td.isoformat(), "s": strat},
            ).fetchone()
        else:
            header = conn.execute(
                text(
                    """
                    SELECT trade_date, strategy, selection_source, generated_at,
                           wechat_summary, report_path
                    FROM sop_review_daily
                    WHERE strategy = :s
                    ORDER BY trade_date DESC
                    LIMIT 1
                    """
                ),
                {"s": strat},
            ).fetchone()
        if not header:
            return None
        td_val = header.trade_date
        if not isinstance(td_val, date):
            td_val = datetime.fromisoformat(str(td_val)[:10]).date()
        items = conn.execute(
            text(
                """
                SELECT rank_no, ts_code, name, score, decision, watch_worthy,
                       close_price, change_pct, strategy_label, action_hint,
                       support_prices, stop_price, target_prices, in_holdings, review_md
                FROM sop_review_items
                WHERE trade_date = :d AND strategy = :s
                ORDER BY rank_no
                """
            ),
            {"d": td_val.isoformat(), "s": strat},
        ).fetchall()
    bundle = {
        "header": dict(header._mapping),
        "items": [dict(r._mapping) for r in items],
    }
    return enrich_sop_review_bundle(bundle)


def _json_list_field(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def load_sop_reviews_for_watch(
    trade_date: date | str | None = None,
    *,
    strategy: str = "combined",
) -> list[dict[str, Any]]:
    """监控/战报用 SOP 元数据：MySQL sop_review_items 优先。"""
    bundle = load_sop_review_bundle(trade_date=trade_date, strategy=strategy)
    if not bundle or not bundle.get("items"):
        return []

    reviews: list[dict[str, Any]] = []
    for item in bundle["items"]:
        code = str(item.get("ts_code", "")).split(".")[0].zfill(6)
        reviews.append(
            {
                "code": code,
                "name": item.get("name") or code,
                "score": float(item.get("score") or 0),
                "decision": item.get("decision") or "",
                "watch_worthy": bool(item.get("watch_worthy")),
                "support": _json_list_field(item.get("support_prices")),
                "stop": item.get("stop_price"),
                "targets": _json_list_field(item.get("target_prices")),
                "in_holdings": bool(item.get("in_holdings")),
            }
        )
    return reviews

