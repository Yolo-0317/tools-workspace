# 《霓裳飞天》视频号发布文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为《霓裳飞天》生成一份包含标题、发布正文、标签、置顶评论和发布提醒的可直接使用的视频号文案。

**Architecture:** 在单集目录新增独立 Markdown 文案文件，沿用《回雪胡旋》的五段结构。完成后以人工事实核对和格式扫描验证诗句、系列序号、成片路径、封面路径、AI声明与禁用 emoji 要求。

**Tech Stack:** Markdown、ripgrep、Git。

## Global Constraints

- 标题采用“敦煌十六舞第四支，栀夏从莲池一步踏上太清”。
- 正文完整呈现李白《古风·其十九》四句取句。
- 互动问题征集敦煌十六舞第五支。
- 保留“原创虚拟角色｜AI辅助制作”。
- 标签固定包含栀夏飞花令、敦煌舞、飞天舞、李白、中国古典舞、古诗词。
- 视频使用 `exports/nichang-feitian-15s-subtitled-v01.mp4`。
- 封面使用 `exports/nichang-feitian-dance-cover-v01.png`。
- 文案不含 emoji，不声称复原历史舞谱。

---

### Task 1: 编写发布文案

**Files:**
- Create: `zhixia-feihualing/episodes/nichang-feitian-15s/wechat-channels-copy.md`

**Interfaces:**
- Consumes: 已确认的标题方向、四句诗、正式成片与封面路径。
- Produces: 可复制到视频号的完整文案与发布提醒。

- [ ] **Step 1: 写入五部分文案**

文件按以下顺序组织：

```text
# 《霓裳飞天》视频号发布文案
## 标题
## 发布正文
## 话题标签
## 置顶评论
## 发布提醒
```

正文开场描写石莲台、蓝橙飘带和飞天舞姿；中段说明系列第四支并完整列出四句诗；结尾以“从莲池到太清”收束，并邀请推荐第五支舞。

- [ ] **Step 2: 核对事实与格式**

```zsh
rg -n '敦煌十六舞第四支|素手把芙蓉|虚步蹑太清|霓裳曳广带|飘拂升天行|原创虚拟角色｜AI辅助制作|敦煌十六舞第五支|nichang-feitian-15s-subtitled-v01.mp4|nichang-feitian-dance-cover-v01.png' zhixia-feihualing/episodes/nichang-feitian-15s/wechat-channels-copy.md
git diff --check -- zhixia-feihualing/episodes/nichang-feitian-15s/wechat-channels-copy.md
```

Expected: 所有要求均有命中，格式检查无输出。

- [ ] **Step 3: 提交**

```zsh
git add zhixia-feihualing/episodes/nichang-feitian-15s/wechat-channels-copy.md
git commit -m "撰写霓裳飞天视频号文案"
```

- [ ] **Step 4: 交付**

回复中以一个可复制写作块展示标题、正文、标签和置顶评论，并提供项目文件链接。
