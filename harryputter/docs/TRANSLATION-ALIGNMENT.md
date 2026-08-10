# 中英对齐修复（2026-06）

> 美版 EPUB 句数 > 珍藏版中文句数时，旧逻辑会把同一句中文贴到多条英文上，或把中文切成「能写 / 出来 / 吗」碎片。本章记录 **ch04 试点** 及可推广到全书的流程。

## 三步分工（推荐 · 2026-06 起）

| 步 | 谁做 | 工具 | 原则 |
|----|------|------|------|
| **① Agent 双语片段** | Agent | `translation_fixes` 里的 **`bilingual_clips[]`** | 每条 `{en, zh}` 是**叙事节拍**（≠ 裸 EPUB 句）；美版 EN / 珍藏版 ZH / 音频切分不一致时必用 |
| **② 英文 ↔ 音频** | 程序 | `align_words.py` · Whisper | 只对 `clips[].en` 做对齐；`manifest.align_mode = bilingual_clips` |
| **③ 挂中文** | 程序 | `attach_translation.py` | 按行序 **1:1** 贴 `clips[].zh`；不走 `en_to_zh` / merge / overrides |

```json
"bilingual_clips": [
  { "en": "Mr. Dursley was the director of a firm called Grunnings, which made drills.", "zh": "弗农德思礼先生在一家名叫格朗宁的公司做主管，公司生产钻机。" },
  { "en": "He was a big, beefy man with hardly any neck, although he did have a very large mustache.", "zh": "他高大魁梧，胖得几乎连脖子都没了，却蓄着一脸大胡子。" }
]
```

**试点**：`hp01` 第 1 章 · 248 条 clips · `translation_method: bilingual_clips`

```bash
# 从已验收 manifest 导出 clips（首次 bootstrap）
python3 scripts/export_bilingual_clips.py --book hp01 --chapter 1

# 重对齐 + 挂译
python3 scripts/align_words.py --book hp01 --chapter 1
python3 scripts/attach_translation.py --book hp01 --chapter 1
```

**典型错位**：0:31 音频已是「格朗宁/钻机」，中文却带「高大魁梧」→ EPUB 索引挂译失败；clips 在 Agent 层先拆开。

## 两层分工（旧章 / fallback）

无 `bilingual_clips` 时仍走 EPUB + 锚点：

| 层 | 谁做 | 工具 | 原则 |
|----|------|------|------|
| **英文 ↔ 音频** | 程序 | `align_words.py` · Whisper 词缓存 | 不改时间轴；`_ALIGN_SUBCLIP_MARKERS` 可拆合并 EPUB 句 |
| **中文 ↔ 英文** | **Agent** | `en_to_zh_text` · `COARSE_GROUPS` · `line_splits` · `line_zh_overrides` | **禁止**程序按字数自动切中文 |

程序：挂译 → 去重 → `line_splits` → merge 无中文尾随行。

**长音频行**（如 15:41 一条含 en 198–208）：程序会把多句 EPUB 中文拼成一行（语义完整但 UI 过长）→ Agent 用 `line_splits` + Whisper 词时间拆成 3–6 条可读字幕，每条独立 `zh`。

## 问题根因

| 现象 | 原因 |
|------|------|
| 连续多行相同中文 | 一段内 EN 句数 > ZH 句数，比例映射让多句 EN 共用一句 ZH |
| 中文碎成半句 | `fan_out` / 按字数切分 ZH，与音频细句不同步 |
| 有英文无中文 | 为避免重复，只在句组第一条挂 ZH，其余 EN 行留空 |
| 时间轴对不上 | Whisper 按音频切句，比 EPUB 更碎 |

## 解决方案（三层）

### 1. 锚点映射（难章 / 错位严重）

`scripts/build_chapter_zh_map.py`：按故事节点 `(en_si, zh_si)` 分段，段内再分配。

- **试点**：`hp01` 第 4 章 → `data/translation_fixes/hp01_ch04.json`（288 条 `en_to_zh_text` 全量覆盖）
- **句组**：`HP01_CH04_COARSE_GROUPS` — 一句中文只写在组内 **第一条** EN 索引上，其余为空

```bash
python3 scripts/build_chapter_zh_map.py --book hp01 --chapter 4
```

### 2. `attach_translation.py`（全书通用）

处理顺序：

1. 有 ≥85% 章节的 `en_to_zh_text` → **仅用 fixes**，不走段落 DP
2. 否则段落 DP + 按比例切分（fallback）
3. **`_zh_for_manifest_line`**：一条音频行若含多句 EPUB 英文，按句序拼接对应中文（不再只认首句）
4. **去重**：相邻两行不得相同 `zh`
5. `line_splits`（如 ch04 13:54 22s 长行按词时间拆 3 段）
6. **`_merge_manifest_zh_groups`**：有 `zh` 的行 + 后面连续无 `zh` 的 EN 行 → **合并为一行**（英文拼接，时间首尾相接）
7. 再次去重；更新 `total_sentences`

**`build_chapter_zh_map.map_segment`**（2026-06 升级）：EN 句数 > ZH 句数时，**整句中文只挂在组内第一条 EN**，其余留空，由步骤 6 合并；禁止按字数切碎中文。

播放器（`web/index.html`）：无 `zh` 的行播放时 **向前继承**（合并后基本用不到；SW 缓存见 `sw.js` 版本号）。

### 3. 质量门禁（三层 · 缺一不可）

美版音频切分 **≠** EPUB 句序；珍藏版中文是 **叙事节拍**，不能按 `en_to_zh[epub_i]` 逐句挂。验收分三层：

| 层 | 脚本 | 查什么 | 通过标准 |
|----|------|--------|----------|
| **A 结构** | `audit_zh_alignment.py` | 缺译、相邻完全相同中文 | `no_zh=0` · `consec_dup=0` |
| **B 叙事** | `audit_bilingual_clips.py` | 按播放顺序在 `zh_extract` 上走游标，查错位/跳段/孤儿句 | `drift=0`（或仅 `shard_only` 对话碎片） |
| **C 抽听** | Agent | 对 B 层 flagged 时间点 + 每章 5 个锚点试听 | 英文音频与中文语义同步 |

```bash
cd harryputter

# A：必要但不充分（过不了一定有问题；过了还可能 5:05 那种错位）
python3 scripts/audit_zh_alignment.py --book hp01 --from 1 --to 1

# B：叙事游标（应用 bilingual_clips 的章必跑）
python3 scripts/audit_bilingual_clips.py --book hp01 --chapter 1
python3 scripts/audit_bilingual_clips.py --book hp01 --chapter 1 --json   # 给 Agent 批修

# 全书摘要（MP3、时间轴、zh 覆盖率）
python3 scripts/audit_book.py --book hp01
```

**叙事游标原理**：`output/hp01/chNN_zh.json` 的 `sentences[]` 是珍藏版**故事顺序**真源。每条 `bilingual_clips[i].zh` 应等于 `zh[j]` 或 `zh[j:k]` 的拼接，且 `j` 随 `i` **单调前进**（允许一条中文拆成多条 clip，禁止整体后退或整段跳进）。

| B 层 issue | 含义 | 修法 |
|------------|------|------|
| `consec_dup` / `prefix_dup` | 相邻重复（如 5:05 停车场念两遍） | 拆/删重复 `zh` |
| `orphan` | 在 zh_extract 窗口内找不到这句中文 | 按游标重挂 `zh[j:k]` |
| `cursor_lost` | 本句中文对，但前面某条 clip 已丢游标 | 从首个 `cursor_lost` 起批量重挂 |
| `jump` | 一次跳过太多 zh 句（中间叙事丢失） | 检查是否 US 多句 EPUB 合并成一条 clip |
| `shard_only` | 长英文句只挂了 `…` / `」` | 对话碎片可保留；否则补全语义 |

**禁止**：用 `en_to_zh_text[str(epub_i)]` 给 clip 批量赋值（EPUB 索引 ≠ 音频 clip 序）。

| 指标 | 目标 |
|------|------|
| `no_zh` | 0（正文行） |
| `consec_dup` | 0（相邻相同中文） |
| `drift` | 0（叙事门） |
| `translation_method` | clips 章：`bilingual_clips`；旧章：`anchor_map_merge_zh_groups` |

## 单章重跑

```bash
cd harryputter
# 仅重挂中文（Whisper 缓存不变）
python3 scripts/attach_translation.py --book hp01 --chapter 4

# 对齐逻辑变更后
BOOK=hp01 ./scripts/realign_range.sh 1 17
```

## Agent 工作流（中文 ↔ 英文）

1. 听/看 `output/hp01/chNN.json` 某时间段，确认 **英文+时间轴** 已由程序对齐，无需改。
2. 若中文错位：编辑 `HP01_CHNN_ANCHORS` / `COARSE_GROUPS` → `python3 scripts/build_chapter_zh_map.py --book hp01 --chapter N`
3. 若一行中文 **>80 字或 >20s**：查 `output/hp01/chNN_words.json` 词时间，在 fixes 里加 `line_splits`（`match_start` + `parts[].end/text/zh`）
4. `python3 scripts/attach_translation.py --book hp01 --chapter N` → `audit_zh_alignment.py`

**不要**让程序自动按字数切 `zh`；只由 Agent 在 `line_splits` 里写语义完整的短段。

## 推广到其他章

1. **所有章**：重跑 `attach_translation.py` 即可得到 **合并 + 去重**（消除大部分连续重复）
2. **仍错位/碎片**：Agent 补锚点 → `translation_fixes/hp01_chNN.json`
3. **长音频单行**：Agent 补 `line_splits`（见 ch04 `812.46s`、`941.86s`）

## ch04 特例保留

- `en_to_zh_text["114"]`：录取通知书整段（美版 EPUB 碎片与 Hagrid 便条合并）
- `line_splits` @ `812.46s`：「告诉你…」/ 坐下 / 「谁？」三段时间轴
- **15:41–16:54**（`en` 198–208 合成一条音频行）：`line_splits` @ `941.86s` 拆 5 段（手帕 / 对不起…父母 / 被杀与追杀 / 伤疤与出名 / 麦金农与脑海景象）；时间来自 Whisper 词轴

## 全书批量状态（hp01 · 2026-06-08）

重跑 `attach_translation.py` 后：`consec_dup` 从百级降至 0–1（余 1 多为章标题 heading 与首行重复，可忽略）。仅 ch04 有 `translation_fixes`；其余章语义仍可能错位，按需补锚点。

## 相关文件

| 路径 | 用途 |
|------|------|
| `scripts/attach_translation.py` | 挂译、去重、合并 |
| `scripts/build_chapter_zh_map.py` | 锚点生成 fixes |
| `data/translation_fixes/hp01_ch01.json` | ch01 真源（**248 `bilingual_clips`**） |
| `data/translation_fixes/hp01_ch04.json` | ch04 真源（`en_to_zh` + `line_splits`） |
| `scripts/bilingual_clips.py` | 加载 clips |
| `scripts/export_bilingual_clips.py` | manifest → clips 导出 |
| `scripts/audit_bilingual_clips.py` | 叙事游标验收（结构 + zh_extract 顺序） |
| `docs/PIPELINE-NOTES.md` §11–12 | Pipeline 总览 |
| `.cursor/skills/harryputter-import/SKILL.md` | Agent 导入 + 中英对齐 SOP |
