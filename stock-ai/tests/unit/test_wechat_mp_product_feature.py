"""需求切入的公众号返佣单品稿型。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

def _product(
    product_id: str,
    *,
    name: str,
    price_fen: int,
    commission_fen: int,
    rate_bp: int,
    sales: int,
    category: str = "空气炸锅",
    flow_sales: int = 0,
) -> dict:
    return {
        "product_id": product_id,
        "warehouse_id": "101",
        "source": 1,
        "source_name": "京东",
        "product_name": name,
        "current_price": price_fen,
        "commission": commission_fen,
        "basic_info": {"commission_rate": rate_bp},
        "sales_tips": str(sales),
        "third_category_name": category,
        "basic_info": {
            "commission_rate": rate_bp,
            "sale": {"sales_on_source": str(sales), "sales_on_flow": str(flow_sales)},
        },
    }


def test_request_filters_bad_products_and_deduplicates_pages() -> None:
    from scripts.tools.wechat_mp_product_feature import prepare_product_feature_request

    good = _product(
        "good", name="斧头牌洗洁精", price_fen=30000,
        commission_fen=2160, rate_bp=720, sales=8000, category="洗洁精",
    )
    low_sales = _product(
        "low", name="另一瓶洗洁精", price_fen=20000,
        commission_fen=2000, rate_bp=1000, sales=900, category="洗洁精",
    )
    inconsistent = _product(
        "bad-rate", name="另一款洗洁精", price_fen=10000,
        commission_fen=100, rate_bp=9000, sales=10000, category="洗洁精",
    )
    calls: list[tuple[str, int, int]] = []

    def search(keyword: str, *, page_no: int, page_size: int):
        calls.append((keyword, page_no, page_size))
        return ([good, low_sales, inconsistent] if page_no == 1 else [good], 4, None)

    request = prepare_product_feature_request(
        keywords=("洗洁精",), search_fn=search,
    )

    assert calls == [("洗洁精", 1, 30), ("洗洁精", 2, 30)]
    assert [item["product_id"] for item in request["candidates"]] == ["good"]
    assert {item["product_id"] for item in request["rejected_candidates"]} == {"low", "bad-rate"}
    assert request["candidates"][0]["commission_yuan"] == 21.6


def test_default_catalog_surfaces_sampled_bestsellers_without_appliances() -> None:
    from scripts.tools.wechat_mp_product_feature import (
        DEFAULT_KEYWORDS, prepare_product_feature_request,
    )

    assert "空气炸锅" not in DEFAULT_KEYWORDS
    assert "充电宝" not in DEFAULT_KEYWORDS
    assert "图书" not in DEFAULT_KEYWORDS
    book = _product("book", name="三体全三册", price_fen=9900, commission_fen=110,
                    rate_bp=111, sales=3000000, category="图书")
    soap = _product("soap", name="斧头牌洗洁精", price_fen=3500, commission_fen=210,
                    rate_bp=600, sales=2000000, category="洗洁精", flow_sales=5)
    snack = _product("snack", name="乳酸菌面包", price_fen=2000, commission_fen=100,
                     rate_bp=500, sales=1500000, category="面包")
    appliance = _product("appliance", name="美的空气炸锅", price_fen=30000,
                         commission_fen=3000, rate_bp=1000, sales=9000000)

    def search(term: str, *, page_no: int, page_size: int):
        rows = [book, soap, snack, appliance] if page_no == 1 else [book]
        return rows, len(rows), None

    request = prepare_product_feature_request(search_fn=search)
    assert request["candidates"][0]["product_id"] == "soap"
    assert request["candidates"][1]["product_id"] == "snack"
    assert request["candidates"][0]["sales_on_flow"] == 5
    assert any(item["product_id"] == "book" for item in request["rejected_candidates"])
    assert any(item["product_id"] == "appliance" for item in request["rejected_candidates"])
    assert request["sales_basis"] == "sampled_select_sales_hint"
    assert request["flow_sales_positive_count"] == 1
    assert "全站" in request["ranking_limit"]
    assert len(request["queries"]) == len(DEFAULT_KEYWORDS) * 2


def test_request_stops_when_no_product_reaches_sales_threshold() -> None:
    from scripts.tools.wechat_mp_product_feature import prepare_product_feature_request

    item = _product(
        "quiet", name="空气炸锅", price_fen=10000,
        commission_fen=1000, rate_bp=1000, sales=999,
    )

    def search(_keyword: str, *, page_no: int, page_size: int):
        return ([item] if page_no == 1 else [], 1, None)

    with pytest.raises(ValueError, match="合格候选"):
        prepare_product_feature_request(keywords=("空气炸锅",), search_fn=search)


def _draft_data() -> dict:
    return {
        "product_id": "100041948493",
        "search_keyword": "空气炸锅",
        "warehouse_id": "101",
        "source_name": "京东",
        "product_name": "美的空气炸锅 6.5L",
        "price_yuan": 302.0,
        "commission_yuan": 21.75,
        "queried_at": "2026-09-26T12:00:00+08:00",
        "title": "下班晚饭来不及做，空气炸锅该怎么看？",
        "digest": "从清洗、容量和台面空间看一件家用小电器。",
        "body": (
            "下班回来还要做饭，最怕收拾台面花的时间比吃饭还久。先想清楚家里有几个人吃，台面能留多少空间。\n\n"
            "如果一周只做一次，普通烤箱或者平底锅可能更合适，未必需要再买一件电器。\n\n"
            "这款美的空气炸锅标称容量6.5L，适合需要一次做多人份、又愿意给它留固定位置的家庭。\n\n"
            "它不能替你备菜，清洗仍要花时间。台面紧张或极少做饭的人不适合购买。\n\n"
            "购买前请以商品页面的价格和参数为准。"
        ),
        "reader_need": "下班晚饭省去复杂烹饪步骤",
        "alternative": "普通烤箱或者平底锅",
        "not_for": "台面紧张或极少做饭的人",
        "source_urls": ["https://item.jd.com/100041948493.html"],
        "fact_checks": [
            {"claim": "标称容量6.5L", "source_url": "https://item.jd.com/100041948493.html"}
        ],
        "editorial_review": {
            "target_reader": "下班后要自己做晚饭的人",
            "reader_question": "买空气炸锅究竟能省下哪些步骤？",
            "core_judgment": "空气炸锅只适合频繁做烘烤类晚饭、又能留出固定台面的人。",
            "body_anchor": "清洗仍要花时间",
            "paragraph_roles": ["问题", "替代", "产品", "限制", "披露"],
        },
        "copy_variants": [
            {"angle": "省时", "title": "下班晚饭来不及做，空气炸锅该怎么看？", "opening": "下班后的晚饭，时间总是不够。"},
            {"angle": "空间", "title": "厨房台面不够，空气炸锅值得买吗？", "opening": "添一台电器，先看台面放不放得下。"},
            {"angle": "清洗", "title": "买空气炸锅前，先想想怎么洗", "opening": "能做一顿饭，也要收拾一顿饭。"},
        ],
    }


def test_single_product_article_has_one_matching_card_and_disclosure() -> None:
    from scripts.tools.wechat_mp_product_feature import (
        build_product_feature_article,
        load_product_feature_draft_data,
        verify_product_feature_article,
    )

    draft = load_product_feature_draft_data(_draft_data())
    article = build_product_feature_article(
        draft,
        current_product={
            "product_id": "100041948493", "warehouse_id": "101",
            "source_name": "京东", "product_name": "美的空气炸锅 6.5L",
            "price_yuan": 302.0, "commission_yuan": 21.75,
        },
        upload_figures=False,
    )

    assert article["content"].count("<mp-common-cpsad") == 1
    assert 'data-pid="101_100041948493"' in article["content"]
    assert "<strong>广告</strong>" in article["content"]
    assert "欢迎点文章下方" not in article["body_text"]
    assert "不构成投资建议" not in article["content"]
    verify_product_feature_article(article, "100041948493")
    without_label = dict(article)
    without_label["content"] = article["content"].replace(
        '<p style="font-size:14px;color:#666;line-height:1.6"><strong>广告</strong>　封面为场景示意图。</p>',
        "",
    )
    with pytest.raises(ValueError, match="广告标识"):
        verify_product_feature_article(without_label, "100041948493")


def test_product_disclosure_is_separate_from_editorial_prose() -> None:
    from scripts.tools.wechat_mp_product_feature import (
        build_product_feature_article,
        load_product_feature_draft_data,
    )

    data = _draft_data()
    draft = load_product_feature_draft_data(data)
    article = build_product_feature_article(
        draft,
        current_product={
            "product_id": "100041948493", "warehouse_id": "101",
            "source_name": "京东", "product_name": "美的空气炸锅 6.5L",
            "price_yuan": 302.0, "commission_yuan": 21.75,
        },
        upload_figures=False,
    )
    content = article["content"]
    assert "广告" not in article["body_text"]
    assert "广告" in content[:content.index("<mp-common-cpsad")][-200:]
    assert "佣金" not in article["body_text"]


def test_product_draft_rejects_internal_ad_card_narration() -> None:
    from scripts.tools.wechat_mp_product_feature import load_product_feature_draft_data

    data = _draft_data()
    data["body"] += "\n\n本文含广告推广。下方是一张返佣商品卡。"
    data["editorial_review"]["paragraph_roles"].append("广告说明")
    with pytest.raises(ValueError, match="广告说明"):
        load_product_feature_draft_data(data)


def test_product_draft_requires_hotspot_style_editorial_review() -> None:
    from scripts.tools.wechat_mp_product_feature import load_product_feature_draft_data

    data = _draft_data()
    del data["editorial_review"]
    with pytest.raises(ValueError, match="编辑审校"):
        load_product_feature_draft_data(data)

    data = _draft_data()
    data["editorial_review"]["body_anchor"] = "正文不存在的核心判断"
    with pytest.raises(ValueError, match="正文锚点"):
        load_product_feature_draft_data(data)


def test_product_draft_requires_three_distinct_copy_angles() -> None:
    from scripts.tools.wechat_mp_product_feature import load_product_feature_draft_data

    data = _draft_data()
    data["copy_variants"] = data["copy_variants"][:2]
    with pytest.raises(ValueError, match="三种文案角度"):
        load_product_feature_draft_data(data)


def test_product_draft_rejects_digest_that_wechat_would_cut_mid_sentence() -> None:
    from scripts.tools.wechat_mp_product_feature import load_product_feature_draft_data

    data = _draft_data()
    data["digest"] = "洗碗" * 22  # 44 个汉字，UTF-8 编码超过摘要的 128 字节上限。
    with pytest.raises(ValueError, match="摘要.*128 字节"):
        load_product_feature_draft_data(data)


def test_product_draft_rejects_editorial_instruction_leak() -> None:
    from scripts.tools.wechat_mp_product_feature import load_product_feature_draft_data

    data = _draft_data()
    data["body"] += "\n\n正文应该补一段商品卖点。"
    data["editorial_review"]["paragraph_roles"].append("错误说明")
    with pytest.raises(ValueError, match="公开文案"):
        load_product_feature_draft_data(data)


def test_product_draft_rejects_cover_outside_wechat_assets() -> None:
    from scripts.tools.wechat_mp_product_feature import load_product_feature_draft_data

    data = _draft_data()
    data["cover_asset_path"] = "/tmp/unverified.jpg"
    with pytest.raises(ValueError, match="封面"):
        load_product_feature_draft_data(data)


def test_product_article_rejects_a_different_product_id() -> None:
    from scripts.tools.wechat_mp_product_feature import (
        build_product_feature_article,
        load_product_feature_draft_data,
    )

    with pytest.raises(ValueError, match="商品身份"):
        build_product_feature_article(
            load_product_feature_draft_data(_draft_data()),
            current_product={
                "product_id": "other", "warehouse_id": "101",
                "source_name": "京东", "product_name": "美的空气炸锅 6.5L",
                "price_yuan": 302.0, "commission_yuan": 21.75,
            },
            upload_figures=False,
        )


def test_product_promotion_exception_requires_exactly_one_card() -> None:
    from scripts.tools.wechat_mp_short_drama import assert_longform_promotion_safe

    card = '<mp-common-cpsad data-pid="101_100041948493"></mp-common-cpsad>'
    assert_longform_promotion_safe({"content": f"<p>正文</p>{card}"}, kind="product_feature")
    with pytest.raises(RuntimeError, match="恰好一张"):
        assert_longform_promotion_safe({"content": "<p>正文</p>"}, kind="product_feature")
    with pytest.raises(RuntimeError, match="恰好一张"):
        assert_longform_promotion_safe({"content": card + card}, kind="product_feature")
    with pytest.raises(RuntimeError, match="普通返佣商品"):
        assert_longform_promotion_safe({"content": card}, kind="hotspot")


def test_failed_new_draft_keeps_existing_product_slot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.tools import wechat_mp_draft_slots as slots

    slot_file = tmp_path / "slots.json"
    slot_file.write_text(
        '{"version":1,"slots":{"product_feature":{"media_id":"old-id","title":"旧单品稿"}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(slots, "SLOTS_PATH", slot_file)
    monkeypatch.setattr(slots, "attach_cover_crop_fields", lambda article, thumb_media_id: article)
    monkeypatch.setattr(slots, "draft_add", lambda articles: (None, {"errmsg": "临时失败"}))
    deleted: list[str] = []
    monkeypatch.setattr(slots, "draft_delete", lambda media_id: deleted.append(media_id))

    media_id, action, error = slots.upsert_product_feature_draft(
        {"title": "新单品稿", "content": "正文"}, thumb_media_id="cover-id",
    )

    assert media_id is None and action == "failed" and error
    assert deleted == []
    assert slots.get_slot_media_id("product_feature") == "old-id"


def test_failed_card_readback_keeps_existing_product_slot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.tools import wechat_mp_draft_slots as slots

    slot_file = tmp_path / "slots.json"
    slot_file.write_text(
        '{"version":1,"slots":{"product_feature":{"media_id":"old-id","title":"旧单品稿"}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(slots, "SLOTS_PATH", slot_file)
    monkeypatch.setattr(slots, "attach_cover_crop_fields", lambda article, thumb_media_id: article)
    monkeypatch.setattr(slots, "draft_add", lambda articles: ("new-id", None))
    deleted: list[str] = []
    monkeypatch.setattr(slots, "draft_delete", lambda media_id: deleted.append(media_id) or None)

    def invalid_card(_media_id: str) -> None:
        raise ValueError("商品卡不一致")

    media_id, action, error = slots.upsert_product_feature_draft(
        {"title": "新单品稿", "content": "正文"},
        thumb_media_id="cover-id",
        verify_saved=invalid_card,
    )

    assert media_id is None and action == "failed" and "商品卡不一致" in error["errmsg"]
    assert deleted == ["new-id"]
    assert slots.get_slot_media_id("product_feature") == "old-id"


def test_product_slot_replaces_old_only_after_new_card_is_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.tools import wechat_mp_draft_slots as slots

    slot_file = tmp_path / "slots.json"
    slot_file.write_text(
        '{"version":1,"slots":{"product_feature":{"media_id":"old-id","title":"旧单品稿"}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(slots, "SLOTS_PATH", slot_file)
    monkeypatch.setattr(slots, "attach_cover_crop_fields", lambda article, thumb_media_id: article)
    events: list[str] = []
    monkeypatch.setattr(slots, "draft_add", lambda articles: events.append("add") or ("new-id", None))
    monkeypatch.setattr(slots, "draft_delete", lambda media_id: events.append(f"delete:{media_id}") or None)

    def verify(media_id: str) -> None:
        assert media_id == "new-id"
        events.append("verify")

    media_id, action, error = slots.upsert_product_feature_draft(
        {"title": "新单品稿", "content": "正文"},
        thumb_media_id="cover-id", verify_saved=verify,
    )

    assert (media_id, action, error) == ("new-id", "recreated", None)
    assert events == ["add", "verify", "delete:old-id"]
    assert slots.get_slot_media_id("product_feature") == "new-id"
    assert slots.get_slot_title("product_feature") == "新单品稿"


def test_draft_api_payload_omits_product_research_metadata() -> None:
    from scripts.tools.wechat_mp_product import draft_article_payload

    payload = draft_article_payload({
        "title": "单品稿", "content": "<p>正文</p>",
        "product_feature_product_id": "123",
        "product_feature_warehouse_id": "101",
        "product_feature_sku_id": "101_123",
    })
    assert set(payload) == {"title", "content"}


def test_refresh_finds_same_product_and_rejects_changed_price() -> None:
    from scripts.tools.wechat_mp_product_feature import (
        load_product_feature_draft_data,
        refresh_selected_product,
    )

    draft_data = _draft_data()
    draft_data.update(product_id="soap-123", search_keyword="洗洁精", product_name="斧头牌洗洁精")
    draft = load_product_feature_draft_data(draft_data)
    row = _product(
        "soap-123", name="斧头牌洗洁精", price_fen=30200,
        commission_fen=2175, rate_bp=720, sales=8000, category="洗洁精",
    )

    def search(_keyword: str, *, page_no: int, page_size: int):
        return ([row] if page_no == 1 else [], 1, None)

    assert refresh_selected_product(draft, search_fn=search)["product_id"] == draft.product_id

    changed = {**row, "current_price": 40000}

    def changed_search(_keyword: str, *, page_no: int, page_size: int):
        return ([changed] if page_no == 1 else [], 1, None)

    with pytest.raises(ValueError, match="价格变化"):
        refresh_selected_product(draft, search_fn=changed_search)


def test_product_kind_is_available_only_as_single_manual_kind(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from scripts.tools import wechat_mp_draft as cli
    from scripts.tools.wechat_mp_content import DAILY_DRAFT_KINDS, DRAFT_KINDS

    assert "product_feature" in DRAFT_KINDS
    assert "product_feature" not in DAILY_DRAFT_KINDS
    monkeypatch.setattr(cli, "prepare_product_feature_request", lambda: {"request_type": "product_feature", "candidates": [{"product_id": "123"}]})
    monkeypatch.setattr(sys, "argv", ["wechat_mp_draft", "--kind", "product_feature", "--dry-run"])

    assert cli.main() == 0
    assert '"product_id": "123"' in capsys.readouterr().out


def test_product_kind_cannot_auto_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.tools import wechat_mp_draft as cli

    monkeypatch.setattr(sys, "argv", ["wechat_mp_draft", "--kind", "product_feature", "--publish"])
    assert cli.main() == 1
