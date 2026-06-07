# HP Read-Along (POC)

**第一章试跑**：`chapter01.mp3` ↔ EPUB Chapter 1 原文 → 播放时同步高亮段落。

不用 Ollama；时间轴靠 `faster-whisper` 转写 + 顺序映射。

## 样本

将以下文件放入 `samples/`（不提交 git）：

- `book.epub`
- `chapter01.mp3`

## 流程

```bash
# 1) 从 EPUB 提取第一章句子
python3 scripts/extract_chapter.py -o manifests/chapter01_text.json

# 2) 用 faster-whisper 对齐时间轴（复用 english-buddy venv）
source ../english-buddy/.venv/bin/activate
python3 scripts/align_whisper.py

# 3) 生成高同步 manifest（推荐预览）
python3 scripts/build_transcript_manifest.py

# 4) 本地预览
python3 -m http.server 8765
# 默认（Whisper 原文，同步最准）: http://127.0.0.1:8765/web/
# EPUB 原文（实验性）:            http://127.0.0.1:8765/web/?mode=epub
```

## 技术说明

- **不用 Ollama**：时间轴靠 `faster-whisper` 转写 + 文本模糊匹配。
- 有声书开头有书名/作者/章节名，脚本会自动跳到正文第一句（约 12s）。
- US EPUB（Sorcerer's）与英版有声书（Philosopher's）章节正文一致；个别拼写差异（mustache/moustache）不影响对齐。

## 限制（POC）

- 整章转写约 30s（CPU）；对齐率为启发式，长章需人工抽检。
- 后续可换 **aeneas** / **WhisperX** 提升句级精度。
