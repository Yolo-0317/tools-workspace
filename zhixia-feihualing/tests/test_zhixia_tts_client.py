from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from zhixia_tts_client import (  # noqa: E402
    DoubaoTTSClient,
    HTTPResponse,
    TTSProtocolError,
    TTSPermanentError,
    TTSTemporaryError,
    TTSRequest,
    parse_sse,
    probe_audio,
)


def sse_data(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload)}"


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def successful_sse() -> tuple[str, ...]:
    return (
        sse_data({"code": 0, "data": b64(b"abc")}),
        sse_data({"code": 0, "data": b64(b"def")}),
        sse_data({"code": 20000000, "message": "OK", "data": None}),
    )


class FakeTransport:
    def __init__(self, responses: list[HTTPResponse | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        endpoint: str,
        headers: dict[str, str],
        body: dict[str, object],
        timeout: float,
    ) -> HTTPResponse:
        self.calls.append(
            {
                "endpoint": endpoint,
                "headers": headers,
                "body": body,
                "timeout": timeout,
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class ClientTests(unittest.TestCase):
    def test_parse_sse_concatenates_audio_chunks(self) -> None:
        result = parse_sse(successful_sse())

        self.assertEqual(result.audio, b"abcdef")
        self.assertEqual(result.message, "OK")

    def test_parse_sse_accepts_byte_lines_and_ignores_non_data_fields(self) -> None:
        lines = [b"event: message", b"", *[line.encode() for line in successful_sse()]]

        self.assertEqual(parse_sse(lines).audio, b"abcdef")

    def test_parse_sse_requires_terminal_success(self) -> None:
        with self.assertRaisesRegex(TTSProtocolError, "terminal success"):
            parse_sse([sse_data({"code": 0, "data": b64(b"abc")})])

    def test_parse_sse_rejects_invalid_base64(self) -> None:
        lines = [
            sse_data({"code": 0, "data": "not-base64"}),
            sse_data({"code": 20000000, "message": "OK"}),
        ]

        with self.assertRaisesRegex(TTSProtocolError, "Base64"):
            parse_sse(lines)

    def test_business_error_is_permanent(self) -> None:
        lines = [sse_data({"code": 45000000, "message": "voice not found"})]

        with self.assertRaisesRegex(TTSPermanentError, "45000000"):
            parse_sse(lines, request_id="request-1")

    def test_request_uses_verified_seed_tts_structure(self) -> None:
        transport = FakeTransport(
            [HTTPResponse(200, successful_sse(), {"X-Request-Id": "server-id"})]
        )
        client = DoubaoTTSClient("secret-key", transport=transport)

        result = client.synthesize(
            TTSRequest("你好", "speaker-id", "seed-tts-2.0", uid="ep04-line01")
        )

        call = transport.calls[0]
        headers = call["headers"]
        body = call["body"]
        self.assertEqual(headers["X-Api-Resource-Id"], "seed-tts-2.0")  # type: ignore[index]
        self.assertEqual(headers["X-Api-Key"], "secret-key")  # type: ignore[index]
        self.assertTrue(headers["X-Api-Request-Id"])  # type: ignore[index]
        self.assertEqual(body["user"], {"uid": "ep04-line01"})  # type: ignore[index]
        params = body["req_params"]  # type: ignore[index]
        self.assertEqual(params["speaker"], "speaker-id")
        self.assertEqual(params["sample_rate"], 24000)
        self.assertEqual(params["audio_params"]["format"], "mp3")
        self.assertEqual(params["audio_params"]["bit_rate"], 64000)
        self.assertEqual(
            json.loads(params["additions"]),
            {"disable_markdown_filter": True},
        )
        self.assertEqual(result.request_id, "server-id")
        self.assertNotIn("secret-key", repr(client))
        self.assertNotIn("secret-key", repr(client.last_request_summary))

    def test_http_401_does_not_retry_or_expose_key(self) -> None:
        transport = FakeTransport([HTTPResponse(401, (), {"X-Request-Id": "denied"})])
        client = DoubaoTTSClient("secret-key", transport=transport)

        with self.assertRaises(TTSPermanentError) as raised:
            client.synthesize(TTSRequest("你好", "speaker-id", "seed-tts-2.0"))

        self.assertEqual(len(transport.calls), 1)
        self.assertNotIn("secret-key", str(raised.exception))

    def test_http_429_retries_then_succeeds(self) -> None:
        transport = FakeTransport(
            [
                HTTPResponse(429, (), {"X-Request-Id": "busy-1"}),
                HTTPResponse(429, (), {"X-Request-Id": "busy-2"}),
                HTTPResponse(200, successful_sse(), {"X-Request-Id": "ok-3"}),
            ]
        )
        sleeps: list[float] = []
        client = DoubaoTTSClient(
            "secret-key",
            transport=transport,
            sleep=sleeps.append,
        )

        result = client.synthesize(TTSRequest("你好", "speaker-id", "seed-tts-2.0"))

        self.assertEqual(result.audio, b"abcdef")
        self.assertEqual(len(transport.calls), 3)
        self.assertEqual(sleeps, [0.5, 1.0])

    def test_connection_failure_stops_after_three_attempts(self) -> None:
        transport = FakeTransport(
            [ConnectionError("offline"), ConnectionError("offline"), ConnectionError("offline")]
        )
        client = DoubaoTTSClient(
            "secret-key",
            transport=transport,
            sleep=lambda _: None,
        )

        with self.assertRaisesRegex(TTSTemporaryError, "3 attempts"):
            client.synthesize(TTSRequest("你好", "speaker-id", "seed-tts-2.0"))

        self.assertEqual(len(transport.calls), 3)

    def test_probe_audio_reads_valid_mp3_properties(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "valid.mp3"
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=24000:cl=mono",
                    "-t",
                    "0.15",
                    "-b:a",
                    "64k",
                    str(audio_path),
                ],
                check=True,
            )

            info = probe_audio(audio_path)

        self.assertEqual(info.codec, "mp3")
        self.assertEqual(info.sample_rate, 24000)
        self.assertEqual(info.channels, 1)
        self.assertGreater(info.duration_ms, 0)

    def test_probe_audio_rejects_wrong_sample_rate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "wrong-rate.mp3"
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=44100:cl=mono",
                    "-t",
                    "0.15",
                    str(audio_path),
                ],
                check=True,
            )

            with self.assertRaisesRegex(ValueError, "24000"):
                probe_audio(audio_path)


if __name__ == "__main__":
    unittest.main()
