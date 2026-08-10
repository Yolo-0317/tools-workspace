#!/usr/bin/env python3
"""
Audit bilingual_clips: structural + narrative-order checks.

美版音频切分 ≠ EPUB 句序；中文是叙事节拍，不能按 en_to_zh[epub_i] 逐句验收。
本脚本用 zh_extract 全文做「叙事游标」：按 clip 播放顺序，每条 zh 应落在游标附近。

用法:
  python3 scripts/audit_bilingual_clips.py --book hp01 --chapter 1
  python3 scripts/audit_bilingual_clips.py --book hp01 --chapter 1 --json
  python3 scripts/audit_bilingual_clips.py --book hp01 --from 1 --to 4 --fail-on drift
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from bilingual_clips import load_bilingual_clips  # noqa: E402
from chapters import manifest_path, zh_extract_path  # noqa: E402

_PUNCT_RE = re.compile(r"[\s…\.。！？、，：:；;""''\"'—\-\(\)（）\[\]]+")


def _norm(s: str) -> str:
    s = s.replace("……", "…").replace("...", "…")
    return _PUNCT_RE.sub("", s)


def _join_zh(zh: list[str], start: int, end: int) -> str:
    return "".join(zh[i] for i in range(start, end) if 0 <= i < len(zh))


@dataclass
class ClipIssue:
    clip: int
    start_sec: float | None
    code: str
    detail: str
    en_preview: str = ""
    zh_preview: str = ""


@dataclass
class ChapterReport:
    book: str
    chapter: int
    clips: int
    structural_ok: bool
    narrative_ok: bool
    no_zh: int = 0
    consec_dup: int = 0
    prefix_dup: int = 0
    shard_only: int = 0
    drift: int = 0
    orphan: int = 0
    backward: int = 0
    cursor_lost: int = 0
    issues: list[ClipIssue] = field(default_factory=list)


def _structural_audit(
    clips: list[dict],
    starts: list[float | None],
) -> tuple[bool, list[ClipIssue], dict[str, int]]:
    issues: list[ClipIssue] = []
    counts = {"no_zh": 0, "consec_dup": 0, "prefix_dup": 0, "shard_only": 0}

    for i, clip in enumerate(clips):
        if clip.get("kind") == "heading":
            continue
        zh = (clip.get("zh") or "").strip()
        en = (clip.get("en") or "").strip()
        if not zh:
            counts["no_zh"] += 1
            issues.append(
                ClipIssue(i, starts[i], "no_zh", "missing zh", en[:60], "")
            )
            continue
        if len(_norm(zh)) <= 2 and len(en) > 40:
            counts["shard_only"] += 1
            issues.append(
                ClipIssue(i, starts[i], "shard_only", "zh is punctuation shard on long en", en[:60], zh)
            )

    for i in range(1, len(clips)):
        z1 = (clips[i - 1].get("zh") or "").strip()
        z2 = (clips[i].get("zh") or "").strip()
        if not z1 or not z2:
            continue
        if z1 == z2:
            counts["consec_dup"] += 1
            issues.append(
                ClipIssue(i, starts[i], "consec_dup", "identical to previous clip", "", z2[:60])
            )
        elif len(z1) > 12 and (z2.startswith(z1) or z1.startswith(z2)):
            counts["prefix_dup"] += 1
            issues.append(
                ClipIssue(
                    i,
                    starts[i],
                    "prefix_dup",
                    "zh is prefix/suffix of previous (likely repeat)",
                    "",
                    z2[:60],
                )
            )

    ok = counts["no_zh"] == 0 and counts["consec_dup"] == 0
    return ok, issues, counts


def _find_in_zh(
    zh: list[str],
    clip_zh: str,
    cursor: int,
    *,
    look_ahead: int,
    max_span: int,
    allow_backward: int = 2,
) -> tuple[int | None, int, str]:
    """Return (new_cursor, span, code): ok | jump | backward | orphan."""
    needle = _norm(clip_zh)
    if len(needle) <= 2:
        return cursor, 0, "skip"

    best: tuple[int, int, int] | None = None  # (distance, start_idx, span)
    start = max(1, cursor - allow_backward)
    end = min(len(zh), cursor + look_ahead + 1)

    for zi in range(start, end):
        for span in range(1, max_span + 1):
            if zi + span > len(zh):
                break
            chunk = _join_zh(zh, zi, zi + span)
            nchunk = _norm(chunk)
            if not nchunk:
                continue
            if needle in nchunk or nchunk in needle:
                dist = abs(zi - cursor)
                if best is None or dist < best[0]:
                    best = (dist, zi, span)

    if best is None:
        # wide resync: clip zh may be correct but cursor was lost earlier
        for zi in range(cursor, min(len(zh), cursor + 80)):
            for span in range(1, max_span + 1):
                if zi + span > len(zh):
                    break
                nchunk = _norm(_join_zh(zh, zi, zi + span))
                if nchunk and (needle in nchunk or nchunk in needle):
                    return zi + span, span, "cursor_lost"
        return None, 0, "orphan"

    dist, zi, span = best
    if zi < cursor - 1:
        return zi + span, span, "backward"
    if zi > cursor + look_ahead:
        return zi + span, span, "jump"
    return zi + span, span, "ok"


def _narrative_audit(
    clips: list[dict],
    zh: list[str],
    starts: list[float | None],
    *,
    look_ahead: int = 12,
) -> tuple[bool, list[ClipIssue], dict[str, int]]:
    issues: list[ClipIssue] = []
    counts = {"drift": 0, "orphan": 0, "backward": 0, "cursor_lost": 0}
    cursor = 1  # zh[0] is chapter heading

    for i, clip in enumerate(clips):
        if clip.get("kind") == "heading":
            continue
        clip_zh = (clip.get("zh") or "").strip()
        if not clip_zh:
            continue

        new_cursor, _span, code = _find_in_zh(
            zh, clip_zh, cursor, look_ahead=look_ahead, max_span=6
        )
        if code == "skip":
            continue
        if code in ("ok", "jump"):
            if new_cursor is not None:
                cursor = new_cursor
            if code == "jump":
                counts["drift"] += 1
                issues.append(
                    ClipIssue(
                        i,
                        starts[i],
                        code,
                        f"narrative skipped ahead (cursor was {cursor - _span})",
                        (clip.get("en") or "")[:60],
                        clip_zh[:60],
                    )
                )
            continue
        if code == "cursor_lost":
            counts["drift"] += 1
            counts["cursor_lost"] += 1
            issues.append(
                ClipIssue(
                    i,
                    starts[i],
                    code,
                    f"zh matches zh_extract but cursor was behind (resynced at {new_cursor})",
                    (clip.get("en") or "")[:60],
                    clip_zh[:60],
                )
            )
            if new_cursor is not None:
                cursor = new_cursor
            continue

        counts["drift"] += 1
        if code == "orphan":
            counts["orphan"] += 1
        elif code == "backward":
            counts["backward"] += 1

        issues.append(
            ClipIssue(
                i,
                starts[i],
                code,
                f"narrative cursor={cursor}, no match in zh_extract window",
                (clip.get("en") or "")[:60],
                clip_zh[:60],
            )
        )

    ok = counts["drift"] == 0
    return ok, issues, counts


def audit_chapter(
    book: str,
    chapter: int,
    *,
    look_ahead: int = 12,
) -> ChapterReport:
    clips = load_bilingual_clips(book, chapter)
    if not clips:
        raise SystemExit(f"No bilingual_clips for {book} ch{chapter}")

    manifest = json.loads(manifest_path(book, chapter).read_text(encoding="utf-8"))
    lines = manifest.get("lines", [])
    starts: list[float | None] = [None] * len(clips)
    for i, ln in enumerate(lines[: len(clips)]):
        starts[i] = ln.get("start")

    zh = json.loads(zh_extract_path(book, chapter).read_text(encoding="utf-8"))["sentences"]

    struct_ok, struct_issues, struct_counts = _structural_audit(clips, starts)
    narr_ok, narr_issues, narr_counts = _narrative_audit(
        clips, zh, starts, look_ahead=look_ahead
    )

    all_issues = struct_issues + narr_issues
    return ChapterReport(
        book=book,
        chapter=chapter,
        clips=len(clips),
        structural_ok=struct_ok,
        narrative_ok=narr_ok,
        no_zh=struct_counts["no_zh"],
        consec_dup=struct_counts["consec_dup"],
        prefix_dup=struct_counts["prefix_dup"],
        shard_only=struct_counts["shard_only"],
        drift=narr_counts["drift"],
        orphan=narr_counts["orphan"],
        backward=narr_counts["backward"],
        cursor_lost=narr_counts["cursor_lost"],
        issues=all_issues,
    )


def _fmt_time(sec: float | None) -> str:
    if sec is None:
        return "??:??"
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m}:{s:02d}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit bilingual_clips structural + narrative order")
    parser.add_argument("--book", default="hp01")
    parser.add_argument("--chapter", type=int, default=None)
    parser.add_argument("--from", dest="from_ch", type=int, default=1)
    parser.add_argument("--to", type=int, default=17)
    parser.add_argument("--look-ahead", type=int, default=12, help="zh_extract sentences to search ahead")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--fail-on",
        choices=("structural", "drift", "any"),
        default=None,
        help="exit 1 if checks fail",
    )
    args = parser.parse_args()

    chapters = [args.chapter] if args.chapter else list(range(args.from_ch, args.to + 1))
    reports = [audit_chapter(args.book, ch, look_ahead=args.look_ahead) for ch in chapters]

    if args.json:
        print(json.dumps([asdict(r) for r in reports], ensure_ascii=False, indent=2))
    else:
        for r in reports:
            flag = "OK" if r.structural_ok and r.narrative_ok else "FAIL"
            print(
                f"{flag} {r.book} ch{r.chapter:02d}: clips={r.clips} "
                f"struct(no_zh={r.no_zh} consec_dup={r.consec_dup} prefix_dup={r.prefix_dup} shard={r.shard_only}) "
                f"narrative(drift={r.drift} orphan={r.orphan} cursor_lost={r.cursor_lost} backward={r.backward})"
            )
            if r.issues:
                print("  flagged clips:")
                for iss in r.issues[:40]:
                    print(
                        f"    [{iss.clip:3d}] {_fmt_time(iss.start_sec)} {iss.code:12s} {iss.detail[:50]}"
                    )
                    if iss.zh_preview:
                        print(f"          zh: {iss.zh_preview}")
                if len(r.issues) > 40:
                    print(f"    ... +{len(r.issues) - 40} more")
            print()

    if args.fail_on:
        for r in reports:
            if args.fail_on == "structural" and not r.structural_ok:
                raise SystemExit(1)
            if args.fail_on == "drift" and not r.narrative_ok:
                raise SystemExit(1)
            if args.fail_on == "any" and (not r.structural_ok or not r.narrative_ok):
                raise SystemExit(1)


if __name__ == "__main__":
    main()
