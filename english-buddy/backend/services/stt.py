"""Local speech-to-text via faster-whisper (per-worker model isolation)."""

from __future__ import annotations

import asyncio
import io
import os
import tempfile
import threading
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

# Load .env before reading WHISPER_* (uvicorn import order may skip main.py's load_dotenv).
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

_DEFAULT_LOCAL = Path.home() / ".cache" / "faster-whisper-small"


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default)).strip()))
    except ValueError:
        return default


def _default_whisper_model() -> str:
    if _DEFAULT_LOCAL.is_dir() and (_DEFAULT_LOCAL / "model.bin").is_file():
        return str(_DEFAULT_LOCAL)
    return "small"


WHISPER_MODEL = _env("WHISPER_MODEL", _default_whisper_model())
WHISPER_DEVICE = _env("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = _env("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_LANGUAGE = _env("WHISPER_LANGUAGE", "en")
WHISPER_WORKERS = _env_int("WHISPER_WORKERS", 2)

_thread_local = threading.local()
_executor_lock = threading.Lock()
_workers_ready_lock = threading.Lock()
_stt_executor: ThreadPoolExecutor | None = None
_stt_sem: asyncio.Semaphore | None = None
_workers_ready = 0
_model_error: str | None = None


def _resolve_model_id() -> str:
    """WHISPER_MODEL can be a hub name (small) or a local directory from download_whisper.sh."""
    path = os.path.expanduser(WHISPER_MODEL)
    if os.path.isdir(path) and os.path.isfile(os.path.join(path, "model.bin")):
        if not os.path.isfile(os.path.join(path, "vocabulary.txt")):
            raise RuntimeError(
                f"Whisper dir missing vocabulary.txt — run: ./scripts/download_whisper.sh"
            )
        return path
    return WHISPER_MODEL


def _create_model() -> "WhisperModel":
    global _model_error
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        _model_error = "faster-whisper not installed"
        raise RuntimeError(_model_error) from e
    try:
        model = WhisperModel(
            _resolve_model_id(),
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        _model_error = None
        return model
    except Exception as e:
        _model_error = str(e)
        raise RuntimeError(f"Whisper load failed: {e}") from e


def _get_executor() -> ThreadPoolExecutor:
    global _stt_executor
    if _stt_executor is not None:
        return _stt_executor
    with _executor_lock:
        if _stt_executor is None:
            _stt_executor = ThreadPoolExecutor(
                max_workers=WHISPER_WORKERS,
                thread_name_prefix="whisper",
            )
    return _stt_executor


def _get_sem() -> asyncio.Semaphore:
    global _stt_sem
    if _stt_sem is None:
        _stt_sem = asyncio.Semaphore(WHISPER_WORKERS)
    return _stt_sem


def _worker_model() -> "WhisperModel":
    global _workers_ready
    model = getattr(_thread_local, "model", None)
    if model is not None:
        return model
    model = _create_model()
    _thread_local.model = model
    with _workers_ready_lock:
        _workers_ready += 1
    return model


def whisper_status() -> dict[str, str | bool | int]:
    resolved = _resolve_model_id()
    local = os.path.isdir(os.path.expanduser(resolved))
    if _workers_ready > 0:
        return {
            "ready": True,
            "model": resolved,
            "local": local,
            "error": "",
            "workers": WHISPER_WORKERS,
            "workers_ready": _workers_ready,
        }
    if _model_error:
        return {
            "ready": False,
            "model": resolved,
            "local": local,
            "error": _model_error,
            "workers": WHISPER_WORKERS,
            "workers_ready": 0,
        }
    return {
        "ready": False,
        "model": resolved,
        "local": local,
        "error": "",
        "workers": WHISPER_WORKERS,
        "workers_ready": 0,
    }


def pcm16_to_wav(pcm: bytes, sample_rate: int = 16000) -> bytes:
    """Wrap raw int16 mono PCM in a WAV container for decoding."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def _transcribe_sync(wav_bytes: bytes, *, fast: bool = False) -> str:
    model = _worker_model()
    path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            path = tmp.name
        transcribe_kw: dict = dict(
            language=WHISPER_LANGUAGE,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=400,
                speech_pad_ms=200,
            ),
        )
        if fast:
            transcribe_kw.update(beam_size=1, best_of=1, temperature=0.0)
        segments, _info = model.transcribe(path, **transcribe_kw)
        parts = [seg.text.strip() for seg in segments if seg.text.strip()]
        return " ".join(parts).strip()
    finally:
        if path and os.path.exists(path):
            os.unlink(path)


def _warmup_worker() -> None:
    _worker_model()


async def transcribe_pcm(
    pcm: bytes,
    sample_rate: int = 16000,
    *,
    fast: bool = False,
) -> str:
    if len(pcm) < sample_rate * 2 * 0.25:  # < 0.25s
        return ""
    wav = pcm16_to_wav(pcm, sample_rate)
    loop = asyncio.get_running_loop()
    async with _get_sem():
        return await loop.run_in_executor(
            _get_executor(),
            lambda: _transcribe_sync(wav, fast=fast),
        )


async def warmup() -> None:
    """Pre-load one Whisper model per worker thread."""
    loop = asyncio.get_running_loop()
    executor = _get_executor()
    tasks = [
        loop.run_in_executor(executor, _warmup_worker)
        for _ in range(WHISPER_WORKERS)
    ]
    await asyncio.gather(*tasks)
