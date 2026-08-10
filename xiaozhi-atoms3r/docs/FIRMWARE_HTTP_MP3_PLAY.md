# 固件：HTTP MP3 + 设备端 MCP（进行中）

配合 `xiaozhi-mac-server/docs/DESIGN_CLOUD_HTTP_QUARK_PLAY.md`。

## 目标

| 工具 | 行为 |
|------|------|
| `self.audio.play_url` | 参数 `url`；断开对话；HTTP 拉 Mac `.../device.mp3`；解码出声；Pyramid 指示灯关闭 |
| `self.audio.pause` | 暂停 PCM 输出（可 `resume`） |
| `self.audio.resume` | 从暂停继续 |
| `self.audio.stop` | 停播；恢复可唤醒/听；Pyramid 指示灯恢复 |
| `self.audio_speaker.set_volume` | 0–100；播放中也可调 |
| Pyramid 触摸 | TP3 音量- / TP4 音量+（可长按连调）；播故事时 TP1 暂停/继续、TP2 停止；播期灯条保持熄灭 |

## Mac 侧已就绪（验收）

```bash
# launchd: com.user.xiaozhi-media 或
cd xiaozhi-mac-server && bash scripts/run-media-stack.sh

curl -sS -X POST http://127.0.0.1:8766/api/media/resolve \
  -H 'Content-Type: application/json' \
  -d '{"query":"冰雪奇缘第一集"}'
# → stream_url = http://<LAN>:8766/stream/quark/<fid>/device.mp3
# 格式：MPEG MP3 96kbps 24kHz mono（对齐 Pyramid AUDIO_OUTPUT_SAMPLE_RATE）
```

## 固件实现要点

1. 板型：`atoms3r-echo-pyramid` / `atoms3r-cam-m12-echo-base` 的 `InitializeTools()`。
2. 播前：`AbortSpeaking` + `StopListening` + `ResetDecoder`（[#863](https://github.com/78/xiaozhi-esp32/issues/863)）。
3. 实现：`main/audio/http_mp3_player.{h,cc}` — `esp_http_client` + `esp_audio_simple_dec`（MP3）→ `AudioCodec::OutputData`。
4. MCP：`self.audio.play_url` / `self.audio.stop`。
5. 与云端 TTS Opus 互斥：播前清空 decode 队列；HTTP 任务写 I2S。
6. 唤醒打断：默认 stop（设计 D4；固件侧后续可挂 wake → `HttpMp3Player::Stop`）。

## 编译 / 烧录（Pyramid）

Pyramid 使用 `partitions/v2/8m-large-app.csv`（OTA 各 `0x340000` / 3.25MiB，assets `0x160000`），以容纳 `esp_audio_simple_dec` MP3。

```bash
cd xiaozhi-atoms3r
export XIAOZHI_BOARD=atoms3r-echo-pyramid
bash scripts/build.sh
bash scripts/flash.sh          # 分区表变更须全量烧录（含 partition + assets）
bash scripts/monitor.sh        # 期望: HttpMp3Player Play start / MP3 info
```

## 联调

1. Mac：`launchctl kickstart -k gui/$(id -u)/com.user.xiaozhi-media`（或 `run-media-stack.sh`）。
2. 云端角色：搜故事 → `resolve_quark_stream_url` → `self.audio.play_url(url=stream_url)`。
3. 串口确认 `HttpMp3Player` 与喇叭出声。
