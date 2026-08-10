# 素材存放（防 Downloads 误删）

**真源目录：`harryputter/samples/`**（已 gitignore，只在本机）。清理 `~/Downloads` 前请先跑：

```bash
./scripts/import_downloads.sh
```

## 目录规划（七本书 · 按「部」）

**按书分目录**（`hp01`…`hp07`），避免章节号冲突：

```text
harryputter/samples/
  hp01/                    # 魔法石 · 17 章
    chapter01.mp3 … chapter17.mp3
  hp02/                    # 密室 · 18 章
    chapter01.mp3 …
  hp03/ … hp07/
  epub/
    en/hp01.epub … hp07.epub
    zh/collection.epub       # 哈利波特珍藏版七册合一
  SOURCES.json
```

Downloads 有声书常见结构：

```text
~/Downloads/Harry Potter and the Philosopher's Stone/Chapter 01 - ….mp3
~/Downloads/Harry Potter and the Chamber of Secrets/…
```

`import_downloads.sh` 现只处理 **HP1（hp01）**；加书时扩展 `BOOK=hp02` 与对应 Downloads 目录。

## 容量估算（MP3）

**HP1 实测**（17 章分章 MP3）：**≈ 203 MiB（~0.20 GB）**

| 估算方式 | 七本 MP3 合计 |
|----------|---------------|
| 按常见有声书体量比例 | **~2.7 GiB** |
| 按原著页数外推 | **~3.0 GiB** |

建议预留 **3–3.5 GiB**（与 HP1 同来源、同码率）。

另计 `output/`（Whisper 缓存 + manifest，可删重建）：七本约 **~80–100 MiB**。

EPUB 很小：英文七本各 ~1 MiB 级；中文珍藏版合一 **~3.7 MiB**。

## 从 Downloads 迁入的文件（hp01）

| 工作区路径 | 原 Downloads 路径 |
|-----------|-------------------|
| `samples/epub/en/hp01.epub` | `Harry Potter and the Sorcerer's - J.K. Rowling.epub` |
| `samples/epub/zh/collection.epub` | `哈利.波特_珍藏版_七册全_.epub` |
| `samples/hp01/chapter01.mp3` … `chapter17.mp3` | `Harry Potter and the Philosopher's Stone/Chapter NN - *.mp3` |

迁入后校验清单见 **`samples/SOURCES.json`**（MD5、字节数、17 章 MP3 是否齐全）。

## 运行时还需要什么

| 文件 | 播放时 | 跑 pipeline 时 |
|------|--------|----------------|
| `hp01/chapterNN.mp3` | **必须** | 必须 |
| `epub/en/hp01.epub` | 不需要 | **必须**（提取英文句） |
| `epub/zh/collection.epub` | 不需要 | **必须**（挂中文） |
| `output/chNN.json` | **必须**（manifest） | pipeline 产出 |

## 注意

- **不要用指向 Downloads 的符号链接** 当 `samples/hp01/chapterNN.mp3`：Python 静态服务 `:8791` 不会提供项目目录外的文件（第 2–4 章曾因此 404）。
- `import_downloads.sh` 会自动把外链 symlink 复制为真实文件，并从旧扁平布局迁移。
- PWA 图标源图在 `picture/harryputter.jpeg`（不进 samples）。
