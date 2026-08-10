from __future__ import annotations

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


def test_is_junk_discussion_figure_detects_qr_and_tv() -> None:
    from pathlib import Path

    from scripts.tools.wechat_mp_discussion_figures import (
        _is_junk_discussion_figure,
        _score_discussion_figure,
    )

    root = Path(__file__).resolve().parents[2]
    slug_dir = root / "assets" / "wechat_mp" / "inline-discussion" / "婚外试管丈夫发声明患"
    qr = slug_dir / "still-01.jpg"
    portrait = slug_dir / "still-02.jpg"
    tv = slug_dir / "still-03.jpg"
    if qr.is_file():
        assert _is_junk_discussion_figure(qr)
    if tv.is_file():
        assert _is_junk_discussion_figure(tv)
    if portrait.is_file():
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
    assert fig_idxs[0] > 10
    assert fig_idxs[-1] < len(paras) - 8
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


def test_collect_page_figure_trials_skips_early_video_frames(monkeypatch) -> None:
    from pathlib import Path

    from scripts.tools.wechat_mp_discussion_figures import _collect_page_figure_trials

    topic = {"trend_title": "员工用代码17小时删光公司89TB数据"}
    root = Path(__file__).resolve().parents[2]
    good = root / "assets/wechat_mp/inline-discussion/婚外试管丈夫发声明患/still-02.jpg"
    if not good.is_file():
        return
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
    out = Path("/tmp/fig_collect_test")
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


def test_stock_matrix_illustration_rejected() -> None:
    from pathlib import Path

    from scripts.tools.wechat_mp_discussion_figures import (
        _is_generic_stock_illustration,
        _is_junk_discussion_figure,
    )

    root = Path(__file__).resolve().parents[2]
    p = root / "assets/wechat_mp/inline-discussion/员工用代码17小时删光公司89tb数据/still-02.jpg"
    if p.is_file():
        assert _is_generic_stock_illustration(p)
        assert _is_junk_discussion_figure(p)


def test_tv_broadcast_aspect_ratio_rejected() -> None:
    from pathlib import Path

    from scripts.tools.wechat_mp_discussion_figures import _is_junk_discussion_figure

    root = Path(__file__).resolve().parents[2]
    p = root / "assets/wechat_mp/inline-discussion/员工用代码17小时删光公司89tb数据/still-01.jpg"
    if p.is_file():
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
