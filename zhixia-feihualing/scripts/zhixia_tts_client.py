#!/usr/bin/env python3
from __future__ import annotations

import base64
import binascii
import json
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping


TTS_ENDPOINT = "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"
TERMINAL_SUCCESS_CODE = 20000000
MAX_ATTEMPTS = 3


class TTSError(RuntimeError):
    """Base error for speech synthesis."""


class TTSProtocolError(TTSError):
    """The server response was incomplete or malformed."""


class TTSTemporaryError(TTSError):
    """A retryable failure remained after all attempts."""


class TTSPermanentError(TTSError):
    """A request cannot succeed without changing input or credentials."""


@dataclass(frozen=True)
class TTSRequest:
    text: str
    speaker: str
    resource_id: str
    uid: str = "zhixia-feihualing"


@dataclass(frozen=True)
class TTSResult:
    audio: bytes
    request_id: str | None = None
    message: str = ""


@dataclass(frozen=True)
class HTTPResponse:
    status_code: int
    lines: Iterable[str | bytes]
    headers: Mapping[str, str]


@dataclass(frozen=True)
class RequestSummary:
    request_id: str
    resource_id: str
    speaker: str
    text_length: int


@dataclass(frozen=True)
class AudioProbe:
    codec: str
    sample_rate: int
    channels: int
    duration_ms: int


Transport = Callable[[str, dict[str, str], dict[str, object], float], HTTPResponse]


def _server_request_id(headers: Mapping[str, str]) -> str | None:
    normalized = {str(key).lower(): str(value) for key, value in headers.items()}
    return normalized.get("x-request-id") or normalized.get("x-tt-logid")


def parse_sse(
    lines: Iterable[str | bytes],
    *,
    request_id: str | None = None,
) -> TTSResult:
    audio_chunks: list[bytes] = []
    terminal_message = ""
    terminal_seen = False

    for raw_line in lines:
        try:
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        except UnicodeDecodeError as exc:
            raise TTSProtocolError(
                f"SSE is not UTF-8 (request_id={request_id or 'unknown'})"
            ) from exc

        line = line.strip()
        if not line or not line.startswith("data:"):
            continue
        payload_text = line.removeprefix("data:").strip()
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise TTSProtocolError(
                f"invalid SSE JSON (request_id={request_id or 'unknown'})"
            ) from exc
        if not isinstance(payload, dict):
            raise TTSProtocolError(
                f"invalid SSE payload (request_id={request_id or 'unknown'})"
            )

        code = payload.get("code")
        if code == 0:
            encoded_audio = payload.get("data")
            if not isinstance(encoded_audio, str):
                raise TTSProtocolError(
                    f"audio chunk is missing (request_id={request_id or 'unknown'})"
                )
            try:
                audio_chunks.append(base64.b64decode(encoded_audio, validate=True))
            except (binascii.Error, ValueError) as exc:
                raise TTSProtocolError(
                    f"invalid audio Base64 (request_id={request_id or 'unknown'})"
                ) from exc
            continue

        if code == TERMINAL_SUCCESS_CODE:
            terminal_seen = True
            terminal_message = str(payload.get("message") or "")
            continue

        message = str(payload.get("message") or "business error")
        raise TTSPermanentError(
            f"TTS business error code={code}, request_id={request_id or 'unknown'}: {message}"
        )

    if not terminal_seen:
        raise TTSProtocolError(
            f"SSE terminal success event is missing (request_id={request_id or 'unknown'})"
        )
    if not audio_chunks:
        raise TTSProtocolError(
            f"SSE returned no audio (request_id={request_id or 'unknown'})"
        )
    return TTSResult(
        audio=b"".join(audio_chunks),
        request_id=request_id,
        message=terminal_message,
    )


def _default_transport(
    endpoint: str,
    headers: dict[str, str],
    body: dict[str, object],
    timeout: float,
) -> HTTPResponse:
    encoded_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=encoded_body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HTTPResponse(
                status_code=response.status,
                lines=tuple(response.readlines()),
                headers=dict(response.headers.items()),
            )
    except urllib.error.HTTPError as exc:
        return HTTPResponse(
            status_code=exc.code,
            lines=tuple(exc.readlines()),
            headers=dict(exc.headers.items()) if exc.headers else {},
        )
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise TimeoutError("TTS request timed out") from exc
        raise ConnectionError("TTS connection failed") from exc


class DoubaoTTSClient:
    def __init__(
        self,
        api_key: str,
        *,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        timeout: float = 30.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("API key cannot be empty")
        self._api_key = api_key
        self._transport = transport or _default_transport
        self._sleep = sleep
        self._timeout = timeout
        self.last_request_summary: RequestSummary | None = None

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(endpoint={TTS_ENDPOINT!r}, "
            f"timeout={self._timeout!r})"
        )

    def synthesize(self, request: TTSRequest) -> TTSResult:
        if not request.text.strip():
            raise ValueError("text cannot be empty")
        if not request.speaker.strip() or not request.resource_id.strip():
            raise ValueError("speaker and resource_id cannot be empty")

        client_request_id = str(uuid.uuid4())
        self.last_request_summary = RequestSummary(
            request_id=client_request_id,
            resource_id=request.resource_id,
            speaker=request.speaker,
            text_length=len(request.text),
        )
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self._api_key,
            "X-Api-Resource-Id": request.resource_id,
            "X-Api-Request-Id": client_request_id,
        }
        body: dict[str, object] = {
            "user": {"uid": request.uid},
            "req_params": {
                "text": request.text,
                "speaker": request.speaker,
                "sample_rate": 24000,
                "audio_params": {
                    "format": "mp3",
                    "speech_rate": 0,
                    "loudness_rate": 0,
                    "bit_rate": 64000,
                },
                "additions": json.dumps({"disable_markdown_filter": True}),
            },
        }

        last_status: int | None = None
        last_request_id: str | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._transport(TTS_ENDPOINT, headers, body, self._timeout)
            except (ConnectionError, TimeoutError) as exc:
                if attempt == MAX_ATTEMPTS:
                    raise TTSTemporaryError(
                        f"TTS transport failed after {MAX_ATTEMPTS} attempts "
                        f"(request_id={client_request_id})"
                    ) from exc
                self._sleep(0.5 * (2 ** (attempt - 1)))
                continue

            last_status = response.status_code
            last_request_id = _server_request_id(response.headers) or client_request_id
            if response.status_code == 200:
                return parse_sse(response.lines, request_id=last_request_id)
            if response.status_code == 429 or 500 <= response.status_code <= 599:
                if attempt < MAX_ATTEMPTS:
                    self._sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                break
            raise TTSPermanentError(
                f"TTS HTTP {response.status_code} (request_id={last_request_id})"
            )

        raise TTSTemporaryError(
            f"TTS HTTP {last_status} failed after {MAX_ATTEMPTS} attempts "
            f"(request_id={last_request_id or client_request_id})"
        )


def probe_audio(path: str | Path) -> AudioProbe:
    audio_path = Path(path)
    if not audio_path.is_file():
        raise ValueError(f"audio file does not exist: {audio_path}")

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_name,sample_rate,channels",
        "-of",
        "json",
        str(audio_path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(completed.stdout)
        streams = data["streams"]
        stream = streams[0]
        codec = str(stream["codec_name"])
        sample_rate = int(stream["sample_rate"])
        channels = int(stream["channels"])
        duration_ms = round(float(data["format"]["duration"]) * 1000)
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError(f"cannot read MP3 properties: {audio_path}") from exc

    if codec != "mp3":
        raise ValueError(f"audio codec must be mp3, got {codec}")
    if sample_rate != 24000:
        raise ValueError(f"audio sample rate must be 24000Hz, got {sample_rate}Hz")
    if channels != 1:
        raise ValueError(f"audio must be mono, got {channels} channels")
    if duration_ms <= 0:
        raise ValueError("audio duration must be positive")
    return AudioProbe(
        codec=codec,
        sample_rate=sample_rate,
        channels=channels,
        duration_ms=duration_ms,
    )


__all__ = [
    "AudioProbe",
    "DoubaoTTSClient",
    "HTTPResponse",
    "RequestSummary",
    "TTSProtocolError",
    "TTSPermanentError",
    "TTSTemporaryError",
    "TTSRequest",
    "TTSResult",
    "parse_sse",
    "probe_audio",
]
