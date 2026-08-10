# harryputter-import · 参考

## 书目 registry（canonical `book_id`）

| book_id | 用户常说 | 英文书名 | 中文 | 章数 | import 脚本 |
|---------|---------|---------|------|------|-------------|
| `hp01` | 第一部 / 魔法石 | Sorcerer's Stone | 哈利·波特与魔法石 | 17 | ✅ `import_downloads.sh` |
| `hp02` | 第二部 / 密室 | Chamber of Secrets | 哈利·波特与密室 | 18 | ✅ `import_downloads.sh` |
| `hp03`–`hp07` | 第三部… | … | … | … | 待扩展 |

**Agent 寻址**：始终 `BOOK=hp01` + 章号 `N`；口语「第一部第十一章」= `hp01` + `11`。

## hp01 章节目录（魔法石）

| id | title_en | title_zh |
|----|----------|----------|
| 1 | The Boy Who Lived | 大难不死的男孩 |
| 2 | The Vanishing Glass | 悄悄消失的玻璃 |
| 3 | The Letters from No One | 猫头鹰传书 |
| 4 | The Keeper of the Keys | 钥匙保管员 |
| 5 | Diagon Alley | 对角巷 |
| 6 | The Journey from Platform Nine and Three-quarters | 从9又3/4站台开始的旅程 |
| 7 | The Sorting Hat | 分院帽 |
| 8 | The Potions Master | 魔药课老师 |
| 9 | The Midnight Duel | 午夜决斗 |
| 10 | Halloween | 万圣节前夜 |
| 11 | Quidditch | 魁地奇 |
| 12 | The Mirror of Erised | 厄里斯魔镜 |
| 13 | Nicolas Flamel | 尼可·勒梅 |
| 14 | Norbert the Norwegian Ridgeback | 挪威脊背龙诺伯 |
| 15 | The Forbidden Forest | 禁林 |
| 16 | Through the Trapdoor | 穿越活板门 |
| 17 | The Man with Two Faces | 双面人 |

查当前进度：`python3 -c "import json;c=json.load(open('harryputter/output/catalog.json'));print(c['ready_count'], '/', c['chapter_count']);[print(x['pad'], x['ready'], x['title_zh']) for x in c['chapters']]"`

## Downloads 源路径（hp01）

| 工作区 | Downloads |
|--------|-----------|
| `samples/epub/en/hp01.epub` | `Harry Potter and the Sorcerer's - J.K. Rowling.epub` |
| `samples/epub/zh/collection.epub` | `哈利.波特_珍藏版_七册全_.epub` |
| `samples/hp01/chapterNN.mp3` | `Harry Potter and the Philosopher's Stone/Chapter NN - *.mp3` |

## 故障速查

| 现象 | 原因 | 处理 |
|------|------|------|
| 音频 404 | MP3 是外链 symlink | `./scripts/import_downloads.sh` 或 `cp` 进 `samples/` |
| manifest 句数远少于 EPUB | 英/美拼写 + 对齐失败 | 已内置 `align_words.py` 等价+插值；重跑 pipeline |
| 无中文 | 未跑 attach 或 zh epub 缺章 | 确认 `collection.epub`，重跑 pipeline |
| 连续重复中文 | EN 句 > ZH 句旧逻辑 | 重跑 `attach_translation.py`（合并+去重） |
| 一行中文过长 / 碎片 | 程序自动切分或错位 | **Agent** 改 `translation_fixes`：`line_splits` / 锚点；见下节 |
| Whisper 中断 exit 143 | Agent 后台 SIGTERM | **前台**跑 `./scripts/pipeline.sh N`，`block_until_ms` 足够长 |
| 点击句子重头播 | Range 请求 | 已修 `serve.py`；`./scripts/restart.sh` |
| PWA 图标不显示 | 硬编码 base | 已动态 base；硬刷新 SW |

## 中文 ↔ 英文（Agent · 程序不自动切字）

**程序**：`align_words` 定英文+时间轴 → `attach_translation` 挂译/去重/合并。  
**Agent**：维护 `harryputter/data/translation_fixes/{book}_chNN.json`。

### line_splits 模板（长音频行）

```json
{
  "match_start": 941.86,
  "parts": [
    { "end": 952.72, "text": "He came ter yer house…", "zh": "海格突然掏出…" },
    { "end": 963.2, "text": "\"Sorry,\" he said.…", "zh": "“对不起，”他说…" }
  ]
}
```

- `match_start`：manifest 行 `start`（±0.35s）
- `text`：与 manifest 该行英文**前缀一致**（可截短；matcher 认前 48 字符）
- `end`：来自 `chNN_words.json` 词时间
- **禁止**在 Python 里按字数 `_split_zh_text` 切 manifest（fallback 段落仅「整句挂首条 EN」）

### hp01 ch04 参考（已优化）

| 时间段 | splits / 锚点 |
|--------|----------------|
| 13:32 `812s` | 告诉你 / 坐下 / 谁 |
| 15:41 `942s` | 手帕 + 噩耗 5 段 |
| 18:44 `1124s` | 神秘人失踪 6 段 |

命令：`python3 scripts/attach_translation.py --book hp01 --chapter 4` → `audit_zh_alignment.py --book hp01 --from 4 --to 4`

全书 SOP：`harryputter/docs/TRANSLATION-ALIGNMENT.md`

## 英/美拼写（EPUB 美版 · Fry 英音）

| EPUB | 音频 |
|------|------|
| mail | post |
| neighbor | neighbour |
| favorite | favourite |

低置信 / `interpolated: true` 句在 UI 半透明，属预期。

## hp02 章节目录（密室）

| id | title_en | title_zh |
|----|----------|----------|
| 1 | The Worst Birthday | 最糟糕的生日 |
| 2 | Dobby's Warning | 多比的警告 |
| … | … | … |
| 18 | Dobby's Reward | 多比的报偿 |

完整映射见 `data/book02_chapters.json`。**注意**：珍藏版 ch1 正文在 `index_split_023.html`（`022` 是目录页）。

## Downloads 源路径（hp02）

| 工作区 | Downloads |
|--------|-----------|
| `samples/epub/en/hp02.epub` | `Harry Potter and the Chamber of - J.K. Rowling.epub` |
| `samples/hp02/chapterNN.mp3` | `Harry Potter and the Chamber of Secrets/Chapter NN - *.mp3` |

## 多书 output 布局

- _manifest_：`output/{book_id}/chNN.json`（勿与第一部共用 `output/chNN.json`）
- _书目索引_：`output/library.json`；单书 catalog：`output/hp01/catalog.json`
- PWA 目录面板可选书目；URL `?book=hp02&ch=01`

## 扩展 hp03+

1. 增加 `data/book03_chapters.json` + `chapters.py` `KNOWN_BOOKS`
2. 扩展 `import_downloads.sh` case 分支
3. `BOOK=hp03 ./scripts/pipeline.sh N`
