# 《早发白帝城》公众号诗境贴图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出一份可直接用于「栀夏未完成」公众号四图贴图的《早发白帝城》完整配文，并在底部承接唯一一条对应视频。

**Architecture:** 四张场景卡按编号组成同一条 `newspic` 的滑动图片列表，单篇成稿只保存一个可直接传给 `--content` 的连续说明文本。图片保持原样，说明承担诗境旁白、诗句揭示、视频入口说明与 AI 辅助生成披露，不在图片之间插入正文，也不修改公众号工程或通用贴图 Skill。

**Tech Stack:** Markdown、现有 PNG 场景卡、微信公众号贴图与视频号卡片。

## Global Constraints

- 只使用 `episodes/baidi/assets/scene-cards/` 中现有四张纯画面场景卡。
- 不加字、不裁图、不重新生成图片，不覆盖任何原始资产。
- 图片严格按 `01`、`02`、`03`、`04` 顺序使用。
- 标题使用 `山还没数完，船已经过了万重山`。
- 统一说明控制在 400～500 字，不逐字复述视频对白。
- 说明中不出现逐图标题、图片文件名或编辑指令。
- 完整诗句与出处只在第四图对应段落出现一次。
- 底部只承接一条对应视频，不添加第二个外链、关注要求或互动任务。
- 末尾包含 `原创虚构动画，画面由 AI 辅助生成。`
- 不虚构真人经历、实地到访、历史时间或诗人心理。

---

### Task 1: 完成白帝城公众号成稿

**Files:**
- Create: `zhixia-feihualing/episodes/baidi/wechat-poetry-copy.txt`
- Read: `zhixia-feihualing/episodes/baidi/assets/scene-cards/README.md`
- Read: `zhixia-feihualing/docs/superpowers/specs/2026-08-26-baidi-wechat-poetry-video-post-design.md`

**Interfaces:**
- Consumes: 四张场景卡的固定文件名、顺序和设计稿中的核心观察。
- Produces: 一份可直接作为 `newspic` 统一说明使用的纯文本成稿；标题和四张图片路径作为发布参数单独提供。

- [ ] **Step 1: 建立贴图发布参数**

发布时使用以下固定参数，不把参数文字写进说明文件：

```text
title=山还没数完，船已经过了万重山
images=01-opening-character-close.png,02-narrow-canyon-wide.png,03-speed-through-canyon.png,04-open-river-ending.png
content=episodes/baidi/wechat-poetry-copy.txt
```

- [ ] **Step 2: 写四段诗境旁白**

在一个连续说明字段中，用风和江水建立船速，再写高峡、狭窄水路与阿砚数不完山峰的动作；人物回望后写出：

```text
两岸猿声啼不住，轻舟已过万重山。
唐·李白《早发白帝城》
```

诗句后用“以前只读到船快，现在读到那些山回头时已经在身后”的观察收束，但不把它写成诗句的唯一解释。

- [ ] **Step 3: 做内容核对**

运行：

```bash
rg -n '两岸猿声啼不住|轻舟已过万重山|唐·李白《早发白帝城》|完整诗境|原创虚构动画，画面由 AI 辅助生成' zhixia-feihualing/episodes/baidi/wechat-poetry-copy.txt
```

预期：说明中不包含图片文件名；诗句、出处、视频入口说明和 AI 披露各出现一次。

- [ ] **Step 4: 核对正文长度与边界**

直接统计 `wechat-poetry-copy.txt` 去除首尾空白后的字符数。预期为 400～500 字；没有“实地”“亲眼”“李白当时想”等虚构亲历或心理断言；视频入口之后没有第二个 CTA。

- [ ] **Step 5: 检查文件与提交**

运行：

```bash
git diff --check -- zhixia-feihualing/episodes/baidi/wechat-poetry-copy.txt
```

预期：退出码为 0。

只提交本次成稿：

```bash
git add -- zhixia-feihualing/episodes/baidi/wechat-poetry-copy.txt
git commit -m "文案：完成白帝城公众号诗境贴图"
```

完成后把成稿以可复制文本交付给用户，并提醒发布时将对应视频号卡片插在指定位置。
