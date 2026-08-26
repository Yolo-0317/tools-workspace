# 栀夏表情口型综合卡 GPT 生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 GPT 和栀夏身份主卡 v02 生成一张 3 列×4 行、包含 6 种克制表情与 6 种普通话基础口型的制作母板。

**Architecture:** 只上传身份主卡 v02，使用固定格位描述控制十二个胸肩近景。生成后按格位数量、身份一致性、表情区、口型区和画面洁净度验收；通过后原样归档并登记为 performance-master。

**Tech Stack:** GPT 图像生成、PNG、Markdown 设计规格、CSV 资产清单、macOS `sips`、Git。

## Global Constraints

- 唯一参考图为 `assets/characters/栀夏角色卡电影半写实-v02.png`。
- 不上传全身比例卡、场景卡、道具卡或其他参考图。
- 输出为单张 9:16、3 列×4 行、共 12 格的胸肩近景综合卡。
- 上两行固定为 6 种表情，下两行固定为 6 种口型。
- 所有格子保持同一脸、年龄、发型、发冠、服装、构图、背景和光线。
- 不生成文字、标签、编号、边框、表格线、Logo 或水印。
- 候选文件为 `assets/characters/栀夏表情口型综合卡电影半写实-v01.png`，用户验收前不得登记为 approved。

---

### Task 1: 在 GPT 中生成十二格候选图

**Files:**
- Reference: `zhixia-feihualing/assets/characters/栀夏角色卡电影半写实-v02.png`
- Candidate: GPT 返回的原始 PNG

**Interfaces:**
- Consumes: 身份主卡 v02 和固定格位提示词。
- Produces: 单张无文字 9:16 十二格候选图。

- [ ] **Step 1: 只上传身份主卡 v02**

不要附加全身比例卡、瀑布场景卡或其他角色图片。

- [ ] **Step 2: 粘贴完整生成提示词**

提示词必须逐格描述第一行至第四行的固定内容，并重复所有格子必须是同一个栀夏。

- [ ] **Step 3: 下载 GPT 原始 PNG**

不截图、不裁切、不添加文字、不二次压缩。

### Task 2: 验收候选综合卡

**Files:**
- Inspect: GPT 返回的原始 PNG
- Compare: `zhixia-feihualing/assets/characters/栀夏角色卡电影半写实-v02.png`

**Interfaces:**
- Consumes: Task 1 候选图。
- Produces: accepted 或 rejected 的明确结论。

- [ ] **Step 1: 检查版式**

Expected: 准确包含 3 列×4 行共 12 格；格位等大；无缺格、重复格、额外头像、标签和边框。

- [ ] **Step 2: 检查身份一致性**

Expected: 十二格的脸、年龄、肤色、发型、发冠、服装、头部大小和裁切一致。

- [ ] **Step 3: 检查六种表情**

Expected: 第一、二行依次为平静专注、轻微温柔微笑、安静思考、从容坚定、轻微好奇惊讶、克制担忧伤感；表演清楚但不夸张。

- [ ] **Step 4: 检查六种口型**

Expected: 第三、四行依次为闭口、轻启、啊类开口、衣诶类横展、喔类圆唇、乌类小圆唇；六格的眉眼保持完全中性。

- [ ] **Step 5: 检查嘴部结构和生成缺陷**

Expected: 唇形、牙齿、口腔与下颌真实；无嘴部过大、下巴变形、双排牙、舌头突出、纯黑口腔和卡通嘴形。

- [ ] **Step 6: 给出验收结论**

格数错误、换脸、发冠漂移、口型眉眼不一致或出现文字时均判定为 rejected。只有五类检查全部通过才判定为 accepted。

### Task 3: 验收后归档制作母板

**Files:**
- Create: `zhixia-feihualing/assets/characters/栀夏表情口型综合卡电影半写实-v01.png`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 2 判定为 accepted 的原始 PNG。
- Produces: approved 的 performance-master 资产记录。

- [ ] **Step 1: 原样保存已验收 PNG**

不得重采样、裁切、调色或添加标签。

- [ ] **Step 2: 验证格式和尺寸**

Run:

```bash
sips -g format -g pixelWidth -g pixelHeight zhixia-feihualing/assets/characters/栀夏表情口型综合卡电影半写实-v01.png
```

Expected: `format: png`，宽高为有效 9:16 竖屏尺寸。

- [ ] **Step 3: 新增唯一资产记录**

资产 ID 使用 `zhixia-expression-viseme-cinematic-semi-real-v01`，类型为 `character`，shot 为 `performance-master`，状态为 `approved`，备注说明仅用于制作和质检分镜卡。

- [ ] **Step 4: 验证资产路径和唯一性**

使用 Python 标准库 `csv` 验证该资产 ID 恰好出现一次、状态为 `approved`、图片路径存在。

- [ ] **Step 5: 只提交综合卡和资产清单**

```bash
git add zhixia-feihualing/assets/characters/栀夏表情口型综合卡电影半写实-v01.png zhixia-feihualing/assets/inventory.csv
git commit -m "资产：定稿栀夏表情口型综合卡"
```
