"""文末返佣商品。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_product import (
    attach_footer_product,
    auto_pick_footer_product,
    draft_article_payload,
    extract_sales_count,
    footer_product_auto_pick,
    footer_product_enabled,
    pick_best_daihuo_product,
    pick_keywords_for_kind,
    resolve_footer_product_key,
    search_daihuo_products,
    summarize_daihuo_product,
)


def test_footer_product_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WECHAT_MP_FOOTER_PRODUCT", raising=False)
    assert footer_product_enabled() is False
    article = {"title": "t", "content": "<p>x</p>", "body_text": "x"}
    assert attach_footer_product(article, kind="market") == article


def test_attach_footer_product_injects_cpsad(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT", "1")
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT_AUTO_PICK", "0")
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT_ID", "10195600087007")
    article = {
        "title": "t",
        "content": "<p>正文</p><p>本文为作者个人投资日记与信息整理。</p>",
    }
    out = attach_footer_product(article, kind="market")
    assert "mp-common-cpsad" in out["content"]
    assert 'data-pid="101_10195600087007"' in out["content"]
    assert out["content"].index("mp-common-cpsad") < out["content"].index("本文为作者")


def test_attach_footer_product_respects_kind_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT", "1")
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT_AUTO_PICK", "0")
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT_ID", "10195600087007")
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT_KINDS", "market")
    assert "mp-common-cpsad" not in attach_footer_product({"title": "t", "content": "<p>x</p>"}, kind="news")["content"]
    assert "mp-common-cpsad" in attach_footer_product({"title": "t", "content": "<p>x</p>"}, kind="market")["content"]


def test_resolve_footer_product_key_uses_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = tmp_path / "cache.json"
    monkeypatch.setattr("scripts.tools.wechat_mp_product.CACHE_PATH", cache)
    with patch(
        "scripts.tools.wechat_mp_client.get_product_card_info",
        return_value=({"product_key": "CACHED_KEY"}, None),
    ) as mock_api:
        key1, err1 = resolve_footer_product_key("999", force_refresh=True)
        key2, err2 = resolve_footer_product_key("999")
    assert err1 is None and key1 == "CACHED_KEY"
    assert err2 is None and key2 == "CACHED_KEY"
    assert mock_api.call_count == 1


def test_summarize_daihuo_product() -> None:
    row = summarize_daihuo_product(
        {
            "product_id": "37685841869",
            "warehouse_id": "101",
            "source": 2,
            "source_name": "京东",
            "product_name": "宁芝静电容键盘",
            "current_price": 129900,
            "commission": 105,
            "basic_info": {"commission_rate": 8},
            "third_category_name": "键盘",
        }
    )
    assert row["product_id"] == "37685841869"
    assert row["price_yuan"] == 1299.0
    assert row["commission_yuan"] == 1.05
    assert row["commission_rate_bp"] == 800


def test_search_daihuo_requires_uin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WECHAT_MP_DAIHUO_UIN", raising=False)
    items, total, err = search_daihuo_products("键盘")
    assert items == [] and total == 0
    assert err and "DAIHUO_UIN" in err["errmsg"]


def test_draft_article_payload_strips_body_text() -> None:
    payload = draft_article_payload({"title": "t", "content": "c", "body_text": "plain"})
    assert "body_text" not in payload
    assert payload["title"] == "t"


def test_footer_product_auto_pick_defaults_with_footer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WECHAT_MP_FOOTER_PRODUCT_AUTO_PICK", raising=False)
    monkeypatch.delenv("WECHAT_MP_FOOTER_PRODUCT", raising=False)
    assert footer_product_auto_pick() is False
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT", "1")
    assert footer_product_auto_pick() is True


def test_footer_product_auto_pick_explicit_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT", "1")
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT_AUTO_PICK", "0")
    assert footer_product_auto_pick() is False


def test_pick_keywords_for_kind_uses_mapping() -> None:
    assert "机械键盘" in pick_keywords_for_kind("workspace")
    assert pick_keywords_for_kind("market") == ["理财", "基金", "记账本", "财经"]


def test_pick_keywords_for_kind_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_MP_FOOTER_PICK_KEYWORD", "咖啡 茶叶")
    assert pick_keywords_for_kind("market") == ["咖啡", "茶叶"]


def test_pick_best_daihuo_product_dedupes_and_picks_highest_commission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WECHAT_MP_PICK_STRATEGY", "commission")
    low = {
        "product_id": "1",
        "sales_tips": 90000,
        "basic_info": {"commission_rate": 1000, "commission": 500},
        "commission": 500,
    }
    high = {
        "product_id": "2",
        "sales_tips": 100,
        "basic_info": {"commission_rate": 2000, "commission": 800},
        "commission": 800,
    }

    def fake_search(keyword: str, **kwargs: object) -> tuple[list[dict], int, None]:
        if keyword == "键盘":
            return [low, high], 2, None
        return [low], 1, None

    monkeypatch.setattr("scripts.tools.wechat_mp_product.search_daihuo_products", fake_search)
    summary, _raw = pick_best_daihuo_product(keywords=["键盘", "鼠标"])
    assert summary["product_id"] == "2"


def test_pick_best_daihuo_product_prefers_sales(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_MP_PICK_STRATEGY", "sales")
    low_sales_high_comm = {
        "product_id": "1",
        "sales_tips": 200,
        "basic_info": {"commission_rate": 2000, "commission": 800},
        "commission": 800,
    }
    high_sales_low_comm = {
        "product_id": "2",
        "sales_tips": 50000,
        "basic_info": {"commission_rate": 500, "commission": 100},
        "commission": 100,
    }

    def fake_search(keyword: str, **kwargs: object) -> tuple[list[dict], int, None]:
        return [low_sales_high_comm, high_sales_low_comm], 2, None

    monkeypatch.setattr("scripts.tools.wechat_mp_product.search_daihuo_products", fake_search)
    summary, _raw = pick_best_daihuo_product(keywords=["充电宝"])
    assert summary["product_id"] == "2"
    assert summary["sales_count"] == 50000


def test_extract_sales_count_from_sale_dict() -> None:
    raw = {"sales_tips": 0, "sale": {"sales_on_source": "1200", "sales_on_ams": "300"}}
    assert extract_sales_count(raw) == 1500


def test_auto_pick_footer_product_updates_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT", "1")
    monkeypatch.setenv("WECHAT_MP_DAIHUO_UIN", "123")
    monkeypatch.delenv("WECHAT_MP_FOOTER_PRODUCT_ID", raising=False)
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_product.pick_best_daihuo_product",
        lambda **kwargs: (
            {
                "product_id": "999",
                "product_name": "测试商品",
                "commission_yuan": 9.9,
                "commission_rate_bp": 1500,
            },
            {"sku_id": "101_999"},
        ),
    )
    saved: list[dict] = []
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_product.save_picked_product",
        lambda summary, raw: saved.append({"summary": summary, "raw": raw}),
    )
    out = auto_pick_footer_product(kind="market")
    assert out and out["product_id"] == "999"
    assert os.environ["WECHAT_MP_FOOTER_PRODUCT_ID"] == "999"
    assert saved and saved[0]["summary"]["product_id"] == "999"


def test_attach_footer_product_runs_auto_pick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT", "1")
    calls: list[str | None] = []
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_product.auto_pick_footer_product",
        lambda *, kind: calls.append(kind) or {"product_id": "10195600087007"},
    )
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT_ID", "10195600087007")
    article = {"title": "t", "content": "<p>本文为作者个人投资日记</p>"}
    attach_footer_product(article, kind="market")
    assert calls == ["market"]
