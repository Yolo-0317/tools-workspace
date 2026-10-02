from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from scripts.tools.wechat_mp_browser_workflow import create_workflow, record_confirmed_body
from scripts.tools.wechat_mp_hotspot_image_policy import (
    VerifiedFigure,
    VerifiedHotspotImages,
)
from scripts.tools.wechat_mp_editorial_handoff import validate_handoff


def _fixture(tmp_path: Path) -> tuple[Path, object, Path, VerifiedHotspotImages]:
    workflow = create_workflow(
        kind="hotspot", topic="月租房", prompt="提示词", root=tmp_path
    )
    body = "\n\n".join(["报道时页面显示月租1500元起。" * 10] * 4)
    confirmed = record_confirmed_body(
        workflow.workflow_id,
        "月租房标题\n\n" + body,
        confirmation_text="核对后推草稿",
        root=tmp_path,
    )
    article = tmp_path / "article.json"
    article.write_text(
        json.dumps(
            {"title": "月租房标题", "body": body},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    image_path = tmp_path / "still-01.jpg"
    Image.effect_noise((800, 600), 70).convert("RGB").save(image_path)
    source = {
        "still-01.jpg": {
            "page_url": "https://news.example/report",
            "source_name": "测试报道",
            "published_at": "2026-09-16",
            "source_type": "news_listing_screenshot",
            "page_title": "月租报道",
            "caption": "报道时的房源价格截图",
            "verified": "true",
            "visual_description": "上海松江房源，页面显示月租1500元起",
            "visual_checked_at": "2026-09-23T17:00:00+08:00",
            "evidence_role": "price_snapshot",
        }
    }
    (tmp_path / "figure_sources.json").write_text(
        json.dumps(source, ensure_ascii=False), encoding="utf-8"
    )
    figure = VerifiedFigure(
        path=image_path,
        rel="discussion/月租房/still-01.jpg",
        caption="报道时的房源价格截图",
        page_url="https://news.example/report",
        source_name="测试报道",
        source_type="news_listing_screenshot",
    )
    selected = VerifiedHotspotImages(
        cover_source=image_path,
        body_figures=(figure,),
        source_meta={"still-01.jpg": source["still-01.jpg"]},
    )
    handoff = tmp_path / "editorial_handoff.json"
    handoff.write_text(
        json.dumps(
            {
                "workflow_id": workflow.workflow_id,
                "article_sha256": hashlib.sha256(article.read_bytes()).hexdigest(),
                "confirmed_body_sha256": confirmed.response_sha256,
                "confirmation_mode": "thread_confirmed_body",
                "editorial_review": {
                    "target_reader": "正在比较月租房源的租客",
                    "reader_question": "页面上的月租1500元起能否代表实际付款金额？",
                    "central_thesis": "页面起价只是报道时的房源快照，签约前还要核对具体房间和费用。",
                    "thesis_anchor": "报道时页面显示月租1500元起。",
                    "paragraph_progression": "正文先交代页面价格，再说明它只代表报道时的具体房源，不把起价写成所有租客的实付价。",
                    "decision": "pass",
                },
                "claims": [
                    {
                        "text": "月租1500元起",
                        "kind": "reported_snapshot",
                        "source_url": "https://news.example/report",
                        "published_at": "2026-09-16",
                        "observed_at": "2026-09-23",
                        "scope_or_period": "2026年9月报道时的上海松江房源",
                        "body_anchor": "报道时页面显示月租1500元起。",
                    }
                ],
                "images": [
                    {
                        "filename": "still-01.jpg",
                        "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                        "evidence_role": "price_snapshot",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return handoff, confirmed, article, selected


def test_complete_handoff_accepts_reported_price_snapshot(tmp_path: Path) -> None:
    handoff, workflow, article, selected = _fixture(tmp_path)

    summary = validate_handoff(
        handoff, workflow=workflow, article_path=article, selected_images=selected
    )

    assert summary.claim_count == 1
    assert summary.image_count == 1


def test_handoff_rejects_article_replaced_after_confirmation(tmp_path: Path) -> None:
    handoff, workflow, article, selected = _fixture(tmp_path)
    article.write_text(article.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(ValueError, match="文章摘要不一致"):
        validate_handoff(
            handoff, workflow=workflow, article_path=article, selected_images=selected
        )


def test_handoff_rejects_snapshot_without_time_limited_body_anchor(tmp_path: Path) -> None:
    handoff, workflow, article, selected = _fixture(tmp_path)
    payload = json.loads(handoff.read_text(encoding="utf-8"))
    payload["claims"][0]["body_anchor"] = "月租1500元起"
    handoff.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="页面快照缺少时间限定"):
        validate_handoff(
            handoff, workflow=workflow, article_path=article, selected_images=selected
        )


def test_handoff_rejects_image_role_mismatch(tmp_path: Path) -> None:
    handoff, workflow, article, selected = _fixture(tmp_path)
    payload = json.loads(handoff.read_text(encoding="utf-8"))
    payload["images"][0]["evidence_role"] = "scene"
    handoff.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="图片用途不一致"):
        validate_handoff(
            handoff, workflow=workflow, article_path=article, selected_images=selected
        )


def test_handoff_rejects_claim_missing_period(tmp_path: Path) -> None:
    handoff, workflow, article, selected = _fixture(tmp_path)
    payload = json.loads(handoff.read_text(encoding="utf-8"))
    payload["claims"][0]["scope_or_period"] = ""
    handoff.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="scope_or_period"):
        validate_handoff(
            handoff, workflow=workflow, article_path=article, selected_images=selected
        )


def test_handoff_rejects_missing_article_level_review(tmp_path: Path) -> None:
    handoff, workflow, article, selected = _fixture(tmp_path)
    payload = json.loads(handoff.read_text(encoding="utf-8"))
    del payload["editorial_review"]
    handoff.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="文章级审稿"):
        validate_handoff(
            handoff, workflow=workflow, article_path=article, selected_images=selected
        )


def test_handoff_rejects_thesis_anchor_missing_from_body(tmp_path: Path) -> None:
    handoff, workflow, article, selected = _fixture(tmp_path)
    payload = json.loads(handoff.read_text(encoding="utf-8"))
    payload["editorial_review"]["thesis_anchor"] = "正文没有这句话"
    handoff.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="核心判断锚点"):
        validate_handoff(
            handoff, workflow=workflow, article_path=article, selected_images=selected
        )
