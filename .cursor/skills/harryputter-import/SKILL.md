---
name: harryputter-import
description: >-
  Import harryputter audiobook chapters by book_id + chapter (e.g. hp01 ch11 =
  哈利波特第一部第十一章). Runs pipeline.sh, verify, catalog. Use when user says
  导入哈利波特第一部、hp01 第N章、harryputter 魔法石 第N章、对齐字幕、中英对齐、line_splits、
  translation_fixes、import harryputter chapter. Do NOT treat bare「第N章」as sufficient
  — always resolve book_id first. 英文↔音频用程序；中文↔英文由 Agent 改 fixes。
paths:
  - harryputter/scripts/pipeline.sh
  - harryputter/scripts/import_downloads.sh
  - harryputter/scripts/verify_chapter.py
  - harryputter/scripts/attach_translation.py
  - harryputter/scripts/audit_bilingual_clips.py
  - harryputter/scripts/build_chapter_zh_map.py
  - harryputter/data/translation_fixes/
  - harryputter/docs/TRANSLATION-ALIGNMENT.md
  - harryputter/docs/PIPELINE-NOTES.md
---

# harryputter-import · 有声书章节导入（书目 + 章号）

> **真源**：`harryputter/`（`:8791`，Caddy `/harryputter/web/`）。

## 寻址规则（必读）

HarryPutter 按 **「部 / 书目」+「章号」** 组织，**禁止**只用「第 N 章」理解任务。

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
cd harryputter
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

**全书 QA**（三层门禁 · `bilingual_clips` 章必跑 B 层）：

```bash
python3 scripts/audit_zh_alignment.py --book hp01 --from 1 --to 1      # A 结构
python3 scripts/audit_bilingual_clips.py --book hp01 --chapter 1       # B 叙事游标
python3 scripts/audit_book.py --book hp01
./scripts/realign_range.sh 1 17   # 对齐/attach 逻辑变更后，复用 Whisper 缓存
```

- **A 过不了** → 一定有问题（缺译 / 相邻重复）
- **A 过、B 不过** → 典型 5:05 式错位：按 `audit_bilingual_clips` 输出的 `clip` + 时间修 `bilingual_clips[].zh`（对照 `zh_extract`，**禁止** `en_to_zh[epub_i]` 批量挂）
- **B 过** → 再抽听 flagged + 每章 5 锚点

见 `harryputter/docs/TRANSLATION-ALIGNMENT.md` §质量门禁、`PIPELINE-NOTES.md` §11–12。

> **现况**：pipeline 产出路径暂为 `output/chNN.json`（仅 **hp01** 已接入 catalog）；hp02+ 需扩展 output 命名后再并行多书。

## 环境

| 项 | 说明 |
|----|------|
| `BOOK` | **必填语义**（shell 默认 `hp01`，但 Agent 须显式指定） |
| venv | `harryputter/.venv` 或 `english-buddy/.venv` |
| 依赖 | `pip install -r harryputter/requirements.txt` |

## pipeline 步骤（勿拆乱序）

`extract_sentences` → `extract_chinese` → `align_words` → `attach_translation` → `build_catalog` → `verify_chapter`

## 三步分工（中英对齐 · 推荐）

| 步 | 执行者 | 工具 | 说明 |
|----|--------|------|------|
| **① 双语片段** | **Agent** | `fixes.bilingual_clips[]` | 每条 `{en, zh}` = 叙事节拍；**优先于** EPUB 索引 |
| **② EN↔音频** | 程序 | `align_words.py` | 只对 `clips[].en` 对齐 |
| **③ 挂中文** | 程序 | `attach_translation.py` | 1:1 贴 `clips[].zh`（`translation_method: bilingual_clips`） |

```bash
# 首次：从验收 manifest 导出
python3 scripts/export_bilingual_clips.py --book hp01 --chapter 1
python3 scripts/align_words.py --book hp01 --chapter 1
python3 scripts/attach_translation.py --book hp01 --chapter 1
```

**试点**：`hp01` ch01 · `data/translation_fixes/hp01_ch01.json`（248 clips）

## 两层分工（旧章 fallback）

无 `bilingual_clips` 时：

| 层 | 执行者 | 工具 | 禁止 |
|----|--------|------|------|
| **英文 ↔ 音频** | 程序 | `align_words.py` | 为修中文改时间轴 |
| **中文 ↔ 英文** | **Agent** | `en_to_zh_text` · `line_splits` · `line_zh_overrides` | 程序按字数切 `zh` |

挂译 → 去重 → `line_splits` → merge → 再去重。

### Agent 优化一章（无 clips 时 · 试点 hp01 ch04）

1. **听读** `output/{book}/chNN.json`，标出 `zh_len>80` 或 `duration>20s` 或语义错位行
2. **查词时间** `output/{book}/chNN_words.json` 定 `line_splits` 的 `end`
3. **编辑 fixes**（三选一或组合）：
   - `build_chapter_zh_map.py`：`HP01_CHNN_ANCHORS` + `COARSE_GROUPS` → 重生 `en_to_zh_text`
   - `line_splits`：`match_start` + `parts[].end/text/zh`（长音频行必读）
   - `line_zh_overrides`：单行兜底
4. **重挂**：`python3 scripts/attach_translation.py --book hp01 --chapter N`
5. **门禁**：`audit_zh_alignment.py` + `audit_book.py`

```bash
cd harryputter
python3 scripts/build_chapter_zh_map.py --book hp01 --chapter 4   # 仅锚点变更时
python3 scripts/attach_translation.py --book hp01 --chapter 4
python3 scripts/audit_zh_alignment.py --book hp01 --from 4 --to 4
```

真源文档：**[harryputter/docs/TRANSLATION-ALIGNMENT.md](harryputter/docs/TRANSLATION-ALIGNMENT.md)** · ch04 fixes：**`data/translation_fixes/hp01_ch04.json`**

## 导入后

- 无需 restart；刷新 PWA
- 汇报格式：`{book_id} 第 {N} 章（{title_zh}）— {lines} 句，catalog {ready_count}/{chapter_count}`

## 禁止

- 勿在未确认 **book_id** 时跑 pipeline
- 勿 `ln -s ~/Downloads/... samples/hp01/chapterNN.mp3`
- 勿删 `chNN_words.json` 除非换 MP3
- 勿把 Whisper 首跑丢后台（易 SIGTERM）

## 延伸阅读

- 书目表 + 章名 + 对齐故障：[reference.md](reference.md)
- 中英对齐 SOP：`harryputter/docs/TRANSLATION-ALIGNMENT.md`
- Pipeline 踩坑：`harryputter/docs/PIPELINE-NOTES.md` §11–12
