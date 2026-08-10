from scripts.tools.wechat_mp_tv_review_article import is_discussion_template_fallback


def test_is_discussion_template_fallback_detects_generic_body() -> None:
    body = (
        "某话题挂上热搜，评论区很快分成两拨。"
        "当成热闹看过即可。"
        "把吵点摊开，比急着下结论更接近真实舆论现场。"
    )
    assert is_discussion_template_fallback(body)


def test_is_discussion_template_fallback_rejects_real_article() -> None:
    body = "8月2日，校园剧《天才女友》开播。胡一天演16岁高一学霸。"
    assert not is_discussion_template_fallback(body)
