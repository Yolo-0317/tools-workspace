#!/usr/bin/env python3
"""Read a .txt fragment and ask Hermes 3 to continue / rewrite in the same voice."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from hermes_client import HermesClient, HermesConfig
from prompt_loader import load_prompt_file, render_user_prompt
from txt_source import extract_by_markers, extract_chapter_range, read_text_file, trim_fragment


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Load a novel .txt slice and continue it with Hermes 3 via Ollama.",
    )
    p.add_argument("--file", "-f", required=True, help="Path to source .txt")
    p.add_argument("--encoding", default="gbk", help="File encoding (default: gbk for legacy novels)")
    p.add_argument("--max-chars", type=int, default=12000, help="Max chars of fragment sent to model")

    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--chapter-start", help="Start chapter label, e.g. 七十")
    g.add_argument("--start-marker", help="Raw start marker string in file")
    p.add_argument("--chapter-end", help="End chapter label (exclusive), e.g. 七十三")
    p.add_argument("--end-marker", help="Raw end marker string (exclusive)")

    p.add_argument(
        "--system-prompt",
        default="novel_system.txt",
        help="System prompt file (name under prompts/ or absolute path). EDIT STYLE HERE.",
    )
    p.add_argument(
        "--user-prompt",
        default="novel_user.txt",
        help="User prompt template with {fragment} {task} {word_count}. EDIT TASK WRAPPER HERE.",
    )
    p.add_argument(
        "--task",
        default=None,
        help="Inline task text; overrides --task-file",
    )
    p.add_argument(
        "--task-file",
        default="novel_task_default.txt",
        help="Task instructions file. EDIT WHAT TO WRITE HERE.",
    )
    p.add_argument("--word-count", type=int, default=1500, help="Target length hint for the model")
    p.add_argument("--num-predict", type=int, default=4096, help="Max tokens to generate")
    p.add_argument("--host", default=None)
    p.add_argument("--model", default=None)
    p.add_argument(
        "--output",
        "-o",
        default=None,
        help="Save result to file (default: outputs/<timestamp>.txt)",
    )
    p.add_argument("--no-stream", action="store_true")
    return p


def pick_fragment(args: argparse.Namespace, text: str) -> str:
    if args.chapter_start:
        fragment = extract_chapter_range(text, args.chapter_start, args.chapter_end)
    else:
        fragment = extract_by_markers(text, start=args.start_marker, end=args.end_marker)
    return trim_fragment(fragment, max_chars=args.max_chars)


def main() -> int:
    args = build_parser().parse_args()

    text = read_text_file(args.file, encoding=args.encoding)
    fragment = pick_fragment(args, text)

    system = load_prompt_file(args.system_prompt)
    user_template = load_prompt_file(args.user_prompt)
    task = args.task if args.task is not None else load_prompt_file(args.task_file)
    user_message = render_user_prompt(
        user_template,
        fragment=fragment,
        task=task,
        word_count=args.word_count,
    )

    config = HermesConfig(system=system)
    if args.host:
        config.host = args.host
    if args.model:
        config.model = args.model

    client = HermesClient(config)
    if not client.ping():
        print(
            f"Ollama unavailable or model missing ({config.model}).",
            file=sys.stderr,
        )
        return 1

    print(f"Fragment: {len(fragment)} chars -> model: {config.model}", file=sys.stderr)
    print("Generating...\n", file=sys.stderr)

    result = client.complete(
        user_message,
        stream=not args.no_stream,
        num_predict=args.num_predict,
    )

    if isinstance(result, str):
        body = result
        print(body)
    else:
        chunks: list[str] = []
        for token in result:
            print(token, end="", flush=True)
            chunks.append(token)
        print()
        body = "".join(chunks)

    out_path = Path(args.output) if args.output else Path("outputs") / f"continuation_{datetime.now():%Y%m%d_%H%M%S}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body + "\n", encoding="utf-8")
    print(f"\nSaved: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
