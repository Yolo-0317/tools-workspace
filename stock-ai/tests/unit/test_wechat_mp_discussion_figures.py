from __future__ import annotations

import pytest

from scripts.tools.wechat_mp_discussion_figures import (
    _is_event_image_url,
    _looks_like_content_photo,
    _is_recommendation_junk_image,
    _normalize_image_url,
    _text_paragraph_indices,
    _pool_rank_key,
    _split_body_paragraphs,
    inject_discussion_figures,
    _content_images_from_html,
)
from scripts.tools.wechat_mp_discussion_research import figure_search_queries


def test_discussion_body_figure_target_defaults_to_three(monkeypatch) -> None:
    from scripts.tools.wechat_mp_discussion_figures import discussion_body_figure_target

    monkeypatch.delenv("WECHAT_MP_DISCUSSION_BODY_FIGURES", raising=False)
    assert discussion_body_figure_target() == 3
    monkeypatch.setenv("WECHAT_MP_DISCUSSION_BODY_FIGURES", "9")
    assert discussion_body_figure_target() == 3


def test_inject_discussion_figures_skips_when_already_present() -> None:
    body = "第一段。\n\n[[fig:discussion/x/still-01.jpg|cap=图源]]\n\n第二段。"
    topic = {"cover_slug": "x", "trend_title": "测试话题"}

    def fake_ensure(_topic, *, max_images=3):
        return [{"rel": "discussion/x/still-02.jpg", "cap": "图源二"}]

    import scripts.tools.wechat_mp_discussion_figures as mod

    orig = mod.ensure_discussion_body_figures
    mod.ensure_discussion_body_figures = fake_ensure
    try:
        out = inject_discussion_figures(body, topic)
        assert "still-02.jpg" in out
        assert "still-01.jpg" not in out
    finally:
        mod.ensure_discussion_body_figures = orig


def test_strip_discussion_figures_removes_markers() -> None:
    from scripts.tools.wechat_mp_discussion_figures import strip_discussion_figures

    body = "第一段。\n\n[[fig:discussion/x/still-01.jpg|cap=图源]]\n\n第二段。"
    out = strip_discussion_figures(body)
    assert "[[fig:" not in out
    assert "第一段" in out and "第二段" in out


def test_is_junk_discussion_figure_detects_qr_and_tv(tmp_path) -> None:
    from PIL import Image
    from scripts.tools.wechat_mp_discussion_figures import (
        _is_junk_discussion_figure,
        _score_discussion_figure,
    )

    qr = tmp_path / "qr.jpg"
    portrait = tmp_path / "portrait.jpg"
    tv = tmp_path / "tv.jpg"
    Image.new("RGB", (400, 400), "white").save(qr)
    Image.effect_noise((800, 600), 80).convert("RGB").save(portrait, quality=80)
    Image.effect_noise((1280, 720), 80).convert("RGB").save(tv, quality=80)

    assert _is_junk_discussion_figure(qr)
    assert _is_junk_discussion_figure(tv)
    assert not _is_junk_discussion_figure(portrait)
    assert _score_discussion_figure(portrait) > 100


def test_distributed_inject_spreads_across_long_body(monkeypatch) -> None:
    from scripts.tools.wechat_mp_discussion_figures import _distributed_inject_para_indices

    idx = _distributed_inject_para_indices(34, 3)
    assert len(idx) == 3
    assert idx[0] >= 4
    assert idx[-1] <= 30
    assert idx[1] - idx[0] >= 5
    assert idx[2] - idx[1] >= 5

    topic = {"cover_slug": "demo-topic", "trend_title": "演示热搜"}

    def fake_ensure(_topic, *, max_images=3):
        return [
            {"rel": "discussion/demo-topic/still-01.jpg", "cap": "图源一"},
            {"rel": "discussion/demo-topic/still-02.jpg", "cap": "图源二"},
            {"rel": "discussion/demo-topic/still-03.jpg", "cap": "图源三"},
        ]

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_discussion_figures.ensure_discussion_body_figures",
        fake_ensure,
    )
    paras = [f"第{i}句正文，用来模拟一句一段的排版。" for i in range(1, 31)]
    body = "\n\n".join(paras)
    out = inject_discussion_figures(body, topic)
    assert out.count("[[fig:") == 3
    paras = _split_body_paragraphs(out)
    fig_idxs = [i for i, p in enumerate(paras) if p.strip().startswith("[[fig:")]
    assert len(fig_idxs) == 3
    assert fig_idxs[0] >= 8
    assert fig_idxs[1] - fig_idxs[0] >= 7
    assert fig_idxs[2] - fig_idxs[1] >= 7
    assert fig_idxs[-1] <= len(paras) - 7
    assert out.count("\n\n") >= 30


def test_inject_discussion_figures_with_mocked_assets(monkeypatch) -> None:
    topic = {"cover_slug": "demo-topic", "trend_title": "演示热搜"}

    def fake_ensure(_topic, *, max_images=3):
        return [
            {"rel": "discussion/demo-topic/still-01.jpg", "cap": "图源：东财（公开报道引用）"},
            {"rel": "discussion/demo-topic/still-02.jpg", "cap": "图源：澎湃（公开报道引用）"},
        ]

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_discussion_figures.ensure_discussion_body_figures",
        fake_ensure,
    )
    body = "\n\n".join(
        [
            "第一段开头。接着两句过渡。",
            "第二段内容。",
            "第三段内容。",
            "第四段内容。",
            "第五段内容。",
            "第六段收尾。",
        ]
    )
    out = inject_discussion_figures(body, topic)
    assert out.count("[[fig:") == 2
    assert "discussion/demo-topic/still-01.jpg" in out


def test_manual_figures_are_used_as_original_illustration_fallback(tmp_path) -> None:
    from PIL import Image
    from scripts.tools import wechat_mp_discussion_figures as mod

    out_dir = tmp_path / "demo-topic"
    out_dir.mkdir()
    Image.effect_noise((800, 600), 100).convert("RGB").save(out_dir / "manual-01.jpg")
    original_root = mod.INLINE_DISCUSSION_ROOT
    mod.INLINE_DISCUSSION_ROOT = tmp_path
    try:
        figures = mod._manual_figure_dicts(out_dir, slug="demo-topic", limit=3)
    finally:
        mod.INLINE_DISCUSSION_ROOT = original_root
    assert figures == [
        {
            "rel": "discussion/demo-topic/manual-01.jpg",
            "cap": "原创新闻插画",
        }
    ]


def test_force_refetch_keeps_generated_cover_when_reports_still_missing(
    tmp_path,
    monkeypatch,
) -> None:
    from PIL import Image
    from scripts.tools import wechat_mp_discussion_figures as mod

    out_dir = tmp_path / "demo-topic"
    out_dir.mkdir()
    cover = out_dir / "cover.jpg"
    Image.effect_noise((900, 383), 100).convert("RGB").save(cover, quality=94)
    monkeypatch.setattr(mod, "INLINE_DISCUSSION_ROOT", tmp_path)
    monkeypatch.setattr(mod, "ensure_discussion_figures", lambda _topic, max_images: [])
    monkeypatch.setattr(mod, "_pick_discussion_cover_source", lambda _out, _topic: None)
    monkeypatch.setenv("WECHAT_MP_DISCUSSION_FIGURES_FORCE", "1")

    result = mod.ensure_discussion_cover(
        {"cover_slug": "demo-topic", "trend_title": "演示事件"}
    )

    assert result == cover


def test_codex_ready_marker_skips_repeated_report_search(tmp_path, monkeypatch) -> None:
    from scripts.tools import wechat_mp_discussion_figures as mod

    out_dir = tmp_path / "demo-topic"
    out_dir.mkdir()
    (out_dir / "codex-images-ready.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(mod, "INLINE_DISCUSSION_ROOT", tmp_path)
    monkeypatch.setattr(
        mod,
        "fetch_discussion_research",
        lambda *_args, **_kwargs: pytest.fail("ready 标记存在时不应重新检索报道"),
    )

    assert mod.ensure_discussion_figures(
        {"cover_slug": "demo-topic", "trend_title": "演示事件"},
        max_images=3,
    ) == []


def test_force_refetch_bypasses_codex_ready_marker(tmp_path, monkeypatch) -> None:
    from scripts.tools import wechat_mp_discussion_figures as mod

    out_dir = tmp_path / "demo-topic"
    out_dir.mkdir()
    (out_dir / "codex-images-ready.json").write_text("{}", encoding="utf-8")
    called: list[bool] = []
    monkeypatch.setattr(mod, "INLINE_DISCUSSION_ROOT", tmp_path)
    monkeypatch.setenv("WECHAT_MP_DISCUSSION_FIGURES_FORCE", "1")
    monkeypatch.setattr(
        mod,
        "fetch_discussion_research",
        lambda *_args, **_kwargs: called.append(True) or [],
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_discussion_research._fetch_news_search_urls",
        lambda *_args, **_kwargs: [],
    )

    mod.ensure_discussion_figures(
        {"cover_slug": "demo-topic", "trend_title": "演示事件"},
        max_images=3,
    )

    assert called == [True]


def test_generated_cover_does_not_suppress_verified_body_photo(
    tmp_path,
    monkeypatch,
) -> None:
    import json
    from pathlib import Path

    from PIL import Image
    from scripts.tools import wechat_mp_discussion_figures as mod

    out_dir = tmp_path / "demo-topic"
    out_dir.mkdir()
    Image.effect_noise((900, 383), 80).convert("RGB").save(out_dir / "cover.jpg")
    Image.effect_noise((800, 600), 70).convert("RGB").save(out_dir / "still-01.jpg")
    Image.effect_noise((800, 600), 60).convert("RGB").save(out_dir / "manual-01.jpg")
    (out_dir / "codex-images-ready.json").write_text("{}", encoding="utf-8")
    (out_dir / "figure_sources.json").write_text(
        json.dumps(
            {
                "still-01.jpg": {
                    "page_title": "武康路积水现场",
                    "page_url": "https://example.com/wukang",
                    "source_name": "现场媒体",
                    "verified": True,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "INLINE_DISCUSSION_ROOT", tmp_path)

    figures = mod.ensure_discussion_body_figures(
        {"cover_slug": "demo-topic", "trend_title": "武康路 积水"},
        max_images=2,
    )

    assert [Path(fig["rel"]).name for fig in figures] == [
        "still-01.jpg",
        "manual-01.jpg",
    ]


def test_figure_caption_uses_verified_source_name() -> None:
    from scripts.tools.wechat_mp_discussion_figures import _figure_caption

    assert (
        _figure_caption({"source_name": "新民晚报", "verified": "true"})
        == "图源：新民晚报现场报道"
    )


def test_legacy_figure_metadata_remains_readable() -> None:
    from scripts.tools.wechat_mp_discussion_figures import _normalize_figure_source

    normalized = _normalize_figure_source(
        {"page_url": "https://example.com/a", "page_title": "同题报道"}
    )

    assert normalized["page_url"] == "https://example.com/a"
    assert normalized["page_title"] == "同题报道"
    assert normalized["verified"] == "false"


def test_source_type_classifies_weibo_and_baidu_news() -> None:
    from scripts.tools.wechat_mp_discussion_figures import _source_type_for_url

    assert _source_type_for_url("https://weibo.com/123/abc") == "weibo"
    assert _source_type_for_url("https://baijiahao.baidu.com/s?id=1") == "baidu_news"
    assert _source_type_for_url("https://www.thepaper.cn/newsDetail_forward_1") == "news"


def test_explicit_no_repost_notice_blocks_automatic_use() -> None:
    from scripts.tools.wechat_mp_discussion_figures import _page_restricts_reuse

    assert _page_restricts_reuse("未经正式授权严禁转载本文，侵权必究")
    assert not _page_restricts_reuse("欢迎转发本文链接，图片来自现场采访。")


def test_verified_figure_source_extracts_site_and_publish_time() -> None:
    from scripts.tools.wechat_mp_discussion_figures import _verified_figure_source

    html = """
    <meta property="og:site_name" content="新民晚报">
    <meta property="article:published_time" content="2026-08-09T18:30:00+08:00">
    """
    source = _verified_figure_source(
        page_url="https://paper.xinmin.cn/article/1",
        image_url="https://img.example.com/wukang.jpg",
        html=html,
        hit=None,
    )

    assert source["source_name"] == "新民晚报"
    assert source["published_at"] == "2026-08-09T18:30:00+08:00"
    assert source["source_type"] == "news"
    assert source["verified"] == "true"
    assert source["caption"] == "图源：新民晚报现场报道"


def test_ordinary_weibo_page_is_not_automatically_verified() -> None:
    from scripts.tools.wechat_mp_discussion_figures import _verified_figure_source

    source = _verified_figure_source(
        page_url="https://weibo.com/123456/abc",
        image_url="https://wx1.sinaimg.cn/large/a.jpg",
        html='<meta property="og:site_name" content="微博">',
        hit=None,
    )

    assert source["source_type"] == "weibo"
    assert source["verified"] == "false"


def test_downloaded_figure_persists_traceable_source_metadata(
    tmp_path,
    monkeypatch,
) -> None:
    import json

    from PIL import Image
    from scripts.tools import wechat_mp_discussion_figures as mod
    from scripts.tools.wechat_mp_hotspot_research import ResearchHit

    page_url = "https://paper.xinmin.cn/article/1"
    image_url = "https://pic.rmb.bdstatic.com/news/wukang.jpg"
    html = f"""
    <title>武康路积水现场报道</title>
    <meta name="description" content="武康路在强降雨后出现短时积水，现场人员正在排水处置并引导市民安全通行。">
    <meta property="og:site_name" content="新民晚报">
    <meta property="article:published_time" content="2026-08-09T18:30:00+08:00">
    <img src="{image_url}">
    """
    monkeypatch.setattr(mod, "INLINE_DISCUSSION_ROOT", tmp_path)
    monkeypatch.setattr(
        mod,
        "fetch_discussion_research",
        lambda *_args, **_kwargs: [
            ResearchHit(
                title="武康路积水现场报道",
                snippet="武康路在强降雨后出现短时积水，现场人员正在排水处置。",
                source="新民晚报",
                url=page_url,
            )
        ],
    )
    monkeypatch.setattr(mod, "_fetch_html", lambda _url: html)
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_discussion_research._fetch_news_search_urls",
        lambda *_args, **_kwargs: [],
    )

    def fake_download(_url, dest, *, referer="") -> bool:
        Image.effect_noise((800, 600), 80).convert("RGB").save(dest, quality=70)
        return True

    monkeypatch.setattr(mod, "_download_image", fake_download)
    monkeypatch.setattr(mod, "_is_junk_discussion_figure", lambda _path: False)
    monkeypatch.setattr(mod, "_score_discussion_figure", lambda _path, page_url="": 500.0)

    figures = mod.ensure_discussion_figures(
        {"cover_slug": "wukang", "trend_title": "武康路 积水"},
        max_images=1,
    )

    metadata = json.loads(
        (tmp_path / "wukang" / "figure_sources.json").read_text(encoding="utf-8")
    )["still-01.jpg"]
    assert figures[0]["cap"] == "图源：新民晚报现场报道"
    assert metadata["image_url"] == image_url
    assert metadata["source_type"] == "news"
    assert metadata["source_name"] == "新民晚报"
    assert metadata["published_at"] == "2026-08-09T18:30:00+08:00"
    assert metadata["verified"] == "true"


def test_restricted_page_is_skipped_before_image_download(tmp_path, monkeypatch) -> None:
    from scripts.tools import wechat_mp_discussion_figures as mod
    from scripts.tools.wechat_mp_hotspot_research import ResearchHit

    page_url = "https://www.jfdaily.com/article/1"
    html = """
    <title>武康路积水现场报道</title>
    <meta name="description" content="武康路在强降雨后出现短时积水，现场人员正在进行排水处置。">
    <meta property="og:site_name" content="上观新闻">
    <p>未经正式授权严禁转载本文，侵权必究。</p>
    <img src="https://img.example.com/news/wukang.jpg">
    """
    monkeypatch.setattr(mod, "INLINE_DISCUSSION_ROOT", tmp_path)
    monkeypatch.setattr(
        mod,
        "fetch_discussion_research",
        lambda *_args, **_kwargs: [
            ResearchHit(
                title="武康路积水现场报道",
                snippet="武康路在强降雨后出现短时积水，现场人员正在进行排水处置。",
                source="上观新闻",
                url=page_url,
            )
        ],
    )
    monkeypatch.setattr(mod, "_fetch_html", lambda _url: html)
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_discussion_research._fetch_news_search_urls",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        mod,
        "_download_image",
        lambda *_args, **_kwargs: pytest.fail("受限页面不应下载图片"),
    )
    monkeypatch.setattr(mod, "_supplement_missing_figures", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(mod, "_borrow_stills_from_pool", lambda *_args, **_kwargs: [])

    assert mod.ensure_discussion_figures(
        {"cover_slug": "wukang", "trend_title": "武康路积水"},
        max_images=1,
    ) == []


def test_figure_queries_add_scene_and_date_variants() -> None:
    queries = figure_search_queries(
        {"trend_title": "武康路积水", "event_date": "2026-08-09"}
    )

    assert "武康路积水 现场" in queries
    assert "武康路积水 2026-08-09" in queries
    assert "武康路积水 图片" in queries


def test_news_search_prioritizes_weibo_before_baidu(monkeypatch) -> None:
    from scripts.tools import wechat_mp_discussion_research as research

    monkeypatch.setattr(research, "_cached_news_urls", lambda _query: [])
    monkeypatch.setattr(
        research,
        "_fetch_weibo_search_urls",
        lambda _query, *, limit: ["https://weibo.com/media/1"],
        raising=False,
    )
    monkeypatch.setattr(
        research,
        "_fetch_baidu_news_urls",
        lambda _query, *, limit: ["https://baijiahao.baidu.com/s?id=1"],
    )
    monkeypatch.setattr(research, "_fetch_sogou_news_urls", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(research, "_fetch_so_news_urls", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(research, "_fetch_baidu_web_urls", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(research, "_remember_news_urls", lambda *_args, **_kwargs: None)

    urls = research._fetch_news_search_urls("武康路积水", limit=4)

    assert urls == [
        "https://weibo.com/media/1",
        "https://baijiahao.baidu.com/s?id=1",
    ]


def test_paragraph_blocks_skips_figure_lines() -> None:
    paragraphs = _split_body_paragraphs("段落一。\n\n[[fig:x|]]\n\n段落二。")
    text_idxs = _text_paragraph_indices(paragraphs)
    assert text_idxs == [0, 2]


def test_recommendation_junk_image_detected() -> None:
    assert _is_recommendation_junk_image(
        "https://dingyue.ws.126.net/2026/08/01/QTng3MCdRrBJS0hZM3aKmy4TKS9rVRqr0mrjn2b92.jpg"
    )
    assert not _is_recommendation_junk_image(
        "https://dingyue.ws.126.net/2026/0801/3f20bab0j00tj2lne0010d000hk00omm.jpg"
    )


def test_china_com_utuku_image_host_recognized() -> None:
    url = "https://img1.utuku.imgcdc.com/650x0/news/20260803/abc.jpg"
    assert _is_event_image_url(url)
    upgraded = _normalize_image_url(url)
    assert "/1200x0/" in upgraded


def test_pool_rank_prefers_article_inline_over_junk() -> None:
    from pathlib import Path

    good = (90_000, Path("a.jpg"), "cap", "https://dingyue.ws.126.net/2026/0801/abc.jpg", 0, 1)
    junk = (900_000, Path("b.jpg"), "cap", "https://dingyue.ws.126.net/2026/08/01/QTng.jpg", 0, 0)
    ranked = sorted([junk, good], key=_pool_rank_key)
    assert ranked[0] == good


def test_baidu_and_toutiao_image_hosts_recognized() -> None:
    baidu = "https://pic.rmb.bdstatic.com/news/2026/0805/abc.jpg"
    toutiao = "https://p3.toutiaoimg.com/img/abc~noop.image"
    assert _is_event_image_url(baidu)
    assert _is_event_image_url(toutiao)


def test_looks_like_content_photo_on_news_paths() -> None:
    url = "https://example.com/news/2026/08/photo_large.jpg"
    assert _looks_like_content_photo(url)
    assert _is_event_image_url(url, from_news_page=True)


def test_lazy_img_data_src_parsed() -> None:
    html = (
        '<img data-src="https://nimg.ws.126.net/?url=https://dingyue.ws.126.net/2026/0801/abc.jpg" />'
    )
    page = "https://news.163.com/article/123.html"
    imgs = _content_images_from_html(html, page)
    assert imgs


def test_figure_search_queries_splits_title() -> None:
    topic = {"trend_title": "官方通报赛格商场坠亡事件"}
    queries = figure_search_queries(topic)
    assert "官方通报赛格商场坠亡事件" in queries
    assert any("赛格" in q or "坠亡" in q for q in queries)


def test_it_figure_fallback_queries_for_data_deletion() -> None:
    from scripts.tools.wechat_mp_discussion_figures import (
        _it_figure_fallback_queries,
        _topic_allows_it_figure_fallback,
    )

    topic = {"trend_title": "员工用代码17小时删光公司89TB数据"}
    assert _topic_allows_it_figure_fallback(topic)
    queries = _it_figure_fallback_queries(topic)
    assert any("删库" in q or "程序员" in q for q in queries)


def test_offtopic_page_title_blocks_entertainment() -> None:
    from scripts.tools.wechat_mp_discussion_figures import _offtopic_page_title

    topic = {"trend_title": "员工用代码17小时删光公司89TB数据"}
    keywords = ["删光", "程序员", "数据"]
    assert _offtopic_page_title("Netflix韩剧《xxx》定档", topic, keywords)
    assert not _offtopic_page_title("程序员删库获刑五年", topic, keywords)


def test_page_relevant_rejects_unrelated_article() -> None:
    from scripts.tools.wechat_mp_discussion_research import ResearchHit
    from scripts.tools.wechat_mp_discussion_figures import _page_relevant_for_figures

    topic = {"trend_title": "员工用代码17小时删光公司89TB数据"}
    keywords = ["删光", "程序员", "数据", "工程师"]
    hit = ResearchHit(
        title="勇士主场大胜湖人 NBA季后赛",
        snippet="篮球比赛精彩瞬间",
        source="sina.com.cn",
        url="https://example.com/nba",
    )
    ok, _ = _page_relevant_for_figures(
        topic, page_url=hit.url, html=None, hit=hit, keywords=keywords
    )
    assert ok is False


def test_it_fallback_not_for_general_social_topic() -> None:
    from scripts.tools.wechat_mp_discussion_figures import (
        _it_figure_fallback_queries,
        _topic_allows_it_figure_fallback,
    )

    topic = {"trend_title": "青岛大学宿管大爷热射病去世"}
    assert not _topic_allows_it_figure_fallback(topic)
    assert _it_figure_fallback_queries(topic) == []


def test_strict_figure_page_rejects_old_unrelated_case() -> None:
    from scripts.tools.wechat_mp_discussion_research import ResearchHit
    from scripts.tools.wechat_mp_discussion_figures import _strict_figure_page_relevant

    topic = {"trend_title": "员工用代码17小时删光公司89TB数据"}
    keywords = ["删光", "程序员", "数据", "89TB"]
    hit = ResearchHit(
        title="女经理不满被资遣 15分钟删光公司1.4万笔研发心血",
        snippet="旧案",
        source="163.com",
        url="https://example.com/old",
    )
    assert not _strict_figure_page_relevant(topic, hit, keywords)


def test_video_news_frame_rejects_1080x720() -> None:
    from scripts.tools.wechat_mp_discussion_figures import _is_video_news_frame

    assert _is_video_news_frame(1080, 720)
    assert _is_video_news_frame(1280, 720)
    assert _is_video_news_frame(1380, 704)
    assert not _is_video_news_frame(800, 600)


def test_embedded_unrelated_photo_rejected() -> None:
    from scripts.tools.wechat_mp_discussion_figures import _is_embedded_unrelated_photo

    assert _is_embedded_unrelated_photo(1127, 942)
    assert not _is_embedded_unrelated_photo(782, 721)


def test_collect_page_figure_trials_skips_early_video_frames(tmp_path, monkeypatch) -> None:
    from pathlib import Path

    from PIL import Image
    from scripts.tools.wechat_mp_discussion_figures import _collect_page_figure_trials

    topic = {"trend_title": "员工用代码17小时删光公司89TB数据"}
    good = tmp_path / "good-fixture.jpg"
    Image.effect_noise((800, 600), 80).convert("RGB").save(good, quality=80)
    urls = [
        "https://example.com/video1.jpg",
        "https://example.com/video2.jpg",
        "https://example.com/video3.jpg",
        "https://example.com/video4.jpg",
        "https://example.com/video5.jpg",
        "https://example.com/video6.jpg",
        "https://example.com/good.jpg",
    ]

    def fake_download(url: str, dest: Path, *, referer: str = "") -> bool:
        if url.endswith("good.jpg"):
            dest.write_bytes(good.read_bytes())
            return True
        dest.write_bytes(b"x" * 25000)
        return True

    def fake_junk(path: Path) -> bool:
        return path.stat().st_size < 30000

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_discussion_figures._download_image",
        fake_download,
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_discussion_figures._is_junk_discussion_figure",
        fake_junk,
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_discussion_figures._score_discussion_figure",
        lambda _p, page_url="": 500.0,
    )
    out = tmp_path / "trials"
    out.mkdir(exist_ok=True)
    trials = _collect_page_figure_trials(
        topic=topic,
        page_url="https://www.163.com/dy/article/x.html",
        candidates=urls,
        out_dir=out,
        pool_name="t_",
        cap="cap",
        page_title="title",
        rel_score=3,
        page_idx=0,
        host_boost=0,
        used_urls=set(),
    )
    assert len(trials) == 1
    from scripts.tools.wechat_mp_discussion_figures import _is_video_news_frame

    assert _is_video_news_frame(1080, 720)
    assert _is_video_news_frame(1280, 720)
    assert _is_video_news_frame(1380, 704)
    assert not _is_video_news_frame(800, 600)


def test_stock_matrix_illustration_rejected(tmp_path) -> None:
    from PIL import Image
    from scripts.tools.wechat_mp_discussion_figures import (
        _is_generic_stock_illustration,
        _is_junk_discussion_figure,
    )

    p = tmp_path / "matrix.jpg"
    Image.new("RGB", (800, 600), (10, 150, 30)).save(p, quality=90)
    assert _is_generic_stock_illustration(p)
    assert _is_junk_discussion_figure(p)


def test_tv_broadcast_aspect_ratio_rejected(tmp_path) -> None:
    from PIL import Image
    from scripts.tools.wechat_mp_discussion_figures import _is_junk_discussion_figure

    p = tmp_path / "broadcast.jpg"
    Image.effect_noise((1280, 720), 80).convert("RGB").save(p, quality=80)
    assert _is_junk_discussion_figure(p)


def test_figure_fingerprint_dedupes_byte_identical_stills() -> None:
    from pathlib import Path

    from scripts.tools.wechat_mp_discussion_figures import (
        _dedupe_figure_paths,
        _figure_fingerprint,
    )

    root = Path(__file__).resolve().parents[2]
    d = root / "assets/wechat_mp/inline-discussion/员工用代码17小时删光公司89tb数据"
    p1 = d / "still-02.jpg"
    p2 = d / "still-04.jpg"
    if p1.is_file() and p2.is_file():
        assert _figure_fingerprint(p1) == _figure_fingerprint(p2)
        assert len(_dedupe_figure_paths([p1, p2])) == 1
