"""wechat_mp_seo：摘要 SEO 与 #话题 推荐。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_seo import (
    DIGEST_MAX,
    HASHTAG_MAX,
    append_hashtag_inline_to_body,
    enrich_digest,
    enrich_title_for_search,
    format_hashtag_line,
    recommended_hashtags,
    title_front_has_search_keywords,
    title_sousou_hook_score,
)


def test_enrich_digest_adds_core_keywords_for_market():
    base = "【06-03 收盘】半导体——指数与结构。个人观察，非荐股。"
    out = enrich_digest(base, "market")
    assert "A股" in out or "收盘复盘" in out
    assert len(out) <= DIGEST_MAX


def test_enrich_digest_skips_when_keywords_present():
    base = "A股收盘复盘：指数与结构。非荐股。"
    out = enrich_digest(base, "market")
    assert out == base[:DIGEST_MAX]


def test_recommended_hashtags_market_close():
    tags = recommended_hashtags("market", edition="close")
    assert tags[0] == "A股"
    assert "收盘复盘" in tags
    assert len(tags) <= HASHTAG_MAX


def test_recommended_hashtags_dragons_with_theme():
    tags = recommended_hashtags(
        "dragons",
        dragon_slot="eod",
        theme="电力",
        phase="发酵",
    )
    assert "A股" in tags
    assert "电力" in tags
    assert len(tags) <= HASHTAG_MAX


def test_recommended_hashtags_banned_excluded():
    tags = recommended_hashtags("top5", extra="牛股推荐")
    assert "牛股推荐" not in tags


def test_format_hashtag_line():
    line = format_hashtag_line(["A股", "收盘复盘"])
    assert line.startswith("推荐 #话题:")
    assert "#A股" in line
    assert "#收盘复盘" in line


def test_enrich_title_for_search_adds_prefix_top5():
    raw = "胜业电气等5只，结构怎么读？"
    out = enrich_title_for_search(raw, "top5", max_len=32)
    assert title_front_has_search_keywords(out, "top5")
    assert len(out) <= 32
    assert "领衔" not in out
    assert "明日盯" not in out


def test_enrich_title_for_search_skips_when_front_ok():
    raw = "A股观察5只｜胜业电气结构对照"
    out = enrich_title_for_search(raw, "top5", max_len=32)
    assert "领衔" not in out
    assert title_front_has_search_keywords(out, "top5")


def test_title_sousou_hook_score_prefers_search_winners():
    assert title_sousou_hook_score("情绪退潮梯队｜粤电力4板结构", "dragons") >= 4
    assert title_sousou_hook_score("A股观察｜胜业电气等5只，结构怎么读？", "top5") >= 4
    assert title_sousou_hook_score("A股电力｜产业链怎么拆？收盘观察", "sector") >= 4
    assert title_sousou_hook_score("情绪退潮怎么玩？粤电力4板还在榜", "dragons") < 0


def test_top5_winner_title_keeps_mingri_dinghua():
    raw = "A股观察｜胜业电气等5只，结构怎么读？"
    out = enrich_title_for_search(raw, "top5", max_len=32)
    assert "胜业电气" in out
    assert "领衔" not in out
    assert "明日盯" not in out
    assert title_front_has_search_keywords(out, "top5")


def test_sync_article_content_keeps_banner_img(monkeypatch, tmp_path) -> None:
    import json

    from scripts.tools import wechat_mp_masthead as mh
    from scripts.tools.wechat_mp_seo import sync_article_content_from_body

    banner = tmp_path / "banner.png"
    banner.write_bytes(b"finance-banner")
    cache_key = mh.banner_cache_key(banner)
    cache_file = tmp_path / "upload_cache.json"
    cache_file.write_text(
        json.dumps({"urls": {cache_key: "https://mmbiz.qpic.cn/test/banner"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(mh, "DEFAULT_BANNER_PATH", banner)
    monkeypatch.setattr(mh, "UPLOAD_CACHE_PATH", cache_file)
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_product.footer_product_enabled",
        lambda: False,
    )
    def fake_short_drama(article, *, kind):
        out = dict(article)
        out["content"] += '<mp-common-cpsad data-adtype="short-play"></mp-common-cpsad>'
        return out

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_short_drama.attach_short_drama",
        fake_short_drama,
    )
    article = {
        "body_text": "> 盘面速览\n\n指数震荡。\n\n本文为作者个人投资日记。",
        "content": "<p>old</p>",
    }
    out = sync_article_content_from_body(article, kind="market")
    assert "https://mmbiz.qpic.cn/test/banner" in out["content"]
    assert "<img " in out["content"]
    assert out["content"].endswith("</mp-common-cpsad>")


def test_commerce_digest_and_hashtags() -> None:
    base = "窄台面对照。（文内有合作推广）"
    out = enrich_digest(base, "commerce", edition="guide")
    assert "租屋" in out or "小家电" in out
    tags = recommended_hashtags("commerce", edition="guide")
    assert "租房好物" in tags
    assert len(tags) <= HASHTAG_MAX


def test_commerce_title_enrich_prefix() -> None:
    raw = "厨房小电器怎么二选一？"
    out = enrich_title_for_search(raw, "commerce", edition="guide", max_len=32)
    assert title_front_has_search_keywords(out, "commerce") or out.startswith("租屋小电")


def test_append_hashtag_inline_before_disclaimer():
    disc = "本文为作者个人复盘笔记与信息整理，不构成投资建议。市场有风险，决策自负。"
    body = f"> 盘面速览\n\n指数震荡。\n\n{disc}"
    tags = recommended_hashtags("market", edition="close")
    out = append_hashtag_inline_to_body(body, tags)
    assert "发布后加话题" not in out
    assert "#A股" in out
    assert "#收盘复盘" in out
    assert out.index("#A股") < out.index(disc)


def test_recommended_hashtags_hotspot_no_agu():
    tags = recommended_hashtags("hotspot", theme="胚胎案")
    assert "A股" not in tags
    assert tags[0] == "热点观察"
    assert "胚胎案" in tags
    assert len(tags) <= HASHTAG_MAX


def test_recommended_hashtags_tv_review():
    tags = recommended_hashtags("tv_review")
    assert tags[0] == "热点观察"
    assert "A股" not in tags


def test_enrich_digest_hotspot():
    base = "【7月30日 热点评论】暑期档票房——"
    out = enrich_digest(base, "hotspot")
    assert "热点观察" in out or "话题评论" in out
    assert "A股" not in out
    assert len(out) <= DIGEST_MAX


def test_title_sousou_hook_hotspot_entity():
    assert title_sousou_hook_score("伪造结婚证做试管案再起波澜", "hotspot") >= 1
    assert title_sousou_hook_score("A股收盘｜指数震荡", "hotspot") < 0
