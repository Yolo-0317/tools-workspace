#!/usr/bin/env python3
"""
儿童故事 TTS — CosyVoice 3 instruct2 / zero_shot。

示例:
  python scripts/tts_story.py --text-file stories/sample_story.txt --out outputs/sample.wav
  python scripts/tts_story.py --text "小兔子说：妈妈，晚安！" --mode instruct
  python scripts/tts_story.py --batch stories/ --out-dir outputs/
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import torch
import torchaudio

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "CosyVoice"
sys.path.insert(0, str(VENDOR))
sys.path.insert(0, str(VENDOR / "third_party" / "Matcha-TTS"))

from cosyvoice.cli.cosyvoice import AutoModel  # noqa: E402

DEFAULT_INSTRUCT = (
    "You are a gentle storyteller for children. "
    "请用温柔、缓慢、亲切的语气讲睡前故事。<|endofprompt|>"
)


def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


def resolve_path(raw: str | Path) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def get_model() -> AutoModel:
    model_dir = resolve_path(
        os.environ.get("COSYVOICE_MODEL_DIR", "pretrained_models/Fun-CosyVoice3-0.5B")
    )
    return AutoModel(model_dir=str(model_dir))


def synthesize(
    model: AutoModel,
    text: str,
    prompt_wav: Path,
    out_path: Path,
    *,
    mode: str,
    instruct: str,
) -> float:
    t0 = time.perf_counter()
    chunks: list = []

    if mode == "instruct":
        stream = model.inference_instruct2(
            text,
            instruct,
            str(prompt_wav),
            stream=False,
        )
    else:
        prompt_text = "You are a helpful assistant.<|endofprompt|>希望你以后能够做的比我还好呦。"
        stream = model.inference_zero_shot(
            text,
            prompt_text,
            str(prompt_wav),
            stream=False,
        )

    for _, item in enumerate(stream):
        chunks.append(item["tts_speech"])

    if not chunks:
        raise RuntimeError("未生成音频")

    audio = chunks[0] if len(chunks) == 1 else torch.cat(chunks, dim=-1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(out_path), audio, model.sample_rate)
    elapsed = time.perf_counter() - t0
    duration = audio.shape[-1] / model.sample_rate
    rtf = elapsed / max(duration, 0.01)
    print(f"已保存: {out_path}  ({duration:.1f}s 音频, {elapsed:.1f}s 合成, RTF={rtf:.2f})")
    return rtf


def read_text_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    # 去掉纯注释行
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    return "\n".join(lines).strip()


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="CosyVoice 3 儿童故事 TTS")
    parser.add_argument("--text", help="要合成的文本")
    parser.add_argument("--text-file", type=Path, help="故事文本文件")
    parser.add_argument("--out", type=Path, default=Path("outputs/story.wav"))
    parser.add_argument("--out-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--batch", type=Path, help="批量处理目录下 .txt")
    parser.add_argument(
        "--mode",
        choices=("instruct", "zero_shot"),
        default="instruct",
        help="instruct=语气可控讲故事; zero_shot=偏克隆参考音色",
    )
    parser.add_argument("--instruct", default=os.environ.get("COSYVOICE_STORY_INSTRUCT", DEFAULT_INSTRUCT))
    parser.add_argument("--prompt-wav", type=Path, default=None)
    args = parser.parse_args()

    prompt_wav = resolve_path(
        args.prompt_wav
        or os.environ.get("COSYVOICE_PROMPT_WAV", "vendor/CosyVoice/asset/zero_shot_prompt.wav")
    )
    if not prompt_wav.exists():
        sys.exit(f"参考音频不存在: {prompt_wav}，请先 bash scripts/install.sh")

    device = os.environ.get("COSYVOICE_DEVICE", "cpu")
    if device == "mps":
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

    print(f"加载模型（首次约 30s）...  device={device}")
    model = get_model()

    jobs: list[tuple[str, Path]] = []

    if args.batch:
        batch_dir = resolve_path(args.batch)
        for txt in sorted(batch_dir.glob("*.txt")):
            jobs.append((read_text_file(txt), args.out_dir / f"{txt.stem}.wav"))
    elif args.text_file:
        jobs.append((read_text_file(resolve_path(args.text_file)), resolve_path(args.out)))
    elif args.text:
        jobs.append((args.text.strip(), resolve_path(args.out)))
    else:
        parser.error("请指定 --text、--text-file 或 --batch")

    for text, out_path in jobs:
        if not text:
            print(f"跳过空文本: {out_path}")
            continue
        print(f"\n合成 ({len(text)} 字): {text[:40]}...")
        synthesize(
            model,
            text,
            prompt_wav,
            out_path,
            mode=args.mode,
            instruct=args.instruct,
        )


if __name__ == "__main__":
    main()
