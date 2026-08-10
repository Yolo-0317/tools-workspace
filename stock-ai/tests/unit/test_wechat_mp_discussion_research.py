from __future__ import annotations

from scripts.tools.wechat_mp_discussion_research import _event_keywords, _hit_relevant
from scripts.tools.wechat_mp_hotspot_research import ResearchHit


def test_event_keywords_from_trend() -> None:
    topic = {"trend_title": "丈夫出轨做试管，亲友劝原配接受现实"}
    keys = _event_keywords(topic)
    assert "丈夫出轨做试管" in keys or "亲友劝原配接受现实" in keys


def test_hit_relevant_requires_topic_overlap() -> None:
    topic = {"trend_title": "丈夫出轨做试管，亲友劝原配接受现实"}
    keys = _event_keywords(topic)
    ok = ResearchHit(
        title="丈夫出轨做试管，亲友竟劝原配接受现实",
        snippet="上海朱女士发现丈夫伪造结婚证做试管",
        source="k.sina.com.cn",
        url="https://example.com/a",
    )
    bad = ResearchHit(
        title="Anthropic称AI模型误侵机构系统",
        snippet="与婚姻无关的科技新闻",
        source="东财",
        url="https://example.com/b",
    )
    assert _hit_relevant(ok, keys)
    assert not _hit_relevant(bad, keys)
