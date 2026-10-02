"""公众号手动返佣单品稿的只读选品与结构化交接。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from scripts.tools.wechat_mp_product import (
    search_daihuo_products,
    summarize_daihuo_product,
)
from scripts.tools.wechat_mp_hotspot_quality_gate import scan_hotspot_public_copy
from scripts.tools.wechat_mp_seo import DIGEST_MAX

SearchFn = Callable[..., tuple[list[dict[str, Any]], int, dict[str, Any] | None]]
DEFAULT_KEYWORDS = (
    "零食", "休闲零食", "早餐面包", "家居日用", "洗洁精", "纸巾", "垃圾袋", "收纳用品",
)
MIN_SALES = 1000
_TARGET_CATEGORY_RE = re.compile(
    r"零食|面包|蛋糕|糕点|饼干|坚果|糖果|巧克力|膨化|蜜饯|果干|肉干|肉脯|"
    r"抽纸|卷纸|纸巾|湿巾|垃圾袋|保鲜袋|密封袋|洗洁精|洗衣液|洗衣粉|香皂|"
    r"牙刷|牙膏|收纳|抹布|清洁剂|清洁用品|厨房清洁|日用百货"
)
_SMALL_APPLIANCE_RE = re.compile(
    r"空气炸锅|电饭煲|电吹风|吹风机|榨汁机|破壁机|微波炉|电烤箱|烤箱|电水壶|"
    r"咖啡机|吸尘器|扫地机器人|电动剃须刀|加湿器|除湿机|挂烫机|料理机"
)
_EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")
_CPS_PID_RE = re.compile(r'<mp-common-cpsad\b[^>]*\bdata-pid=["\']([^"\']+)["\']', re.I)
_AD_LABEL_HTML = (
    '<p style="font-size:14px;color:#666;line-height:1.6">'
    '<strong>广告</strong>　封面为场景示意图。'
    '</p>'
)


def _rejection_reason(item: dict[str, Any]) -> str:
    if not item.get("product_id") or not item.get("product_name"):
        return "商品身份不完整"
    if _SMALL_APPLIANCE_RE.search(f"{item.get('category') or ''} {item['product_name']}"):
        return "小家电不在本次探索范围"
    if not _TARGET_CATEGORY_RE.search(str(item.get("category") or "")):
        return "品类不在零食或日用小百货范围"
    price = float(item.get("price_yuan") or 0)
    commission = float(item.get("commission_yuan") or 0)
    if price <= 0 or commission <= 0:
        return "报价或预计佣金缺失"
    if int(item.get("sales_count") or 0) < MIN_SALES:
        return "销量提示不足"
    rate_bp = int(item.get("commission_rate_bp") or 0)
    if rate_bp <= 0:
        return "佣金比例缺失"
    implied = price * rate_bp / 10000
    if abs(implied - commission) > 1 and abs(implied - commission) > commission * 0.2:
        return "佣金金额与比例矛盾"
    return ""


def prepare_product_feature_request(
    *,
    keywords: tuple[str, ...] = DEFAULT_KEYWORDS,
    search_fn: SearchFn = search_daihuo_products,
) -> dict[str, Any]:
    """读取 Select 前两页，返回供人工核对的候选，不更新选品缓存。"""
    if not keywords:
        raise ValueError("至少提供一个需求关键词")
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    queries: list[dict[str, Any]] = []
    for keyword in keywords:
        term = keyword.strip()
        if not term:
            continue
        for page_no in (1, 2):
            rows, total, err = search_fn(term, page_no=page_no, page_size=30)
            if err:
                raise RuntimeError(f"返佣商品搜索失败 [{term} 第{page_no}页]: {err.get('errmsg') or err}")
            queries.append({"keyword": term, "page_no": page_no, "returned": len(rows), "total": total})
            for raw in rows:
                item = summarize_daihuo_product(raw)
                item["sku_id"] = str(raw.get("sku_id") or "")
                item["search_keyword"] = term
                sale = (raw.get("basic_info") or {}).get("sale") or raw.get("sale") or {}
                item["sales_on_flow"] = int(sale.get("sales_on_flow") or 0)
                item["sales_on_source"] = int(sale.get("sales_on_source") or 0)
                key = (item["source_name"], item["product_id"])
                if key not in seen:
                    seen[key] = item
    qualified: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in seen.values():
        reason = _rejection_reason(item)
        if reason:
            rejected.append({**item, "reason": reason})
        else:
            qualified.append(item)
    if not qualified:
        raise ValueError("没有符合销量、佣金与资料门槛的合格候选")
    qualified.sort(
        key=lambda item: (int(item["sales_count"]), float(item["commission_yuan"])),
        reverse=True,
    )
    lane_leaders: list[dict[str, Any]] = []
    lanes_seen: set[str] = set()
    for item in qualified:
        lane = item["search_keyword"]
        if lane not in lanes_seen:
            lane_leaders.append(item)
            lanes_seen.add(lane)
    return {
        "request_type": "product_feature",
        "slot_key": "product_feature",
        "queried_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "sales_basis": "sampled_select_sales_hint",
        "flow_sales_positive_count": sum(1 for item in qualified if item["sales_on_flow"] > 0),
        "ranking_limit": "Select 关键词采样，不代表公众号流量主全站畅销榜；销量是 Select 提示，常来自来源平台，跨来源可能不同口径",
        "queries": queries,
        "candidates": qualified[:10],
        "lane_leaders": lane_leaders,
        "rejected_candidates": rejected,
        "instructions": {
            "writer": "current_codex",
            "select_one": True,
            "article": "对一件零食或日用小百货候选准备三种文案角度，再选一版从具体需求切入、用可核实事实明确推荐",
            "research": "商品参数、价格和售后从品牌官网、官方店或当前销售平台商品页核对",
            "disclosure": "商品卡前单独标明广告；不编造亲测、公众号销量或成交效果",
        },
    }


@dataclass(frozen=True)
class ProductFeatureDraft:
    product_id: str
    search_keyword: str
    warehouse_id: str
    source_name: str
    product_name: str
    price_yuan: float
    commission_yuan: float
    queried_at: str
    title: str
    digest: str
    body: str
    reader_need: str
    alternative: str
    not_for: str
    source_urls: tuple[str, ...]
    fact_checks: tuple[tuple[str, str], ...]
    cover_asset_path: Path | None
    editorial_review: dict[str, Any]
    copy_variants: tuple[dict[str, str], ...]


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"返佣单品稿字段 {key} 必须是非空文本")
    return value.strip()


def load_product_feature_draft_data(data: dict[str, Any]) -> ProductFeatureDraft:
    if not isinstance(data, dict):
        raise ValueError("返佣单品稿必须是 JSON 对象")
    texts = {key: _required_text(data, key) for key in (
        "product_id", "search_keyword", "warehouse_id", "source_name", "product_name", "queried_at",
        "title", "digest", "body", "reader_need", "alternative", "not_for",
    )}
    if len(texts["title"]) > 32:
        raise ValueError("返佣单品稿标题最多 32 字")
    if len(texts["digest"].encode("utf-8")) > DIGEST_MAX:
        raise ValueError(f"返佣单品稿摘要最多 {DIGEST_MAX} 字节")
    if re.search(r"本文含广告推广|下方是一张返佣商品卡|返佣商品卡|购买可能使本号获得佣金", texts["body"]):
        raise ValueError("正文包含编辑口吻的广告说明；广告标识由商品入口单独生成")
    if texts["alternative"] not in texts["body"] or texts["not_for"] not in texts["body"]:
        raise ValueError("正文须说明替代办法和不适合的人群")
    if _EMOJI_RE.search("\n".join((texts["title"], texts["digest"], texts["body"]))):
        raise ValueError("返佣单品稿不得包含 emoji")
    if re.search(r"亲测|我实测|我买了|我用了|本人试用", texts["body"]):
        raise ValueError("未经证明的亲测表述不得进入返佣单品稿")
    if "<mp-common-cpsad" in texts["body"]:
        raise ValueError("正文不得自行插入返佣卡")
    urls = data.get("source_urls")
    if not isinstance(urls, list) or not urls or any(
        not isinstance(url, str) or not url.startswith("https://") for url in urls
    ):
        raise ValueError("商品事实必须有 HTTPS 来源链接")
    findings = scan_hotspot_public_copy(
        title=texts["title"], digest=texts["digest"], body=texts["body"], research_urls=urls,
    )
    if findings:
        details = "；".join(f"{item.code}: {item.excerpt}" for item in findings)
        raise ValueError(f"返佣单品稿公开文案未通过门禁：{details}")
    review = data.get("editorial_review")
    if not isinstance(review, dict):
        raise ValueError("返佣单品稿缺少编辑审校记录")
    for key in ("target_reader", "reader_question", "core_judgment", "body_anchor"):
        _required_text(review, key)
    if len(review["core_judgment"]) < 20:
        raise ValueError("编辑审校的核心判断须具体完整")
    if review["body_anchor"] not in texts["body"]:
        raise ValueError("编辑审校的正文锚点没有出现在正文中")
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", texts["body"]) if part.strip()]
    roles = review.get("paragraph_roles")
    if len(paragraphs) < 4 or not isinstance(roles, list) or len(roles) != len(paragraphs) or any(
        not isinstance(role, str) or not role.strip() for role in roles
    ):
        raise ValueError("编辑审校须逐段说明信息或判断增量")
    variants = data.get("copy_variants")
    if not isinstance(variants, list) or len(variants) < 3:
        raise ValueError("返佣试验稿至少准备三种文案角度")
    clean_variants: list[dict[str, str]] = []
    for variant in variants:
        if not isinstance(variant, dict):
            raise ValueError("文案角度必须是对象")
        clean_variants.append({key: _required_text(variant, key) for key in ("angle", "title", "opening")})
    if len({variant["angle"] for variant in clean_variants}) < 3:
        raise ValueError("返佣试验稿必须有三种不同文案角度")
    if texts["title"] not in {variant["title"] for variant in clean_variants}:
        raise ValueError("终稿标题必须对应一种已审阅的文案角度")
    checks = data.get("fact_checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("商品事实核对清单不能为空")
    facts: list[tuple[str, str]] = []
    for row in checks:
        if not isinstance(row, dict):
            raise ValueError("商品事实核对项必须是对象")
        claim = _required_text(row, "claim")
        source_url = _required_text(row, "source_url")
        if source_url not in urls or claim not in texts["body"]:
            raise ValueError("商品事实必须在正文出现并绑定已列出的来源")
        facts.append((claim, source_url))
    try:
        price = float(data["price_yuan"])
        commission = float(data["commission_yuan"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("商品报价和预计佣金必须是数字") from exc
    if price <= 0 or commission <= 0:
        raise ValueError("商品报价和预计佣金必须大于零")
    cover_path = None
    if data.get("cover_asset_path"):
        asset_root = (Path(__file__).resolve().parents[2] / "assets" / "wechat_mp").resolve()
        candidate = Path(str(data["cover_asset_path"]))
        if not candidate.is_absolute():
            candidate = Path(__file__).resolve().parents[2] / candidate
        candidate = candidate.resolve()
        if not candidate.is_relative_to(asset_root) or not candidate.is_file():
            raise ValueError("封面必须是 assets/wechat_mp 中已核对的现有素材")
        if candidate.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            raise ValueError("封面必须是 JPG 或 PNG 图片")
        cover_path = candidate
    return ProductFeatureDraft(
        **texts,
        price_yuan=price,
        commission_yuan=commission,
        source_urls=tuple(urls),
        fact_checks=tuple(facts),
        cover_asset_path=cover_path,
        editorial_review=review,
        copy_variants=tuple(clean_variants),
    )


def load_product_feature_draft(path: Path) -> ProductFeatureDraft:
    return load_product_feature_draft_data(json.loads(path.read_text(encoding="utf-8")))


def refresh_selected_product(
    draft: ProductFeatureDraft,
    *,
    search_fn: SearchFn = search_daihuo_products,
) -> dict[str, Any]:
    """写草稿前复查同一来源商品的身份、报价和预计佣金。"""
    for page_no in (1, 2):
        rows, _total, err = search_fn(draft.search_keyword, page_no=page_no, page_size=30)
        if err:
            raise RuntimeError(f"商品复查失败: {err.get('errmsg') or err}")
        for raw in rows:
            item = summarize_daihuo_product(raw)
            if item["product_id"] != draft.product_id or item["source_name"] != draft.source_name:
                continue
            if str(item.get("warehouse_id") or "") != draft.warehouse_id:
                raise ValueError("商品身份中的仓库标识发生变化")
            item["sku_id"] = str(raw.get("sku_id") or "")
            price = float(item["price_yuan"])
            commission = float(item["commission_yuan"])
            if price <= 0 or abs(price - draft.price_yuan) / draft.price_yuan > 0.1:
                raise ValueError("商品价格变化超过 10%，请重新选品")
            if commission <= 0 or abs(commission - draft.commission_yuan) / draft.commission_yuan > 0.2:
                raise ValueError("预计单笔佣金变化超过 20%，请重新选品")
            if _rejection_reason(item):
                raise ValueError("商品复查后不再符合选品门槛")
            return item
    raise ValueError("商品已不在当前返佣搜索结果中，请重新选品")


def verify_product_feature_article(article: dict[str, Any], product_id: str) -> None:
    from scripts.tools.wechat_mp_product import cps_data_pid

    content = str(article.get("content") or "")
    matches = _CPS_PID_RE.findall(content)
    if len(matches) != 1 or matches[0] != cps_data_pid(
        product_id,
        warehouse_id=str(article.get("product_feature_warehouse_id") or "101"),
        daihuo_meta={
            "product_id": product_id,
            "warehouse_id": str(article.get("product_feature_warehouse_id") or "101"),
            "sku_id": str(article.get("product_feature_sku_id") or ""),
        },
    ):
        raise ValueError("返佣单品稿商品卡数量或商品身份不一致")
    card_position = content.find("<mp-common-cpsad")
    if card_position < 0 or "广告" not in content[max(0, card_position - 200):card_position]:
        raise ValueError("返佣商品入口前缺少显著广告标识")
    if "data-adtype=\"short-play\"" in str(article.get("content") or ""):
        raise ValueError("返佣单品稿不得包含短剧组件")


def build_product_feature_article(
    draft: ProductFeatureDraft,
    *,
    current_product: dict[str, Any],
    upload_figures: bool,
) -> dict[str, Any]:
    from scripts.tools.wechat_mp_content import _article_shell
    from scripts.tools.wechat_mp_product import build_cpsad_html, cps_data_pid

    if str(current_product.get("product_id") or "") != draft.product_id or str(
        current_product.get("source_name") or ""
    ) != draft.source_name:
        raise ValueError("商品身份与成稿不一致")
    price = float(current_product.get("price_yuan") or 0)
    commission = float(current_product.get("commission_yuan") or 0)
    if price <= 0 or abs(price - draft.price_yuan) / draft.price_yuan > 0.1:
        raise ValueError("商品价格变化超过 10%，请重新选品")
    if commission <= 0 or abs(commission - draft.commission_yuan) / draft.commission_yuan > 0.2:
        raise ValueError("预计单笔佣金变化超过 20%，请重新选品")
    article = _article_shell(
        title=draft.title,
        digest=draft.digest,
        body_text=draft.body,
        kind="product_feature",
        upload_figures=upload_figures,
        attach_promotion=False,
    )
    warehouse = str(current_product.get("warehouse_id") or draft.warehouse_id)
    sku_id = str(current_product.get("sku_id") or "")
    pid = cps_data_pid(
        draft.product_id,
        warehouse_id=warehouse,
        daihuo_meta={"product_id": draft.product_id, "warehouse_id": warehouse, "sku_id": sku_id},
    )
    article["content"] += _AD_LABEL_HTML + build_cpsad_html(pid)
    article["product_feature_warehouse_id"] = warehouse
    article["product_feature_sku_id"] = sku_id
    article["product_feature_product_id"] = draft.product_id
    verify_product_feature_article(article, draft.product_id)
    return article
