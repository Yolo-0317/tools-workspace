#!/usr/bin/env python3
"""公众号文末返佣商品：getcardinfo → footer product_key → draft product_info。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

# 加载 stock-ai/.env（与 wechat_mp_client 一致）
from scripts.tools.wechat_mp_client import mp_configured  # noqa: F401 — 触发 dotenv

ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = ROOT / "data" / "wechat_mp_footer_product.json"
DAIHUO_SELECT_URL = (
    "https://daihuo.qq.com/trpc.cps.weixin_select.WeiXinSelect/Select"
)
TZ = ZoneInfo("Asia/Shanghai")

# 金融科技读者号：后台商品库搜索关键词（官方无列表 API，仅供人工选品）
PICK_KEYWORDS = (
    ("market", "理财 基金 记账本 财经"),
    ("news", "财经 商务 办公 充电宝"),
    ("top5", "键盘 鼠标 显示器 支架"),
    ("dragons", "护眼灯 台灯 咖啡"),
    ("workspace", "机械键盘 硬盘 路由器 显示器"),
    ("temp", "机械键盘 扩展坞 硬盘 充电器"),
)
PICK_KEYWORDS_BY_KIND = dict(PICK_KEYWORDS)

# 带货垂直（wechat_mp_commerce_draft --vertical）
PICK_KEYWORDS_BY_VERTICAL: dict[str, str] = {
    "tech": "机械键盘 显示器 充电宝 路由器",
    "home": "收纳 置物架 厨房收纳 沥水篮 挂钩",
    "mother": "母婴 绘本 儿童 奶粉",
    "outdoor": "露营 防晒 户外 登山",
    "office": "工学椅 台灯 支架 鼠标垫",
    "beauty": "护肤 洗面奶 防晒 面膜",
    "guide": "好物 推荐 测评 数码",
    "review": "测评 体验 好物",
    "trend": "新品 热门 趋势 数码",
}


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def pick_strategy() -> str:
    """commission=仅佣金；sales=销量优先（默认）；balanced=先过销量门槛再比佣金。"""
    raw = _env("WECHAT_MP_PICK_STRATEGY", "sales").lower()
    if raw in ("commission", "sales", "balanced"):
        return raw
    return "sales"


def pick_min_sales() -> int:
    return max(0, _env_int("WECHAT_MP_PICK_MIN_SALES", 500))


def footer_product_enabled() -> bool:
    raw = _env("WECHAT_MP_FOOTER_PRODUCT", "0").lower()
    return raw in ("1", "true", "yes", "on")


def footer_product_id() -> str:
    return _env("WECHAT_MP_FOOTER_PRODUCT_ID")


def footer_product_card_type() -> int:
    raw = _env("WECHAT_MP_FOOTER_PRODUCT_CARD_TYPE", "1")
    try:
        val = int(raw)
    except ValueError:
        val = 1
    return val if val in (0, 1, 2, 3) else 1


def daihuo_uin() -> str:
    """流量主选品页 uin（浏览器 Network 里 Select 请求的 uin 字段）。"""
    return _env("WECHAT_MP_DAIHUO_UIN")


def footer_product_kinds() -> set[str] | None:
    raw = _env("WECHAT_MP_FOOTER_PRODUCT_KINDS")
    if not raw:
        return None
    kinds = {k.strip().lower() for k in raw.split(",") if k.strip()}
    return kinds or None


def footer_product_auto_pick() -> bool:
    """推稿前是否自动 Select 选品（默认随 FOOTER_PRODUCT 开启；策略见 pick_strategy）。"""
    raw = _env("WECHAT_MP_FOOTER_PRODUCT_AUTO_PICK", "")
    if raw:
        return raw.lower() in ("1", "true", "yes", "on")
    return footer_product_enabled()


def pick_keywords_for_kind(kind: str | None) -> list[str]:
    """槽位选品搜索词；WECHAT_MP_FOOTER_PICK_KEYWORD 覆盖全部槽位。"""
    override = _env("WECHAT_MP_FOOTER_PICK_KEYWORD")
    if override:
        return [w for w in override.split() if w.strip()]
    if kind:
        k = kind.strip().lower()
        mapped = PICK_KEYWORDS_BY_KIND.get(k, "") or PICK_KEYWORDS_BY_VERTICAL.get(k, "")
        if mapped:
            return [w for w in mapped.split() if w.strip()]
    fallback = _env("WECHAT_MP_FOOTER_PICK_KEYWORD_DEFAULT", "充电宝")
    return [w for w in fallback.split() if w.strip()] or ["充电宝"]


def _load_cache() -> dict[str, Any]:
    if not CACHE_PATH.is_file():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(payload: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_footer_product_key(
    product_id: str,
    *,
    card_type: int | None = None,
    force_refresh: bool = False,
    daihuo_meta: dict[str, Any] | None = None,
) -> tuple[str | None, dict[str, Any] | None]:
    """调用 getcardinfo 获取 footer 所需的 product_key（带本地缓存）。"""
    pid = str(product_id or "").strip()
    if not pid:
        return None, {"errcode": -1, "errmsg": "product_id 为空"}

    ct = footer_product_card_type() if card_type is None else card_type
    cache = _load_cache()
    cached = cache.get("footer") or {}
    if (
        not force_refresh
        and cached.get("product_id") == pid
        and cached.get("card_type") == ct
        and cached.get("product_key")
    ):
        return str(cached["product_key"]), None

    from scripts.tools.wechat_mp_client import get_product_card_info

    meta = daihuo_meta or (cache.get("daihuo") or {})
    attempts: list[dict[str, Any]] = [{"product_id": pid}]
    sku = str(meta.get("sku_id") or "").strip()
    if sku:
        attempts.append({"product_id": pid, "sku_id": sku})
    wh = str(meta.get("warehouse_id") or "").strip()
    src = meta.get("source")
    if wh and src is not None:
        attempts.append(
            {
                "product_id": pid,
                "warehouse_id": wh,
                "source": src,
                "sku_id": sku,
            }
        )
    uin = daihuo_uin()
    if uin:
        for base in attempts:
            extra = {k: v for k, v in base.items() if k != "product_id"}
            data, err = get_product_card_info(
                product_id=str(base["product_id"]),
                article_type="news",
                card_type=ct,
                extra=extra or None,
            )
            if not err and data.get("product_key"):
                key = str(data["product_key"]).strip()
                cache["footer"] = {
                    "product_id": pid,
                    "card_type": ct,
                    "product_key": key,
                    "updated_at": datetime.now(TZ).isoformat(timespec="seconds"),
                }
                _save_cache(cache)
                return key, None

    data, err = get_product_card_info(
        product_id=pid,
        article_type="news",
        card_type=ct,
    )
    if err:
        return None, err
    key = str(data.get("product_key") or "").strip()
    if not key:
        return None, {
            "errcode": -2,
            "errmsg": "getcardinfo 未返回 product_key（CPS 商品需在后台插入一次或配置 WECHAT_MP_DAIHUO_COOKIE）",
            "response": data,
        }

    cache["footer"] = {
        "product_id": pid,
        "card_type": ct,
        "product_key": key,
        "updated_at": datetime.now(TZ).isoformat(timespec="seconds"),
    }
    _save_cache(cache)
    return key, None


_DISCLAIMER_MARKS = (
    "本文为作者个人投资日记",
    "本文为作者个人工程笔记",
    "部分链接含推广合作",
    "含推广链接",
)
_CPSAD_RE = re.compile(
    r'<mp-common-cpsad[^>]*data-pid=["\']([^"\']+)["\']',
    re.I,
)


def cps_data_pid(
    product_id: str,
    *,
    warehouse_id: str = "101",
    daihuo_meta: dict[str, Any] | None = None,
) -> str:
    """返佣 CPS 商品在正文中的 pid（warehouse_product，非 getcardinfo product_key）。"""
    pid = str(product_id or "").strip()
    meta = daihuo_meta or (_load_cache().get("daihuo") or {})
    if str(meta.get("product_id") or "").strip() == pid:
        sku = str(meta.get("sku_id") or "").strip()
        if sku:
            return sku
        wh = str(meta.get("warehouse_id") or warehouse_id).strip()
        return f"{wh}_{pid}"
    return f"{warehouse_id}_{pid}"


def build_cpsad_html(data_pid: str, *, template_id: str = "list") -> str:
    trace = str(uuid.uuid4())
    return (
        '<section nodeleaf="">'
        f'<mp-common-cpsad data-pluginname="mpcps" data-templateid="{template_id}" '
        f'data-cpsversion="v122" data-goodssouce="1" data-traceid="{trace}" '
        f'data-pid="{data_pid}"></mp-common-cpsad>'
        "</section>"
    )


_DISCLAIMER_BOX_BG = "#fff5f5"
_CPS_BODY_RATIO = 2 / 3
_BLOCK_END_RE = re.compile(r"</(?:p|section)>", re.I)


def _body_end_before_disclaimer(content: str) -> int:
    """正文区结束下标（不含免责框及其后）。"""
    if _DISCLAIMER_BOX_BG in content:
        idx = content.index(_DISCLAIMER_BOX_BG)
        p_start = content.rfind("<p", 0, idx)
        if p_start >= 0:
            return p_start
        return idx
    for mark in _DISCLAIMER_MARKS:
        if mark not in content:
            continue
        idx = content.index(mark)
        p_start = content.rfind("<p", 0, idx)
        if p_start >= 0:
            return p_start
        return idx
    return len(content)


def cps_injection_index(content: str, *, ratio: float = _CPS_BODY_RATIO) -> int:
    """在正文约 `ratio` 处对齐到段/块尾，返回 CPS 插入下标。"""
    body_end = _body_end_before_disclaimer(content)
    body = content[:body_end]
    if not body.strip():
        return body_end
    boundaries = [m.end() for m in _BLOCK_END_RE.finditer(body)]
    if not boundaries:
        return body_end
    target = int(len(body) * ratio)
    for pos in boundaries:
        if pos >= target:
            return pos
    return boundaries[-1]


def inject_cpsad_at_body_ratio(
    content: str,
    data_pid: str,
    *,
    ratio: float = _CPS_BODY_RATIO,
) -> str:
    """返佣卡插在正文约 2/3 处（段尾对齐，避开免责框）。"""
    tag = build_cpsad_html(data_pid)
    if _CPSAD_RE.search(content):
        return content
    pos = cps_injection_index(content, ratio=ratio)
    return content[:pos] + tag + content[pos:]


def inject_cpsad_for_kind(
    content: str,
    data_pid: str,
    *,
    kind: str | None = None,
) -> str:
    """各槽位统一：正文约 2/3 处插入 CPS（`kind` 保留兼容，不参与定位）。"""
    _ = kind
    return inject_cpsad_at_body_ratio(content, data_pid)


# 兼容旧名
inject_cpsad_after_first_section = inject_cpsad_for_kind


def inject_cpsad_before_disclaimer(content: str, data_pid: str) -> str:
    tag = build_cpsad_html(data_pid)
    if _CPSAD_RE.search(content):
        return content
    for mark in _DISCLAIMER_MARKS:
        if mark not in content:
            continue
        idx = content.index(mark)
        # 免责声明已转成 HTML 时，勿插进 <p> 中间（会破坏版式）
        p_start = content.rfind("<p", 0, idx)
        if p_start >= 0:
            p_end = content.find("</p>", idx)
            if p_end >= 0 and p_start < idx < p_end:
                return content[:p_start] + tag + content[p_start:]
        return content[:idx] + tag + content[idx:]
    return content.rstrip() + tag


def _commission_rate_bp(raw: dict[str, Any]) -> int:
    """统一为万分比（1620 → 16.20%）。"""
    basic = raw.get("basic_info") or {}
    rate = basic.get("commission_rate", raw.get("commission_rate"))
    if rate is None:
        return 0
    if isinstance(rate, float):
        if 0 < rate <= 1:
            return int(round(rate * 10000))
        return int(rate)
    r = int(rate)
    if r > 100:
        return r
    if 0 < r <= 100:
        return r * 100
    return r


def extract_sales_count(raw: dict[str, Any]) -> int:
    """Select 返回的销量提示：sales_tips 或 sale.* 字段。"""
    tips = raw.get("sales_tips")
    if tips is not None:
        try:
            v = int(tips)
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass
    sale = raw.get("sale")
    if not isinstance(sale, dict):
        sale = (raw.get("basic_info") or {}).get("sale")
    if isinstance(sale, dict):
        total = 0
        for key in ("sales_on_source", "sales_on_ams", "sales_on_flow", "sales_of_kol"):
            try:
                total += int(str(sale.get(key) or "0").strip() or "0")
            except ValueError:
                continue
        if total > 0:
            return total
    return 0


def _score_daihuo_raw(raw: dict[str, Any]) -> tuple[int, ...]:
    sales = extract_sales_count(raw)
    rate = _commission_rate_bp(raw)
    basic = raw.get("basic_info") or {}
    comm = int(raw.get("commission") or basic.get("commission") or 0)
    strategy = pick_strategy()
    if strategy == "commission":
        return (rate, comm, sales)
    if strategy == "balanced":
        return (1 if sales >= pick_min_sales() else 0, sales, rate, comm)
    return (sales, rate, comm)


def auto_pick_footer_product(*, kind: str | None = None) -> dict[str, Any] | None:
    """Select 搜多词按策略选 1 款（默认销量优先），写入缓存并更新 FOOTER_PRODUCT_ID。"""
    if not footer_product_auto_pick() or not footer_product_enabled():
        return None
    if not daihuo_uin():
        print("⚠️ auto-pick 跳过: 未配置 WECHAT_MP_DAIHUO_UIN", file=sys.stderr)
        return None
    kinds = footer_product_kinds()
    if kinds and kind and kind.strip().lower() not in kinds:
        return None
    keywords = pick_keywords_for_kind(kind)
    try:
        summary, raw = pick_best_daihuo_product(keywords=keywords)
    except Exception as exc:
        print(f"⚠️ auto-pick 失败 ({kind or 'all'}): {exc}，沿用 FOOTER_PRODUCT_ID/缓存", file=sys.stderr)
        return None
    save_picked_product(summary, raw)
    os.environ["WECHAT_MP_FOOTER_PRODUCT_ID"] = str(summary["product_id"])
    rate = summary.get("commission_rate_bp")
    rate_txt = f"{int(rate) / 100:.2f}%" if isinstance(rate, (int, float)) else "?"
    sales = summary.get("sales_count", 0)
    print(
        f"auto-pick [{kind or 'all'}]: {str(summary.get('product_name') or '')[:40]} "
        f"销量≈{sales} 佣¥{summary.get('commission_yuan', 0):.2f}({rate_txt}) "
        f"策略={pick_strategy()} id={summary.get('product_id')} kw={','.join(keywords)}",
        file=sys.stderr,
    )
    return summary


def attach_footer_product(article: dict[str, Any], *, kind: str | None = None) -> dict[str, Any]:
    """文末返佣商品：优先 CPS `<mp-common-cpsad data-pid>`，其次 footer product_key。"""
    if not footer_product_enabled():
        return article
    kinds = footer_product_kinds()
    if kinds and kind and kind.strip().lower() not in kinds:
        return article

    auto_pick_footer_product(kind=kind)
    pid = footer_product_id()
    if not pid:
        pid = str((_load_cache().get("daihuo") or {}).get("product_id") or "")
    if not pid:
        return article

    cache = _load_cache()
    meta = cache.get("daihuo") or {}
    data_pid = cps_data_pid(pid, daihuo_meta=meta)
    out = dict(article)
    out["content"] = inject_cpsad_for_kind(
        str(out.get("content") or ""),
        data_pid,
        kind=kind,
    )
    name = str(meta.get("product_name") or "")[:40]
    print(f"文末返佣(CPS): {name or data_pid} data-pid={data_pid}", file=sys.stderr)

    key, err = resolve_footer_product_key(pid, daihuo_meta=meta)
    if key and not err:
        out["product_info"] = {"footer_product_info": {"product_key": key}}
    return out


def draft_article_payload(article: dict[str, Any]) -> dict[str, Any]:
    """去掉 draft API 不需要的本地字段。"""
    from scripts.tools.wechat_mp_content import content_source_url_enabled

    item = dict(article)
    item.pop("body_text", None)
    if not content_source_url_enabled():
        item.pop("content_source_url", None)
    return item


def search_daihuo_products(
    keyword: str,
    *,
    page_no: int = 1,
    page_size: int = 30,
    uin: str | None = None,
    scene: int = 2,
) -> tuple[list[dict[str, Any]], int, dict[str, Any] | None]:
    """
    模拟 mp 编辑器「返佣商品库」搜索（daihuo.qq.com Select）。
    无需 Cookie，但需 WECHAT_MP_DAIHUO_UIN。
    """
    import requests

    u = (uin or daihuo_uin()).strip()
    if not u:
        return [], 0, {"errcode": -1, "errmsg": "未配置 WECHAT_MP_DAIHUO_UIN"}

    body = {
        "uin": u,
        "page": {"no": max(1, page_no), "size": max(1, min(page_size, 30))},
        "scene": scene,
        "product_query": {
            "keyword": keyword.strip(),
            "article_template": False,
            "search_type": 0,
        },
    }
    headers = {
        "content-type": "application/json",
        "Referer": "https://file.daihuo.qq.com/",
        "Origin": "https://file.daihuo.qq.com",
    }
    session = requests.Session()
    session.trust_env = False
    try:
        resp = session.post(DAIHUO_SELECT_URL, json=body, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return [], 0, {"errcode": -2, "errmsg": str(exc)}

    if int(data.get("ret") or 0) != 0:
        return [], 0, {
            "errcode": data.get("ret"),
            "errmsg": data.get("msg") or data.get("errmsg") or "Select 失败",
        }
    items = list(data.get("list") or [])
    total = int(data.get("total_count") or len(items))
    return items, total, None


def summarize_daihuo_product(raw: dict[str, Any]) -> dict[str, Any]:
    """整理 Select 条目为可读摘要。"""
    basic = raw.get("basic_info") or {}
    price_fen = int(raw.get("current_price") or basic.get("current_price") or 0)
    comm_fen = int(raw.get("commission") or basic.get("commission") or 0)
    rate_bp = _commission_rate_bp(raw)
    return {
        "product_id": str(raw.get("product_id") or ""),
        "warehouse_id": str(raw.get("warehouse_id") or ""),
        "source": raw.get("source"),
        "source_name": raw.get("source_name") or "",
        "product_name": str(raw.get("product_name") or "")[:80],
        "shop_name": raw.get("shop_name") or "",
        "price_yuan": round(price_fen / 100, 2),
        "commission_yuan": round(comm_fen / 100, 2),
        "commission_rate_bp": rate_bp,
        "sales_count": extract_sales_count(raw),
        "category": raw.get("third_category_name") or raw.get("second_category_name") or "",
    }


def print_daihuo_search_results(
    items: list[dict[str, Any]],
    *,
    total: int,
    verify_cards: bool = False,
) -> None:
    print(f"共 {total} 条，本页 {len(items)} 条")
    for idx, raw in enumerate(items, 1):
        row = summarize_daihuo_product(raw)
        rate = row["commission_rate_bp"]
        rate_txt = f"{rate/100:.2f}%" if isinstance(rate, (int, float)) else "?"
        sales = row.get("sales_count", 0)
        card_ok = ""
        if verify_cards and row["product_id"]:
            from scripts.tools.wechat_mp_client import get_product_card_info

            _, err = get_product_card_info(
                product_id=row["product_id"],
                article_type="news",
                card_type=footer_product_card_type(),
            )
            card_ok = " draft=OK" if not err else " draft=NO"
        print(
            f"{idx:2d}. id={row['product_id']} ¥{row['price_yuan']:.0f} "
            f"销量≈{sales} 佣¥{row['commission_yuan']:.2f}({rate_txt}) "
            f"{row['source_name']}/{row['category']}{card_ok}\n"
            f"    {row['product_name']}"
        )
    if items and not verify_cards:
        print(
            "\n提示：Select 的 product_id 未必等于 draft getcardinfo 的 id；"
            "用 --verify-cards 探测，或后台插入后 --extract。"
        )


def pick_best_daihuo_product(
    *,
    keyword: str = "充电宝",
    keywords: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """从 Select 结果里选 1 款（默认销量优先，同销量再比佣金）。"""
    terms = keywords if keywords is not None else [keyword]
    seen: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    for term in terms:
        items, _total, err = search_daihuo_products(term, page_size=30)
        if err:
            errors.append(err)
            continue
        for raw in items:
            pid = str(raw.get("product_id") or "").strip()
            if pid and pid not in seen:
                seen[pid] = raw
    if not seen:
        if errors:
            raise RuntimeError(errors[0].get("errmsg") or errors[0])
        raise RuntimeError(f"Select 无结果: {terms!r}")

    pool = list(seen.values())
    strategy = pick_strategy()
    min_sales = pick_min_sales()
    if strategy in {"sales", "balanced"} and min_sales > 0:
        qualified = [r for r in pool if extract_sales_count(r) >= min_sales]
        if qualified:
            pool = qualified
        elif strategy == "balanced":
            print(
                f"⚠️ auto-pick: 无商品销量≥{min_sales}，回退为销量最高款",
                file=sys.stderr,
            )
            pool = sorted(pool, key=extract_sales_count, reverse=True)[:5]

    best_raw = max(pool, key=_score_daihuo_raw)
    return summarize_daihuo_product(best_raw), best_raw


def save_picked_product(summary: dict[str, Any], raw: dict[str, Any]) -> None:
    cache = _load_cache()
    cache["daihuo"] = {
        "product_id": summary.get("product_id"),
        "warehouse_id": summary.get("warehouse_id"),
        "source": summary.get("source"),
        "sku_id": raw.get("sku_id"),
        "product_name": summary.get("product_name"),
        "price_yuan": summary.get("price_yuan"),
        "commission_yuan": summary.get("commission_yuan"),
        "sales_count": summary.get("sales_count"),
        "pick_strategy": pick_strategy(),
        "picked_at": datetime.now(TZ).isoformat(timespec="seconds"),
    }
    _save_cache(cache)


def push_draft_with_footer(*, kind: str = "workspace") -> int:
    """推指定槽位草稿（需 WECHAT_MP_FOOTER_PRODUCT=1 与 product_id）。"""
    import subprocess

    cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "scripts.tools.wechat_mp_draft",
        "--kind",
        kind,
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), check=False)
    return int(proc.returncode)


def extract_product_keys_from_drafts() -> list[dict[str, Any]]:
    """从草稿箱扫描已手动插入的商品，反查 product_id / product_key。"""
    from scripts.tools.wechat_mp_client import _mp_post_json, get_access_token, API_BASE

    token, err = get_access_token()
    if err:
        raise RuntimeError(f"token 失败: {err}")

    found: list[dict[str, Any]] = []
    offset = 0
    while offset < 100:
        data = _mp_post_json(
            f"{API_BASE}/draft/batchget",
            params={"access_token": token},
            payload={"offset": offset, "count": 20, "no_content": 0},
        )
        if data.get("errcode"):
            raise RuntimeError(data)
        items = data.get("item") or []
        if not items:
            break
        for it in items:
            content = it.get("content") or {}
            for news in content.get("news_item") or []:
                title = str(news.get("title") or "")
                pi = news.get("product_info") or {}
                footer = pi.get("footer_product_info") or {}
                if footer.get("product_key"):
                    found.append(
                        {
                            "title": title,
                            "product_key": footer.get("product_key"),
                            "media_id": it.get("media_id"),
                        }
                    )
                html = str(news.get("content") or "")
                for m in _CPSAD_RE.finditer(html):
                    data_pid = m.group(1)
                    parts = data_pid.split("_", 1)
                    row: dict[str, Any] = {
                        "title": title,
                        "data_pid": data_pid,
                        "media_id": it.get("media_id"),
                        "source": "mp-common-cpsad",
                    }
                    if len(parts) == 2:
                        row["warehouse_id"] = parts[0]
                        row["product_id"] = parts[1]
                    found.append(row)
                for m in re.finditer(r'data-product-id=["\']?(\d+)', html):
                    found.append(
                        {
                            "title": title,
                            "product_id": m.group(1),
                            "media_id": it.get("media_id"),
                            "source": "content_html",
                        }
                    )
        offset += len(items)
        if len(items) < 20:
            break
    return found


def print_pick_recommendations() -> None:
    print("=== 返佣商品选品建议（金融 + 科技读者） ===")
    print()
    print("可用 daihuo Select 搜索：uv run python -m scripts.tools.wechat_mp_product --search 机械键盘")
    print("（需 WECHAT_MP_DAIHUO_UIN；Select id 与 draft getcardinfo 可能不一致，见 --verify-cards）")
    print()
    print("或后台人工选 1 款 → --extract / --verify。")
    print()
    print("后台路径：mp.weixin.qq.com → 素材管理/新建图文 → 工具栏「商品」→ 返佣商品库")
    print(
        "建议：auto-pick 默认 WECHAT_MP_PICK_STRATEGY=sales（销量优先，见 sales_tips）；"
        "balanced=先过 WECHAT_MP_PICK_MIN_SALES 再比佣金；commission=仅佣金（旧逻辑）。"
    )
    print("优先选与正文弱相关、合规的泛科技/办公类；高佣低销转化差。")
    print()
    for kind, keywords in PICK_KEYWORDS:
        print(f"  · {kind:9s} 搜索关键词：{keywords}")
    print()
    print("选好后：")
    print("  1) 若界面能看到商品 ID → WECHAT_MP_FOOTER_PRODUCT_ID=…")
    print("  2) 或先插入文末保存草稿 → uv run python -m scripts.tools.wechat_mp_product --extract")
    print("  3) 验证：uv run python -m scripts.tools.wechat_mp_product --verify <product_id>")
    print("  4) 启用：WECHAT_MP_FOOTER_PRODUCT=1")


def main() -> int:
    parser = argparse.ArgumentParser(description="公众号文末返佣商品：验证 / 反查 / 选品建议")
    parser.add_argument("--recommend", action="store_true", help="输出选品关键词与操作流程")
    parser.add_argument("--verify", metavar="PRODUCT_ID", help="验证 product_id 并缓存 product_key")
    parser.add_argument("--extract", action="store_true", help="从草稿箱反查已插入的商品")
    parser.add_argument("--search", metavar="KEYWORD", help="daihuo 返佣商品库搜索（模拟编辑器 Select）")
    parser.add_argument("--page", type=int, default=1, help="--search 页码")
    parser.add_argument("--size", type=int, default=10, help="--search 每页条数（最大 30）")
    parser.add_argument(
        "--verify-cards",
        action="store_true",
        help="--search 时对每条尝试 getcardinfo（较慢）",
    )
    parser.add_argument(
        "--pick",
        action="store_true",
        help="Select 选 1 款商品并写入 data/wechat_mp_footer_product.json（策略见 WECHAT_MP_PICK_STRATEGY）",
    )
    parser.add_argument("--pick-keyword", default="充电宝", help="--pick 搜索词")
    parser.add_argument(
        "--push",
        metavar="KIND",
        default="",
        help="推草稿槽位（如 workspace）；配合 --pick 或已配置 FOOTER_PRODUCT",
    )
    parser.add_argument("--card-type", type=int, default=None, help="getcardinfo card_type，默认读 env")
    args = parser.parse_args()

    if args.recommend:
        print_pick_recommendations()
        return 0

    if args.verify:
        key, err = resolve_footer_product_key(
            args.verify,
            card_type=args.card_type,
            force_refresh=True,
        )
        if err:
            print(f"❌ {err.get('errmsg')} (errcode={err.get('errcode')})", file=sys.stderr)
            return 1
        print(f"OK product_id={args.verify} product_key={key}")
        print(f"已写入 {CACHE_PATH}")
        print("启用：WECHAT_MP_FOOTER_PRODUCT=1 WECHAT_MP_FOOTER_PRODUCT_ID=" + args.verify)
        return 0

    if args.search:
        items, total, err = search_daihuo_products(
            args.search,
            page_no=args.page,
            page_size=args.size,
        )
        if err:
            print(f"❌ {err.get('errmsg')} (errcode={err.get('errcode')})", file=sys.stderr)
            return 1
        print_daihuo_search_results(items, total=total, verify_cards=args.verify_cards)
        return 0

    if args.pick:
        if not daihuo_uin():
            print("❌ 请配置 WECHAT_MP_DAIHUO_UIN", file=sys.stderr)
            return 1
        try:
            kw = [w for w in args.pick_keyword.split() if w.strip()] or ["充电宝"]
            summary, raw = pick_best_daihuo_product(keywords=kw)
            save_picked_product(summary, raw)
        except Exception as exc:
            print(f"❌ {exc}", file=sys.stderr)
            return 1
        os.environ["WECHAT_MP_FOOTER_PRODUCT_ID"] = str(summary["product_id"])
        os.environ.setdefault("WECHAT_MP_FOOTER_PRODUCT", "1")
        key, err = resolve_footer_product_key(
            str(summary["product_id"]),
            force_refresh=True,
            daihuo_meta=raw,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"\n已写入 {CACHE_PATH}")
        if key:
            print(f"OK product_key={key}")
        else:
            msg = (err or {}).get("errmsg") or "无 product_key"
            print(f"⚠️ {msg}", file=sys.stderr)
            print(
                "下一步：后台把同款商品插入文末保存草稿 → "
                "uv run python -m scripts.tools.wechat_mp_product --extract",
                file=sys.stderr,
            )
        if args.push:
            return push_draft_with_footer(kind=args.push)
        print("\n.env 建议：")
        print(f"WECHAT_MP_DAIHUO_UIN={daihuo_uin()}")
        print(f"WECHAT_MP_FOOTER_PRODUCT=1")
        print(f"WECHAT_MP_FOOTER_PRODUCT_ID={summary['product_id']}")
        return 0 if key else 2

    if args.push:
        os.environ.setdefault("WECHAT_MP_FOOTER_PRODUCT", "1")
        return push_draft_with_footer(kind=args.push)

    if args.extract:
        try:
            rows = extract_product_keys_from_drafts()
        except Exception as exc:
            print(f"❌ {exc}", file=sys.stderr)
            return 1
        if not rows:
            print("草稿箱中未发现商品。请先在后台插入 1 个返佣商品并保存草稿，再重试。")
            return 1
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
        cps = next((r for r in rows if r.get("data_pid")), None)
        if cps:
            cache = _load_cache()
            cache["daihuo"] = {
                **(cache.get("daihuo") or {}),
                "sku_id": cps["data_pid"],
                "product_id": cps.get("product_id"),
                "warehouse_id": cps.get("warehouse_id"),
                "extracted_from": cps.get("title"),
            }
            _save_cache(cache)
            print(f"\n已缓存 data-pid={cps['data_pid']} → {CACHE_PATH}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
