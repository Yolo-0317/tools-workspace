# 语音合成（TTS）选型

English Buddy 管线：**Whisper（听）→ Ollama（想）→ TTS（说）**。三者是分开的。

## Ollama 有没有 TTS？

**目前没有。** Ollama 官方只做 **大语言模型**（你现在的 `qwen2.5:3b` 等），没有 `ollama pull` 一条命令就能用的内置 TTS，也没有稳定的 `/api/tts` 一类接口（社区 issue 在讨论，尚无时间表）。

库里偶尔能看到名字带 TTS 的模型，多数仍需 **外部程序** 做真正的波形合成，不能指望「只装 Ollama」就解决人声。

## 本项目怎么用 Ollama？

| 环节 | 引擎 |
|------|------|
| STT | 本地 faster-whisper |
| LLM | Ollama `OLLAMA_MODEL` |
| TTS | **edge-tts**（当前默认，联网）或 **Piper**（离线） |

## 想更自然、仍尽量本地

| 方案 | 说明 |
|------|------|
| **Piper + `synthesis.json`** | 当前默认；调 `length_scale` / `pitch_shift` / `noise_*` |
| **edge-tts** | `.env` 设 `TTS_ENGINE=edge`；艾莎默认 `EmmaMultilingual`（活泼），可改 `ELSA_EDGE_VOICE` |
| **Kokoro / MeloTTS / Coqui** | 需另接服务或改 `backend/services/tts.py`，未内置 |

艾莎节目音色目录：`voices/piper/elsa/`（模型 + `synthesis.json`）。
