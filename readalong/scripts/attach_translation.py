#!/usr/bin/env python3
"""
Attach Chinese translation to aligned English manifest lines.

1. DP-align EPUB EN sentences (241) → ZH sentences (525) with anchors + length.
2. Map each manifest line to its EN sentence index → attach ZH.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_ANCHORS: list[tuple[list[str], list[str]]] = [
    (["privet"], ["女贞路"]),
    (["dursley"], ["德思礼"]),
    (["grunnings"], ["格朗宁"]),
    (["drill"], ["钻机"]),
    (["dudley"], ["达力"]),
    (["potter"], ["波特"]),
    (["mustache", "moustache"], ["胡子", "大胡子"]),
    (["beefy"], ["魁梧", "胖"]),
    (["neck"], ["脖子"]),
    (["blond", "blonde"], ["金发"]),
    (["mrs"], ["太太", "夫人"]),
    (["mr dursley", "mr. dursley", "vernon"], ["弗农", "德思礼先生"]),
    (["owl"], ["猫头鹰"]),
    (["cat", "tabby"], ["猫", "花斑猫"]),
    (["cloak"], ["斗篷"]),
    (["briefcase"], ["公文包"]),
    (["cereal"], ["麦片"]),
    (["dumbledore"], ["邓布利多"]),
    (["mcgonagall"], ["麦格"]),
    (["hagrid"], ["海格"]),
    (["harry"], ["哈利"]),
    (["map"], ["地图"]),
    (["peculiar", "strange", "mysterious"], ["古怪", "异常", "神秘", "离奇"]),
    (["traffic"], ["车流", "交通"]),
    (["tyke"], ["臭小子", "小家伙"]),
    (["tantrum", "screaming"], ["脾气", "发脾气", "唧哇"]),
    (["good-bye", "goodbye", "kiss"], ["亲", "道别"]),
    (["drive", "driveway"], ["车道", "车道"]),
    (["neighbor"], ["邻居", "左邻右舍"]),
    (["secret"], ["秘密"]),
    (["tuesday", "gray", "grey"], ["星期二", "阴沉", "晦暗"]),
    (["whisper"], ["窃窃私语", "小声", "絮絮"]),
    (["shooting star"], ["流星"]),
    (["deputy"], ["副总理"]),
    (["street"], ["街道", "马路"]),
    (["hummed"], ["哼"]),
]


def _norm_en(text: str) -> str:
    return text.lower().replace("'", "'")


def _anchor_score(en: str, zh: str) -> float:
    en_n = _norm_en(en)
    pos = neg = 0.0
    for en_keys, zh_keys in _ANCHORS:
        en_hit = any(k in en_n for k in en_keys)
        zh_hit = any(k in zh for k in zh_keys)
        if en_hit and zh_hit:
            pos += 1.0
        elif en_hit:
            neg += 0.4
        elif zh_hit:
            neg += 0.15
    if pos == 0:
        return 0.2
    return max(0.0, min(1.0, (pos - neg) / max(pos, 1.0)))


def _length_score(en: str, zh: str) -> float:
    ratio = len(zh) / max(len(en), 1)
    ideal = 0.45
    return max(0.0, 1.0 - abs(ratio - ideal) / ideal)


def _pair_score(en: str, zh: str) -> float:
    return 0.68 * _anchor_score(en, zh) + 0.32 * _length_score(en, zh)


def _align_sentences_dp(
    en_sents: list[str],
    zh_sents: list[str],
    *,
    max_zh_per_en: int = 5,
) -> dict[int, str]:
    m, n = len(en_sents), len(zh_sents)
    neg = -1e9
    dp = [[neg] * (n + 1) for _ in range(m + 1)]
    nxt = [[1] * (n + 1) for _ in range(m + 1)]
    dp[m][n] = 0.0

    for i in range(m - 1, -1, -1):
        for j in range(n - 1, -1, -1):
            remaining_en = m - i
            best = neg
            best_k = 1
            max_k = min(max_zh_per_en, max(1, n - j - remaining_en + 1))
            for k in range(1, max_k + 1):
                if j + k > n:
                    break
                zh = "".join(zh_sents[j : j + k])
                sc = _pair_score(en_sents[i], zh) + dp[i + 1][j + k]
                if sc > best:
                    best = sc
                    best_k = k
            dp[i][j] = best
            nxt[i][j] = best_k

    out: dict[int, str] = {}
    i = j = 0
    while i < m and j < n:
        k = nxt[i][j]
        out[i] = "".join(zh_sents[j : j + k])
        j += k
        i += 1
    return out


def _find_sentence_index(en_sentences: list[str], text: str) -> int:
    text = text.strip()
    if text in en_sentences:
        return en_sentences.index(text)
    for i, s in enumerate(en_sentences):
        if s == text or (len(text) > 20 and text in s) or (len(s) > 20 and s in text):
            return i
    key = text[:50]
    for i, s in enumerate(en_sentences):
        if s.startswith(key[:25]) or key.startswith(s[:25]):
            return i
    return -1


def attach(manifest: dict, en_data: dict, zh_data: dict) -> dict:
    en_sents = en_data["sentences"]
    zh_sents = zh_data["sentences"]
    en_to_zh = _align_sentences_dp(en_sents, zh_sents)

    attached = 0
    for line in manifest.get("lines", []):
        en_text = line.get("text", "").strip()
        si = _find_sentence_index(en_sents, en_text)
        if si < 0:
            if "zh" in line:
                del line["zh"]
            continue
        zh = en_to_zh.get(si, "")
        if zh:
            line["zh"] = zh
            attached += 1
        elif "zh" in line:
            del line["zh"]

    manifest["translation_source"] = "samples/book_zh.epub"
    manifest["translation_method"] = "sentence_dp_anchors"
    manifest["translated_lines"] = attached
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chapter", type=int, default=1)
    args = parser.parse_args()

    ch_pad = f"{args.chapter:02d}"
    manifest_path = ROOT / "output" / f"ch{ch_pad}.json"
    en_path = ROOT / "output" / f"ch{ch_pad}_sentences.json"
    zh_path = ROOT / "output" / f"ch{ch_pad}_zh.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    en_data = json.loads(en_path.read_text(encoding="utf-8"))
    zh_data = json.loads(zh_path.read_text(encoding="utf-8"))

    manifest = attach(manifest, en_data, zh_data)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Wrote {manifest_path} — zh on {manifest['translated_lines']}/"
        f"{len(manifest.get('lines', []))} lines"
    )


if __name__ == "__main__":
    main()
