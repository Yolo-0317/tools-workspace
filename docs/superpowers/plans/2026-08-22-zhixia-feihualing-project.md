# 栀夏飞花令项目建档实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `tools-workspace` 中建立《栀夏飞花令》抖音原创国风动画IP的唯一资料源，固化现有设定、EP01进度、生产流程和账号运营方案。

**Architecture:** 项目作为仓库根目录下的独立内容工程存在，不依赖 `stock-ai` 的公众号素材目录。角色、世界观、视觉、剧集、资产和运营分别建档，`README.md` 只维护当前状态和导航。

**Tech Stack:** Markdown、CSV、本地媒体文件、FFmpeg、ChatGPT网页图像生成、视频生成平台。

## Global Constraints

- 项目路径固定为 `zhixia-feihualing/`。
- 9:16竖屏，原创国风二维动画IP，AI仅作为辅助生产工具。
- 栀夏最终设定采用18岁、高马尾、青砚常服；早期12岁、双丫髻设定作废。
- 阿砚固定为宣纸白墨灵、暖琥珀眼、朱砂额印、两只笔锋耳、严格四肢、唯一墨尾。
- 未经当次确认，不执行产生费用的视频生成。
- 不改动已有公众号项目和用户未提交素材。

---

### Task 1: 建立项目入口和注册信息

**Files:**
- Create: `zhixia-feihualing/README.md`
- Modify: `project-registry/projects.json`

- [x] **Step 1:** 建立项目入口，写明定位、当前进度、目录导航和下一步。
- [x] **Step 2:** 在项目注册表登记路径、生命周期、入口文档和别名。
- [x] **Step 3:** 用 `python3 scripts/workspace_preflight.py --project zhixia-feihualing --risk normal` 验证路由。

### Task 2: 固化IP母版

**Files:**
- Create: `zhixia-feihualing/docs/account-plan.md`
- Create: `zhixia-feihualing/docs/world-bible.md`
- Create: `zhixia-feihualing/docs/character-bible.md`
- Create: `zhixia-feihualing/docs/visual-bible.md`

- [x] **Step 1:** 记录抖音账号定位、栏目结构、首月节奏与判断指标。
- [x] **Step 2:** 记录飞花令机制、世界观边界和主线叙事原则。
- [x] **Step 3:** 将最终角色设定与废弃设定分开记录。
- [x] **Step 4:** 固化画风、色彩、光线、场景和禁止项。

### Task 3: 固化EP01和生产流程

**Files:**
- Create: `zhixia-feihualing/docs/production-workflow.md`
- Create: `zhixia-feihualing/episodes/ep01/script.md`
- Create: `zhixia-feihualing/episodes/ep01/storyboard.md`
- Create: `zhixia-feihualing/episodes/ep01/prompts/README.md`
- Create: `zhixia-feihualing/episodes/ep01/review-notes.md`

- [x] **Step 1:** 将01A至05C整理为可检查的镜头表。
- [x] **Step 2:** 明确当前完成度和下一镜05A。
- [x] **Step 3:** 将超长提示词重构为固定母版、镜头变量和关键禁止项三层。
- [x] **Step 4:** 记录付费生成、连续性检查和本地后期门禁。

### Task 4: 建立资产与运营台账

**Files:**
- Create: `zhixia-feihualing/assets/README.md`
- Create: `zhixia-feihualing/assets/inventory.csv`
- Create: `zhixia-feihualing/exports/README.md`
- Create: `zhixia-feihualing/operations/publishing-calendar.md`
- Create: `zhixia-feihualing/operations/video-copy.md`
- Create: `zhixia-feihualing/operations/performance-data.csv`
- Create: `zhixia-feihualing/docs/source-notes/chatgpt-conversation-summary-2026-08-22.md`

- [x] **Step 1:** 建立角色、场景、生成图、视频、音频和音乐目录说明。
- [x] **Step 2:** 建立首发内容日历、发布文案母版和表现数据表。
- [x] **Step 3:** 保存原始ChatGPT对话链接、已提炼事实和设定冲突处理结果。
- [x] **Step 4:** 校验JSON、CSV、Markdown链接和新增文件清单。
