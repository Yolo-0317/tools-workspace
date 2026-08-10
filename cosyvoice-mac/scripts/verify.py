#!/usr/bin/env python3
"""冒烟测试：检查环境、模型、参考音频。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "CosyVoice"
sys.path.insert(0, str(VENDOR))
sys.path.insert(0, str(VENDOR / "third_party" / "Matcha-TTS"))


def _ok(msg: str) -> None:
    print(f"OK  {msg}")


def _fail(msg: str) -> None:
    print(f"FAIL {msg}")
    sys.exit(1)


def main() -> None:
    import torch

    arch = os.uname().machine
    _ok(f"架构: {arch}")
    _ok(f"Python: {sys.version.split()[0]}")
    _ok(f"PyTorch: {torch.__version__}")

    if not VENDOR.is_dir():
        _fail(f"缺少上游仓库，请运行: bash scripts/install.sh  ({VENDOR})")

    model_dir = Path(
        os.environ.get("COSYVOICE_MODEL_DIR", ROOT / "pretrained_models" / "Fun-CosyVoice3-0.5B")
    )
    if not model_dir.is_absolute():
        model_dir = ROOT / model_dir
    if not model_dir.exists():
        _fail(f"模型未下载: {model_dir}")

    prompt = Path(
        os.environ.get(
            "COSYVOICE_PROMPT_WAV",
            VENDOR / "asset" / "zero_shot_prompt.wav",
        )
    )
    if not prompt.is_absolute():
        prompt = ROOT / prompt
    if not prompt.exists():
        _fail(f"参考音频不存在: {prompt}")

    device = os.environ.get("COSYVOICE_DEVICE", "cpu")
    if device == "mps":
        if not torch.backends.mps.is_available():
            _fail("COSYVOICE_DEVICE=mps 但 MPS 不可用，请改 cpu")
        _ok("MPS 可用（实验性，官方更推荐 cpu）")
    else:
        _ok(f"设备: {device}")

    _ok(f"模型: {model_dir}")
    _ok(f"参考音: {prompt}")
    print("\n环境检查通过。可运行 tts_story.py 生成试音。")


if __name__ == "__main__":
    main()
