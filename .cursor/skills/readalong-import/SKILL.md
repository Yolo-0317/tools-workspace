---
name: readalong-import
description: >-
  Import readalong audiobook chapters by book_id + chapter (e.g. hp01 ch11 =
  哈利波特第一部第十一章). Runs pipeline.sh, verify, catalog. Use when user says
  导入哈利波特第一部、hp01 第N章、readalong 魔法石 第N章、对齐字幕、import readalong chapter.
  Do NOT treat bare「第N章」as sufficient — always resolve book_id first.
paths:
  - readalong/scripts/pipeline.sh
  - readalong/scripts/import_downloads.sh
  - readalong/scripts/verify_chapter.py
  - readalong/docs/PIPELINE-NOTES.md
---

# readalong-import · 有声书章节导入（书目 + 章号）

> **真源**：`readalong/`（`:8791`，Caddy `/readalong/web/`）。

## 寻址规则（必读）

Readalong 按 **「部 / 书目」+「章号」** 组织，**禁止**只用「第 N 章」理解任务。

| 用户说法 | `book_id` | 章号 |
|---------|-----------|------|
| 哈利波特**第一部**第 11 章 / 魔法石第 11 章 | `hp01` | `11` |
| hp01 ch11 / BOOK=hp01 第 11 章 | `hp01` | `11` |
| 哈利波特**第二部**第 3 章（待支持） | `hp02` | `3` |

- **canonical id**：`hp01` … `hp07`（见 [reference.md](reference.md) 书目表）
- 用户只说「导入第 11 章」→ **先问或从上下文确认书目**；无上下文时 **不得** 默认执行
- 汇报时用全称：**「hp01（魔法石）第 11 章 · 魁地奇」**

## 何时触发

| 用户意图 | 动作 |
|---------|------|
| 「导入哈利波特第一部第 N 章」 | `BOOK=hp01 ./scripts/pipeline.sh N` + verify |
| 「从 Downloads 迁入 hp01 素材」 | `BOOK=hp01 ./scripts/import_downloads.sh` |
| 「批量导入 hp01 ch5–ch9」 | 逐章 pipeline（Whisper 首跑 ~5 min/章） |
| 播放 404 / 少句 / 无中文 | [reference.md](reference.md) 故障表 |

## 快速执行（单章）

将 `BOOK`、`N` 替换为实际书目与章号（示例：**hp01 第 11 章**）：

```bash
cd readalong
BOOK=hp01
N=11
PAD=$(printf '%02d' "$N")

# 1. 素材齐全（缺则先迁入）
test -f "samples/${BOOK}/chapter${PAD}.mp3" \
  -a -f "samples/epub/en/${BOOK}.epub" \
  -a -f samples/epub/zh/collection.epub \
  || BOOK="$BOOK" ./scripts/import_downloads.sh

# 2. pipeline（首跑 Whisper ~5–8 min，须前台跑完，block_until_ms ≥ 600000）
BOOK="$BOOK" ./scripts/pipeline.sh "$N"

# 3. 校验
python3 scripts/verify_chapter.py --book "$BOOK" --chapter "$N"
python3 -c "
import json
c=json.load(open('output/catalog.json'))
ch=[x for x in c['chapters'] if x['id']==$N][0]
print(c['book_id'], 'ch'+ch['pad'], ch['title_zh'], 'ready=', ch['ready'])
"
```

**通过标准**：`verify_chapter.py` merged ≥ 95%；`output/ch${PAD}.json` 存在；catalog 该章 `ready: true`。

> **现况**：pipeline 产出路径暂为 `output/chNN.json`（仅 **hp01** 已接入 catalog）；hp02+ 需扩展 output 命名后再并行多书。

## 环境

| 项 | 说明 |
|----|------|
| `BOOK` | **必填语义**（shell 默认 `hp01`，但 Agent 须显式指定） |
| venv | `readalong/.venv` 或 `english-buddy/.venv` |
| 依赖 | `pip install -r readalong/requirements.txt` |

## pipeline 步骤（勿拆乱序）

`extract_sentences` → `extract_chinese` → `align_words` → `attach_translation` → `build_catalog` → `verify_chapter`

## 导入后

- 无需 restart；刷新 PWA
- 汇报格式：`{book_id} 第 {N} 章（{title_zh}）— {lines} 句，catalog {ready_count}/{chapter_count}`

## 禁止

- 勿在未确认 **book_id** 时跑 pipeline
- 勿 `ln -s ~/Downloads/... samples/hp01/chapterNN.mp3`
- 勿删 `chNN_words.json` 除非换 MP3
- 勿把 Whisper 首跑丢后台（易 SIGTERM）

## 延伸阅读

- 书目表 + 章名：[reference.md](reference.md)
- 踩坑：`readalong/docs/PIPELINE-NOTES.md`
