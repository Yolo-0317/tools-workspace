# 栀夏九歌祭舞 v02 高写实视频输入主卡 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute this plan inline in the current task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用日常 v04 标准身份脸与九歌 v01 固定造型，生成一张“大幅正脸＋正面全身”的高写实 Seedance 视频输入候选卡。

**Architecture:** v04 只提供身份脸和身体比例，九歌 v01 只提供妆发、冠梳、服装、配饰、纹样与袖缘结构。生成结果先保存为 v02 候选版并进行视觉与文件核验，不覆盖 v01、不修改正式上传规则。

**Tech Stack:** Codex 内置图片生成、图像视觉复核、FFmpeg 解码检查。

## Global Constraints

- 上半区约45%为正面头肩大特写，下半区约55%为同一人的正面全身。
- 图中不得出现三视图、六表情、文字、拆解、色板、签名或道具。
- 身份必须匹配日常 v04；九歌妆发服装必须匹配 v01。
- 加强自然毛孔、细绒毛、眼周结构、真实发丝和低反光织物，消除油亮数字人观感。
- 左右袖缘尾端合计严格两个，连接袖口且不拖地。
- 只创建候选图，不覆盖或废弃任何已归档资产。

---

### Task 1: 生成并核验 v02 候选图

**Files:**
- Reference: `zhixia-feihualing/assets/characters/归档/栀夏角色卡高写实CG-v04.png`
- Reference: `zhixia-feihualing/assets/characters/归档/栀夏九歌祭舞统一角色母板-v01-正式版.png`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-08-29-zhixia-jiuge-photoreal-video-input-card-design.md`
- Create: `zhixia-feihualing/assets/characters/work/栀夏九歌祭舞-v02-高写实视频输入主卡-候选版.png`

**Interfaces:**
- Consumes: v04 的唯一标准身份脸；九歌 v01 的唯一固定造型。
- Produces: 一张尚未归档、可供用户视觉确认的 v02 候选图。

- [x] **Step 1: 记录生成前失败基线**

人工复核九歌 v01：确认存在正脸占比小、多脸平均、脸型偏窄、皮肤与织物油润的问题，以此作为 v02 必须消除的基线。

- [x] **Step 2: 使用双参考生成候选图**

调用内置图片生成：图片1锁定 v04 身份，图片2锁定九歌 v01 造型；提示词固定双区布局、自然皮肤、真实发丝、低反光织物、黑漆局部光泽和严格两个袖缘尾端。

- [x] **Step 3: 检查输出并仅做单点迭代**

逐项核对身份脸、年龄、上下两个人像一致性、服装结构、两个袖缘尾端、皮肤高光、头发和织物材质。若只出现一个集中偏差，进行一次单点定向编辑；不得在同一轮同时重做脸、服装与版式。

- [x] **Step 4: 保存候选图并验证文件**

将选定输出复制到候选路径，运行：

```bash
ffmpeg -v error -i 'zhixia-feihualing/assets/characters/work/栀夏九歌祭舞-v02-高写实视频输入主卡-候选版.png' -f null -
sips -g pixelWidth -g pixelHeight 'zhixia-feihualing/assets/characters/work/栀夏九歌祭舞-v02-高写实视频输入主卡-候选版.png'
```

预期：图片完整解码，纵向构图，文件非空；视觉验收结果明确记录为通过或列出尚需修复的具体偏差。
