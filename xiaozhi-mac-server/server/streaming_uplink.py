"""Segment continuous Opus uplink into utterance turns (auto / realtime listen modes)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from server.config import settings
from server.opus_codec import OpusCodec

log = logging.getLogger(__name__)

_DEFAULT_NOISE = 0.006
_DEFAULT_THRESHOLD = settings.stream_min_rms


@dataclass
class OpusStreamingTurnSegmenter:
    """Detect end-of-utterance from RMS silence between Opus frames."""

    sample_rate: int = settings.uplink_rate
    frame_ms: int = settings.frame_ms
    silence_ms: int = settings.stream_silence_ms
    min_speech_ms: int = settings.stream_min_speech_ms
    max_utterance_ms: int = settings.stream_max_utterance_ms
    start_speech_frames: int = settings.stream_start_speech_frames
    min_rms: float = settings.stream_min_rms
    noise_multiplier: float = settings.stream_noise_multiplier

    _codec: OpusCodec = field(default_factory=OpusCodec, repr=False)
    _pre_roll: list[bytes] = field(default_factory=list, init=False, repr=False)
    _speech_packets: list[bytes] = field(default_factory=list, init=False, repr=False)
    _calibration_rms: list[float] = field(default_factory=list, init=False, repr=False)
    _noise_floor: float = field(default=_DEFAULT_NOISE, init=False, repr=False)
    _speech_threshold: float = field(default=_DEFAULT_THRESHOLD, init=False, repr=False)
    _in_speech: bool = field(default=False, init=False, repr=False)
    _heard_speech: bool = field(default=False, init=False, repr=False)
    _pre_roll_frames: int = field(default=0, init=False, repr=False)
    _silence_frames: int = field(default=0, init=False, repr=False)
    _speech_frames: int = field(default=0, init=False, repr=False)
    _total_frames: int = field(default=0, init=False, repr=False)
    _level_ema: float = field(default=0.0, init=False, repr=False)
    _holdoff_frames: int = field(default=0, init=False, repr=False)
    _calibrated: bool = field(default=False, init=False, repr=False)

    def reset(self) -> None:
        self._pre_roll.clear()
        self._speech_packets.clear()
        self._calibration_rms.clear()
        self._noise_floor = _DEFAULT_NOISE
        self._speech_threshold = _DEFAULT_THRESHOLD
        self._in_speech = False
        self._heard_speech = False
        self._pre_roll_frames = 0
        self._silence_frames = 0
        self._speech_frames = 0
        self._total_frames = 0
        self._level_ema = 0.0
        self._holdoff_frames = 0
        self._calibrated = False

    def begin_holdoff(self, ms: int) -> None:
        """Ignore uplink briefly after server TTS so speaker bleed does not poison VAD."""
        self.reset()
        self._holdoff_frames = max(1, ms // self.frame_ms)
        log.info("Stream VAD holdoff %dms (%d frames)", ms, self._holdoff_frames)

    def _silence_threshold(self) -> float:
        return self._speech_threshold * settings.stream_silence_ratio

    def _apply_default_calibration(self, *, reason: str) -> None:
        self._noise_floor = _DEFAULT_NOISE
        self._speech_threshold = _DEFAULT_THRESHOLD
        self._calibrated = True
        log.warning(
            "Stream VAD using defaults (%s) threshold=%.4f noise=%.4f",
            reason,
            self._speech_threshold,
            self._noise_floor,
        )

    def _finalize_calibration(self) -> None:
        if self._calibrated:
            return
        if len(self._calibration_rms) < 12:
            self._apply_default_calibration(reason="insufficient quiet samples")
            return
        ordered = sorted(self._calibration_rms)
        q1 = ordered[max(0, len(ordered) // 4)]
        self._noise_floor = max(_DEFAULT_NOISE, q1)
        if self._noise_floor > settings.stream_noise_floor_max:
            self._apply_default_calibration(
                reason=f"noise floor {self._noise_floor:.4f} too high"
            )
            return
        self._speech_threshold = min(
            max(self.min_rms, self._noise_floor * self.noise_multiplier),
            settings.stream_speech_threshold_max,
        )
        self._calibrated = True
        log.info(
            "Stream VAD calibrated threshold=%.4f noise=%.4f silence=%.4f",
            self._speech_threshold,
            self._noise_floor,
            self._silence_threshold(),
        )

    def _calibrate_if_needed(self, level: float) -> None:
        if self._calibrated:
            return
        if self._holdoff_frames > 0 and level >= self.min_rms:
            return
        self._calibration_rms.append(level)
        if len(self._calibration_rms) >= 12:
            self._finalize_calibration()

    def _frame_rms(self, packet: bytes) -> float:
        pcm = self._codec.decode_packet(packet, self.sample_rate)
        if pcm.size == 0:
            return 0.0
        audio = pcm.astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(audio * audio)))
        self._level_ema = rms if self._level_ema <= 0 else self._level_ema * 0.82 + rms * 0.18
        return self._level_ema

    def _begin_speech(self) -> None:
        self._in_speech = True
        self._heard_speech = False
        self._silence_frames = 0
        self._speech_frames = 0
        self._speech_packets = list(self._pre_roll)
        self._pre_roll.clear()
        self._pre_roll_frames = 0

    def _finish_turn(self) -> list[bytes]:
        packets = list(self._speech_packets)
        self._speech_packets.clear()
        self._in_speech = False
        self._heard_speech = False
        self._silence_frames = 0
        self._speech_frames = 0
        self._total_frames = 0
        self._pre_roll.clear()
        self._pre_roll_frames = 0
        return packets

    def feed(self, packet: bytes) -> list[list[bytes]]:
        if not packet:
            return []

        level = self._frame_rms(packet)
        if self._holdoff_frames > 0:
            self._holdoff_frames -= 1
            self._calibrate_if_needed(level)
            if self._holdoff_frames == 0 and not self._calibrated:
                self._finalize_calibration()
            return []

        if not self._calibrated:
            self._calibrate_if_needed(level)

        self._total_frames += 1
        is_loud = level >= self._speech_threshold
        completed: list[list[bytes]] = []

        if not self._in_speech:
            if is_loud:
                self._pre_roll_frames += 1
                self._pre_roll.append(packet)
                if len(self._pre_roll) > self.start_speech_frames + 2:
                    self._pre_roll.pop(0)
                if self._pre_roll_frames >= self.start_speech_frames:
                    self._begin_speech()
                    self._speech_packets.append(packet)
                    self._speech_frames = 1
                    self._heard_speech = True
            else:
                self._pre_roll_frames = 0
                self._pre_roll.append(packet)
                if len(self._pre_roll) > 2:
                    self._pre_roll.pop(0)
            return completed

        self._speech_packets.append(packet)
        if level >= self._speech_threshold:
            self._heard_speech = True
            self._silence_frames = 0
            self._speech_frames += 1
        elif level < self._silence_threshold():
            self._silence_frames += 1
        else:
            # Hysteresis band: neither speech peak nor clear silence.
            pass

        speech_ms = self._speech_frames * self.frame_ms
        silent_ms = self._silence_frames * self.frame_ms
        utterance_ms = self._total_frames * self.frame_ms

        if (
            self._heard_speech
            and silent_ms >= self.silence_ms
            and speech_ms >= self.min_speech_ms
        ):
            turn = self._finish_turn()
            if turn:
                log.info("Stream VAD utterance end (%d packets)", len(turn))
                completed.append(turn)
            return completed

        if utterance_ms >= self.max_utterance_ms and self._heard_speech:
            turn = self._finish_turn()
            if turn:
                log.info("Stream VAD utterance max-length (%d packets)", len(turn))
                completed.append(turn)
        return completed

    def flush(self) -> list[list[bytes]]:
        if not self._speech_packets:
            self.reset()
            return []
        if not self._heard_speech:
            self.reset()
            return []
        speech_ms = self._speech_frames * self.frame_ms
        if speech_ms < self.min_speech_ms:
            self.reset()
            return []
        turn = self._finish_turn()
        self.reset()
        return [turn] if turn else []
