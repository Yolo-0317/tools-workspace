#!/usr/bin/env python3
"""Validate the complete Jiuge 15-second dance-design package."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


CHAPTERS = [
    ("01", "东皇太一", "01-donghuang-taiyi-15s.md"),
    ("02", "云中君", "02-yunzhongjun-15s.md"),
    ("03", "湘君", "03-xiangjun-15s.md"),
    ("04", "湘夫人", "04-xiangfuren-15s.md"),
    ("05", "大司命", "05-dasiming-15s.md"),
    ("06", "少司命", "06-shaosiming-15s.md"),
    ("07", "东君", "07-dongjun-15s.md"),
    ("08", "河伯", "08-hebo-15s.md"),
    ("09", "山鬼", "09-shangui-15s.md"),
    ("10", "国殇", "10-guoshang-15s.md"),
    ("11", "礼魂", "11-lihun-15s.md"),
]

HEADINGS = [
    "## 原典与现代转译",
    "## 十五秒舞蹈设计卡",
    "## Seedance 完整提示词",
    "## 验收要点",
]

WINDOWS = [
    "0.300—4.200 秒",
    "5.000—8.800 秒",
    "9.600—13.500 秒",
    "13.500—15.000 秒",
]

CSV_FIELDS = [
    "order", "chapter", "ritual_phase", "emotion_arc",
    "opening_silhouette", "spatial_route",
    "peak1_family", "peak1_direction", "peak1_window", "peak1_carrier", "peak1_camera",
    "peak2_family", "peak2_direction", "peak2_window", "peak2_carrier", "peak2_camera",
    "peak3_family", "peak3_direction", "peak3_window", "peak3_carrier", "peak3_camera",
    "sleeve_trajectory", "prop", "ending", "status", "notes",
]

VISUAL_PROMPT_REQUIRED = [
    "原创虚构数字角色",
    "九歌祭舞 v03",
    "严格两个",
    "不复刻角色卡排版",
]

NATIVE_RECITATION_FROM_ORDER = 3

NATIVE_AUDIO_REQUIRED = (
    "生成完整的双声道环境声",
    "年轻中国女性的画外朗诵",
    "栀夏全程不张嘴说话",
    "不需要与声音对口型",
    "正常自然人声",
    "不拖字、不吟唱、不机械慢放",
    "只朗诵这些文字，不增词、不改词",
)

LEGACY_NO_VOICE_PHRASES = (
    "不得生成可辨识人声",
    "无可辨识人声",
    "不生成任何可辨识人声",
)

RECITATION_CONTRACTS = {
    "湘君": ("君不行兮夷犹，蹇谁留兮中洲。", "中洲"),
    "湘夫人": ("袅袅兮秋风，洞庭波兮木叶下。", "木叶下"),
    "大司命": ("广开兮天门，纷吾乘兮玄云。", "玄云"),
    "少司命": ("秋兰兮麋芜，罗生兮堂下。", "堂下"),
    "东君": ("暾将出兮东方，照吾槛兮扶桑。", "扶桑"),
    "河伯": ("与女游兮九河，冲风起兮水扬波。", "水扬波"),
    "山鬼": ("既含睇兮又宜笑，子慕予兮善窈窕。", "善窈窕"),
    "国殇": ("身既死兮神以灵，魂魄毅兮为鬼雄。", "鬼雄"),
    "礼魂": ("春兰兮秋菊，长无绝兮终古。", "终古"),
}

PROMPT_EMPTY_HANDS_REQUIRED = (
    "双手始终空着",
    "全程不触碰、不拿取任何器物",
)

DESIGN_CARD_REQUIRED = (
    "- 视线对象：",
    "- 初始表情：",
    "- 情绪转折：",
    "- 结束状态：",
)

LEDGER_AESTHETIC_NOTE_TOKENS = (
    "视线对象=",
    "表情弧线=",
    "声音模式=",
)

PROMPT_HANDHELD_FORBIDDEN = (
    "道具牵引",
    "只持一枝",
    "唯一花枝",
    "持花手",
    "执剑手",
    "唯一礼剑",
    "同一只手持有",
)

PROMPT_FORBIDDEN = [
    "主高潮家族",
    "验收标准",
    "测试通过",
    "B站",
    "bilibili.com",
    "hkdance.com",
    "chncpa.org",
]


def fail(message: str) -> None:
    raise ValueError(message)


def prompt_body(text: str) -> str:
    marker = "## Seedance 完整提示词"
    if marker not in text:
        return ""
    tail = text.split(marker, 1)[1]
    return tail.split("## 验收要点", 1)[0]


def validate_prompt(path: Path, chapter: str) -> None:
    if not path.is_file():
        fail(f"missing prompt: {path.name}")
    text = path.read_text(encoding="utf-8")
    if chapter not in text:
        fail(f"{path.name}: missing chapter name {chapter}")
    for heading in HEADINGS:
        if heading not in text:
            fail(f"{path.name}: missing heading {heading}")
    for window in WINDOWS:
        if window not in text:
            fail(f"{path.name}: missing time window {window}")
    if not path.name.startswith("01-"):
        for phrase in DESIGN_CARD_REQUIRED:
            if phrase not in text:
                fail(f"{path.name}: missing design-card field {phrase[2:-1]}")
    body = prompt_body(text)
    for phrase in VISUAL_PROMPT_REQUIRED:
        if phrase not in body:
            fail(f"{path.name}: prompt body missing {phrase}")
    order = int(path.name.split("-", 1)[0])
    if order >= NATIVE_RECITATION_FROM_ORDER:
        for phrase in LEGACY_NO_VOICE_PHRASES:
            if phrase in body:
                fail(f"{path.name}: prompt body contains legacy no-voice rule {phrase}")
        for phrase in NATIVE_AUDIO_REQUIRED:
            if phrase not in body:
                fail(f"{path.name}: prompt body missing native audio phrase {phrase}")
        quoted_text, final_cue = RECITATION_CONTRACTS[chapter]
        if f"朗诵：“{quoted_text}”" not in body:
            fail(f"{path.name}: prompt body missing quoted recitation")
        if f"约第13.4秒才说出末尾短句“{final_cue}”" not in body:
            fail(f"{path.name}: prompt body missing final recitation cue")
    for phrase in PROMPT_EMPTY_HANDS_REQUIRED:
        if phrase not in body:
            fail(f"{path.name}: prompt body missing {phrase}")
    for phrase in PROMPT_HANDHELD_FORBIDDEN:
        if phrase in body:
            fail(f"{path.name}: prompt body contains forbidden handheld term {phrase}")
    for phrase in PROMPT_FORBIDDEN:
        if phrase in body:
            fail(f"{path.name}: prompt body contains forbidden term {phrase}")


def signature(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row["opening_silhouette"],
        row["spatial_route"],
        row["peak1_family"],
        row["peak2_family"],
        row["peak3_family"],
        row["sleeve_trajectory"],
        row["prop"],
        row["ending"],
        "|".join((row["peak1_camera"], row["peak2_camera"], row["peak3_camera"])),
    )


def validate_ledger(path: Path) -> None:
    if not path.is_file():
        fail("missing ledger: operations/jiuge-dance-design-history.csv")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CSV_FIELDS:
            fail("ledger header does not match the 26-field contract")
        rows = list(reader)
    if len(rows) != len(CHAPTERS):
        fail(f"ledger must contain 11 rows, found {len(rows)}")

    expected_windows = ("0.300—4.200秒", "5.000—8.800秒", "9.600—13.500秒")
    recent_peak_sequences: list[tuple[str, str, str]] = []
    recent_direction_sequences: list[tuple[str, str, str]] = []

    for index, (row, (order, chapter, _)) in enumerate(zip(rows, CHAPTERS)):
        if row["order"] != order or row["chapter"] != chapter:
            fail(f"ledger row {index + 1}: expected {order} {chapter}")
        if any(not row[field].strip() for field in CSV_FIELDS):
            fail(f"ledger row {order}: contains an empty field")
        if row["status"] != "designed":
            fail(f"ledger row {order}: status must be designed")
        actual_windows = (row["peak1_window"], row["peak2_window"], row["peak3_window"])
        if actual_windows != expected_windows:
            fail(f"ledger row {order}: incorrect peak windows")
        if row["prop"] != "无":
            fail(f"ledger row {order}: expected prop 无")
        if order != "01":
            for token in LEDGER_AESTHETIC_NOTE_TOKENS:
                if token not in row["notes"]:
                    fail(f"ledger row {order}: missing notes token {token}")

        peak_sequence = (row["peak1_family"], row["peak2_family"], row["peak3_family"])
        direction_sequence = (row["peak1_direction"], row["peak2_direction"], row["peak3_direction"])
        if recent_peak_sequences and peak_sequence == recent_peak_sequences[-1]:
            fail(f"ledger row {order}: repeats the previous peak sequence")
        if peak_sequence in recent_peak_sequences[-5:]:
            fail(f"ledger row {order}: repeats a peak sequence within five chapters")
        if direction_sequence in recent_direction_sequences[-5:]:
            fail(f"ledger row {order}: repeats a direction sequence within five chapters")
        recent_peak_sequences.append(peak_sequence)
        recent_direction_sequences.append(direction_sequence)

        if index:
            current = signature(row)
            previous = signature(rows[index - 1])
            same = sum(left == right for left, right in zip(current, previous))
            if same >= 3:
                fail(f"ledger row {order}: shares {same} visual fingerprints with previous chapter")


def validate(project_root: Path) -> None:
    design = project_root / "docs" / "jiuge-dance-research-and-design.md"
    if not design.is_file():
        fail("missing research design: docs/jiuge-dance-research-and-design.md")
    prompts = project_root / "assets" / "prompts" / "jiuge"
    for _, chapter, filename in CHAPTERS:
        validate_prompt(prompts / filename, chapter)
    validate_ledger(project_root / "operations" / "jiuge-dance-design-history.csv")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(args.project_root.resolve())
    except ValueError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: Jiuge 15s three-peak dance designs are complete and distinct")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
