# 《晓出净慈寺送林子方》视频号文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一份可直接复制到视频号后台的《晓出净慈寺送林子方》舞蹈诗境发布文案。

**Architecture:** 单一 Markdown 文件保存标题、正文、话题标签、置顶评论和发布提醒。正文按照“动作钩子—舞蹈与诗境关系—完整全诗—原创声明与互动”组织；使用只读文本检查确认诗句、关键词、素材路径和无表情符号边界。

**Tech Stack:** Markdown、ripgrep、Git

## Global Constraints

- 标题固定为“栀夏一抬袖，西湖六月便开满了荷花”。
- 正文完整引用杨万里《晓出净慈寺送林子方》四句，不改字。
- 正文自然包含“AI美女舞蹈”和“中国古典舞”，但不把账号写成工具教学号。
- 明确栀夏与阿砚是原创虚拟角色，并保留“AI辅助制作”。
- 标签固定为 `#栀夏飞花令 #杨万里 #晓出净慈寺送林子方 #AI美女舞蹈 #中国古典舞 #古诗词`。
- 不使用表情符号、最高级、真人舞者、专业资历、Seedance、提示词或参数表述。
- 发布提醒指向 `exports/jingci-lotus-15s-subtitled-v01.mp4` 和 `exports/jingci-lotus-dance-cover-v01.png`。

---

### Task 1: 编写并验证视频号发布文案

**Files:**
- Create: `episodes/jingci-lotus-15s/wechat-channels-copy.md`

**Interfaces:**
- Consumes: 已确认的舞蹈诗境内容、正式成片路径、封面路径和文案设计规格。
- Produces: 可直接复制的视频号标题、正文、标签、置顶评论和发布提醒。

- [x] **Step 1: 编写标题与正文**

正文用袖风推动水纹、荷叶舒展和红荷迎日开放建立画面钩子；第二段说明栀夏用中国古典舞的低位扫展、转身与舒展进入诗境；随后独立引用四句全诗，并以原创虚拟角色声明和下一首互动收束。

- [x] **Step 2: 编写话题、置顶评论与发布提醒**

使用六个固定标签；置顶评论邀请观众回复诗名或诗句；发布提醒指定正式字幕成片、正式舞蹈封面和平台 AI 内容声明。

- [x] **Step 3: 验证内容边界**

Run: `rg -n "毕竟西湖六月中|风光不与四时同|接天莲叶无穷碧|映日荷花别样红|AI美女舞蹈|中国古典舞|原创虚拟角色|AI辅助制作|jingci-lotus-15s-subtitled-v01.mp4|jingci-lotus-dance-cover-v01.png" episodes/jingci-lotus-15s/wechat-channels-copy.md`

Expected: 所有要求均命中。

Run: `rg -n "😀|🎬|✨|Seedance|提示词|全网第一|最美|真人舞者|专业舞蹈演员" episodes/jingci-lotus-15s/wechat-channels-copy.md`

Expected: 无输出，退出码为 1。

- [x] **Step 4: 检查差异并提交**

Run: `git diff --check`

只提交实施计划和 `wechat-channels-copy.md`，不提交其他未关联修改。
