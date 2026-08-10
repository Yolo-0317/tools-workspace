"""Opus encode/decode aligned with xiaozhi-esp32 (60 ms frames)."""

from __future__ import annotations

import io
from typing import Iterable

import av
import numpy as np
import opuslib


class OpusCodec:
    def __init__(
        self,
        uplink_rate: int = 16000,
        downlink_rate: int = 24000,
        frame_ms: int = 60,
    ) -> None:
        self.uplink_rate = uplink_rate
        self.downlink_rate = downlink_rate
        self.frame_ms = frame_ms
        self.uplink_frame_samples = uplink_rate * frame_ms // 1000
        self.downlink_frame_samples = downlink_rate * frame_ms // 1000
        self._encoders: dict[int, opuslib.Encoder] = {}
        self._decoders: dict[int, opuslib.Decoder] = {}

    def _encoder(self, rate: int) -> opuslib.Encoder:
        if rate not in self._encoders:
            self._encoders[rate] = opuslib.Encoder(
                rate, 1, opuslib.APPLICATION_AUDIO
            )
        return self._encoders[rate]

    def _decoder(self, rate: int) -> opuslib.Decoder:
        if rate not in self._decoders:
            self._decoders[rate] = opuslib.Decoder(rate, 1)
        return self._decoders[rate]

    def encode_pcm(self, pcm: np.ndarray, rate: int) -> list[bytes]:
        """Encode int16 mono PCM into Opus packets (one per frame_ms)."""
        if pcm.dtype != np.int16:
            pcm = pcm.astype(np.int16)
        frame_samples = rate * self.frame_ms // 1000
        encoder = self._encoder(rate)
        packets: list[bytes] = []
        for start in range(0, len(pcm), frame_samples):
            chunk = pcm[start : start + frame_samples]
            if len(chunk) < frame_samples:
                chunk = np.pad(chunk, (0, frame_samples - len(chunk)))
            packets.append(encoder.encode(chunk.tobytes(), frame_samples))
        return packets

    def decode_packet(self, packet: bytes, rate: int) -> np.ndarray:
        if not packet:
            return np.array([], dtype=np.int16)
        decoder = self._decoder(rate)
        frame_samples = rate * self.frame_ms // 1000
        pcm_bytes = decoder.decode(packet, frame_samples)
        return np.frombuffer(pcm_bytes, dtype=np.int16)

    def decode_packets(self, packets: Iterable[bytes], rate: int) -> np.ndarray:
        decoder = self._decoder(rate)
        frame_samples = rate * self.frame_ms // 1000
        chunks: list[np.ndarray] = []
        for packet in packets:
            if not packet:
                continue
            pcm_bytes = decoder.decode(packet, frame_samples)
            chunks.append(np.frombuffer(pcm_bytes, dtype=np.int16))
        if not chunks:
            return np.array([], dtype=np.int16)
        return np.concatenate(chunks)

    @staticmethod
    def mp3_to_pcm_int16(mp3_data: bytes, target_rate: int) -> np.ndarray:
        """Decode MP3 (edge-tts output) to mono int16 at target_rate."""
        buf = io.BytesIO(mp3_data)
        container = av.open(buf, format="mp3")
        resampler = av.AudioResampler(format="s16", layout="mono", rate=target_rate)
        out: list[np.ndarray] = []
        for frame in container.decode(audio=0):
            for resampled in resampler.resample(frame):
                arr = resampled.to_ndarray()
                if arr.ndim > 1:
                    arr = arr[0]
                out.append(arr.astype(np.int16))
        if not out:
            return np.array([], dtype=np.int16)
        return np.concatenate(out)
