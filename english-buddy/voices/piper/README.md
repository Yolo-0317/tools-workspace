# Piper 本地语音（离线）

| 目录 | 模型 | 用途 |
|------|------|------|
| `elsa/` | `en_US-amy-medium` + `synthesis.json` | 艾莎带读（轻快明亮：略快语速 + 提音高） |
| `ultra/` | `en_US-ryan-medium` | 奥特曼带读老师（男声） |

首次安装或换机：

```bash
cd english-buddy
./scripts/download_piper_voices.sh
```

`.env` 设 `TTS_ENGINE=piper`（默认）。ONNX 约 60MB/个，勿提交 git。
