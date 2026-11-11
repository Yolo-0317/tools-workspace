# 栀夏九歌祭舞整合式视频母板 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一张保留九歌 v01 全部造型信息、以单张正面大脸锁定身份、并降低油润 CG 感的 v03 视频母板候选图。

**Architecture:** 以 v01 正式母板作为唯一编辑底板，以日常 v04 只提供面部身份，以此前 v02 候选图只提供写实皮肤和低反光材质方向。先完成一次整卡编辑，再只允许一次针对单一问题的局部修正，最终非破坏性保存到工作区。

**Tech Stack:** Codex 内置图片生成工具、图片视觉检查、FFmpeg、sips。

## Global Constraints

- 不覆盖 `栀夏九歌祭舞统一角色母板-v01-正式版.png`。
- 删除右上六宫格表情，替换为唯一正面平视中性大脸。
- 保留三视图、服装拆解、发饰结构、袖缘结构、材质特写、色板和底部信息区。
- 所有可见面孔统一为日常 v04 的同一位栀夏，但使用九歌妆发服装。
- 固定严格两个袖缘尾端；不得混入敦煌造型或新增道具。
- 新图只作为候选版，不自动更新正式上传规则。

---

### Task 1: 建立可比较的输入基线

**Files:**
- Read: `assets/characters/归档/栀夏九歌祭舞统一角色母板-v01-正式版.png`
- Read: `assets/characters/归档/栀夏角色卡高写实CG-v04.png`
- Read: `assets/characters/work/栀夏九歌祭舞-v02-高写实视频输入主卡-候选版.png`

**Interfaces:**
- Consumes: v01 的信息架构与服化道、v04 的面部身份、v02 的写实材质方向。
- Produces: 三张角色明确、互不混用的编辑输入。

- [x] **Step 1: 视觉核对三张输入图**

确认 v01 是编辑底板、v04 不提供服装、v02 不提供版式。

- [x] **Step 2: 记录失败基线**

失败基线为：v01 多表情且偏 CG；v02 缺少三视图与拆解信息。

### Task 2: 生成整合式 v03 候选图

**Files:**
- Create: `assets/characters/work/栀夏九歌祭舞-v03-整合式高写实视频母板-候选版.png`

**Interfaces:**
- Consumes: Task 1 的三张输入与全局约束。
- Produces: 一张完整档案卡式候选图。

- [x] **Step 1: 执行一次高保真整卡编辑**

用内置图片编辑工具删除右上六宫格，换成唯一大脸；锁定其余版式与信息模块，并统一所有可见脸。

- [x] **Step 2: 对照验收清单检查输出**

逐项检查大脸、三视图、服装拆解、发饰、袖型、材质、色板、严格两个袖缘尾端和非敦煌化。

- [x] **Step 3: 必要时只做一次单点修正**

只修正最影响视频稳定性的单一偏差；不得同时重构版式和人物。

### Task 3: 保存与文件验证

**Files:**
- Verify: `assets/characters/work/栀夏九歌祭舞-v03-整合式高写实视频母板-候选版.png`

**Interfaces:**
- Consumes: Task 2 通过视觉核对的最终候选图。
- Produces: 可正常解码、尺寸明确、可供用户确认的视频输入候选资产。

- [x] **Step 1: 非破坏性复制到工作区**

仅创建 v03 候选文件，不覆盖 v01、v02 或归档文件。

- [x] **Step 2: 验证文件完整性**

运行：

```bash
test -s 'assets/characters/work/栀夏九歌祭舞-v03-整合式高写实视频母板-候选版.png'
ffmpeg -v error -i 'assets/characters/work/栀夏九歌祭舞-v03-整合式高写实视频母板-候选版.png' -f null -
sips -g pixelWidth -g pixelHeight 'assets/characters/work/栀夏九歌祭舞-v03-整合式高写实视频母板-候选版.png'
```

预期：文件非空、FFmpeg 无错误、sips 返回正整数尺寸。

- [x] **Step 3: 汇报候选状态**

展示 v03 并明确：它尚未归档，也尚未通过实际视频一致性测试。

### Task 4: 修正未通过的身份脸

**Files:**
- Modify: `assets/characters/work/栀夏九歌祭舞-v03-整合式高写实视频母板-候选版.png`
- Read: `assets/characters/归档/栀夏角色卡高写实CG-v04.png`
- Create: `assets/characters/work/栀夏九歌祭舞-v03-整合式高写实视频母板-身份对齐候选版.png`

**Interfaces:**
- Consumes: 首轮 v03 的完整档案结构与 v04 的标准身份脸。
- Produces: 只修正可见面孔、其余信息结构保持不变的身份对齐候选图。

- [x] **Step 1: 执行单变量身份修订**

只替换右上大脸以及三视图、发饰区中的可见小脸；锁定所有非面部区域。

- [x] **Step 2: 制作同尺度并排脸图**

分别裁切 v04 标准脸与修订后大脸，统一为相同画布尺寸并横向拼接。

- [x] **Step 3: 逐项核对身份**

检查脸部纵横比例、下颌、眼睛大小与眼距、眉形、鼻梁鼻翼、嘴唇与 18 岁年龄感；未通过则不归档。

- [x] **Step 4: 验证候选文件**

确认 PNG 非空、FFmpeg 解码无错误、尺寸为正整数，并汇报真实验收结论。

### Task 5: 归档身份对齐正式版

**Files:**
- Create: `assets/characters/归档/栀夏九歌祭舞-v03-整合式高写实视频母板-正式版.png`
- Create: `assets/characters/栀夏九歌祭舞-v03-整合式高写实视频母板-Seedance上传版.jpg`
- Create: `assets/characters/栀夏九歌祭舞-v03-整合式高写实视频母板-Seedance固定说明.md`
- Modify: `docs/character-bible.md`
- Modify: `docs/cultural-poetry-dance-roadmap.md`
- Modify: `assets/inventory.csv`

**Interfaces:**
- Consumes: 用户确认的身份对齐候选版 v03。
- Produces: 无损正式归档、压缩上传版与一致的项目规则登记。

- [x] **Step 1: 创建正式版与上传版**

保留无损 PNG，并创建同尺寸高质量 JPEG 上传派生版。

- [x] **Step 2: 更新单一事实源**

登记 v03 为九歌新视频默认单图输入；保留 v01 作为服化道设计和历史追溯真源。

- [x] **Step 3: 标注测试边界**

记录“已通过视觉身份验收、实际 Seedance 稳定性待低成本测试”，不得写成视频已验证。

- [x] **Step 4: 完成归档验证**

检查 PNG/JPEG 可解码、尺寸与字节数正确、正式 PNG 和用户确认候选图哈希一致，并检查文档与清单格式。
