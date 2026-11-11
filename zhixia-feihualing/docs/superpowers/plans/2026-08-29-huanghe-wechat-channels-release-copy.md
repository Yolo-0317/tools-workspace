# 《黄河》视频号发布文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一套可直接复制到视频号使用的《黄河》标题、正文、六个话题标签、置顶评论与发布提醒。

**Architecture:** 单一 Markdown 文件承载完整发布成稿，严格复用已确认的系列模板和本集设计稿。该交付物是人工文案，不增加自动化测试；通过逐项人工核对标题、关键词、诗句、原创声明、标签数量和合规边界完成验收。

**Tech Stack:** Markdown、人工文案校对、Git。

## Global Constraints

- 标题固定为“栀夏这一跃，接住了从天上来的黄河”。
- 正文自然使用“AI美女舞蹈”和“中国古典舞”各一次。
- 引用“黄河之水天上来，奔流到海不复回。”并保留阿砚对白。
- 明示“原创虚构角色｜AI辅助制作”。
- 标签固定为六个：`#栀夏飞花令`、`#李白`、`#将进酒`、`#AI美女舞蹈`、`#中国古典舞`、`#古诗词`。
- 不把栀夏称为真人或专业舞者，不写 Seedance、提示词、镜头编号、最高级或擦边表达。
- 发布提醒要求选择视频号 AI 内容声明。

---

### Task 1: 编写并验收视频号发布成稿

**Files:**
- Create: `zhixia-feihualing/episodes/huanghe/wechat-channels-copy.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-29-huanghe-wechat-channels-release-copy-design.md`、本集正式视频和封面已确认的画面事实。
- Produces: 可直接复制使用的标题、发布正文、话题标签、置顶评论和发布提醒。

- [ ] **Step 1: 写标题与正文**

按以下完整内容写入，不增加制作工具说明：

```markdown
## 标题

栀夏这一跃，接住了从天上来的黄河

## 发布正文

黄河从云间奔来，栀夏踩着浪声腾身一跃，长袖带起一道迎光的水弧。

这一次，AI美女舞蹈不只是在山河前起舞。栀夏用中国古典舞的腾跃、旋转与身韵，跳进李白《将进酒》的开篇：

“黄河之水天上来，奔流到海不复回。”

阿砚：“哇，黄河真从天上冲下来啦！”

下一次，你想看栀夏跳进哪一句诗？

原创虚构角色｜AI辅助制作
```

- [ ] **Step 2: 写标签、置顶评论与发布提醒**

标签必须恰好为：

```text
#栀夏飞花令 #李白 #将进酒 #AI美女舞蹈 #中国古典舞 #古诗词
```

置顶评论要求观众直接留下最想看栀夏演绎的一句诗；发布提醒要求勾选视频号 AI 内容声明，并禁止追加真人舞者或专业资历描述。

- [ ] **Step 3: 人工验收文案**

逐项确认：标题与确认稿一致；两项搜索关键词各出现一次；诗句和阿砚对白准确；原创虚构角色声明存在；标签恰好六个；不存在 Seedance、提示词、镜头代码、真人舞者、专业资历、最高级或擦边表达。

- [ ] **Step 4: 检查格式并提交**

Run: `git diff --check`

Expected: 无输出且退出码为 0。

```bash
git add zhixia-feihualing/docs/superpowers/plans/2026-08-29-huanghe-wechat-channels-release-copy.md \
  zhixia-feihualing/episodes/huanghe/wechat-channels-copy.md
git commit -m "编写黄河视频号发布文案"
```
