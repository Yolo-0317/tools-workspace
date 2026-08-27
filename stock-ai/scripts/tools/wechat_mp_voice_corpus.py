#!/usr/bin/env python3
"""写稿语料库：代码侧 prompt 与 skill 同步。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "data" / "wechat_mp_voice_corpus"
SKILL_DIR = ROOT.parent / ".cursor" / "skills" / "wechat-mp-writing"


def load_discussion_voice_prompt(*, dianji: bool = False) -> str:
    base_path = CORPUS_DIR / "discussion_base.txt"
    if not base_path.is_file():
        return _legacy_fallback()
    parts = [base_path.read_text(encoding="utf-8").strip()]
    if dianji:
        dianji_path = CORPUS_DIR / "discussion_dianji.txt"
        if dianji_path.is_file():
            parts.append(dianji_path.read_text(encoding="utf-8").strip())
    return "\n\n".join(p for p in parts if p)


def _legacy_fallback() -> str:
    from scripts.tools.wechat_mp_tv_review_article import _discussion_voice_prompt_block_legacy

    return _discussion_voice_prompt_block_legacy()


def cmd_sync(_: argparse.Namespace) -> int:
    """检查语料文件存在；skill 真源为 .cursor/skills/wechat-mp-writing/voice-corpus*.md"""
    missing = []
    for name in ("discussion_base.txt", "discussion_dianji.txt"):
        if not (CORPUS_DIR / name).is_file():
            missing.append(name)
    if missing:
        print("缺少:", ", ".join(missing), file=sys.stderr)
        return 1
    skill_voice = SKILL_DIR / "voice-corpus.md"
    skill_dianji = SKILL_DIR / "voice-corpus-dianji.md"
    print("OK 代码 prompt 已就绪:", CORPUS_DIR)
    if skill_voice.is_file():
        print("  skill 真源:", skill_voice)
    if skill_dianji.is_file():
        print("  专栏叠加:", skill_dianji)
    print("改语气/用词：先改 skill 中 §六用词表与 §七金样，再同步本目录 txt。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="写稿语料库")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_sync = sub.add_parser("sync", help="检查语料库与 skill 路径")
    p_sync.set_defaults(func=cmd_sync)
    p_show = sub.add_parser("show", help="打印合并后的 discussion prompt")
    p_show.add_argument("--dianji", action="store_true")
    p_show.set_defaults(func=lambda a: print(load_discussion_voice_prompt(dianji=a.dianji)) or 0)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
