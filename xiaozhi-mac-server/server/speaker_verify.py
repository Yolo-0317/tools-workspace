"""Optional speaker verification: only accept enrolled voice during voice turns."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from server.config import settings

log = logging.getLogger(__name__)

_ENCODER = None
_RESAMPLE_fn = None


def speaker_verify_available() -> bool:
    try:
        from resemblyzer import VoiceEncoder  # noqa: F401

        return True
    except ImportError:
        return False


def _print_path() -> Path:
    path = Path(settings.speaker_print_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_encoder():
    global _ENCODER
    if _ENCODER is None:
        from resemblyzer import VoiceEncoder

        _ENCODER = VoiceEncoder()
    return _ENCODER


def _resample_to_16k(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    global _RESAMPLE_fn
    if sample_rate == 16000:
        return audio.astype(np.float32, copy=False)
    if _RESAMPLE_fn is None:
        import librosa

        _RESAMPLE_fn = librosa.resample
    return _RESAMPLE_fn(audio, orig_sr=sample_rate, target_sr=16000).astype(np.float32)


def _embed_audio(audio: np.ndarray, sample_rate: int) -> np.ndarray | None:
    if audio.size < int(sample_rate * 0.6):
        return None
    wav = _resample_to_16k(audio, sample_rate)
    if wav.size < 9600:
        return None
    encoder = _load_encoder()
    return encoder.embed_utterance(wav)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-8:
        return 0.0
    return float(np.dot(a, b) / denom)


def is_enrolled() -> bool:
    return _print_path().is_file()


def status() -> dict[str, object]:
    return {
        "available": speaker_verify_available(),
        "enabled": settings.speaker_verify,
        "enrolled": is_enrolled(),
        "threshold": settings.speaker_verify_threshold,
        "path": str(_print_path()),
    }


def load_profile() -> np.ndarray | None:
    path = _print_path()
    if not path.is_file():
        return None
    data = np.load(path)
    emb = data.get("embedding")
    if emb is None:
        return None
    return np.asarray(emb, dtype=np.float32)


def save_profile(embedding: np.ndarray) -> None:
    path = _print_path()
    np.savez(path, embedding=np.asarray(embedding, dtype=np.float32))
    meta = {
        "threshold": settings.speaker_verify_threshold,
        "dims": int(embedding.shape[0]),
    }
    path.with_suffix(".json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_profile() -> bool:
    path = _print_path()
    removed = False
    if path.is_file():
        path.unlink()
        removed = True
    meta = path.with_suffix(".json")
    if meta.is_file():
        meta.unlink()
        removed = True
    return removed


def enroll_pcm(audio: np.ndarray, sample_rate: int) -> tuple[bool, str]:
    if not speaker_verify_available():
        return False, "未安装声纹依赖，请运行：pip install -r requirements-speaker.txt"
    embedding = _embed_audio(audio, sample_rate)
    if embedding is None:
        return False, "录音太短，请清晰说 2-3 秒，例如「我是小智的主人」。"
    save_profile(embedding)
    log.info("Speaker profile enrolled dims=%s", embedding.shape[0])
    return True, "声纹注册成功，之后只会响应你的声音。"


def verify_pcm(audio: np.ndarray, sample_rate: int) -> tuple[bool, float, str]:
    if not settings.speaker_verify:
        return True, 1.0, ""
    if not speaker_verify_available():
        return True, 1.0, ""
    profile = load_profile()
    if profile is None:
        return True, 1.0, ""
    embedding = _embed_audio(audio, sample_rate)
    if embedding is None:
        return False, 0.0, "声音太短，请靠近麦克风再说一次。"
    score = _cosine(profile, embedding)
    ok = score >= settings.speaker_verify_threshold
    if ok:
        return True, score, ""
    return (
        False,
        score,
        f"这不是已注册的声音（相似度 {score:.2f}），我只听主人的指令。",
    )
