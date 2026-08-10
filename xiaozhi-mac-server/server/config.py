"""Load settings from environment / .env."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".env.example", override=False)
# Monorepo: reuse stock-ai DeepSeek key when not set locally.
_STOCK_AI_ENV = _ROOT.parent / "stock-ai" / ".env"
if _STOCK_AI_ENV.is_file():
    load_dotenv(_STOCK_AI_ENV, override=False)


def _lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


_XIAOZHI_WHISPER_PROFILES = {
    "fast": Path.home() / ".cache" / "xiaozhi-whisper-tiny",
    "balanced": Path.home() / ".cache" / "xiaozhi-whisper-base",
    "accurate": Path.home() / ".cache" / "xiaozhi-whisper-small",
}
_XIAOZHI_WHISPER_DEFAULT = _XIAOZHI_WHISPER_PROFILES["balanced"]


def _whisper_model_path() -> str:
    raw = os.getenv("WHISPER_MODEL")
    if raw:
        return os.path.expanduser(os.path.expandvars(raw))
    profile = os.getenv("WHISPER_PROFILE", "balanced").strip().lower()
    return str(_XIAOZHI_WHISPER_PROFILES.get(profile, _XIAOZHI_WHISPER_DEFAULT))


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("HOST", "0.0.0.0")
    ws_port: int = int(os.getenv("WS_PORT", "8765"))
    http_port: int = int(os.getenv("HTTP_PORT", "8766"))
    token: str = os.getenv("TOKEN", "demo-token")
    llm_backend: str = os.getenv("LLM_BACKEND", "ollama").strip().lower()
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "").strip()
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "150"))
    llm_history_turns: int = int(os.getenv("LLM_HISTORY_TURNS", "8"))
    quark_pick_llm: bool = os.getenv("QUARK_PICK_LLM", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    quark_pick_top: int = int(os.getenv("QUARK_PICK_TOP", "20"))
    ollama_url: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
    whisper_model: str = _whisper_model_path()
    whisper_profile: str = os.getenv("WHISPER_PROFILE", "balanced").strip().lower()
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")
    whisper_beam_size: int = int(os.getenv("WHISPER_BEAM_SIZE", "1"))
    whisper_cpu_threads: int = int(os.getenv("WHISPER_CPU_THREADS", "0"))
    whisper_preload: bool = os.getenv("WHISPER_PRELOAD", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    tts_voice: str = os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural")
    uplink_rate: int = int(os.getenv("UPLINK_RATE", "16000"))
    downlink_rate: int = int(os.getenv("DOWNLINK_RATE", "24000"))
    frame_ms: int = int(os.getenv("FRAME_MS", "60"))
    device_default_volume: int = int(os.getenv("DEVICE_DEFAULT_VOLUME", "40"))
    stream_audio_gain: float = float(os.getenv("STREAM_AUDIO_GAIN", "2.0"))
    stream_listen_every_s: float = float(os.getenv("STREAM_LISTEN_EVERY_S", "0"))
    stream_listen_window_s: float = float(os.getenv("STREAM_LISTEN_WINDOW_S", "1.5"))
    playback_wake_interrupt: bool = os.getenv("PLAYBACK_WAKE_INTERRUPT", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    playback_history_limit: int = int(os.getenv("PLAYBACK_HISTORY_LIMIT", "10"))
    playback_resume_min_ms: int = int(os.getenv("PLAYBACK_RESUME_MIN_MS", "5000"))
    streaming_asr: bool = os.getenv("STREAMING_ASR", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    stream_silence_ms: int = int(os.getenv("STREAM_SILENCE_MS", "900"))
    stream_min_speech_ms: int = int(os.getenv("STREAM_MIN_SPEECH_MS", "500"))
    stream_max_utterance_ms: int = int(os.getenv("STREAM_MAX_UTTERANCE_MS", "20000"))
    stream_start_speech_frames: int = int(os.getenv("STREAM_START_SPEECH_FRAMES", "3"))
    stream_min_rms: float = float(os.getenv("STREAM_MIN_RMS", "0.022"))
    stream_noise_multiplier: float = float(os.getenv("STREAM_NOISE_MULTIPLIER", "4.5"))
    stream_speech_threshold_max: float = float(
        os.getenv("STREAM_SPEECH_THRESHOLD_MAX", "0.06")
    )
    stream_calibration_holdoff_ms: int = int(
        os.getenv("STREAM_CALIBRATION_HOLDOFF_MS", "1200")
    )
    stream_wake_holdoff_ms: int = int(os.getenv("STREAM_WAKE_HOLDOFF_MS", "4200"))
    stream_noise_floor_max: float = float(os.getenv("STREAM_NOISE_FLOOR_MAX", "0.04"))
    stream_silence_ratio: float = float(os.getenv("STREAM_SILENCE_RATIO", "0.72"))
    asr_backend: str = os.getenv("ASR_BACKEND", "tencent").strip().lower()
    asr_fallback_local: bool = os.getenv("ASR_FALLBACK_LOCAL", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    tencent_secret_id: str = (
        os.getenv("TENCENT_SECRET_ID", "") or os.getenv("TENCENTCLOUD_SECRET_ID", "")
    ).strip()
    tencent_secret_key: str = (
        os.getenv("TENCENT_SECRET_KEY", "") or os.getenv("TENCENTCLOUD_SECRET_KEY", "")
    ).strip()
    tencent_asr_engine: str = os.getenv("TENCENT_ASR_ENGINE", "16k_zh")
    tencent_asr_region: str = os.getenv("TENCENT_ASR_REGION", "")
    use_mcp_tools: bool = os.getenv("USE_MCP_TOOLS", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    mcp_gateway_url: str = os.getenv("XIAOZHI_GATEWAY", "").strip()
    mcp_endpoint: str = os.getenv("MCP_ENDPOINT", "").strip()
    # Cloud+HTTP design: HTTP media only (no local WS dialogue / Whisper).
    media_only: bool = os.getenv("MEDIA_ONLY", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    # Device-facing MP3 after ffmpeg (DESIGN_CLOUD_HTTP_QUARK_PLAY).
    device_mp3_bitrate_k: int = int(os.getenv("DEVICE_MP3_BITRATE_K", "96"))
    # Match AtomS3R Pyramid / Echo Base codec output (24 kHz).
    device_mp3_sample_rate: int = int(os.getenv("DEVICE_MP3_SAMPLE_RATE", "24000"))
    device_mp3_channels: int = int(os.getenv("DEVICE_MP3_CHANNELS", "1"))

    @property
    def lan_ip(self) -> str:
        return _lan_ip()

    @property
    def ws_url(self) -> str:
        return f"ws://{self.lan_ip}:{self.ws_port}"

    @property
    def ota_url(self) -> str:
        return f"http://{self.lan_ip}:{self.http_port}/xiaozhi/ota/"

    @property
    def gateway_base_url(self) -> str:
        if self.mcp_gateway_url:
            return self.mcp_gateway_url.rstrip("/")
        return f"http://{self.lan_ip}:{self.http_port}"


settings = Settings()
