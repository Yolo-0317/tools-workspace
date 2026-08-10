# HarryPutter · 周六发文草稿（2026-06-14）

> 账号：**牛马也智能** · 槽位建议：`workspace` 技术分享 / 或手动 `temp`  
> 定位：不卖听书，分享「EPUB + MP3 → 句级同步带读 PWA」方案（见 `PRODUCT-STRATEGY.md`）

---

## 一、项目现状（写稿用摘要）

| 项 | 状态 |
|----|------|
| **项目名** | HarryPutter（原 readalong，2026-06-08 重命名） |
| **一句话** | 正版 EPUB 原文 + 有声书 MP3 → Whisper 词级时间轴 → 与 EPUB 句子单调对齐 → 浏览器/PWA 句级高亮跟读 |
| **hp01 魔法石** | 17/17 章就绪 · 2392 句 · 约 8.4h 音频 |
| **hp02 密室** | 18/18 章就绪 · 2482 句 · 约 9.7h 音频 |
| **合计** | 35 章 · 4874 句 · 约 18.1h |
| **技术栈** | Python（faster-whisper、对齐脚本）+ 静态 PWA + FastAPI（`:8791`）+ Caddy 反代 |
| **部署** | launchd 本机常驻；Hub `https://hub.yoloworld.site:8883/harryputter/web/` |
| **公网策略** | 外网试读 **仅第 1 章**；全章需内网或 admin 登录；**MP3/EPUB 不进公开仓库**（BYO 素材） |
| **推广节奏** | 代码与文档就绪；公网试读推广前须过 `PRODUCT-STRATEGY.md` §4 安全清单 |

### 读者能得到什么

- **试读**：外网打开 PWA，听/读第 1 章，看句级高亮与中英对照是否对齐。
- **自建**：clone 工作区 `harryputter/` 子目录逻辑，自备 EPUB+MP3，`./scripts/pipeline.sh N` 本地生成。
- **得不到**：不会在公众号/公网分发完整有声书文件；不做「关注换全本」运维。

### 核心难点（可写进正文，显得有料）

1. 文本没少在 EPUB，常丢在 **音频↔句子对齐**（美版 EPUB + 英版 Stephen Fry 朗读）。
2. 英/美拼写差异、章首 `CHAPTER N` 口播需跳过，对不上的句子 **插值补时间轴**（界面半透明标记）。
3. 中文不是机翻全书：程序对齐 EN↔音频，Agent 维护 `translation_fixes` / `line_splits`。
4. 首章 Whisper 缓存约 5 分钟/章，之后改对齐逻辑不必重跑。

---

## 二、公众号草稿（可直接粘贴后台）

### 标题（三选一）

1. **有声书能精确到「句」吗？我做了一个哈利波特跟读 Demo**（推荐）
2. EPUB 加 MP3，怎样做成句级高亮？哈利波特带读实验
3. 下班搞 side project：把魔法石做成 PWA 跟读器

### 摘要（≤120 字）

```text
工具工作区里的 HarryPutter：EPUB 原文 + MP3，Whisper 词级时间轴对齐到每一句，浏览器句级高亮跟读。魔法石 17 章、密室 18 章已跑通 pipeline；外网试读第 1 章，素材须自备。
```

### 正文

```markdown
周末写一篇 side project 复盘，和 A 股无关，但和「工具工作区」里另一块能力有关：给孩子（也给自己）做英文跟读。

> 它解决什么问题

手里有正版 EPUB 和 Stephen Fry 版有声书 MP3，播放器只能「拖进度条」，看不到**当前读到哪一句**。想做的是：**音频走到哪，屏幕上就亮哪一句英文**，下面一行中文对照，点词能查词典——手机上还能「添加到主屏幕」当 PWA 用。

> 方案一句话

**不用大模型对全文**，也**不用手工打轴**。流水线是：

EPUB 抽句子 → faster-whisper 转写 MP3 得词级时间戳 → 程序把词流单调匹配到 EPUB 每一句 → 生成 manifest → 静态页按播放时间高亮。

项目名叫 **HarryPutter**（哈利波特带读），在个人 monorepo 的 `harryputter/` 目录里。

> 现在做到哪了

| 书目 | 进度 | 规模（约） |
|------|------|------------|
| 《魔法石》hp01 | 17/17 章 | 2392 句 · 8.4h 音频 |
| 《密室》hp02 | 18/18 章 | 2482 句 · 9.7h 音频 |

每一章过 `verify_chapter.py`：manifest 行数要对上 EPUB 句子数；对不齐的会标成插值句（界面半透明），方便人工回头修。

> 踩过的坑（省你两小时）

1. **少句往往不是 EPUB 少了**，是对齐锚点错了——美版 EPUB 用 mail/post、airplane/aeroplane，和英版朗读不一致。
2. **MP3 必须拷进工作区 `samples/`**，不能只 symlink 到 Downloads，否则线上 404。
3. **第 1 章和第 2 章起对齐起点不同**：第一章可能有全书前言，后面各章要从该章 EPUB 第一句锚定。
4. **中文对照**靠 `translation_fixes` 人工修，不是全书机翻；程序负责英文和音频严丝合缝。

细节我写在仓库 `docs/PIPELINE-NOTES.md`，以后加章按 Skill 走 `BOOK=hp01 ./scripts/pipeline.sh N` 即可。

> 你怎么试

**外网试读（仅第 1 章）**：

https://hub.yoloworld.site:8883/harryputter/web/

Safari 或 Chrome 打开，建议「添加到主屏幕」。默认书目可在页内切换；公网门禁下外网只能听第一章，用来验证对齐效果，不是发资源站。

**自己跑全本（BYO 素材）**：

```bash
cd harryputter
./scripts/import_downloads.sh    # 把你的 EPUB/MP3 迁入 samples/
./scripts/pipeline.sh 1          # 首章约 5 分钟 Whisper
# 本机 http://127.0.0.1:8791/web/
```

仓库**不含** MP3/EPUB 版权文件，须自备正版素材；代码、播放器、脚本可随工具工作区一起看。

> 为什么不在公号里发全本

这是**技术分享**，不是卖听书。公网托管完整 HP 有声书既踩版权，也扛不住带宽。更合理的路径是：试读证明对齐靠谱 → 读者本地 pipeline 自建。

推广前我还在过一遍 Hub 安全清单（限流、试读门禁、admin 别用弱口令），清单在 `docs/PRODUCT-STRATEGY.md`——**试读链接会长期有效，但不会把全章 MP3 挂公网。**

> 和 english-buddy 的关系

同在工作区里：`english-buddy` 面向少儿 ORT 教材带读；HarryPutter 面向「已有 EPUB+有声书」的句级同步。技术同源（Whisper、时间轴、PWA），场景不同。

---

如果你也手上有 EPUB+MP3，想复现句级带读，试读链接在上面；pipeline 问题可以留言，我不做一对一部署辅导，但文档和 Issues 欢迎讨论。

个人观点 / 技术实验，与投资建议无关。
```

### 文末话题（原创通过后加，≤5 个）

```text
#英语学习 #哈利波特 #有声书 #PWA #开源工具
```

（若后台分类可选：**科技** 或 **教育**）

### 封面建议

- 用 `harryputter/picture/harryputter.jpeg` 或工作区技术分享封面 `stock-ai/assets/wechat_mp/` 里偏工具感竖图
- 槽位：手动推 `workspace` 或 `temp`，**不要占** 交易日 sector/dragons/news 定时槽

---

## 三、发布前 checklist

- [ ] 外网用手机 4G（非家里 WiFi）打开试读，确认 **仅能播放第 1 章**
- [ ] 正文不写 admin 密码、不写内网全章入口
- [ ] 素材版权表述：BYO、试读 Demo、不托管全本 MP3
- [ ] 周六为 **weekend_skip** 自动批次，须 **手动发表**（非 18:20 定时稿）
- [ ] 可选：关注自动回复贴 `PRODUCT-STRATEGY.md` § 回复模板（补 Git 地址若已公开）

### 关注自动回复（可选）

```text
【HarryPutter 句级带读 · 试读】

试读（第 1 章）：https://hub.yoloworld.site:8883/harryputter/web/
（建议添加到主屏幕）

说明：个人技术 Demo，仓库不含 MP3/EPUB，须自备正版素材。
README：工具工作区 harryputter/ 目录

不做一对一部署辅导；文档见 PIPELINE-NOTES.md
```

---

## 四、周六推送命令（若要进草稿箱）

```bash
cd stock-ai
# 若已做 workspace 静态稿入口，可：
# uv run python -m scripts.tools.wechat_mp_draft --kind workspace --dry-run

# 或复制本文 §二 正文，在 mp 后台手动新建图文
```

---

## 修订

| 日期 | 说明 |
|------|------|
| 2026-06-10 | 初稿：hp01+hp02 全书统计、周六发文正文与 checklist |
