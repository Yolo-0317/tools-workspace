"""stock-ai hub 引流段落。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_stock_ai_cta import (
    attach_stock_ai_cta,
    stock_ai_cta_paragraph,
)


def test_stock_ai_cta_paragraph_news(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_MP_STOCK_AI_CTA", "1")
    para = stock_ai_cta_paragraph(kind="news")
    assert "hub.yoloworld.site" in para
    assert "/news" in para


def test_attach_stock_ai_cta(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_MP_STOCK_AI_CTA", "1")
    monkeypatch.setenv("WECHAT_MP_STOCK_AI_CTA_KINDS", "news")
    art = {
        "body_text": "正文\n\n本文为作者个人投资日记，不构成投资建议。",
        "kind": "news",
    }
    out = attach_stock_ai_cta(art, kind="news")
    assert "hub.yoloworld.site" in out["body_text"]
