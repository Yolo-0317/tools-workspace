"""热点深评稿选题与标题。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_hotspot_article import (
    HotspotTopic,
    _parse_llm_pick_index,
    _theme_bucket,
    build_hotspot_title,
    hotspot_topic_as_discussion,
    hotspot_topic_count,
    pick_hotspot_topics,
)


def test_hotspot_topic_count_default_one():
    assert hotspot_topic_count() == 1


def test_theme_bucket_geo():
    assert _theme_bucket("霍尔木兹海峡暂时关闭") == "geo"


def test_theme_bucket_space():
    assert _theme_bucket("海上回收火箭成功") == "space"


def test_pick_hotspot_topics_single_default(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_HOTSPOT_LLM_PICK", "0")
    items = [
        {"title": "霍尔木兹海峡暂时关闭", "href": "a", "attention_score": 5000.0},
        {"title": "算力卡采购额预测", "href": "b", "attention_score": 3000.0},
        {"title": "海上回收火箭成功", "href": "c", "attention_score": 1000.0},
    ]
    topics = pick_hotspot_topics(items, limit=1, trade_label="7月10日收盘")
    assert len(topics) == 1
    assert topics[0].item["title"] == "霍尔木兹海峡暂时关闭"


def test_parse_llm_pick_index():
    assert _parse_llm_pick_index("选题=3，理由：航天链映射清晰", max_n=5) == 3
    assert _parse_llm_pick_index("2", max_n=5) == 2


def test_reflow_hotspot_body_splits_merged_section():
    from scripts.tools.wechat_mp_hotspot_polish import reflow_hotspot_body

    raw = ">海峡通行受阻伊朗方面称海峡暂时关闭，油服板块分化。"
    out = reflow_hotspot_body(raw)
    assert "> " not in out
    assert "伊朗方面称海峡暂时关闭" in out


def test_sanitize_hotspot_reader_meta_strips_path_opening():
    from scripts.tools.wechat_mp_hotspot_polish import sanitize_hotspot_reader_meta

    raw = "\n".join(
        [
            "本篇不复盘快讯清单，只围绕周末霍尔木兹海峡通行受阻这一单一变量，"
            "沿事件—油价—板块映射—可验证指标递进阅读；"
            "下文先交代选题逻辑，再拆解传导与向后观察点。",
            "",
            "> 为啥盯这条",
            "霍尔木兹海峡暂闭直接牵动油运与油服定价预期。",
            "",
            "> 海峡通行受阻",
            "先说事实：伊朗方面称海峡暂时关闭。",
        ]
    )
    out = sanitize_hotspot_reader_meta(raw)
    assert "递进阅读" not in out
    assert "下文先" not in out
    assert "单一变量" not in out
    assert "快讯清单" not in out
    assert "> 为啥盯这条" not in out
    assert "霍尔木兹海峡暂闭" in out


def test_strip_llm_process_leak_removes_prompt_echo():
    from scripts.tools.wechat_mp_hotspot_polish import (
        sanitize_hotspot_reader_meta,
        strip_llm_process_leak,
        strip_llm_process_leak_html,
    )

    leak = (
        '*Wait-theusersaidNOTtowritedataacquisitiongapslike"".Ineedtoremovethatlastnoteentirely-'
        'theusersaid"只输出正文Markdown，'
    )
    raw = "\n".join(
        [
            "> 为啥盯这条",
            "仿制药关税预期会影响原料药与制剂出口定价。",
            "",
            "---*说明：指数层面具体涨跌幅因数据源暂不可用，正文以板块强弱关系为观察框架。",
            leak,
            "不要解释\"andalsoforbiddentypelanguage.Letmeoutputfinalcleanversiononly.",
            "",
            "> 先说事实",
            "特朗普计划自2028年起征收仿制药关税。",
            "这是泄漏后的重复终稿，不应保留。",
        ]
    )
    stripped = strip_llm_process_leak(raw)
    assert "Wait-theuser" not in stripped
    assert "只输出正文" not in stripped
    assert "数据源暂不可用" not in stripped
    assert "重复终稿" not in stripped
    assert "仿制药关税预期" in stripped
    out = sanitize_hotspot_reader_meta(raw)
    assert "Wait-theuser" not in out
    assert "只输出正文Markdown" not in out
    assert "仿制药关税预期" in out
    assert "特朗普计划自2028" not in out

    html = (
        '<p style="x">文中个股仅作行情对照样本，非推荐名单；市场有风险，决策须独立判断。</p>'
        f"<p>{leak}</p>"
        "<p>不要解释&quot;andalsoforbiddentypelanguage.Letmeoutputfinalcleanversiononly.</p>"
        "<p>重复终稿开篇不应保留。</p>"
        "<p>若这篇对你有用，欢迎点文章下方「推荐」，也方便推给同样在复盘的朋友。</p>"
        "<p>本文为作者个人市场信息整理与复盘笔记，非证券投资咨询、非理财推介，不构成投资建议；市场有风险，决策自负。</p>"
    )
    cleaned = strip_llm_process_leak_html(html)
    assert "Wait-theuser" not in cleaned
    assert "重复终稿" not in cleaned
    assert "欢迎点文章下方" in cleaned
    assert "本文为作者个人" in cleaned
    assert "决策须独立判断" in cleaned


def test_sanitize_hotspot_selection_leak_strips_editorial_process():
    from scripts.tools.wechat_mp_hotspot_polish import sanitize_hotspot_selection_leak

    raw = "\n".join(
            [
                "> 为啥盯这条",
                "在候选五条中，霍尔木兹海峡暂闭直接触及全球原油海运瓶颈；"
            "相较「戴高乐」号返港等边际缓和信号，或阿曼会谈等外交缓冲，海峡关闭属于硬约束。",
            "",
            "> 海峡通行受阻",
            "先说事实：伊朗方面称海峡暂时关闭。",
        ]
    )
    out = sanitize_hotspot_selection_leak(raw)
    assert "候选五条" not in out
    assert "相较「戴高乐」" not in out
    assert "霍尔木兹海峡暂闭" in out or "全球原油海运瓶颈" in out


def test_reflow_hotspot_why_section_glued():
    from scripts.tools.wechat_mp_hotspot_polish import reflow_hotspot_body

    raw = "为什么选这一题霍尔木兹海峡承担全球原油海运的重要通道职能，通行中断或延误会直接抬升运费。"
    out = reflow_hotspot_body(raw)
    assert "为啥盯这条" not in out
    assert "霍尔木兹海峡承担" in out


def test_reflow_hotspot_why_section_glued_with_gt():
    from scripts.tools.wechat_mp_hotspot_polish import reflow_hotspot_body

    raw = ">为什么选这一题霍尔木兹海峡承载全球原油海运的关键流量"
    out = reflow_hotspot_body(raw)
    assert "为啥盯这条" not in out
    assert "霍尔木兹海峡承载" in out


def test_reflow_hotspot_why_section():
    from scripts.tools.wechat_mp_hotspot_polish import reflow_hotspot_body

    raw = ">为什么选这一题五条候选同属中东地缘。"
    out = reflow_hotspot_body(raw)
    assert "为啥盯这条" not in out
    assert "五条候选" not in out


def test_reflow_hotspot_keeps_public_fact_with_numbered_candidates_word() -> None:
    from scripts.tools.wechat_mp_hotspot_polish import reflow_hotspot_body

    raw = "公开名单显示，五条候选线路都经过同一片施工区域。"

    assert reflow_hotspot_body(raw) == raw


def test_reflow_hotspot_strips_markdown_bold() -> None:
    from scripts.tools.wechat_mp_hotspot_polish import reflow_hotspot_body, strip_markdown_bold

    raw = "**真正卡住的，往往不是缺一部能播的戏。**\n\n下一段。"
    assert strip_markdown_bold(raw.split("\n\n")[0]) == "真正卡住的，往往不是缺一部能播的戏。"
    out = reflow_hotspot_body(raw)
    assert "**" not in out


def test_reflow_hotspot_layout_keeps_highlight_control_line_standalone() -> None:
    from scripts.tools.wechat_mp_hotspot_polish import reflow_hotspot_layout

    body = (
        "前一段交代已经发生的事实。"
        "\n\n[[hl:法院判新郎新娘承担40%的赔偿责任。]]"
        "\n\n后一段解释为什么组织者也要承担责任。"
    )

    out = reflow_hotspot_layout(body)

    assert "\n\n[[hl:法院判新郎新娘承担40%的赔偿责任。]]\n\n" in out


def test_sanitize_news_reader_meta_keeps_rich_control_line_standalone() -> None:
    from scripts.tools.wechat_mp_news_article import _sanitize_news_reader_meta

    raw = (
        "前文需要清洗。\n\n"
        "[[hl:法院判新郎新娘承担40%的赔偿责任。]]\n\n"
        "后文继续展开。"
    )

    out = _sanitize_news_reader_meta(raw)

    assert "\n\n[[hl:法院判新郎新娘承担40%的赔偿责任。]]\n\n" in out
    assert out.startswith("前文需要清洗")
    assert out.endswith("后文继续展开")


def test_hotspot_title_suffix_pool_oral():
    from scripts.tools.wechat_mp_hotspot_article import (
        _HOTSPOT_STOCK_SUFFIXES,
        _HOTSPOT_TITLE_SUFFIXES,
        _pick_hotspot_suffix,
    )

    assert len(_HOTSPOT_TITLE_SUFFIXES) >= 8
    assert all(s.endswith("？") for s in _HOTSPOT_TITLE_SUFFIXES)
    assert all(s.endswith("？") for s in _HOTSPOT_STOCK_SUFFIXES)
    picked = {_pick_hotspot_suffix(h, _HOTSPOT_TITLE_SUFFIXES) for h in ("霍尔木兹", "返港", "火箭", "航母", "以伊")}
    assert len(picked) >= 2


def test_build_hotspot_title_single_topic():
    topics = [
        HotspotTopic(
            item={
                "title": "海上回收火箭成功",
                "matched_stock_name": "中国卫星",
                "matched_stock_code": "600118",
            },
            bucket="space",
            score=1.0,
            section_title="海上回收火箭成功",
        ),
    ]
    title = build_hotspot_title(topics)
    assert len(title) <= 32
    assert "中国卫星" in title or "火箭" in title or "热点" in title


def test_build_hotspot_title_uses_concrete_hook_when_viral_mode_is_on(monkeypatch) -> None:
    import scripts.tools.wechat_mp_hotspot_article as hotspot

    monkeypatch.setenv("WECHAT_MP_TITLE_VIRAL_MODE", "1")
    monkeypatch.setattr(
        hotspot,
        "llm_build_hotspot_title",
        lambda **_: "董明珠任校长，格力技校能改命吗？",
    )
    topics = [
        HotspotTopic(
            item={"title": "董明珠任格力技校校长"},
            bucket="other",
            score=1.0,
            section_title="董明珠任格力技校校长",
        )
    ]

    assert hotspot.build_hotspot_title(topics) == "董明珠当校长，技校生毕业真能进格力吗？"


def test_topic_section_title_v_reversal():
    from scripts.tools.wechat_mp_hotspot_article import _topic_section_title

    item = {"title": "科技股早盘上演V型反转 跌停潮后半导体领涨反弹"}
    assert _topic_section_title(item) == "科创50深V反转，半导体链"


def test_build_hotspot_title_v_reversal_hook():
    topics = [
        HotspotTopic(
            item={"title": "科技股早盘上演V型反转 跌停潮后半导体领涨反弹"},
            bucket="tech",
            score=1.0,
            section_title="科创50深V反转，半导体链",
        ),
    ]
    title = build_hotspot_title(topics)
    assert len(title) <= 32
    assert "深V" in title or "反转" in title
    assert title.count("A股") <= 1
    assert "A股A股" not in title


def test_build_hotspot_title_no_duplicate_agu():
    topics = [
        HotspotTopic(
            item={"title": "央企密集增持、监管座谈护航！A股稳市机制托底市场"},
            bucket="policy_rescue",
            score=1.0,
            section_title="央企密集增持、监管座谈护航！A股稳市",
        ),
    ]
    title = build_hotspot_title(topics)
    assert title.count("A股") <= 1
    assert "A股A股" not in title


def test_build_hotspot_title_no_dangling_return_verb():
    topics = [
        HotspotTopic(
            item={"title": '"戴高乐"号航母从中东返回法国'},
            bucket="geo",
            score=1.0,
            section_title='"戴高乐"号航母从中东返回法国',
        ),
    ]
    title = build_hotspot_title(topics)
    assert len(title) <= 32
    assert title.endswith("？")
    assert "返港" in title or "返回法国" in title or "返法" in title


def test_build_hotspot_title_geo_no_mid_name_cut():
    from scripts.tools.wechat_mp_hotspot_article import _topic_section_title

    item = {
        "title": "以色列国防部长：伊朗方面企图针对内塔尼亚胡发动袭击",
    }
    section = _topic_section_title(item)
    assert section == "中东局势再升温"
    topics = [
        HotspotTopic(
            item=item,
            bucket="geo",
            score=1.0,
            section_title=section,
        ),
    ]
    title = build_hotspot_title(topics)
    assert len(title) <= 32
    assert "内塔" not in title or "内塔尼亚胡" in title
    assert "：" not in title.split("｜", 1)[-1] or title.startswith("热点深评｜")
    assert "中东" in title or "热点深评" in title
    assert title.endswith("？")


def test_hotspot_topic_as_discussion_carries_research_urls() -> None:
    topic = HotspotTopic(
        item={
            "title": "笔试第一称被第二名花钱劝弃考",
            "web_research": [{"url": "https://news.163.com/a/1.html", "title": "报道"}],
        },
        bucket="other",
        score=1.0,
        section_title="笔试第一",
    )
    d = hotspot_topic_as_discussion(topic)
    assert d["trend_title"] == "笔试第一称被第二名花钱劝弃考"
    assert d["from_trend"] is True
    assert "https://news.163.com/a/1.html" in d["research_urls"]
    assert d["cover_slug"]


def test_hotspot_prompt_with_role_places_role_before_kind_and_facts() -> None:
    from scripts.tools.wechat_mp_hotspot_article import _hotspot_prompt_with_role

    prompt = _hotspot_prompt_with_role(
        kind_label="社会热点深评",
        prompt="【联网事实】某公开事实\n\n## 写作要求\n只写已核验事实",
    )

    assert prompt.index("## 账号角色卡（最先遵守）") < prompt.index(
        "## 稿型任务：社会热点深评"
    )
    assert prompt.index("## 稿型任务：社会热点深评") < prompt.index("【联网事实】")


def test_hotspot_rewrite_prompt_keeps_account_role_card(monkeypatch) -> None:
    from scripts.tools import wechat_mp_hotspot_article as hotspot

    captured: list[str] = []
    monkeypatch.setattr(hotspot, "is_wechat_mp_llm_configured", lambda: True)
    monkeypatch.setattr(
        hotspot,
        "call_wechat_mp_llm",
        lambda messages, **_: captured.append(messages[-1]["content"])
        or ("正文。" * 900),
    )

    hotspot._rewrite_trends_hotspot_against_references(
        "初稿。" * 900,
        reference_block="参考报道",
    )

    assert "## 账号角色卡（最先遵守）" in captured[0]
    assert captured[0].index("## 账号角色卡（最先遵守）") < captured[0].index(
        "【参考文章】"
    )


def test_finance_hotspot_rewrite_prompt_keeps_account_role_card(monkeypatch) -> None:
    from scripts.tools import wechat_mp_hotspot_article as hotspot

    captured: list[str] = []
    monkeypatch.setattr(hotspot, "is_wechat_mp_llm_configured", lambda: True)
    monkeypatch.setattr(
        hotspot,
        "call_wechat_mp_llm",
        lambda messages, **_: captured.append(messages[-1]["content"])
        or ("正文。" * 900),
    )

    hotspot._rewrite_hotspot_against_references(
        "初稿。" * 900,
        reference_block="参考报道",
        trade_label="8月18日收盘",
    )

    assert "## 账号角色卡（最先遵守）" in captured[0]
    assert captured[0].index("## 账号角色卡（最先遵守）") < captured[0].index(
        "【参考文章】"
    )


def test_social_hotspot_generation_prompt_keeps_account_role_card(monkeypatch) -> None:
    from scripts.tools import wechat_mp_hotspot_article as hotspot

    topic = HotspotTopic(
        item={"title": "普通人的公共事件", "web_reference_block": ""},
        bucket="other",
        score=1.0,
        section_title="普通人的公共事件",
    )
    captured: list[str] = []
    monkeypatch.setattr(hotspot, "_build_context_blob", lambda *_, **__: "【联网事实】公开事实")
    monkeypatch.setattr(hotspot, "is_wechat_mp_llm_configured", lambda: True)
    monkeypatch.setattr(hotspot, "_hotspot_llm_max_attempts", lambda: 1)
    monkeypatch.setattr(hotspot, "_hotspot_body_usable", lambda *_, **__: True)
    monkeypatch.setattr(
        hotspot,
        "call_wechat_mp_llm",
        lambda messages, **_: captured.append(messages[-1]["content"])
        or ("正文。" * 900),
    )

    hotspot._generate_trends_hotspot_body([topic], trade_label="8月18日", edition="close")

    prompt = captured[0]
    assert prompt.count("## 账号角色卡（最先遵守）") == 1
    assert prompt.index("## 账号角色卡（最先遵守）") < prompt.index("【联网事实】")


def test_finance_hotspot_generation_prompt_keeps_account_role_card(monkeypatch) -> None:
    from datetime import date

    from scripts.tools import wechat_mp_hotspot_article as hotspot

    topic = HotspotTopic(
        item={"title": "某行业出现变化", "web_reference_block": ""},
        bucket="other",
        score=1.0,
        section_title="某行业出现变化",
    )
    captured: list[str] = []
    monkeypatch.setattr(hotspot, "resolve_hotspot_trade_date", lambda: date(2026, 8, 18))
    monkeypatch.setattr(hotspot, "pick_hotspot_candidates", lambda: [topic])
    monkeypatch.setattr(hotspot, "pick_hotspot_topics", lambda **_: [topic])
    monkeypatch.setattr(hotspot, "_attach_hotspot_research", lambda item: item)
    monkeypatch.setattr(hotspot, "hotspot_source", lambda: "news")
    monkeypatch.setattr(hotspot, "hotspot_candidate_count", lambda: 1)
    monkeypatch.setattr(hotspot, "hotspot_merged_llm", lambda: False)
    monkeypatch.setattr(hotspot, "_build_context_blob", lambda *_, **__: "【联网事实】公开事实")
    monkeypatch.setattr(hotspot, "is_wechat_mp_llm_configured", lambda: True)
    monkeypatch.setattr(hotspot, "_hotspot_body_usable", lambda *_, **__: True)
    monkeypatch.setattr(
        hotspot,
        "call_wechat_mp_llm",
        lambda messages, **_: captured.append(messages[-1]["content"])
        or ("正文。" * 900),
    )

    hotspot.generate_hotspot_body()

    prompt = captured[0]
    assert prompt.count("## 账号角色卡（最先遵守）") == 1
    assert prompt.index("## 账号角色卡（最先遵守）") < prompt.index("【联网事实】")
