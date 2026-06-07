# Readalong — 有声书句级同步带读

独立项目：**EPUB 原文 + MP3** → 精确到**句子**的时间轴 → 播放时高亮。

不用 Ollama。对齐靠 `faster-whisper` **词级时间戳** + 与 EPUB 句子的单调匹配。

## 快速开始（第一章试跑）

```bash
cd readalong
# 样本放 samples/：book.epub + chapter01.mp3（可从 hp-readalong/samples 复制）

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 一键：提取句子 → 词级转写 → 对齐 → manifest
./scripts/pipeline.sh 1

# 安装常驻 + 公网（不经 Home Hub 登录）
./scripts/install-launchd.sh
cd ../sidestore-infra && docker compose restart caddy
```

| 环境 | URL |
|------|-----|
| 本机 | http://127.0.0.1:8791/web/ |
| 内网 | https://hub.yoloworld.site:8443/readalong/web/ |
| 外网 | https://hub.yoloworld.site:8883/readalong/web/ |

首次转写约 5 分钟（32 分钟章节）；结果缓存于 `output/ch01_words.json`，之后对齐秒开。

## 目录

```text
readalong/
  scripts/
    extract_sentences.py   # EPUB → 句子列表
    align_words.py         # 词级 forced alignment
    pipeline.sh
  output/                  # manifest + 缓存（gitignore）
  web/index.html           # 播放器
  samples/                 # 本地素材，不提交
```

## 添加新章节

1. 放入 `samples/chapterNN.mp3`
2. 在 `scripts/extract_sentences.py` 的 `CHAPTER_FILES` 增加 EPUB 路径
3. `./scripts/pipeline.sh NN`
