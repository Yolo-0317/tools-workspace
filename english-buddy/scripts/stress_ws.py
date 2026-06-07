#!/usr/bin/env python3
"""WebSocket load test for English Buddy read-along (local)."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import struct
import time
from dataclasses import dataclass, field

try:
    import websockets
except ImportError as e:
    raise SystemExit("pip install websockets") from e

SAMPLE_RATE = 16000
MATERIAL = (
    "Good morning, teacher.\n"
    "Good morning, everyone.\n"
    "How are you today?"
)
CHILD_LINES = [
    "Good morning teacher",
    "Good morning everyone",
    "How are you today",
]


@dataclass
class ClientResult:
    client_id: int
    ok: bool
    error: str = ""
    connect_ms: float = 0.0
    kickoff_ms: float = 0.0
    turn_ms: list[float] = field(default_factory=list)


async def recv_until(ws, *types: str, timeout: float = 120.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = await asyncio.wait_for(ws.recv(), timeout=deadline - time.monotonic())
        if isinstance(raw, bytes):
            continue
        msg = json.loads(raw)
        if msg.get("type") in types:
            return msg
    raise TimeoutError(f"timeout waiting for {types}")


async def drain_until_tts_end(ws, timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = await asyncio.wait_for(ws.recv(), timeout=deadline - time.monotonic())
        if isinstance(raw, bytes):
            continue
        msg = json.loads(raw)
        if msg.get("type") == "tts_end":
            return
        if msg.get("type") == "tts_failed":
            raise RuntimeError(msg.get("message", "tts_failed"))
        if msg.get("type") == "error":
            raise RuntimeError(msg.get("message", "error"))
    raise TimeoutError("timeout waiting for tts_end")


def make_pcm(seconds: float = 1.2) -> bytes:
    """16kHz mono int16 — enough for STT path (may not transcribe)."""
    n = int(SAMPLE_RATE * seconds)
    # quiet noise so Whisper still runs VAD path
    return struct.pack(f"<{n}h", *([int(120 * (i % 7 - 3)) for i in range(n)]))


async def run_client(
    url: str,
    client_id: int,
    *,
    mode: str,
    turns: int,
) -> ClientResult:
    res = ClientResult(client_id=client_id, ok=False)
    try:
        t0 = time.monotonic()
        async with websockets.connect(url, max_size=8 * 1024 * 1024) as ws:
            await recv_until(ws, "ready", timeout=30.0)
            res.connect_ms = (time.monotonic() - t0) * 1000

            await ws.send(
                json.dumps(
                    {
                        "type": "start_call",
                        "mode": "read_along",
                        "program": "elsa_snow",
                        "reading_material": MATERIAL,
                    }
                )
            )
            await recv_until(ws, "call_started", timeout=15.0)
            t_k = time.monotonic()
            await drain_until_tts_end(ws, timeout=180.0)
            res.kickoff_ms = (time.monotonic() - t_k) * 1000

            for i in range(min(turns, len(CHILD_LINES))):
                t_turn = time.monotonic()
                if mode == "stt":
                    await ws.send(make_pcm(1.5))
                    await ws.send(json.dumps({"type": "utterance_end"}))
                else:
                    await ws.send(
                        json.dumps(
                            {
                                "type": "text_message",
                                "text": CHILD_LINES[i],
                            }
                        )
                    )
                await drain_until_tts_end(ws, timeout=180.0)
                res.turn_ms.append((time.monotonic() - t_turn) * 1000)

            res.ok = True
    except Exception as e:
        res.error = repr(e)
    return res


async def run_connect_only(url: str, n: int, hold_s: float) -> tuple[int, int]:
    ok = 0
    async def one(i: int) -> bool:
        try:
            async with websockets.connect(url, max_size=2 * 1024 * 1024) as ws:
                await recv_until(ws, "ready", timeout=20.0)
                await asyncio.sleep(hold_s)
                return True
        except Exception:
            return False

    results = await asyncio.gather(*[one(i) for i in range(n)])
    ok = sum(1 for r in results if r)
    return ok, n


def summarize(label: str, results: list[ClientResult]) -> None:
    ok = [r for r in results if r.ok]
    fail = [r for r in results if not r.ok]
    print(f"\n=== {label} ===")
    print(f"clients: {len(results)}  success: {len(ok)}  fail: {len(fail)}")
    if fail:
        for r in fail[:5]:
            print(f"  fail#{r.client_id}: {r.error}")
    if not ok:
        return
    kicks = [r.kickoff_ms for r in ok]
    turns = [t for r in ok for t in r.turn_ms]
    print(f"kickoff_ms  p50={statistics.median(kicks):.0f}  max={max(kicks):.0f}")
    if turns:
        print(
            f"turn_ms     p50={statistics.median(turns):.0f}  "
            f"p95={sorted(turns)[max(0, int(len(turns) * 0.95) - 1)]:.0f}  "
            f"max={max(turns):.0f}  n={len(turns)}"
        )


async def main() -> None:
    p = argparse.ArgumentParser(description="English Buddy WS stress test")
    p.add_argument("--url", default="ws://127.0.0.1:18787/ws/call")
    p.add_argument("--clients", type=int, default=4)
    p.add_argument("--turns", type=int, default=3)
    p.add_argument(
        "--mode",
        choices=("text", "stt", "connect"),
        default="text",
        help="text=带读+TTS(无STT); stt=utterance_end+Whisper; connect=仅连接",
    )
    p.add_argument("--sweep", action="store_true", help="run 1,2,4,6,8 clients (text mode)")
    args = p.parse_args()

    print(f"target: {args.url}")
    print(f"mode: {args.mode}")

    if args.mode == "connect":
        for n in (5, 10, 20, 30):
            t0 = time.monotonic()
            ok, total = await run_connect_only(args.url, n, hold_s=3.0)
            print(f"connect hold {n}: ok={ok}/{total} in {(time.monotonic()-t0)*1000:.0f}ms")
        return

    if args.sweep:
        for n in (1, 2, 4, 6, 8):
            # edge-TTS under load: high concurrency queues heavily
            t0 = time.monotonic()
            results = await asyncio.gather(
                *[
                    run_client(args.url, i, mode=args.mode, turns=args.turns)
                    for i in range(n)
                ]
            )
            summarize(f"{args.mode} x{n} clients", list(results))
            print(f"wall_ms: {(time.monotonic() - t0) * 1000:.0f}")
            await asyncio.sleep(2.0)
        return

    t0 = time.monotonic()
    results = await asyncio.gather(
        *[
            run_client(args.url, i, mode=args.mode, turns=args.turns)
            for i in range(args.clients)
        ]
    )
    summarize(f"{args.mode} x{args.clients} clients", list(results))
    print(f"wall_ms: {(time.monotonic() - t0) * 1000:.0f}")


if __name__ == "__main__":
    asyncio.run(main())
