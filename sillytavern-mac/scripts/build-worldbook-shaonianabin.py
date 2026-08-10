#!/usr/bin/env python3
"""从 source/shaonianabin.txt 生成 SillyTavern 世界书（按篇分块索引）。"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "shaonianabin.txt"
OUT = ROOT / "vendor" / "SillyTavern" / "data" / "default-user" / "worlds" / "shaonianabin.json"

CHUNK_MAX = 480
GROUP = "少年阿宾"

TERMS = [
    "阿宾", "钰慧", "房东太太", "房东", "卢莎", "学姐", "莲莲", "孟卉", "胡太太",
    "台北", "专校", "垦丁", "澎湖", "卢家", "通史", "图书馆", "舞会", "理发",
    "打工", "寒假", "搬家", "生日", "Walk Through",
]

SECTION_RE = re.compile(r"（([一二三四五六七八九十百零〇两\d]+)）([^\n\r]+)")


def load_text() -> str:
    raw = SOURCE.read_bytes()
    for enc in ("gb18030", "gbk", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"无法解码: {SOURCE}")


def chunk_paragraphs(text: str, max_len: int = CHUNK_MAX) -> list[str]:
    parts: list[str] = []
    buf = ""
    for para in re.split(r"\r?\n+", text):
        para = para.strip()
        if not para:
            continue
        if len(para) > max_len:
            if buf:
                parts.append(buf)
                buf = ""
            for i in range(0, len(para), max_len):
                parts.append(para[i : i + max_len])
            continue
        if len(buf) + len(para) + 2 <= max_len:
            buf = f"{buf}\n\n{para}" if buf else para
        else:
            if buf:
                parts.append(buf)
            buf = para
    if buf:
        parts.append(buf)
    return parts


def keys_for(text: str, extra: list[str] | None = None) -> list[str]:
    found = [t for t in TERMS if t in text]
    if extra:
        for e in extra:
            e = e.strip()
            if e and e not in found:
                found.append(e)
    if not found:
        found = ["少年阿宾", "阿宾"]
    return found[:12]


def base_entry(uid: int, keys: list[str], content: str, comment: str, *, constant: bool = False) -> dict:
    return {
        "uid": uid,
        "key": keys,
        "keysecondary": [],
        "comment": comment,
        "content": content.strip(),
        "constant": constant,
        "selective": not constant,
        "order": 100,
        "position": 0,
        "disable": False,
        "displayIndex": uid,
        "addMemo": True,
        "group": GROUP,
        "groupOverride": False,
        "groupWeight": 100,
        "sticky": 0,
        "cooldown": 0,
        "delay": 0,
        "probability": 100,
        "depth": 4,
        "useProbability": True,
        "role": None,
        "vectorized": False,
        "excludeRecursion": False,
        "preventRecursion": False,
        "delayUntilRecursion": False,
        "scanDepth": None,
        "caseSensitive": None,
        "matchWholeWords": None,
        "useGroupScoring": None,
        "automationId": "",
    }


def build_section_index(markers: list[tuple[str, str]]) -> str:
    lines = ["《少年阿宾》篇章索引（聊天提到篇名时可对照，勿一次剧透全书）："]
    for num, title in markers:
        lines.append(f"- （{num}）{title}")
    return "\n".join(lines)


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"缺少源文件: {SOURCE}")

    text = load_text()
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        raise SystemExit("未找到（一）式篇章标题")

    marker_list = [(m.group(1), m.group(2).strip()) for m in matches]
    entries: dict[str, dict] = {}
    uid = 0

    lore = [
        (
            "世界观",
            ["少年阿宾", "阿宾", "背景", "世界观", "台北"],
            """《少年阿宾》作者阿Ben。90年代台湾背景，主角阿宾考上台北附近私立专校，
为免通勤在台北租屋，故事由租屋生活展开，跨度从上学到日后成家，单元剧式长篇。
文风偏青春都市，对话用繁体/口语化的现代中文；角色名与篇名以原著为准。
世界书按篇分块，仅关键词命中时注入，勿脱离当前篇章胡编未出场人物。""",
            True,
        ),
        (
            "阿宾",
            ["阿宾", "主角", "我"],
            "阿宾：大学生，性格健康活泼、好奇、人缘广。叙述常为第一人称「我」。",
            False,
        ),
        (
            "钰慧",
            ["钰慧", "初识钰慧", "女友"],
            "钰慧：阿宾重要感情线人物之一，初识于校园社交圈，后长期交往。",
            False,
        ),
        (
            "RP格式",
            ["RP", "格式", "第一人称", "聊天", "房东太太"],
            """[聊天 RP 格式]
角色卡对话时用第一人称（我），动作用*星号*，台词用引号。
仅简体中文，禁止任何英文。
禁止第三人称小说旁白（胡太太/她/阿宾/他作叙述者）。
世界书篇块原文仅供背景，勿照抄其叙述方式。""",
            True,
        ),
        (
            "篇章索引",
            ["篇章", "目录", "第几篇"],
            build_section_index(marker_list),
            False,
        ),
    ]

    for comment, keys, content, constant in lore:
        entries[str(uid)] = base_entry(uid, keys, content, comment, constant=constant)
        uid += 1

    for i, m in enumerate(matches):
        num, title = m.group(1), m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        section_keys = [title, f"（{num}）{title}", f"第{num}篇", num, GROUP]
        for j, chunk in enumerate(chunk_paragraphs(body)):
            comment = f"（{num}）{title}-{j + 1}" if len(chunk_paragraphs(body)) > 1 else f"（{num}）{title}"
            entries[str(uid)] = base_entry(uid, keys_for(chunk, section_keys), chunk, comment)
            uid += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"已写入 {OUT}")
    print(f"篇章数: {len(marker_list)}")
    print(f"条目数: {len(entries)}")
    print(f"源文字数: {len(text)}")


if __name__ == "__main__":
    main()
