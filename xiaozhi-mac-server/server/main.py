"""XiaoZhi local Mac gateway entrypoint."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.config import settings
from server.http_server import run_http_server
from server.ws_server import run_ws_server


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    log = logging.getLogger("xiaozhi-mac-server")
    log.info("LAN IP: %s", settings.lan_ip)
    log.info("MEDIA_ONLY: %s", settings.media_only)
    log.info("HTTP: http://%s:%s/", settings.lan_ip, settings.http_port)
    if settings.media_only:
        log.info(
            "Media mode: device MP3 http://%s:%s/stream/quark/{{fid}}/device.mp3",
            settings.lan_ip,
            settings.http_port,
        )
        log.info("Skip WebSocket dialogue / Whisper (cloud HTTP design)")
    else:
        log.info("WebSocket: %s", settings.ws_url)
        log.info("OTA: %s", settings.ota_url)
        log.info("LLM backend: %s", settings.llm_backend)
        if settings.llm_backend == "deepseek":
            log.info(
                "DeepSeek model: %s (key %s)",
                settings.deepseek_model,
                "set" if settings.deepseek_api_key else "missing",
            )
        else:
            log.info("Ollama model: %s @ %s", settings.ollama_model, settings.ollama_url)
        log.info("ASR backend: %s", settings.asr_backend)
        if settings.asr_backend == "tencent":
            from server.tencent_asr import tencent_asr_configured

            log.info(
                "Tencent ASR: engine=%s credentials=%s fallback_local=%s",
                settings.tencent_asr_engine,
                "set" if tencent_asr_configured() else "missing",
                settings.asr_fallback_local,
            )
        if settings.asr_backend == "local" or settings.asr_fallback_local:
            log.info(
                "Whisper profile: %s model=%s preload=%s",
                settings.whisper_profile,
                settings.whisper_model,
                settings.whisper_preload,
            )
        log.info("Web text demo: http://%s:%s/demo/", settings.lan_ip, settings.http_port)

    async def _run() -> None:
        if settings.media_only:
            await run_http_server()
            await asyncio.Future()
            return
        if settings.whisper_preload and (
            settings.asr_backend == "local" or settings.asr_fallback_local
        ):
            from server.pipeline import preload_whisper

            await asyncio.to_thread(preload_whisper)
        await asyncio.gather(run_http_server(), run_ws_server())

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        log.info("Stopped")


if __name__ == "__main__":
    main()
