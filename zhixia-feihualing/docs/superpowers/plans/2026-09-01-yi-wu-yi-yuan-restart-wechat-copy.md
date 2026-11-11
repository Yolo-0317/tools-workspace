# 《一舞一愿》01｜重新出发 视频号文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 12 秒《重新出发》成片撰写并保存一套可直接复制的视频号标题、正文、六个标签、首评和发布提醒。

**Architecture:** 单一 Markdown 文件承载完整发布物，按标题、发布正文、话题标签、首评和发布提醒分区。人类传播文案不增加逐字自动化测试，交付前依据设计规格逐项人工核对分享入口、收藏入口、古诗出处、平台边界和素材路径。

**Tech Stack:** Markdown、人工编辑检查、Git

## Global Constraints

- 设计真源为 `docs/superpowers/specs/2026-09-01-yi-wu-yi-yuan-restart-wechat-copy-design.md`。
- 标题固定为 `《一舞一愿》01｜重新出发`。
- 正文同时包含“送给正在重新出发的人”和“留给此刻的自己”两个入口。
- 古诗固定为“长风破浪会有时，直挂云帆济沧海”，出处为唐·李白《行路难·其一》；不得改写。
- 标签固定为 `#栀夏飞花令 #一舞一愿 #重新出发 #行路难 #国风舞蹈 #古诗词`。
- 说明固定为 `原创虚拟角色｜AI辅助制作`，发布时选择平台 AI 内容声明。
- 不含诱导转发、玄学承诺、AI 技术炫耀或与成片不符的天宫描述。
- 视频使用 `exports/yiwu-yiyuan-qiancheng-01-restart-12s-subtitled-v01.mp4`，封面使用 `exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v03.png`。

---

### Task 1: 撰写并质检视频号发布物

**Files:**
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/wechat-channels-copy.md`

**Interfaces:**
- Consumes: 已确认的文案设计、12 秒正式字幕成片和 v03 封面。
- Produces: 可直接复制的视频号标题、正文、标签、首评和发布提醒。

- [x] **Step 1: 写入标题与发布正文**

标题使用固定栏目格式。正文以“送给正在重新出发的人，也留给此刻重新整理方向的自己”建立双入口；中段承认重新开始并不轻松，同时肯定过去没有白走；随后写现代祝愿、完整古诗与出处，并以原创虚拟角色和 AI 辅助制作说明收尾。

- [x] **Step 2: 写入标签、首评与发布提醒**

标签严格使用六个固定项。首评写“重新开始不代表之前的路白走”，再自然询问观众最近在重新开始什么，不要求转发、@他人或回复固定口令。发布提醒列出正式视频、v03 封面和平台 AI 内容声明。

- [x] **Step 3: 逐项人工质检**

对照设计规格检查五个区块齐全；正文包含转送与收藏双入口；古诗和出处无误；标签恰为六个；首评不重复正文；无“快转给”“接住好运”“必定成功”等诱导或承诺；视频与封面路径存在。

- [x] **Step 4: 提交文案**

Run:

```bash
git diff --check -- zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/wechat-channels-copy.md
git add zhixia-feihualing/docs/superpowers/plans/2026-09-01-yi-wu-yi-yuan-restart-wechat-copy.md zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/wechat-channels-copy.md
git commit -m "编写一舞一愿重新出发视频号文案"
```

Expected: 格式检查无输出，提交只包含实施计划与本集视频号文案。
