#!/usr/bin/env python3
"""Audit harryputter book: EN text, ZH translation, and audio alignment."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from chapters import manifest_path  # noqa: E402


def _load_manifest(book_id: str, ch: int) -> dict:
    path = manifest_path(book_id, ch)
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _audio_duration(mp3: Path) -> float | None:
    try:
        import mutagen  # type: ignore

        return float(mutagen.File(str(mp3)).info.length)
    except Exception:
        pass
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(mp3),
            ],
            text=True,
        ).strip()
        return float(out)
    except Exception:
        return None


def audit_chapter(book_id: str, ch: int) -> dict:
    m = _load_manifest(book_id, ch)
    lines = m.get("lines") or []
    total = m.get("total_sentences") or len(lines)
    duration = float(m.get("duration") or 0)
    body_start = float(m.get("body_start_sec") or 0)

    mp3_rel = m.get("audio") or f"samples/{book_id}/chapter{ch:02d}.mp3"
    mp3 = ROOT / mp3_rel

    issues: list[str] = []
    warnings: list[str] = []

    if not mp3.is_file():
        issues.append(f"MP3 missing: {mp3_rel}")
    elif mp3.is_symlink():
        issues.append(f"MP3 is symlink: {mp3_rel}")

    if len(lines) != total:
        issues.append(f"manifest lines {len(lines)} != total_sentences {total}")

    no_time = [i for i, ln in enumerate(lines) if ln.get("start") is None or ln.get("end") is None]
    if no_time:
        issues.append(f"{len(no_time)} lines missing start/end")

    bad_order = []
    overlaps = []
    large_gaps = []
    for i, ln in enumerate(lines):
        s = float(ln.get("start") or 0)
        e = float(ln.get("end") or 0)
        if e <= s:
            bad_order.append(i)
        if i > 0:
            prev_e = float(lines[i - 1].get("end") or 0)
            if s < prev_e - 0.05:
                overlaps.append((i, prev_e - s))
            gap = s - prev_e
            if gap > 25 and not lines[i - 1].get("interpolated") and not ln.get("interpolated"):
                large_gaps.append((i, gap))

    if bad_order:
        issues.append(f"{len(bad_order)} lines with end<=start")
    if overlaps:
        warnings.append(f"{len(overlaps)} timestamp overlaps (max {max(o[1] for o in overlaps):.1f}s)")
    if large_gaps:
        warnings.append(f"{len(large_gaps)} gaps >25s (max {max(g[1] for g in large_gaps):.1f}s at line {large_gaps[0][0]})")

    last_end = float(lines[-1].get("end") or 0) if lines else 0
    if duration and last_end > duration + 2:
        issues.append(f"last line end {last_end:.1f}s > duration {duration:.1f}s")
    if duration and last_end < duration * 0.85:
        warnings.append(f"timeline ends at {last_end:.1f}s ({last_end/duration:.0%} of {duration:.1f}s audio)")

    interp = sum(1 for ln in lines if ln.get("interpolated"))
    low_conf = sum(1 for ln in lines if float(ln.get("confidence") or 0) < 0.75)
    no_zh = sum(1 for ln in lines if not (ln.get("zh") or "").strip())
    body_lines = [ln for ln in lines if ln.get("kind") != "heading"]
    no_zh_body = sum(1 for ln in body_lines if not (ln.get("zh") or "").strip())
    zh_pct = (len(body_lines) - no_zh_body) / len(body_lines) * 100 if body_lines else 0

    if no_zh_body > len(body_lines) * 0.25:
        warnings.append(f"zh missing on {no_zh_body}/{len(body_lines)} body lines ({zh_pct:.0f}% covered)")
    elif no_zh_body:
        warnings.append(f"zh missing on {no_zh_body} body lines")

    if interp > total * 0.15:
        warnings.append(f"high interpolated ratio {interp}/{total} ({interp/total:.0%})")

    mp3_dur = _audio_duration(mp3) if mp3.is_file() else None
    if mp3_dur and duration and abs(mp3_dur - duration) > 3:
        warnings.append(f"manifest duration {duration:.1f}s vs mp3 {mp3_dur:.1f}s")

    return {
        "chapter": ch,
        "title": m.get("title", ""),
        "lines": len(lines),
        "total": total,
        "duration": duration,
        "body_start": body_start,
        "interp": interp,
        "low_conf": low_conf,
        "no_zh": no_zh,
        "no_zh_body": no_zh_body,
        "zh_pct": zh_pct,
        "last_end": last_end,
        "issues": issues,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", default="hp01")
    parser.add_argument("--from", dest="from_ch", type=int, default=1)
    parser.add_argument("--to", type=int, default=17)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = []
    for ch in range(args.from_ch, args.to + 1):
        results.append(audit_chapter(args.book, ch))

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"=== {args.book} ch{args.from_ch:02d}–ch{args.to:02d} audit ===\n")
        issue_chs = []
        warn_chs = []
        for r in results:
            status = "OK"
            if r["issues"]:
                status = "FAIL"
                issue_chs.append(r["chapter"])
            elif r["warnings"]:
                status = "WARN"
                warn_chs.append(r["chapter"])
            print(
                f"{status:4} Ch{r['chapter']:02d}: {r['lines']}/{r['total']} lines, "
                f"zh {r['zh_pct']:.0f}%, interp {r['interp']}, low_conf {r['low_conf']}, "
                f"audio {r['last_end']:.0f}/{r['duration']:.0f}s"
            )
            for msg in r["issues"]:
                print(f"      ISSUE: {msg}")
            for msg in r["warnings"]:
                print(f"      warn: {msg}")

        print()
        print(f"Summary: {len(results)} chapters, {len(issue_chs)} fail, {len(warn_chs)} warn")
        if issue_chs:
            print(f"  FAIL: {issue_chs}")
        if warn_chs:
            print(f"  WARN: {warn_chs}")

    has_fail = any(r["issues"] for r in results)
    sys.exit(1 if has_fail else 0)


if __name__ == "__main__":
    main()
