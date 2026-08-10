"""HTTP Range streaming from Quark CDN + optional local proxy."""

from __future__ import annotations

import asyncio
import logging
import secrets
import shutil
from collections import OrderedDict
from collections.abc import AsyncIterator
from typing import Any

import httpx
import numpy as np
from aiohttp import web

from server.config import settings
from server.opus_codec import OpusCodec
from server.quark_client import QuarkStreamSource

log = logging.getLogger(__name__)

_MIME_BY_EXT = {
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
}


def _guess_content_type(source: QuarkStreamSource) -> str:
    ext = "." + source.filename.rsplit(".", 1)[-1].lower() if "." in source.filename else ""
    return _MIME_BY_EXT.get(ext, "application/octet-stream")


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


async def proxy_quark_stream(
    request: web.Request, source: QuarkStreamSource
) -> web.StreamResponse:
    """Proxy Quark CDN bytes with Range passthrough (206/200)."""
    range_header = request.headers.get("Range")
    headers = {"Cookie": source.cookie}
    if range_header:
        headers["Range"] = range_header

    client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=300.0))
    upstream = client.build_request("GET", source.download_url, headers=headers)
    resp = await client.send(upstream, stream=True)
    if resp.status_code not in (200, 206):
        body = await resp.aread()
        await resp.aclose()
        await client.aclose()
        raise web.HTTPBadGateway(
            text=f"upstream {resp.status_code}: {body[:200]!r}"
        )

    out = web.StreamResponse(status=resp.status_code)
    out.headers["Accept-Ranges"] = resp.headers.get("Accept-Ranges", "bytes")
    if "Content-Range" in resp.headers:
        out.headers["Content-Range"] = resp.headers["Content-Range"]
    if "Content-Length" in resp.headers:
        out.headers["Content-Length"] = resp.headers["Content-Length"]
    out.headers["Content-Type"] = resp.headers.get(
        "Content-Type"
    ) or _guess_content_type(source)
    await out.prepare(request)

    try:
        async for chunk in resp.aiter_bytes():
            await out.write(chunk)
    finally:
        await resp.aclose()
        await client.aclose()
    return out


async def iter_opus_from_http_source(
    source: QuarkStreamSource,
    *,
    target_rate: int | None = None,
    frame_ms: int | None = None,
    should_stop=None,
    on_process=None,
    start_offset_s: float = 0,
) -> AsyncIterator[bytes]:
    """Decode remote audio via ffmpeg stdout and yield Opus packets."""
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg not found; install with: brew install ffmpeg")

    rate = target_rate or settings.downlink_rate
    ms = frame_ms or settings.frame_ms
    gain = settings.stream_audio_gain
    codec = OpusCodec(
        uplink_rate=settings.uplink_rate,
        downlink_rate=rate,
        frame_ms=ms,
    )
    header_block = f"Cookie: {source.cookie}\r\n"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-headers",
        header_block,
    ]
    if start_offset_s > 0.05:
        cmd.extend(["-ss", f"{start_offset_s:.3f}"])
    cmd.extend(["-i", source.download_url])
    if gain > 1.01:
        cmd.extend(["-af", f"volume={gain:.2f}"])
    cmd.extend(
        [
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        str(rate),
        "pipe:1",
        ]
    )
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    if on_process is not None:
        on_process(proc)
    assert proc.stdout is not None
    frame_bytes = rate * ms // 1000 * 2
    buffer = bytearray()
    try:
        while True:
            if should_stop and should_stop():
                break
            try:
                chunk = await asyncio.wait_for(proc.stdout.read(8192), timeout=0.35)
            except asyncio.TimeoutError:
                continue
            if not chunk:
                break
            buffer.extend(chunk)
            while len(buffer) >= frame_bytes:
                frame = bytes(buffer[:frame_bytes])
                del buffer[:frame_bytes]
                pcm = np.frombuffer(frame, dtype=np.int16)
                for packet in codec.encode_pcm(pcm, rate):
                    yield packet
        if buffer:
            pcm = np.frombuffer(bytes(buffer), dtype=np.int16)
            if pcm.size:
                for packet in codec.encode_pcm(pcm, rate):
                    yield packet
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        if proc.returncode not in (0, None, -15):
            err = (await proc.stderr.read()).decode("utf-8", errors="replace") if proc.stderr else ""
            log.warning("ffmpeg stream ended with code=%s stderr=%s", proc.returncode, err[:300])


async def proxy_quark_audio_stream(
    request: web.Request, source: QuarkStreamSource
) -> web.StreamResponse:
    """Extract movie audio via ffmpeg and stream MP3 to the browser."""
    if not ffmpeg_available():
        raise web.HTTPServiceUnavailable(text="ffmpeg not installed")

    header_block = f"Cookie: {source.cookie}\r\n"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-headers",
        header_block,
        "-i",
        source.download_url,
    ]
    if source.audio_map:
        cmd.extend(["-map", source.audio_map])
    cmd.extend(
        [
            "-vn",
            "-acodec",
            "libmp3lame",
            "-ab",
            "128k",
            "-f",
            "mp3",
            "pipe:1",
        ]
    )
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout is not None

    out = web.StreamResponse(status=200)
    out.headers["Content-Type"] = "audio/mpeg"
    out.headers["Cache-Control"] = "no-cache"
    await out.prepare(request)

    try:
        while True:
            chunk = await proc.stdout.read(16384)
            if not chunk:
                break
            await out.write(chunk)
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        if proc.returncode not in (0, None, -15) and proc.stderr:
            err = (await proc.stderr.read()).decode("utf-8", errors="replace")
            log.warning(
                "ffmpeg audio extract ended code=%s file=%s stderr=%s",
                proc.returncode,
                source.filename,
                err[:300],
            )
    return out


async def stream_source_handler(request: web.Request) -> web.StreamResponse:
    app = request.app
    cache: dict[str, QuarkStreamSource] = app["quark_stream_cache"]
    fid = request.match_info["fid"]
    source = cache.get(fid)
    if not source:
        raise web.HTTPNotFound(text="unknown or expired stream fid")
    return await proxy_quark_stream(request, source)


async def stream_source_audio_handler(request: web.Request) -> web.StreamResponse:
    app = request.app
    cache: dict[str, QuarkStreamSource] = app["quark_stream_cache"]
    fid = request.match_info["fid"]
    source = cache.get(fid)
    if not source:
        raise web.HTTPNotFound(text="unknown or expired stream fid")
    return await proxy_quark_audio_stream(request, source)


def playback_stream_path(source: QuarkStreamSource) -> str:
    if source.needs_audio_extract:
        return f"/stream/quark/{source.fid}/audio"
    return f"/stream/quark/{source.fid}"


def device_mp3_path(fid: str) -> str:
    """Path for ESP HTTP player (Mac ffmpeg → unified MP3)."""
    return f"/stream/quark/{fid}/device.mp3"


def device_mp3_bitrate_bytes_per_sec() -> int:
    br = max(32, min(192, settings.device_mp3_bitrate_k))
    return (br * 1000) // 8


def estimate_position_ms(*, bytes_sent: int, base_offset_ms: int = 0) -> int:
    """CBR estimate for device.mp3 pipe (96k default)."""
    bps = max(1, device_mp3_bitrate_bytes_per_sec())
    return max(0, base_offset_ms + int(bytes_sent * 1000 / bps))


async def _ensure_stream_source(app: web.Application, fid: str) -> QuarkStreamSource:
    cache: dict[str, QuarkStreamSource] = app["quark_stream_cache"]
    source = cache.get(fid)
    if source is not None:
        return source
    from dataclasses import replace

    from server.media_index import find_file_by_fid
    from server.quark_client import QuarkClient

    client = QuarkClient.from_env()
    if client is None:
        raise web.HTTPServiceUnavailable(text="Quark not configured")
    hit = find_file_by_fid(fid)
    try:
        source = client.resolve_stream_source(
            fid,
            filename_hint=hit.filename if hit else "",
            size_hint=hit.size if hit else 0,
        )
    except Exception as exc:
        log.warning("resolve fid=%s failed: %s", fid, exc)
        raise web.HTTPNotFound(text=f"cannot resolve fid: {exc}") from exc
    if hit is not None and hit.audio_map:
        source = replace(source, audio_map=hit.audio_map)
    cache[fid] = source
    return source


async def proxy_quark_device_mp3(
    request: web.Request,
    source: QuarkStreamSource,
    *,
    start_offset_ms: int = 0,
    device_key: str = "cloud-media",
) -> web.StreamResponse:
    """Transcode Quark CDN audio to a fixed MP3 for ESP HTTP players.

    While streaming, update PlaybackStore progress (CBR estimate from MP3 bitrate).
    """
    if not ffmpeg_available():
        raise web.HTTPServiceUnavailable(text="ffmpeg not installed")

    from server.playback_memory import PlaybackStore

    br = max(32, min(192, settings.device_mp3_bitrate_k))
    ar = settings.device_mp3_sample_rate
    ac = 1 if settings.device_mp3_channels <= 1 else 2
    start_offset_s = max(0.0, start_offset_ms / 1000.0)
    store = PlaybackStore(device_key)
    # Only track if this fid is the current play session (resolve/next/resume called begin).
    track = store.current is not None and store.current.fid == source.fid

    # Force resample via filter + -ar (some inputs ignore -ar alone when streaming).
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-headers",
        f"Cookie: {source.cookie}\r\n",
    ]
    if start_offset_s > 0.05:
        cmd.extend(["-ss", f"{start_offset_s:.3f}"])
    cmd.extend(["-i", source.download_url])
    if source.audio_map:
        cmd.extend(["-map", source.audio_map])
    cmd.extend(
        [
            "-vn",
            "-af",
            f"aresample={ar}",
            "-ac",
            str(ac),
            "-ar",
            str(ar),
            "-c:a",
            "libmp3lame",
            "-b:a",
            f"{br}k",
            "-f",
            "mp3",
            "pipe:1",
        ]
    )
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout is not None
    out = web.StreamResponse(status=200)
    out.headers["Content-Type"] = "audio/mpeg"
    out.headers["Cache-Control"] = "no-store"
    await out.prepare(request)

    bytes_sent = 0
    completed = False
    try:
        while True:
            chunk = await proc.stdout.read(8192)
            if not chunk:
                completed = True
                break
            await out.write(chunk)
            bytes_sent += len(chunk)
            if track:
                pos = estimate_position_ms(
                    bytes_sent=bytes_sent, base_offset_ms=start_offset_ms
                )
                store.update_progress(pos)
    except (ConnectionResetError, BrokenPipeError, ConnectionError, asyncio.CancelledError, OSError) as exc:
        completed = False
        log.info(
            "device mp3 client gone fid=%s bytes=%s err=%s",
            source.fid[:24],
            bytes_sent,
            type(exc).__name__,
        )
    finally:
        if track:
            pos = estimate_position_ms(
                bytes_sent=bytes_sent, base_offset_ms=start_offset_ms
            )
            # Reload in case another request updated store; only finish matching fid.
            store = PlaybackStore(device_key)
            if store.current and store.current.fid == source.fid:
                store.finish(interrupted=not completed, final_position_ms=pos)
                log.info(
                    "device mp3 progress fid=%s completed=%s pos_ms=%s",
                    source.fid[:24],
                    completed,
                    pos,
                )
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
        err = b""
        if proc.stderr:
            err = await proc.stderr.read()
        if proc.returncode not in (0, None) and err:
            log.warning(
                "device mp3 ffmpeg code=%s fid=%s stderr=%s",
                proc.returncode,
                source.fid,
                err[:300],
            )
    return out


async def stream_device_mp3_handler(request: web.Request) -> web.StreamResponse:
    fid = request.match_info["fid"]
    source = await _ensure_stream_source(request.app, fid)
    from_ms = 0
    raw = request.rel_url.query.get("from_ms") or request.rel_url.query.get("t_ms")
    if raw is not None:
        try:
            from_ms = max(0, int(float(raw)))
        except ValueError:
            from_ms = 0
    device_key = request.rel_url.query.get("device") or "cloud-media"
    return await proxy_quark_device_mp3(
        request,
        source,
        start_offset_ms=from_ms,
        device_key=device_key,
    )


_TTS_CACHE_LIMIT = 64


def _tts_cache(app: web.Application) -> OrderedDict[str, bytes]:
    cache = app.get("tts_cache")
    if cache is None:
        cache = OrderedDict()
        app["tts_cache"] = cache
    return cache


def cache_tts_audio(app: web.Application, mp3_bytes: bytes) -> str:
    token = secrets.token_urlsafe(10)
    cache = _tts_cache(app)
    cache[token] = mp3_bytes
    cache.move_to_end(token)
    while len(cache) > _TTS_CACHE_LIMIT:
        cache.popitem(last=False)
    return f"/stream/tts/{token}"


async def stream_tts_handler(request: web.Request) -> web.Response:
    token = request.match_info["token"]
    mp3_bytes = _tts_cache(request.app).get(token)
    if not mp3_bytes:
        raise web.HTTPNotFound(text="unknown or expired tts token")
    return web.Response(body=mp3_bytes, content_type="audio/mpeg")


def register_stream_routes(app: web.Application) -> None:
    app["quark_stream_cache"] = {}
    app.router.add_get("/stream/quark/{fid}/device.mp3", stream_device_mp3_handler)
    app.router.add_get("/stream/quark/{fid}/audio", stream_source_audio_handler)
    app.router.add_get("/stream/quark/{fid}", stream_source_handler)
    app.router.add_get("/stream/tts/{token}", stream_tts_handler)


def cache_stream_source(app: web.Application, source: QuarkStreamSource) -> str:
    app["quark_stream_cache"][source.fid] = source
    return source.fid


def stream_playback_summary(source: QuarkStreamSource, host: str, port: int) -> dict[str, Any]:
    return {
        "fid": source.fid,
        "filename": source.filename,
        "size": source.size,
        "proxy_url": f"http://{host}:{port}/stream/quark/{source.fid}",
        "device_mp3_url": f"http://{host}:{port}{device_mp3_path(source.fid)}",
        "mode": "http-range-proxy",
    }
