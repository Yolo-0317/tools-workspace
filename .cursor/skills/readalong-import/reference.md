# readalong-import · 参考

## 书目 registry（canonical `book_id`）

| book_id | 用户常说 | 英文书名 | 中文 | 章数 | import 脚本 |
|---------|---------|---------|------|------|-------------|
| `hp01` | 第一部 / 魔法石 | Sorcerer's Stone | 哈利·波特与魔法石 | 17 | ✅ `import_downloads.sh` |
| `hp02` | 第二部 / 密室 | Chamber of Secrets | 哈利·波特与密室 | 18 | 待扩展 |
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

查当前进度：`python3 -c "import json;c=json.load(open('readalong/output/catalog.json'));print(c['ready_count'], '/', c['chapter_count']);[print(x['pad'], x['ready'], x['title_zh']) for x in c['chapters']]"`

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
| Whisper 中断 exit 143 | Agent 后台 SIGTERM | **前台**跑 `./scripts/pipeline.sh N`，`block_until_ms` 足够长 |
| 点击句子重头播 | Range 请求 | 已修 `serve.py`；`./scripts/restart.sh` |
| PWA 图标不显示 | 硬编码 base | 已动态 base；硬刷新 SW |

## 英/美拼写（EPUB 美版 · Fry 英音）

| EPUB | 音频 |
|------|------|
| mail | post |
| neighbor | neighbour |
| favorite | favourite |

低置信 / `interpolated: true` 句在 UI 半透明，属预期。

## 扩展 hp02+

1. 在 `data/book01_chapters.json` 同级增加书目 JSON（或扩展 `chapters.py`）
2. 扩展 `import_downloads.sh` 的 `BOOK=hp02` 与 Downloads 目录名
3. `BOOK=hp02 ./scripts/pipeline.sh N`

当前 **import 脚本仅 hp01 全自动**；hp02+ 需手动放 MP3 到 `samples/hp02/`。
