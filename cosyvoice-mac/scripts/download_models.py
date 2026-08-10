#!/usr/bin/env python3
"""下载 Fun-CosyVoice3-0.5B 到 pretrained_models/。"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "pretrained_models" / "Fun-CosyVoice3-0.5B"
REPO_ID = "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"


def main() -> None:
    if (MODEL_DIR / "cosyvoice.yaml").exists() or any(MODEL_DIR.glob("*.pt")):
        print(f"模型已存在，跳过: {MODEL_DIR}")
        return

    MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
    print(f"从 HuggingFace 下载 {REPO_ID} -> {MODEL_DIR}")

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        from modelscope import snapshot_download  # type: ignore[no-redef]

    snapshot_download(REPO_ID, local_dir=str(MODEL_DIR))
    print("下载完成。")


if __name__ == "__main__":
    main()
