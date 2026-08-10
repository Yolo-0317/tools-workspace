# HarryPutter — 有声书句级同步带读

独立项目：**EPUB 原文 + MP3** → 精确到**句子**的时间轴 → 播放时高亮。

不用 Ollama。对齐靠 `faster-whisper` **词级时间戳** + 与 EPUB 句子的单调匹配。

## 素材（清理 Downloads 前先看这里）

**真源在 `harryputter/samples/`，不要依赖 `~/Downloads`。**

```bash
./scripts/import_downloads.sh   # 从 Downloads 迁入 EPUB + 17 章 MP3，写 samples/SOURCES.json
```

| 文档 | 内容 |
|------|------|
| [docs/SAMPLES.md](docs/SAMPLES.md) | 文件对照表、播放 vs pipeline 依赖 |
| [docs/PIPELINE-NOTES.md](docs/PIPELINE-NOTES.md) | 踩坑（symlink、美 EPUB/英音频、对齐） |
| [docs/PRODUCT-STRATEGY.md](docs/PRODUCT-STRATEGY.md) | **开源引流策略 · 公网试听前网络安全清单** |
| `samples/SOURCES.json` | 迁入后的 MD5 / 是否齐全 |

## 快速开始（第一章试跑）

```bash
cd harryputter
./scripts/import_downloads.sh

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

./scripts/pipeline.sh 1
./scripts/install-launchd.sh
cd ../sidestore-infra && docker compose restart caddy
```

| 环境 | URL |
|------|-----|
| 本机 | http://127.0.0.1:8791/web/ |
| 内网 | https://hub.yoloworld.site:8443/harryputter/web/ |
| 外网 | https://hub.yoloworld.site:8883/harryputter/web/（**试读第 1 章**；内网 IP 全章） |

**试读门禁**：外网默认仅第 1 章；内网 IP 白名单全章。**管理员登录**（外网全章）：右上角「登录」，`admin` 账号密码见本机 `harryputter/.env`（勿提交 git）。

`GET /api/config` · `POST /api/auth/login` · `POST /api/auth/logout`

**Caddy 静态分离**：`web/` 由 Caddy 直出磁盘；`samples/`、`output/`、`/api/*` 反代 `:8791`。

**PWA**：Safari / Chrome →「添加到主屏幕」；底部 **刷新** 清 SW 缓存。

**导入新章**：见 `.cursor/skills/harryputter-import/`（须指定书目，如 `BOOK=hp01 ./scripts/pipeline.sh 11` = 第一部第十一章）。

首次 Whisper 转写约 5 分钟/章；缓存于 `output/chNN_words.json`。

## 目录

```text
harryputter/
  samples/
    hp01/                # 第1部 MP3（chapter01…17）
    epub/en/hp01.epub    # 英文 EPUB
    epub/zh/collection.epub
  output/                # manifest + Whisper 缓存（gitignore）
  data/book01_chapters.json
  docs/SAMPLES.md
  docs/PIPELINE-NOTES.md
  scripts/
    import_downloads.sh
    verify_chapter.py
    pipeline.sh
    realign_range.sh     # 批量重对齐（不重新 Whisper）
  web/index.html
  picture/harryputter.jpeg
```

## 添加新章节

```bash
./scripts/import_downloads.sh          # 有新 MP3 时先迁入
./scripts/pipeline.sh N                # 提取 → 对齐 → 中文 → catalog → verify
python3 scripts/verify_chapter.py --book hp01 --chapter N
```

章节目录真源：`data/book01_chapters.json`（17 章 EPUB 内路径已配置）。

**通过标准**：manifest 行数 = EPUB 句子数；详见 [docs/PIPELINE-NOTES.md](docs/PIPELINE-NOTES.md)。
