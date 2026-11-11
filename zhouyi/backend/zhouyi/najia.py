"""Deterministic Jing Fang eight-palace Najia chart construction."""

from .core import ID_TO_BITS


RULE_VERSION = "jingfang-najia-v1"
TRIGRAM_BY_BITS = {
    "111": "乾", "110": "兑", "101": "离", "100": "震",
    "011": "巽", "010": "坎", "001": "艮", "000": "坤",
}
PALACES = {
    "乾": [1, 44, 33, 12, 20, 23, 35, 14],
    "兑": [58, 47, 45, 31, 39, 15, 62, 54],
    "离": [30, 56, 50, 64, 4, 59, 6, 13],
    "震": [51, 16, 40, 32, 46, 48, 28, 17],
    "巽": [57, 9, 37, 42, 25, 21, 27, 18],
    "坎": [29, 60, 3, 63, 49, 55, 36, 7],
    "艮": [52, 22, 26, 41, 38, 10, 61, 53],
    "坤": [2, 24, 19, 11, 34, 43, 5, 8],
}
PALACE_ELEMENTS = {"乾": "金", "兑": "金", "离": "火", "震": "木", "巽": "木", "坎": "水", "艮": "土", "坤": "土"}
PALACE_STAGES = ("本宫", "一世", "二世", "三世", "四世", "五世", "游魂", "归魂")
SHI_POSITIONS = (6, 1, 2, 3, 4, 5, 4, 3)
NAJIA = {
    "乾": (("甲", ("子", "寅", "辰")), ("壬", ("午", "申", "戌"))),
    "坤": (("乙", ("未", "巳", "卯")), ("癸", ("丑", "亥", "酉"))),
    "震": (("庚", ("子", "寅", "辰")), ("庚", ("午", "申", "戌"))),
    "巽": (("辛", ("丑", "亥", "酉")), ("辛", ("未", "巳", "卯"))),
    "坎": (("戊", ("寅", "辰", "午")), ("戊", ("申", "戌", "子"))),
    "离": (("己", ("卯", "丑", "亥")), ("己", ("酉", "未", "巳"))),
    "艮": (("丙", ("辰", "午", "申")), ("丙", ("戌", "子", "寅"))),
    "兑": (("丁", ("巳", "卯", "丑")), ("丁", ("亥", "酉", "未"))),
}
BRANCH_ELEMENTS = {
    "亥": "水", "子": "水", "寅": "木", "卯": "木", "巳": "火", "午": "火",
    "申": "金", "酉": "金", "辰": "土", "戌": "土", "丑": "土", "未": "土",
}
GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
CONTROLS = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
CLASH = {"子": "午", "午": "子", "丑": "未", "未": "丑", "寅": "申", "申": "寅", "卯": "酉", "酉": "卯", "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳"}
COMBINE = {"子": "丑", "丑": "子", "寅": "亥", "亥": "寅", "卯": "戌", "戌": "卯", "辰": "酉", "酉": "辰", "巳": "申", "申": "巳", "午": "未", "未": "午"}
SPIRITS = ("青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武")
SPIRIT_START = {"甲": 0, "乙": 0, "丙": 1, "丁": 1, "戊": 2, "己": 3, "庚": 4, "辛": 4, "壬": 5, "癸": 5}
TOPIC_USES = {"work": ["官鬼"], "learning": ["父母"], "cooperation": ["应爻"], "relationship": ["应爻"], "life": ["世爻"]}
RULE_SOURCES = [{
    "book": "增删卜易",
    "chapters": ["八纯卦纳甲图", "旬空计算法", "世应章第六", "六冲章第二十"],
    "source_url": "https://zh.wikisource.org/zh-hans/增删卜易",
    "verification": "来源抽取并核对规则表，尚未逐字校勘",
}]


def _palace(hexagram_id: int):
    for palace, sequence in PALACES.items():
        if hexagram_id in sequence:
            index = sequence.index(hexagram_id)
            return palace, index
    raise ValueError("卦序不在八宫表中")


def _relative(palace_element: str, line_element: str) -> str:
    if palace_element == line_element:
        return "兄弟"
    if GENERATES[line_element] == palace_element:
        return "父母"
    if GENERATES[palace_element] == line_element:
        return "子孙"
    if CONTROLS[line_element] == palace_element:
        return "官鬼"
    return "妻财"


def _influence(source: str, source_element: str, line_element: str) -> str:
    if source_element == line_element:
        return f"{source}同气"
    if GENERATES[source_element] == line_element:
        return f"{source}生"
    if CONTROLS[source_element] == line_element:
        return f"{source}克"
    if GENERATES[line_element] == source_element:
        return f"生{source}"
    return f"克{source}"


def _lines(bits: str, palace_element: str, calendar: dict, moving: set[int]) -> list[dict]:
    low = TRIGRAM_BY_BITS[bits[:3]]
    high = TRIGRAM_BY_BITS[bits[3:]]
    branches = []
    for trigram, side in ((low, 0), (high, 1)):
        stem, values = NAJIA[trigram][side]
        branches.extend((stem, branch) for branch in values)
    result = []
    spirit_start = SPIRIT_START[calendar["day_stem"]]
    for index, ((stem, branch), bit) in enumerate(zip(branches, bits), start=1):
        element = BRANCH_ELEMENTS[branch]
        flags = []
        if branch == calendar["month_branch"]:
            flags.append("月建")
        if CLASH[branch] == calendar["month_branch"]:
            flags.append("月破")
        if branch == calendar["day_branch"]:
            flags.append("日辰")
        if CLASH[branch] == calendar["day_branch"]:
            flags.append("日冲")
        if COMBINE[branch] == calendar["day_branch"]:
            flags.append("日合")
        if branch in calendar["xunkong"]:
            flags.append("旬空")
        result.append({
            "position": index,
            "yin_yang": "阳" if bit == "1" else "阴",
            "stem_branch": stem + branch,
            "element": element,
            "relative": _relative(palace_element, element),
            "spirit": SPIRITS[(spirit_start + index - 1) % 6],
            "moving": index in moving,
            "flags": flags,
            "influences": [
                _influence("月", BRANCH_ELEMENTS[calendar["month_branch"]], element),
                _influence("日", BRANCH_ELEMENTS[calendar["day_branch"]], element),
            ],
        })
    return result


def build_najia(cast: dict, calendar: dict, topic: str) -> dict:
    palace, stage_index = _palace(cast["original_id"])
    palace_element = PALACE_ELEMENTS[palace]
    shi = SHI_POSITIONS[stage_index]
    ying = (shi + 2) % 6 + 1
    moving = set(cast["moving"])
    return {
        "version": RULE_VERSION,
        "original_hexagram_id": cast["original_id"],
        "changed_hexagram_id": cast["changed_id"],
        "palace": palace,
        "palace_element": palace_element,
        "palace_stage": PALACE_STAGES[stage_index],
        "shi_position": shi,
        "ying_position": ying,
        "use_candidates": TOPIC_USES.get(topic, ["世爻"]),
        "sources": RULE_SOURCES,
        "original_lines": _lines(cast["original_bits"], palace_element, calendar, moving),
        "changed_lines": _lines(cast["changed_bits"], palace_element, calendar, set()),
        "observations": [
            {"kind": "用神候选", "text": "主题映射仅提供候选，需结合具体问题确认。"},
            {"kind": "动爻", "text": f"本次共有 {len(moving)} 个动爻。"},
        ],
    }
