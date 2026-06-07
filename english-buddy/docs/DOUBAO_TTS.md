# 豆包 TTS（可选 · 已停用默认）

公主节目已改 **本地 Piper** 仿「温柔桃子」调校，无需火山付费。

以下为可选接入说明（需 `tts_backend=doubao` 且配置密钥）。

## 开通与配置

1. 登录 [火山引擎 · 豆包语音](https://www.volcengine.com/docs/6561/1108211)
2. 创建应用，拿到 **APP ID** 与 **Access Token**
3. 在 `english-buddy/.env` 填写：

```bash
DOUBAO_APP_ID=你的appid
DOUBAO_ACCESS_TOKEN=你的token
DOUBAO_CLUSTER=volcano_tts

# 可选：换音色（见控制台「大模型音色列表」）
# 小何 — 豆包常见亲切女声（默认）
ELSA_DOUBAO_VOICE=zh_female_xiaohe_uranus_bigtts
# 爽快思思 — 更活泼
# ELSA_DOUBAO_VOICE=zh_female_shuangkuaisisi_uranus_bigtts

# 带读英文
DOUBAO_EXPLICIT_LANGUAGE=en
DOUBAO_SPEED_RATIO=1.0
```

4. 重启：`./scripts/restart.sh`

## 未配置时

没有 `DOUBAO_*` 时，艾莎自动 **回退本地 Piper**（`en_US-amy-medium`），不阻塞通话。

## 说明

- 豆包 TTS 为 **联网** 调用；奥特曼节目不受影响。
- 音色 ID 以火山文档为准，2.0 大模型音色需按文档选 V1/V3 接口（当前实现为 V1 HTTP）。
