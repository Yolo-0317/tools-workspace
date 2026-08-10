# Pipeline 踩坑记录（新增章节前必读）

## 1. 文本没丢在 EPUB，丢在对齐

- `samples/epub/en/hp01.epub` 与 Downloads 里 `Harry Potter and the Sorcerer's - J.K. Rowling.epub` **MD5 相同**。
- 第三章曾显示「少句」，根因是 **manifest 对齐失败**，不是 EPUB 提取少字。
- **校验**：`python3 scripts/verify_chapter.py --chapter N`（merged 词数应 ≥ HTML 正文 95%）。

## 2. 美版 EPUB + 英式有声书（Stephen Fry）

EPUB 是美版用词，MP3 是英版朗读，常见不一致：

| EPUB（美） | 音频（英） |
|-----------|-----------|
| mail | post |
| video camera | cine camera |
| airplane | aeroplane |
| neighbor | neighbour |
| favorite | favourite |

**处理**（已在 `align_words.py`）：

- 章首跳过 `CHAPTER N` 口播，锚定第一句 EPUB 正文。
- 英/美 token 等价 + 略降匹配阈值。
- 仍对不上的句子 **插值补时间轴**（`interpolated: true`，界面半透明，confidence≈0.35）。

## 3. MP3 必须是 `samples/` 里的真实文件

- **禁止** `ln -s ~/Downloads/... samples/hp01/chapter02.mp3`（服务端 404）。
- `pipeline.sh` 会检测外链 symlink 并 `cp` 进 `samples/`。
- 推荐：`./scripts/import_downloads.sh` 一次性迁入。

## 4. 章节 1 vs 2+ 对齐起点

- **第 1 章**：音频可能有全书前言，用 `Mr. and Mrs. Dursley` 锚定正文。
- **第 2 章起**：用 **该章 EPUB 第一句** 在 Whisper 词流里定位，跳过 `CHAPTER THREE` 等片头。

## 5. Whisper 缓存

- `output/chNN_words.json`：词级转写缓存（首跑 ~5 分钟/章）。
- 只改 `align_words.py` 或 EPUB 句子时 **不必删**；换 MP3 或要重转写时再删。

## 6. 推荐新章工作流

```bash
./scripts/import_downloads.sh          # 确保 MP3/EPUB 在工作区
./scripts/pipeline.sh N                  # 提取 → 对齐 → 中文 → catalog
python3 scripts/verify_chapter.py --chapter N
```

**通过标准**（当前策略）：

- `verify_chapter.py`：merged 词数 ≥ 95% HTML 正文。
- manifest：**lines 数 = sentences 数**（允许含 interpolated；高置信句越多越好）。

## 7. 章标题 / 小节名（有声书片头）

- EPUB 章首有 `<h2>CHAPTER N</h2>` + `<h4>TITLE</h4>`，Stephen Fry 会朗读出来。
- `extract_sentences.py` 在正文前插入 **`kind: heading`** 行（如 `Chapter 9 · The Midnight Duel`）。
- 中文来自珍藏版章首段（如 `第九章 · 午夜决斗`）。
- 播放器对 `heading` 行居中加粗显示；重跑 `./scripts/pipeline.sh N` 即可更新已有章。

## 8. 历史问题章节

| 章 | 曾出问题 | 处理 |
|----|---------|------|
| 2–4 | MP3 symlink → 404 | `import_downloads.sh` + 真实文件 |
| 3 | 186/231 句 manifest | `align_words.py` 英/美等价 + 插值 |
| 4 | 67/221 句 manifest | 同上，重跑后 221/221 |
| 9 | 多句吞并 37–186s 音频块 | `align_words.py` 限制 lookahead + 25s 硬顶；重跑 `./scripts/pipeline.sh 9` |
| 1–2 | 章末缺 3/10 句 | 插值在 `nxt.start ≤ prev.end` 时失败；已加兜底，241/241、190/190 |

## 9. 批量重对齐（不改 Whisper）

对齐逻辑更新后，不必重跑 Whisper：

```bash
./scripts/realign_range.sh 1 11    # hp01 第 1–11 章
```

等价于每章 `align_words.py` + `attach_translation.py` + `build_catalog.py`。

## 10. 外网试读 / 内网全章 / 管理员登录

- 外网默认 `HARRYPUTTER_MAX_PUBLIC_CHAPTER=1`；内网 IP 前缀见 `HARRYPUTTER_FULL_ACCESS_CIDRS`。
- **管理员**：`harryputter/.env` 中 `HARRYPUTTER_ADMIN_USER` / `HARRYPUTTER_ADMIN_PASSWORD`（gitignore，勿提交）。
- 登录后 cookie `ra_session`（默认 Path=`/`，兼容 hub 与 `:8791` 直连）外网也可听全章；未登录仍试读第 1 章。
- PWA 将 token 存 `localStorage` + 可读 cookie `ra_bearer`（iOS 主屏幕备份）；启动时 `POST /api/auth/refresh` 恢复 HttpOnly cookie（供 `<audio>`）。
- 登出/登录会同时清除 `Path=/` 与旧版 `Path=/harryputter/` 的会话 cookie。
- API：`POST /api/auth/login` · `POST /api/auth/refresh` · `POST /api/auth/logout` · `GET /api/auth/me`
- Caddy：`web/` 静态直出；`samples/`、`output/`、`/api/*` 反代 `:8791`。

## 11. 中文对齐（EN 句 > ZH 句）

- 美版 EPUB 按句切分常 **多于** 珍藏版中文（例：ch04 288 vs 190，ch17 411 vs 319）。
- **全书通用**（2026-06）：`attach_translation.py` 挂译 → 相邻去重 → 无中文行与上条合并 → 每行 EN 配一句 ZH。重跑：`python3 scripts/attach_translation.py --book hp01 --chapter N`
- **难章锚点**（ch04 已做）：`build_chapter_zh_map.py` + `data/translation_fixes/hp01_ch04.json`。详见 **[TRANSLATION-ALIGNMENT.md](TRANSLATION-ALIGNMENT.md)**。

## 12. 全书 QA（`audit_book.py`）

```bash
python3 scripts/audit_book.py --book hp01
python3 scripts/audit_zh_alignment.py --book hp01   # 缺译 / 连续重复中文
python3 scripts/verify_chapter.py --book hp01 --chapter 1
BOOK=hp01 ./scripts/realign_range.sh 1 17         # 对齐变更后批量重挂
```

| 检查项 | 工具 / 标准 |
|--------|-------------|
| EPUB 未丢字 | `verify_chapter.py` merged ≥95% |
| 音频可播 | `samples/hp01/chapterNN.mp3` 真实文件；`:8791/samples/...` HTTP 200 |
| 时间轴 | `audit_book.py` 无 `end<=start`；插值句 `interpolated: true` 半透明 |
| 中文覆盖 | `audit_book.py` body 行 zh 100% |
| 中文不重复 | `audit_zh_alignment.py`：`consec_dup=0` |
| 难章 | ch05/ch11 插值比例仍高；语义错位需补 `translation_fixes` |

**插值塌缩**：极短 gap 内多句挤在同一 timestamp → `align_words.py` `_fill_range` 每句最少 0.12s。

更新本文当发现新坑时，并在 README 链到此处。
