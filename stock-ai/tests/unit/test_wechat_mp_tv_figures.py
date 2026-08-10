"""影视剧照注入与路径解析。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_figures import resolve_inline_path
from scripts.tools.wechat_mp_tv_figures import (
    inject_tv_review_figures,
    normalize_tv_review_body,
)
from scripts.tools.wechat_mp_tv_topics import CURATED_HOT


def test_resolve_tv_inline_path() -> None:
    from scripts.tools.wechat_mp_douban_stills import ensure_douban_stills

    topic = next(t for t in CURATED_HOT if t["title_en"] == "Euphoria")
    ensure_douban_stills(dict(topic))
    p = resolve_inline_path("tv/euphoria/douban-still-01.jpg")
    assert p.name == "douban-still-01.jpg"


def test_normalize_tv_review_body_strips_bold() -> None:
    raw = "> 戳我的就这几处\n\n**1.人物深度**\n\nRue 有弧线。\n\n**2、节奏**"
    out = normalize_tv_review_body(raw)
    assert "**" not in out
    assert "· 人物深度" in out
    assert "· 节奏" in out


def test_normalize_strips_label_colon_section() -> None:
    raw = "> 简单交代：一部青春剧，但从不只讲高中生\n\n正文"
    out = normalize_tv_review_body(raw)
    assert "简单交代" not in out
    assert "> 一部青春剧，但从不只讲高中生" in out


def test_normalize_merits_relabels_duplicate_character_bullets() -> None:
    raw = (
        "> 戳我的就这三处\n\n"
        "· 人物：Rue 的毒瘾线还在。\n\n"
        "· 人物弧线：Jules 和 Rue 的对手戏。\n\n"
        "· 节奏：第三集后才顺。"
    )
    out = normalize_tv_review_body(raw)
    assert out.count("· 人物") == 1
    assert "· 叙事：Jules" in out or "· 镜头：Jules" in out


def test_inject_tv_figures_after_sections() -> None:
    topic = next(t for t in CURATED_HOT if t["title_en"] == "Euphoria")
    body = (
        "> 四年空窗后回来，还值得开刷吗\n\n值得看但别期待过高。\n\n"
        "> 一部青春剧，但从不只讲高中生\n\n第三季回归。\n\n"
        "> 戳我的就这几处\n\n第一点。\n\n"
        "> 谁会很爱，谁可以略过\n\n适合老观众。"
    )
    out = inject_tv_review_figures(body, topic)
    assert "ratings-card" not in out
    assert "· 豆瓣" in out
    assert "· IMDb" in out
    assert "· Metacritic" in out
    assert "[[fig:tv/euphoria/douban-still-01.jpg" in out
    assert "cap=图源：豆瓣 movie.douban.com/subject/34874603" in out
    assert "（配图：" in out
    idx2 = out.index("douban-still-02")
    idx3 = out.index("douban-still-03")
    idx_fit = out.index("谁会很爱")
    assert idx2 < idx_fit < idx3


def test_inject_tv_ratings_after_first_paragraph() -> None:
    topic = next(t for t in CURATED_HOT if t["title_en"] == "Euphoria")
    body = (
        "> 四年空窗后回来，老观众为什么吵翻了\n\n"
        "第一段正文在这里。\n\n"
        "第二段还在第一节。\n\n"
        "> 一部青春剧\n\n"
        "第二节正文。"
    )
    out = inject_tv_review_figures(body, topic)
    idx_para = out.index("第一段正文")
    idx_score = out.index("· 豆瓣")
    idx_para2 = out.index("第二段还在")
    assert idx_para < idx_score < idx_para2


def test_inject_tv_figures_legacy_section_titles() -> None:
    topic = next(t for t in CURATED_HOT if t["title_en"] == "Euphoria")
    body = (
        "> 先说结论\n\n结论。\n\n> 它是什么\n\n介绍。\n\n"
        "> 为什么值得看\n\n理由。\n\n> 适合谁\n\n人群。"
    )
    out = inject_tv_review_figures(body, topic)
    assert out.count("[[fig:") == 3


def test_inject_teach_you_a_lesson_figures_after_episode_anchors() -> None:
    topic = next(t for t in CURATED_HOT if t["title_en"] == "Teach You a Lesson")
    body = (
        "> 看着像揍人爽剧\n\n"
        "政府成立教权保护局。\n\n"
        "金武烈演罗华振。\n\n"
        "> 分集速写\n\n"
        "· 第1集（议员儿子案）：楼顶跳下。\n\n"
        "· 第2集（汽车科帮派案）：补习班台词。\n\n"
        "· 第3集（黑道学生案）：越界停顿。\n\n"
        "· 第4集（朴贤雄案）：政治利益场。\n\n"
        "· 第5集（恐龙家长案）：电话轰炸。\n\n"
        "> 爱这口的会熬夜\n\n"
        "若你讨厌以暴制暴。\n\n"
        "> 拿不准就开前两集\n\n"
        "先试两集。"
    )
    out = inject_tv_review_figures(body, topic)
    assert out.count("[[fig:") == 10
    idx_ep1 = out.index("第1集（议员儿子案）")
    idx_ep1_fig = out.index("still-01")
    idx_ep2 = out.index("第2集（汽车科帮派案）")
    idx_ep2_fig = out.index("still-03")
    assert idx_ep1 < idx_ep1_fig < idx_ep2 < idx_ep2_fig


def test_no_masthead_for_tv_review() -> None:
    from scripts.tools.wechat_mp_masthead import masthead_html

    assert masthead_html("tv_review", upload_images=False, local_preview=True) == ""
