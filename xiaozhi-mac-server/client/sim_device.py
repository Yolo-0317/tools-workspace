"""Simulate M5Stack / xiaozhi-esp32 voice device on Mac (mic + speaker)."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path

import numpy as np
import opuslib
import sounddevice as sd
import websockets

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.config import settings

log = logging.getLogger(__name__)

UPLINK_RATE = settings.uplink_rate
DOWNLINK_RATE = settings.downlink_rate
FRAME_MS = settings.frame_ms
UPLINK_FRAME = UPLINK_RATE * FRAME_MS // 1000
DOWNLINK_FRAME = DOWNLINK_RATE * FRAME_MS // 1000


def _device_mac_id() -> str:
    node = uuid.getnode()
    return ":".join(f"{node:012x}"[i : i + 2] for i in range(0, 12, 2))


class SimDevice:
    def __init__(self, ws_url: str, token: str, device_id: str | None = None) -> None:
        self.ws_url = ws_url
        self.token = token
        self.device_id = device_id or _device_mac_id()
        self.session_id: str | None = None
        self.encoder = opuslib.Encoder(UPLINK_RATE, 1, opuslib.APPLICATION_AUDIO)
        self.decoder = opuslib.Decoder(DOWNLINK_RATE, 1)
        self.play_queue: asyncio.Queue[np.ndarray] = asyncio.Queue()
        self.recording = False
        self._record_buffer: list[bytes] = []
        self._story_playing = False

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Protocol-Version": "1",
            "Device-Id": self.device_id,
            "Client-Id": str(uuid.uuid4()),
        }

    async def connect(self) -> websockets.ClientConnection:
        ws = await websockets.connect(
            self.ws_url,
            additional_headers=self._headers(),
            ping_interval=20,
            max_size=8 * 1024 * 1024,
        )
        hello = {
            "type": "hello",
            "version": 1,
            "features": {"mcp": True},
            "transport": "websocket",
            "audio_params": {
                "format": "opus",
                "sample_rate": UPLINK_RATE,
                "channels": 1,
                "frame_duration": FRAME_MS,
            },
        }
        await ws.send(json.dumps(hello))
        raw = await ws.recv()
        if isinstance(raw, bytes):
            raise RuntimeError("Expected server hello JSON, got binary")
        data = json.loads(raw)
        if data.get("type") != "hello":
            raise RuntimeError(f"Unexpected first message: {data}")
        self.session_id = data.get("session_id")
        log.info("Connected session=%s", self.session_id)
        return ws

    async def listen_start(self, ws: websockets.ClientConnection, mode: str = "manual") -> None:
        msg = {
            "session_id": self.session_id,
            "type": "listen",
            "state": "start",
            "mode": mode,
        }
        await ws.send(json.dumps(msg))
        self.recording = True
        self._record_buffer = []

    async def listen_stop(self, ws: websockets.ClientConnection) -> None:
        self.recording = False
        msg = {
            "session_id": self.session_id,
            "type": "listen",
            "state": "stop",
        }
        await ws.send(json.dumps(msg))

    def _mic_callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG001
        if status:
            log.debug("Input status: %s", status)
        if not self.recording:
            return
        pcm = (indata[:, 0] * 32767).astype(np.int16)
        for start in range(0, len(pcm), UPLINK_FRAME):
            chunk = pcm[start : start + UPLINK_FRAME]
            if len(chunk) < UPLINK_FRAME:
                chunk = np.pad(chunk, (0, UPLINK_FRAME - len(chunk)))
            packet = self.encoder.encode(chunk.tobytes(), UPLINK_FRAME)
            self._record_buffer.append(packet)

    async def _drain_uplink(self, ws: websockets.ClientConnection) -> None:
        while self.recording or self._record_buffer:
            if self._record_buffer:
                packet = self._record_buffer.pop(0)
                await ws.send(packet)
            else:
                await asyncio.sleep(0.01)

    async def _playback_worker(self) -> None:
        with sd.OutputStream(
            samplerate=DOWNLINK_RATE,
            channels=1,
            dtype="float32",
        ) as stream:
            while True:
                pcm = await self.play_queue.get()
                if pcm is None:
                    break
                stream.write(pcm.astype(np.float32) / 32768.0)

    async def _handle_server_message(
        self, ws: websockets.ClientConnection, message: str | bytes
    ) -> None:
        if isinstance(message, bytes):
            pcm_bytes = self.decoder.decode(message, DOWNLINK_FRAME)
            arr = np.frombuffer(pcm_bytes, dtype=np.int16)
            await self.play_queue.put(arr)
            return

        data = json.loads(message)
        msg_type = data.get("type")
        if msg_type == "stt":
            print(f"\n[你说] {data.get('text', '')}")
        elif msg_type == "tts":
            state = data.get("state")
            if state == "sentence_start":
                text = data.get("text", "")
                print(f"[小智] {text}")
                if any(k in text for k in ("播放", "提取音轨", "开始播放")):
                    self._story_playing = True
                    print("[网盘] 正在流式播放，请稍候…")
            elif state == "start":
                print("[小智] 开始说话...")
            elif state == "stop":
                if self._story_playing:
                    print("[网盘] 播放结束\n")
                    self._story_playing = False
                else:
                    print("[小智] 说完了\n")
        elif msg_type == "llm":
            pass
        else:
            log.debug("Server message: %s", data)

    async def recv_loop(self, ws: websockets.ClientConnection) -> None:
        async for message in ws:
            await self._handle_server_message(ws, message)

    async def run_push_to_talk(self) -> None:
        playback = asyncio.create_task(self._playback_worker())
        ws = await self.connect()
        recv_task = asyncio.create_task(self.recv_loop(ws))

        print("\n--- 小智 Mac 模拟设备 ---")
        print("协议: xiaozhi WebSocket v1 / Opus 16k uplink / 24k downlink")
        print(f"Device-Id: {self.device_id}  (真机为 MAC 地址)")
        print("操作:")
        print("  回车       开始录音（对着 Mac 麦克风说话）")
        print("  再按回车   结束并发送")
        print("  t + 回车   文字输入（跳过麦克风，调试用）")
        print("  q + 回车   退出")
        print("点播示例: 想听儿童故事 / 想听冰雪奇缘")
        print(f"服务器: {self.ws_url}\n")

        with sd.InputStream(
            samplerate=UPLINK_RATE,
            channels=1,
            dtype="float32",
            blocksize=UPLINK_FRAME,
            callback=self._mic_callback,
        ):
            while True:
                cmd = await asyncio.to_thread(input, "> ")
                cmd = cmd.strip().lower()
                if cmd == "q":
                    break
                if cmd == "t":
                    text = await asyncio.to_thread(input, "文字: ")
                    await self._send_text_turn(ws, text.strip())
                    continue

                print("[录音中] 说话... 再按回车结束")
                await self.listen_start(ws)
                drain = asyncio.create_task(self._drain_uplink(ws))
                await asyncio.to_thread(input)
                await self.listen_stop(ws)
                await drain

        recv_task.cancel()
        await self.play_queue.put(None)
        await playback
        await ws.close()

    async def _send_text_turn(self, ws: websockets.ClientConnection, text: str) -> None:
        """Simulator-only: listen/stop with text field skips ASR."""
        if not text:
            return
        await self.listen_start(ws)
        msg = {
            "session_id": self.session_id,
            "type": "listen",
            "state": "stop",
            "text": text,
        }
        await ws.send(json.dumps(msg))
        self.recording = False


async def main_async(args: argparse.Namespace) -> None:
    device = SimDevice(
        args.url,
        args.token,
        device_id=args.device_id or None,
    )
    await device.run_push_to_talk()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Simulate xiaozhi ESP32 voice device")
    parser.add_argument(
        "--url",
        default=settings.ws_url,
        help="WebSocket server URL (default: settings.ws_url)",
    )
    parser.add_argument("--token", default=settings.token, help="Bearer token")
    parser.add_argument(
        "--device-id",
        default="",
        help="Device-Id header (default: this Mac MAC-style id)",
    )
    args = parser.parse_args()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
