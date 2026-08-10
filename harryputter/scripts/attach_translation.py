#!/usr/bin/env python3
"""
Attach Chinese translation to aligned English manifest lines.

1. DP-align EPUB EN sentences (241) → ZH sentences (525) with anchors + length.
2. Map each manifest line to its EN sentence index → attach ZH.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from bilingual_clips import load_bilingual_clips  # noqa: E402
from chapters import manifest_path, sentences_path, zh_epub_path, zh_extract_path  # noqa: E402

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
    (["boom"], ["轰"]),
    (["smash", "crash"], ["咔嚓", "哗啦", "轰"]),
    (["pause"], ["静了一会儿", "静了"]),
    (["giant", "stranger"], ["巨人", "大汉", "彪形"]),
    (["doorway", "door", "hinges"], ["门", "门口", "门框", "合页"]),
    (["rifle", "armed"], ["枪", "来福枪"]),
    (["cannon"], ["炮", "打炮"]),
    (["tea"], ["茶"]),
    (["face", "beard", "beetle", "eyes"], ["脸", "胡须", "甲虫", "眼睛"]),
    (["hut"], ["屋", "木屋", "小屋"]),
    (["storm"], ["风暴"]),
    (["sofa"], ["沙发"]),
    (["birthday"], ["生日"]),
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


def _coalesce_zh_sentences(zh_sents: list[str]) -> list[str]:
    """Merge pause/SFX fragments so EN clause order matches ZH narrative order."""
    if not zh_sents:
        return []
    out: list[str] = [zh_sents[0]]
    i = 1
    while i < len(zh_sents):
        s = zh_sents[i]
        if s.startswith("外面静") and len(out) > 0:
            out[-1] += s
        else:
            out.append(s)
        i += 1
    return out


def _en_continues_pair(cur: str, nxt: str) -> bool:
    cur = cur.strip()
    nxt = nxt.strip()
    if not cur or not nxt:
        return False
    open_q = cur.count("\u201c") - cur.count("\u201d") + cur.count('"')
    split_mid_quote = open_q % 2 == 1 or cur.endswith(("?", ",", ":", ";", "—", "-"))
    continues = nxt[0].islower() or nxt.startswith(("'", "\u2019", ". . .", "..."))
    if split_mid_quote and continues:
        return True
    return False


def _merge_en_for_alignment(en_sents: list[str]) -> tuple[list[str], list[list[int]]]:
    """Fold split EN clauses so DP does not skip the next ZH sentence."""
    merged: list[str] = []
    groups: list[list[int]] = []
    i = 0
    while i < len(en_sents):
        if i + 1 < len(en_sents) and _en_continues_pair(en_sents[i], en_sents[i + 1]):
            merged.append(f"{en_sents[i]} {en_sents[i + 1]}")
            groups.append([i, i + 1])
            i += 2
        else:
            merged.append(en_sents[i])
            groups.append([i])
            i += 1
    return merged, groups


def _align_sentences_dp(
    en_sents: list[str],
    zh_sents: list[str],
    *,
    max_zh_per_en: int = 8,
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
                if k > 1:
                    sc -= 0.12 * (k - 1)
                if len(en_sents[i]) < 60 and k > 1:
                    sc -= 0.2 * (k - 1)
                if sc > best:
                    best = sc
                    best_k = k
            dp[i][j] = best
            nxt[i][j] = best_k

    out: dict[int, str] = {}
    lists: dict[int, list[str]] = {}
    i = j = 0
    while i < m and j < n:
        k = nxt[i][j]
        chunk = zh_sents[j : j + k]
        out[i] = "".join(chunk)
        lists[i] = chunk
        j += k
        i += 1
    return out, lists


def _align_sentences_dp_lists(
    en_sents: list[str],
    zh_sents: list[str],
    *,
    max_zh_per_en: int = 8,
) -> dict[int, list[str]]:
    _, lists = _align_sentences_dp(en_sents, zh_sents, max_zh_per_en=max_zh_per_en)
    return lists


def _merge_fragment_en_paragraphs(
    en_paras: list[str],
    *,
    max_len: int = 50,
) -> tuple[list[str], dict[int, int]]:
    """Fold one-line EN fragments (e.g. Hagrid's note) into the previous paragraph."""
    merged: list[str] = []
    remap: dict[int, int] = {}
    for i, raw in enumerate(en_paras):
        p = raw.strip()
        if not p:
            remap[i] = max(0, len(merged) - 1)
            continue
        if merged and len(p) <= max_len:
            merged[-1] = f"{merged[-1]} {p}".strip()
            remap[i] = len(merged) - 1
        else:
            merged.append(p)
            remap[i] = len(merged) - 1
    return merged, remap


_ZH_SPLIT_PUNCT = "。！？；\n"
_ZH_SOFT_PUNCT = "，、："


def _snap_zh_split(zh: str, target: int) -> int:
    if target <= 0:
        return 0
    if target >= len(zh):
        return len(zh)
    window = range(max(1, target - 14), min(len(zh), target + 14))
    best = target
    best_rank = 10**9
    for pos in window:
        ch = zh[pos - 1]
        if ch in _ZH_SPLIT_PUNCT:
            rank = abs(pos - target)
        elif ch in _ZH_SOFT_PUNCT:
            rank = abs(pos - target) + 4
        else:
            continue
        if rank < best_rank:
            best_rank = rank
            best = pos
    return best


def _split_zh_text(zh: str, parts: int, weights: list[int] | None = None) -> list[str]:
    """Split one ZH string across N EN lines, preferring punctuation boundaries."""
    zh = zh.strip()
    if parts <= 1 or not zh:
        return [zh]
    weights = [max(1, w) for w in (weights or [1] * parts)]
    total = sum(weights)
    cuts = [0]
    acc = 0
    for w in weights[:-1]:
        acc += w
        cuts.append(_snap_zh_split(zh, round(len(zh) * acc / total)))
    cuts.append(len(zh))
    chunks = [zh[cuts[i] : cuts[i + 1]].strip() for i in range(parts)]
    for _ in range(parts):
        if all(chunks):
            break
        for i, ch in enumerate(chunks):
            if ch:
                continue
            if i > 0 and chunks[i - 1]:
                prev = chunks[i - 1]
                mid = max(1, len(prev) // 2)
                chunks[i] = prev[mid:].strip()
                chunks[i - 1] = prev[:mid].strip()
            elif i + 1 < len(chunks) and chunks[i + 1]:
                nxt = chunks[i + 1]
                mid = max(1, len(nxt) // 2)
                chunks[i] = nxt[:mid].strip()
                chunks[i + 1] = nxt[mid:].strip()
    if len(chunks) != parts or not all(chunks):
        step = max(1, len(zh) // parts)
        chunks = [zh[i * step : (i + 1) * step if i < parts - 1 else len(zh)].strip() for i in range(parts)]
    return [c for c in chunks if c] or [zh]


def _distribute_zh_in_paragraph(
    sis: list[int],
    en_sents: list[str],
    zh_list: list[str],
) -> dict[int, str]:
    """Map EN sentence indices to ZH within one aligned paragraph (no char-level ZH split)."""
    if not sis or not zh_list:
        return {}
    n_en, n_zh = len(sis), len(zh_list)
    out: dict[int, str] = {}
    if n_en <= n_zh:
        for local, en_si in enumerate(sis):
            if local < n_zh:
                out[en_si] = zh_list[local]
        return out

    for zj in range(n_zh):
        en_start = zj * n_en // n_zh
        en_end = (zj + 1) * n_en // n_zh if zj < n_zh - 1 else n_en
        group = sis[en_start:en_end]
        if not group:
            continue
        zh = zh_list[zj]
        out[group[0]] = zh
        for si in group[1:]:
            out[si] = ""
    return out


def _merge_manifest_zh_groups(manifest: dict) -> int:
    """Merge EN lines that share one ZH (zh on first line only) into a single row."""
    lines = manifest.get("lines", [])
    if not lines:
        return 0
    out: list[dict] = []
    merged = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.get("kind") == "heading" or not (line.get("zh") or "").strip():
            out.append(line)
            i += 1
            continue
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if nxt.get("kind") == "heading" or (nxt.get("zh") or "").strip():
                break
            j += 1
        if j <= i + 1:
            out.append(line)
            i += 1
            continue
        group = lines[i:j]
        texts = [g.get("text", "").strip() for g in group if g.get("text", "").strip()]
        merged_line = {k: v for k, v in line.items() if k not in ("text", "start", "end")}
        merged_line["text"] = " ".join(texts)
        merged_line["start"] = float(group[0].get("start", 0))
        merged_line["end"] = float(group[-1].get("end", merged_line["start"]))
        merged_line["zh"] = line.get("zh")
        merged_line["merged_count"] = len(group)
        if any(g.get("interpolated") for g in group):
            merged_line["interpolated"] = True
        confs = [g.get("confidence") for g in group if g.get("confidence") is not None]
        if confs:
            merged_line["confidence"] = min(confs)
        out.append(merged_line)
        merged += len(group) - 1
        i = j
    manifest["lines"] = out
    return merged


def _dedupe_consecutive_manifest_zh(manifest: dict) -> None:
    """Hard rule: consecutive lines must not show identical ZH."""
    lines = manifest.get("lines", [])
    prev = ""
    for line in lines:
        if line.get("kind") == "heading":
            prev = ""
            continue
        zh = (line.get("zh") or "").strip()
        if zh and zh == prev:
            line.pop("zh", None)
        else:
            prev = zh


def _fan_out_manifest_zh(manifest: dict, en_sents: list[str]) -> None:
    """When several audio lines map to the same EN sentence, split ZH across them."""
    lines = manifest.get("lines", [])
    i = 0
    while i < len(lines):
        if lines[i].get("kind") == "heading":
            i += 1
            continue
        zh = lines[i].get("zh")
        if not zh:
            i += 1
            continue
        si = _find_sentence_index(en_sents, lines[i].get("text", ""))
        j = i + 1
        while j < len(lines):
            if lines[j].get("kind") == "heading":
                break
            if lines[j].get("zh") != zh:
                break
            if _find_sentence_index(en_sents, lines[j].get("text", "")) != si:
                break
            j += 1
        if j > i + 1:
            n = j - i
            # Long ZH shared across lines: keep the full sentence (avoid mid-phrase shards).
            if len(zh) / n >= 14:
                i = j
                continue
            weights = [max(1, len(lines[k].get("text", ""))) for k in range(i, j)]
            chunks = _split_zh_text(zh, n, weights)
            if len(chunks) == n:
                for k, chunk in enumerate(chunks):
                    lines[i + k]["zh"] = chunk
        i = j


def _load_translation_fixes(book: str, chapter: int) -> dict | None:
    path = ROOT / "data" / "translation_fixes" / f"{book}_ch{chapter:02d}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _apply_translation_fixes(
    en_to_zh: dict[int, str],
    zh_sents: list[str],
    fixes: dict,
) -> None:
    for key, zi in (fixes.get("en_to_zh_index") or {}).items():
        idx = int(key)
        if 0 <= zi < len(zh_sents):
            en_to_zh[idx] = zh_sents[zi]
    for key, zis in (fixes.get("en_to_zh_indices") or {}).items():
        idx = int(key)
        parts = [zh_sents[int(z)] for z in zis if 0 <= int(z) < len(zh_sents)]
        if parts:
            en_to_zh[idx] = "".join(parts)
    for key, text in (fixes.get("en_to_zh_text") or {}).items():
        en_to_zh[int(key)] = text or ""


def _fixes_override_en_to_zh(fixes: dict | None, en_sents: list[str]) -> dict[int, str] | None:
    """When fixes ship a near-complete map, use it exclusively (no paragraph fallback)."""
    raw = fixes.get("en_to_zh_text") if fixes else None
    if not raw or len(raw) < len(en_sents) * 0.85:
        return None
    return {int(k): (v or "") for k, v in raw.items()}


def _split_manifest_lines(manifest: dict, fixes: dict) -> None:
    """Split one long manifest line into timed sub-lines (each with its own zh)."""
    lines = manifest.get("lines", [])
    for spec in fixes.get("line_splits") or []:
        match_start = float(spec["match_start"])
        parts = spec.get("parts") or []
        if not parts:
            continue
        first_text = (parts[0].get("text") or "").strip()
        idx = None
        for i, line in enumerate(lines):
            if abs(line.get("start", 0) - match_start) >= 0.35:
                continue
            cur = (line.get("text") or "").strip()
            if first_text and (
                cur == first_text
                or cur.startswith(first_text[: min(48, len(first_text))])
            ):
                idx = i
                break
            if len(parts) > 1 and all(
                (parts[k].get("text") or "").strip() in cur for k in (0, len(parts) - 1) if parts[k].get("text")
            ):
                idx = i
                break
        if idx is None:
            continue
        if idx + 1 < len(lines):
            next_text = (lines[idx + 1].get("text") or "").strip()
            second_text = (parts[1].get("text") or "").strip() if len(parts) > 1 else ""
            if second_text and next_text.startswith(second_text[:24]):
                continue
        orig = lines[idx]
        if not parts:
            continue
        new_lines: list[dict] = []
        for pi, part in enumerate(parts):
            start = float(part.get("start", orig["start"] if pi == 0 else new_lines[-1]["end"]))
            end = float(part["end"])
            nl = {k: v for k, v in orig.items() if k not in ("zh", "text", "start", "end")}
            nl["start"] = start
            nl["end"] = end
            if part.get("text"):
                nl["text"] = part["text"]
            if part.get("zh"):
                nl["zh"] = part["zh"]
            new_lines.append(nl)
        new_lines[-1]["end"] = orig["end"]
        lines[idx : idx + 1] = new_lines


def _reapply_split_part_zh(manifest: dict, fixes: dict) -> None:
    """Re-attach zh on split sub-lines (short text like \"Who?\" misses sentence index)."""
    for spec in fixes.get("line_splits") or []:
        for part in spec.get("parts") or []:
            text = (part.get("text") or "").strip()
            zh = part.get("zh")
            if not text or not zh:
                continue
            for line in manifest.get("lines", []):
                if (line.get("text") or "").strip() == text:
                    line["zh"] = zh


def _apply_line_zh_overrides(manifest: dict, fixes: dict) -> None:
    for spec in fixes.get("line_zh_overrides") or []:
        match_start = float(spec["start"])
        best: dict | None = None
        best_delta = 0.55
        for line in manifest.get("lines", []):
            delta = abs(line.get("start", 0) - match_start)
            if delta < best_delta:
                best_delta = delta
                best = line
        if best is None:
            continue
        if spec.get("text"):
            best["text"] = spec["text"]
        best["zh"] = spec["zh"]


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


def _find_sentence_indices_in_text(en_sentences: list[str], text: str) -> list[int]:
    """All EPUB sentence indices whose text appears inside one aligned audio line."""
    text = text.strip()
    if not text:
        return []
    if text in en_sentences:
        return [en_sentences.index(text)]

    text_l = text.lower()
    hits: list[tuple[int, int]] = []
    for si, sent in enumerate(en_sentences):
        s = sent.strip()
        if len(s) < 6:
            continue
        for n in (min(55, len(s)), 35, 22, 14):
            key = s[:n].lower()
            if len(key) < 8:
                continue
            pos = text_l.find(key)
            if pos >= 0:
                hits.append((pos, si))
                break
    if not hits:
        si = _find_sentence_index(en_sentences, text)
        return [si] if si >= 0 else []
    hits.sort()
    out: list[int] = []
    for _, si in hits:
        if not out or out[-1] != si:
            out.append(si)
    return out


def _zh_for_manifest_line(
    en_sentences: list[str],
    en_to_zh: dict[int, str],
    text: str,
    *,
    join_threshold: int = 200,
) -> str:
    """Attach ZH to one manifest row. Join multiple EPUB sentences only on long merged audio lines."""
    text = text.strip()
    if not text:
        return ""
    indices = _find_sentence_indices_in_text(en_sentences, text)
    if not indices:
        return ""
    if len(indices) == 1 or len(text) < join_threshold:
        si = _find_sentence_index(en_sentences, text)
        pick = si if si >= 0 else indices[0]
        return (en_to_zh.get(pick) or "").strip()
    parts: list[str] = []
    for si in indices:
        zh = (en_to_zh.get(si) or "").strip()
        if zh and (not parts or zh != parts[-1]):
            parts.append(zh)
    return "".join(parts)


def _attach_bilingual_clips(manifest: dict, clips: list[dict], *, translation_source: str) -> dict:
    """Step ③: 1:1 zh from Agent clips (line count must match align output)."""
    lines = manifest.get("lines", [])
    if len(lines) != len(clips):
        raise SystemExit(
            f"bilingual_clips count {len(clips)} != manifest lines {len(lines)} — re-export clips or realign"
        )
    attached = 0
    for line, clip in zip(lines, clips):
        zh = (clip.get("zh") or "").strip()
        if clip.get("kind") == "heading":
            line["kind"] = "heading"
        if zh:
            line["zh"] = zh
            attached += 1
        elif "zh" in line:
            del line["zh"]
    manifest["total_sentences"] = len(lines)
    manifest["translation_source"] = translation_source
    manifest["translation_method"] = "bilingual_clips"
    manifest["translated_lines"] = attached
    return manifest


def attach(manifest: dict, en_data: dict, zh_data: dict, *, translation_source: str) -> dict:
    book_id = manifest.get("book_id", "hp01")
    chapter = int(manifest.get("chapter", 0))
    clips = load_bilingual_clips(book_id, chapter)
    if clips and manifest.get("align_mode") == "bilingual_clips":
        return _attach_bilingual_clips(manifest, clips, translation_source=translation_source)

    en_sents = en_data["sentences"]
    en_paras = en_data.get("merged_paragraphs") or []
    sent_paras = en_data.get("sentence_paragraphs") or []
    zh_sents = _coalesce_zh_sentences(zh_data["sentences"])
    heading_zh = zh_data.get("heading_zh") or (
        zh_sents[0] if zh_sents and (zh_data.get("kinds") or [None])[0] == "heading" else ""
    )

    fixes = _load_translation_fixes(manifest.get("book_id", "hp01"), int(manifest.get("chapter", 0)))
    en_to_zh: dict[int, str] = _fixes_override_en_to_zh(fixes, en_sents) or {}
    if not en_to_zh:
        if en_paras and sent_paras:
            align_paras, para_remap = _merge_fragment_en_paragraphs(en_paras)
            para_zh_lists = _align_sentences_dp_lists(align_paras, zh_sents, max_zh_per_en=6)
            para_sents: dict[int, list[int]] = {}
            for si, pi in enumerate(sent_paras):
                if si <= 0 or pi < 0:
                    continue
                new_pi = para_remap.get(pi, pi)
                para_sents.setdefault(new_pi, []).append(si)
            for pi, sis in para_sents.items():
                zh_list = para_zh_lists.get(pi, [])
                if not zh_list:
                    continue
                en_to_zh.update(_distribute_zh_in_paragraph(sis, en_sents, zh_list))
        else:
            merged_en, groups = _merge_en_for_alignment(en_sents)
            merged_map, _ = _align_sentences_dp(merged_en, zh_sents)
            for mi, idxs in enumerate(groups):
                zh = merged_map.get(mi, "")
                if not zh:
                    continue
                en_to_zh[idxs[0]] = zh
        if fixes:
            _apply_translation_fixes(en_to_zh, zh_data["sentences"], fixes)

    attached = 0
    for line in manifest.get("lines", []):
        if line.get("kind") == "heading":
            if heading_zh:
                line["zh"] = heading_zh
                attached += 1
            elif "zh" in line:
                del line["zh"]
            continue

        en_text = line.get("text", "").strip()
        zh = _zh_for_manifest_line(en_sents, en_to_zh, en_text)
        if zh:
            line["zh"] = zh
            attached += 1
        elif "zh" in line:
            del line["zh"]

    _dedupe_consecutive_manifest_zh(manifest)

    if fixes:
        _split_manifest_lines(manifest, fixes)
        _reapply_split_part_zh(manifest, fixes)
        _apply_line_zh_overrides(manifest, fixes)
        _dedupe_consecutive_manifest_zh(manifest)

    _merge_manifest_zh_groups(manifest)
    _dedupe_consecutive_manifest_zh(manifest)

    if heading_zh:
        for line in manifest.get("lines", []):
            if line.get("kind") == "heading":
                continue
            if (line.get("zh") or "").strip() == heading_zh.strip():
                line.pop("zh", None)
            break

    manifest["total_sentences"] = len(manifest.get("lines", []))
    attached = sum(1 for line in manifest.get("lines", []) if line.get("zh"))

    manifest["translation_source"] = translation_source
    manifest["translation_method"] = "anchor_map_merge_zh_groups"
    manifest["translated_lines"] = attached
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", default="hp01")
    parser.add_argument("--chapter", type=int, default=1)
    args = parser.parse_args()

    ch_pad = f"{args.chapter:02d}"
    mpath = manifest_path(args.book, args.chapter)
    en_path = sentences_path(args.book, args.chapter)
    zh_path = zh_extract_path(args.book, args.chapter)
    zh_src = str(zh_epub_path(args.book).relative_to(ROOT))

    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    en_data = json.loads(en_path.read_text(encoding="utf-8"))
    zh_data = json.loads(zh_path.read_text(encoding="utf-8"))

    manifest = attach(manifest, en_data, zh_data, translation_source=zh_src)
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Wrote {mpath} — zh on {manifest['translated_lines']}/"
        f"{len(manifest.get('lines', []))} lines"
    )


if __name__ == "__main__":
    main()
