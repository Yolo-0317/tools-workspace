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

## 7. 历史问题章节

| 章 | 曾出问题 | 处理 |
|----|---------|------|
| 2–4 | MP3 symlink → 404 | `import_downloads.sh` + 真实文件 |
| 3 | 186/231 句 manifest | `align_words.py` 英/美等价 + 插值 |
| 4 | 67/221 句 manifest | 同上，重跑后 221/221 |
| 1–2 | 章末缺 3/10 句 | 插值在 `nxt.start ≤ prev.end` 时失败；已加兜底，241/241、190/190 |

更新本文当发现新坑时，并在 README 链到此处。
