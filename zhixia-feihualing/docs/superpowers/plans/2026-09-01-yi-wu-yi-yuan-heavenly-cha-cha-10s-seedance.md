# 《一舞一愿·欢喜得意》10 秒天宫恰恰 Seedance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已确认的10秒天宫恰恰设计整理为一份可直接提交给 Seedance 的角色卡单输入提示词。

**Architecture:** 单一 `prompt.md` 同时保存上传素材、生成参数、可复制正文和生成门禁。正文使用一个角色身份锚点、四个宽时间段、一条正面摄影机路径、无人声恰恰音乐和最小高风险禁止项；角色卡中的“探戈”仅作为外部文件名存在，不进入正向舞种描述。

**Tech Stack:** Markdown、Seedance 2.0 图生视频提示词、既有栀夏角色母板

## Global Constraints

- 唯一角色输入为 `assets/characters/栀夏天宫探戈角色母板-v01-Seedance上传版.jpg`。
- 视频固定为10秒、9:16、单镜头、单人、前景英雄式天宫。
- 舞种正向指令固定为专业国际拉丁单人恰恰舞，不使用探戈动作。
- 0.300秒内出现明确脚步与换重，第一秒进入主体舞句。
- 人物占画面高度约70%—75%，仙冠、双脚和鞋底完整可见。
- 原片只生成约124 BPM恰恰器乐、环境声和动作声，不生成任何可辨识人声。
- 后期朗诵、字幕与混音不得进入 Seedance 可复制正文。

---

### Task 1: 编写并验证 Seedance 提示词

**Files:**
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt.md`

**Interfaces:**
- Consumes: 已确认的天宫恰恰设计与现有角色母板固定说明。
- Produces: 一份可直接复制的 Seedance 正文和外层生成门禁。

- [ ] **Step 1: 写入外层输入和参数**

记录唯一上传图、10秒、9:16、1080p、有声、单次候选，以及后期使用已确认10秒朗诵但不让 Seedance 生成人声的边界。

- [ ] **Step 2: 写入可复制正文**

正文依次包含原创角色和视觉锚点、前景英雄式天宫、四段恰恰动作轴、单一摄影机路径、约124 BPM无人声音乐和最小禁止项。服装与鞋履使用中性视觉描述，不把“探戈”作为正向标签。

- [ ] **Step 3: 运行内容门禁**

Run:

```bash
rg -n "专业国际拉丁单人恰恰舞|0\.300秒|70%—75%|124 BPM|不得跳探戈|不得生成任何可辨识人声" episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt.md
```

Expected: 六项要求全部命中。

Run:

```bash
sed -n '/## Seedance 可复制正文/,/## 生成参数与门禁/p' episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt.md | rg -n "后期朗诵|字幕文件|assets/|角色母板-v01-Seedance上传版"
```

Expected: 无输出，退出状态为1，证明内部路径和后期说明没有污染可复制正文。

- [ ] **Step 4: 检查格式并提交**

Run: `git diff --check -- episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt.md`

Expected: 无输出，退出状态为0。

```bash
git add episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt.md
git commit -m "编写一舞一愿天宫恰恰提示词"
```
