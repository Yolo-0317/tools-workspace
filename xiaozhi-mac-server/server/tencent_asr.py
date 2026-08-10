"""Tencent Cloud one-sentence ASR (SentenceRecognition, free tier 5000/mo)."""

from __future__ import annotations

import base64
import io
import logging
import wave

import numpy as np

from server.config import settings
from server.opus_codec import OpusCodec

log = logging.getLogger(__name__)

_codec = OpusCodec(
    uplink_rate=settings.uplink_rate,
    downlink_rate=settings.downlink_rate,
    frame_ms=settings.frame_ms,
)


def tencent_asr_configured() -> bool:
    return bool(settings.tencent_secret_id and settings.tencent_secret_key)


def _pcm_to_wav_bytes(pcm: np.ndarray, sample_rate: int) -> bytes:
    if pcm.dtype != np.int16:
        pcm = pcm.astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def _recognize_wav(wav_bytes: bytes) -> str:
    if not wav_bytes:
        return ""
    if not tencent_asr_configured():
        raise RuntimeError("Tencent ASR credentials missing (TENCENT_SECRET_ID / TENCENT_SECRET_KEY)")

    from tencentcloud.asr.v20190614 import asr_client, models
    from tencentcloud.common import credential
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
        TencentCloudSDKException,
    )
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile

    cred = credential.Credential(settings.tencent_secret_id, settings.tencent_secret_key)
    http_profile = HttpProfile()
    http_profile.reqMethod = "POST"
    http_profile.endpoint = "asr.tencentcloudapi.com"
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client = asr_client.AsrClient(cred, settings.tencent_asr_region, client_profile)

    req = models.SentenceRecognitionRequest()
    req.ProjectId = 0
    req.SubServiceType = 2
    req.EngSerViceType = settings.tencent_asr_engine
    req.SourceType = 1
    req.VoiceFormat = "wav"
    req.Data = base64.b64encode(wav_bytes).decode("ascii")
    req.DataLen = len(wav_bytes)

    try:
        resp = client.SentenceRecognition(req)
    except TencentCloudSDKException as exc:
        log.warning("Tencent ASR failed: %s", exc)
        raise

    text = (resp.Result or "").strip()
    if text:
        log.info("Tencent ASR text=%r bytes=%s", text, len(wav_bytes))
    return text


def transcribe_opus_packets(packets: list[bytes]) -> str:
    pcm = _codec.decode_packets(packets, settings.uplink_rate)
    if pcm.size == 0:
        return ""
    wav_bytes = _pcm_to_wav_bytes(pcm, settings.uplink_rate)
    return _recognize_wav(wav_bytes)


def transcribe_audio_bytes(data: bytes) -> str:
    if not data:
        return ""
    from server.audio_pcm import decode_audio_bytes

    pcm_f = decode_audio_bytes(data, settings.uplink_rate)
    if pcm_f.size == 0:
        return ""
    pcm = (pcm_f * 32768.0).astype(np.int16)
    wav_bytes = _pcm_to_wav_bytes(pcm, settings.uplink_rate)
    return _recognize_wav(wav_bytes)
