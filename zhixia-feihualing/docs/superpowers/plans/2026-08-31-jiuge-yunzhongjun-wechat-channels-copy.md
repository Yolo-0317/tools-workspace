# 《九歌·云中君》视频号文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为《栀夏·九歌祭舞》第二篇《云中君》建立可直接发布的视频号正文、话题标签、首评和发布提醒。

**Architecture:** 只新增一个篇目级 Markdown 发布文件，沿用现有 `wechat-channels-copy.md` 的标题、正文、标签、首评和提醒结构。正文承担诗意叙事，首评承担原典出处、读音说明与互动补充。

**Tech Stack:** Markdown、Git

## Global Constraints

- 标题必须为 `《栀夏·九歌祭舞》02｜云中君`。
- 栀夏是迎神、随神、送神的祭舞者，不是云中君本尊。
- 文案必须保持清冷、舒缓、含蓄，不写成仙侠故事或考据复原。
- 必须包含 `原创虚拟角色｜AI辅助制作`，并提醒发布时选择平台 AI 内容声明。
- 首评必须注明诗句出处，并注明“猋”读作 `biāo`。

---

### Task 1: 建立《云中君》视频号发布文件

**Files:**
- Create: `episodes/jiuge-yunzhongjun-15s/wechat-channels-copy.md`
- Reference: `docs/superpowers/specs/2026-08-31-jiuge-yunzhongjun-wechat-channels-copy-design.md`

**Interfaces:**
- Consumes: 已确认的系列标题格式、成片诗句和《云中君》发布定位。
- Produces: 可直接复制到视频号的标题、正文、话题标签和首评。

- [ ] **Step 1: 写入最终发布文案**

```markdown
# 《九歌·云中君》视频号发布文案

## 标题

《栀夏·九歌祭舞》02｜云中君

## 发布正文

云神既降，又远举云中。

低云掠过石台，栀夏循着云门向高处追随。一次倾身，一次腾跃，再沿云海旋身远行——相逢不过一瞬，目送却延伸到了天际。

“灵皇皇兮既降，猋远举兮云中。”

这是《栀夏·九歌祭舞》第二篇《云中君》。栀夏仍是迎神、随神、送神的祭舞者；她所追随的，是云中来去无定的神意。

如果只能留住一个瞬间，你会选云神降临，还是远举云中？

原创虚拟角色｜AI辅助制作

## 话题标签

#栀夏飞花令 #楚辞 #九歌 #云中君 #国风舞蹈 #中国古典舞

## 首评（置顶评论）

“猋”读 biāo，在这句里可理解为迅疾远去。诗句出自屈原《九歌·云中君》。这一篇没有把栀夏变成云神，而是让她以祭舞者的身份经历降临、追随与目送。你更喜欢开头穿云，还是结尾望向高天？

## 发布提醒

- 视频使用 `exports/jiuge-yunzhongjun-15s-subtitled-v02.mp4`。
- 封面使用 `exports/yunzhongjun-cover-v01.png`。
- 发布时选择视频号要求的 AI 内容声明。
```

- [ ] **Step 2: 核对必备字段**

Run:

```bash
rg -n '《栀夏·九歌祭舞》02｜云中君|灵皇皇兮既降|猋.*biāo|原创虚拟角色｜AI辅助制作|AI 内容声明' episodes/jiuge-yunzhongjun-15s/wechat-channels-copy.md
```

Expected: 五项内容全部命中，标题编号、诗句、读音、AI 标识和发布提醒均存在。

- [ ] **Step 3: 核对发布素材路径**

Run:

```bash
test -f exports/jiuge-yunzhongjun-15s-subtitled-v02.mp4 && test -f exports/yunzhongjun-cover-v01.png
```

Expected: 命令退出状态为 0。

- [ ] **Step 4: 提交发布文件**

```bash
git add episodes/jiuge-yunzhongjun-15s/wechat-channels-copy.md
git commit -m "归档云中君视频号文案"
```
