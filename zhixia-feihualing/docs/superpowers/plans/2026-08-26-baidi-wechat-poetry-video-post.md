# 《早发白帝城》公众号诗境贴图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出一份可直接用于「栀夏未完成」公众号四图贴图的《早发白帝城》完整配文，并在底部承接唯一一条对应视频。

**Architecture:** 单篇成稿保存在《早发白帝城》剧集目录，按现有四张场景卡的编号顺序组织文字。图片保持原样，正文只承担诗境旁白、诗句揭示、视频入口说明与 AI 辅助生成披露，不修改公众号工程或通用贴图 Skill。

**Tech Stack:** Markdown、现有 PNG 场景卡、微信公众号贴图与视频号卡片。

## Global Constraints

- 只使用 `episodes/baidi/assets/scene-cards/` 中现有四张纯画面场景卡。
- 不加字、不裁图、不重新生成图片，不覆盖任何原始资产。
- 图片严格按 `01`、`02`、`03`、`04` 顺序使用。
- 标题使用 `山还没数完，船已经过了万重山`。
- 正文控制在 280～330 个中文字符左右，不逐字复述视频对白。
- 完整诗句与出处只在第四图对应段落出现一次。
- 底部只承接一条对应视频，不添加第二个外链、关注要求或互动任务。
- 末尾包含 `原创虚构动画，画面由 AI 辅助生成。`
- 不虚构真人经历、实地到访、历史时间或诗人心理。

---

### Task 1: 完成白帝城公众号成稿

**Files:**
- Create: `zhixia-feihualing/episodes/baidi/wechat-poetry-post.md`
- Read: `zhixia-feihualing/episodes/baidi/assets/scene-cards/README.md`
- Read: `zhixia-feihualing/docs/superpowers/specs/2026-08-26-baidi-wechat-poetry-video-post-design.md`

**Interfaces:**
- Consumes: 四张场景卡的固定文件名、顺序和设计稿中的核心观察。
- Produces: 一份由标题、四段配图文字、诗句、视频卡片插入说明和 AI 披露组成的 Markdown 成稿。

- [ ] **Step 1: 建立成稿骨架**

创建 `episodes/baidi/wechat-poetry-post.md`，依次写入以下固定结构：

```markdown
# 山还没数完，船已经过了万重山

## 图 1
对应图片：`assets/scene-cards/01-opening-character-close.png`

## 图 2
对应图片：`assets/scene-cards/02-narrow-canyon-wide.png`

## 图 3
对应图片：`assets/scene-cards/03-speed-through-canyon.png`

## 图 4
对应图片：`assets/scene-cards/04-open-river-ending.png`

## 视频入口

风声、猿声和轻舟穿峡的完整诗境，放在下面这条视频里。

发布时在本行之后插入《早发白帝城》对应的视频号卡片。

原创虚构动画，画面由 AI 辅助生成。
```

- [ ] **Step 2: 写四段诗境旁白**

第一段用风和江水建立船速；第二段写高峡与狭窄水路；第三段用阿砚数不完山峰的动作完成角色锚点；第四段在人物回望后写出：

```text
两岸猿声啼不住，轻舟已过万重山。
唐·李白《早发白帝城》
```

诗句后用“以前只读到船快，现在读到那些山回头时已经在身后”的观察收束，但不把它写成诗句的唯一解释。

- [ ] **Step 3: 做内容核对**

运行：

```bash
rg -n '01-opening|02-narrow|03-speed|04-open|两岸猿声啼不住|轻舟已过万重山|唐·李白《早发白帝城》|视频号卡片|原创虚构动画，画面由 AI 辅助生成' zhixia-feihualing/episodes/baidi/wechat-poetry-post.md
```

预期：四个图片文件名按编号递增；诗句、出处、视频卡片插入说明和 AI 披露各出现一次。

- [ ] **Step 4: 核对正文长度与边界**

人工只统计公众号读者可见正文，不把 Markdown 标题、图片文件名和发布说明计入字数。预期正文约 280～330 个中文字符；没有“实地”“亲眼”“李白当时想”等虚构亲历或心理断言；视频入口之后没有第二个 CTA。

- [ ] **Step 5: 检查文件与提交**

运行：

```bash
git diff --check -- zhixia-feihualing/episodes/baidi/wechat-poetry-post.md
```

预期：退出码为 0。

只提交本次成稿：

```bash
git add -- zhixia-feihualing/episodes/baidi/wechat-poetry-post.md
git commit -m "文案：完成白帝城公众号诗境贴图"
```

完成后把成稿以可复制文本交付给用户，并提醒发布时将对应视频号卡片插在指定位置。
