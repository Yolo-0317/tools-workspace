#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Callable, Mapping, TextIO

from zhixia_tts_client import DoubaoTTSClient
from zhixia_tts_manifest import load_episode_manifest, load_voice_config
from zhixia_tts_pipeline import (
    GenerationPlan,
    TTSClient,
    build_generation_plan,
    generate_pending_lines,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_KEY_NAME = "VOLCENGINE_SPEECH_API_KEY"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="预览或生成一字三诗角色配音",
    )
    parser.add_argument("--episode", required=True, help="剧集编号，例如 ep04")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="确认后调用豆包 TTS；缺省时只预览",
    )
    parser.add_argument("--line", help="仅处理一个台词 ID，例如 03-poem-02")
    return parser


def _load_api_key(root: Path, environ: Mapping[str, str]) -> str | None:
    environment_value = environ.get(API_KEY_NAME, "").strip()
    if environment_value:
        return environment_value

    dotenv_path = root / ".env"
    if not dotenv_path.is_file():
        return None
    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    prefix = f"{API_KEY_NAME}="
    for line in lines:
        if not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        return value or None
    return None


def _select_line(plan: GenerationPlan, line_id: str | None) -> GenerationPlan:
    if line_id is None:
        return plan
    known_ids = {line.id for line in plan.manifest.lines}
    if line_id not in known_ids:
        raise ValueError(f"配音清单中不存在台词：{line_id}")
    ready = tuple(state for state in plan.ready if state.line.id == line_id)
    pending = tuple(state for state in plan.pending if state.line.id == line_id)
    return replace(
        plan,
        ready=ready,
        pending=pending,
        total_characters=sum(len(state.line.text) for state in pending),
    )


def _print_plan(plan: GenerationPlan, stdout: TextIO) -> None:
    role_counts = Counter(state.line.role for state in plan.pending)
    print(f"剧集：{plan.manifest.episode}，主题：{plan.manifest.theme}", file=stdout)
    print(f"待生成：{len(plan.pending)} 句", file=stdout)
    print(f"已就绪并跳过：{len(plan.ready)} 句", file=stdout)
    for role, count in sorted(role_counts.items()):
        print(f"{plan.manifest.voices[role].name}：{count} 句", file=stdout)
    print(f"待生成字符数：{plan.total_characters}", file=stdout)
    print(f"输出目录：{plan.audio_dir}", file=stdout)
    print(f"预计产生豆包 TTS 调用：{plan.expected_api_calls} 次", file=stdout)
    if plan.pending:
        print(
            "待生成台词：" + "、".join(state.line.id for state in plan.pending),
            file=stdout,
        )


def _redact(message: str, secret: str | None) -> str:
    if secret:
        return message.replace(secret, "[REDACTED]")
    return message


def run_cli(
    argv: list[str] | None = None,
    *,
    project_root: str | Path | None = None,
    client_factory: Callable[[str], TTSClient] = DoubaoTTSClient,
    input_func: Callable[[str], str] = input,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    environ: Mapping[str, str] | None = None,
) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    try:
        voices = load_voice_config(root / "config" / "voices.json")
        manifest_path = root / "episodes" / args.episode / "voice-lines.json"
        manifest = load_episode_manifest(manifest_path, voices)
        if manifest.episode != args.episode:
            raise ValueError(
                f"清单 episode 为 {manifest.episode}，与参数 {args.episode} 不一致"
            )
        plan = _select_line(
            build_generation_plan(root, manifest),
            args.line,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"无法建立生成计划：{exc}", file=stderr)
        return 2

    _print_plan(plan, stdout)
    if not args.generate:
        print("当前为预览模式，未调用语音接口。", file=stdout)
        return 0
    if plan.expected_api_calls == 0:
        print("没有待生成台词，未调用语音接口。", file=stdout)
        return 0

    confirmation = f"GENERATE {manifest.episode}"
    print(
        f"即将产生 {plan.expected_api_calls} 次豆包 TTS 调用。"
        f"请输入 {confirmation} 继续：",
        file=stdout,
    )
    if input_func("> ") != confirmation:
        print(f"已取消：确认文字必须完全一致为 {confirmation}。", file=stdout)
        return 2

    environment = os.environ if environ is None else environ
    api_key = _load_api_key(root, environment)
    if not api_key:
        print(
            f"缺少 {API_KEY_NAME}，请先配置环境变量或项目 .env。",
            file=stderr,
        )
        return 2

    try:
        client = client_factory(api_key)
        completed = generate_pending_lines(plan, client)
    except Exception as exc:
        safe_message = _redact(str(exc), api_key)
        print(f"生成失败：{type(exc).__name__}: {safe_message}", file=stderr)
        return 1

    generated_count = plan.expected_api_calls
    print(f"生成完成：本次生成 {generated_count} 句。", file=stdout)
    if completed.pending:
        print(f"整集仍有 {len(completed.pending)} 句待生成。", file=stdout)
    else:
        print(f"五句均已就绪，字幕已写入：{completed.subtitle_path}", file=stdout)
    return 0


def main(argv: list[str] | None = None) -> int:
    return run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
