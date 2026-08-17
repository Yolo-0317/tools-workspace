"""市场稿 dry-run 不得上传微信素材。"""

from __future__ import annotations

from scripts.tools import wechat_mp_client as client_mod
from scripts.tools import wechat_mp_content as content_mod
from scripts.tools import wechat_mp_figures as figures_mod
from scripts.tools import wechat_mp_market_article as market_article_mod
from scripts.tools import wechat_mp_market_polish as market_polish_mod


def test_market_article_with_upload_disabled_does_not_upload_images(monkeypatch) -> None:
    monkeypatch.setattr(
        market_article_mod,
        "generate_researcher_market_body",
        lambda **kwargs: "> 市场温度\n\n指数缩量整理，等待新的验证信号。",
    )
    monkeypatch.setattr(market_polish_mod, "finalize_market_body", lambda body, **kwargs: body)
    monkeypatch.setattr(
        market_polish_mod,
        "align_market_title_mood",
        lambda title, body: title,
    )
    monkeypatch.setattr(content_mod, "_market_title", lambda *args, **kwargs: "市场等待新信号")
    monkeypatch.setattr(content_mod, "_market_digest", lambda *args, **kwargs: "市场观察摘要")
    monkeypatch.setattr(content_mod, "_record_market_title", lambda **kwargs: None)
    monkeypatch.setattr(content_mod, "_save_market_body_cache", lambda **kwargs: None)
    monkeypatch.setattr(
        figures_mod,
        "inject_market_figures",
        lambda body: f"{body}\n\n[[fig:market-index.png|指数示意]]",
    )
    monkeypatch.setattr(
        figures_mod,
        "upload_inline_figure",
        lambda filename: (_ for _ in ()).throw(AssertionError("dry-run 不得上传图片")),
    )
    monkeypatch.setattr(client_mod, "mp_configured", lambda: True)

    article = content_mod.build_article("market", upload_figures=False)

    assert "（配图）" in article["content"]
