from zhouyi.calendar import normalize_cast_time
from zhouyi.core import describe_cast
from zhouyi.najia import build_najia


CALENDAR = normalize_cast_time("2024-02-10T10:00:00+08:00")


def cast(values):
    coin_map = {6: [2, 2, 2], 7: [2, 2, 3], 8: [2, 3, 3], 9: [3, 3, 3]}
    return describe_cast([coin_map[value] for value in values])


def test_qian_chart_uses_bottom_up_najia_relatives_and_shi_ying():
    chart = build_najia(cast([7] * 6), CALENDAR, "work")

    assert chart["palace"] == "乾"
    assert chart["palace_element"] == "金"
    assert chart["shi_position"] == 6
    assert chart["ying_position"] == 3
    assert [line["stem_branch"] for line in chart["original_lines"]] == [
        "甲子", "甲寅", "甲辰", "壬午", "壬申", "壬戌"
    ]
    assert [line["relative"] for line in chart["original_lines"]] == [
        "子孙", "妻财", "父母", "官鬼", "兄弟", "父母"
    ]
    assert chart["original_lines"][0]["spirit"] == "青龙"
    assert chart["original_lines"][1]["flags"] == ["月建", "旬空"]
    assert chart["use_candidates"] == ["官鬼"]
    assert chart["sources"] == [
        {
            "book": "增删卜易",
            "chapters": ["八纯卦纳甲图", "旬空计算法", "世应章第六", "六冲章第二十"],
            "source_url": "https://zh.wikisource.org/zh-hans/增删卜易",
            "verification": "来源抽取并核对规则表，尚未逐字校勘",
        }
    ]


def test_kun_chart_uses_reverse_inner_and_outer_branches():
    chart = build_najia(cast([8] * 6), CALENDAR, "learning")

    assert chart["palace"] == "坤"
    assert chart["palace_element"] == "土"
    assert [line["stem_branch"] for line in chart["original_lines"]] == [
        "乙未", "乙巳", "乙卯", "癸丑", "癸亥", "癸酉"
    ]
    assert chart["use_candidates"] == ["父母"]


def test_eight_palace_sequences_mark_wandering_and_returning_souls():
    wandering = build_najia(cast([8, 8, 8, 8, 7, 8]), CALENDAR, "")  # 比，坤宫归魂
    returning = build_najia(cast([7, 7, 7, 8, 7, 8]), CALENDAR, "")  # 需，坤宫游魂

    assert (wandering["palace"], wandering["palace_stage"], wandering["shi_position"]) == ("坤", "归魂", 3)
    assert (returning["palace"], returning["palace_stage"], returning["shi_position"]) == ("坤", "游魂", 4)


def test_moving_line_gets_changed_najia_but_keeps_original_palace_for_relative():
    chart = build_najia(cast([9, 7, 7, 7, 7, 7]), CALENDAR, "cooperation")

    assert chart["original_hexagram_id"] == 1
    assert chart["changed_hexagram_id"] == 44
    assert chart["original_lines"][0]["moving"] is True
    assert chart["changed_lines"][0]["stem_branch"] == "辛丑"
    assert chart["changed_lines"][0]["relative"] == "父母"
    assert chart["use_candidates"] == ["应爻"]
