# 栀夏全身比例卡 v02 GPT 生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 GPT 将新版身份主卡的胸部丰满度和抹胸上缘高度同步到现有全身比例卡的正面、右侧面和背面，同时保持其余内容不变。

**Architecture:** 现有全身比例卡作为唯一编辑底图和最高优先级参考，新版身份主卡只提供胸部体态和抹胸高度。GPT 返回候选图后，分别验收三视图结构一致性、未授权漂移和衣料连续性；通过后才保存为 v02 并更新资产状态。

**Tech Stack:** GPT 图像生成、PNG、Markdown 设计规格、CSV 资产清单、macOS `sips`、Git。

## Global Constraints

- 图一为 `assets/characters/栀夏全身比例卡电影半写实-v01.png`，是唯一编辑底图。
- 图二为用户确认的新版身份主卡，只负责胸部丰满度、胸廓曲线、抹胸上缘高度和衣料贴合关系。
- 只调整胸部体态、抹胸高度及附近衣料，不修改脸、发型、发冠、腰胯、四肢、长裙、薄纱、腰带、鞋履、背景、光线或三视图版式。
- 正面、右侧面和背面必须同步，不能只修改正面。
- 候选文件为 `assets/characters/栀夏全身比例卡电影半写实-v02.png`，不得覆盖 v01。
- v02 未经用户验收不得登记为 approved，也不得修改 v01 的 approved 状态。

---

### Task 1: 在 GPT 中生成 v02 候选图

**Files:**
- Reference 1: `zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v01.png`
- Reference 2: 用户确认的新版身份主卡 PNG
- Candidate: GPT 返回的原始 PNG

**Interfaces:**
- Consumes: 两张参考图和已确认同步规格。
- Produces: 单张无文字 9:16 完整三视图候选图。

- [ ] **Step 1: 按顺序上传两张参考图**

先上传现有全身比例卡，再上传新版身份主卡。不要添加第三张参考图。

- [ ] **Step 2: 粘贴完整局部同步提示词**

提示词必须重复声明图一为唯一编辑底图，图二不得控制脸、身体比例、服装其余部分和画面版式。

- [ ] **Step 3: 下载 GPT 原始 PNG**

不截图、不裁切、不调色、不二次压缩，不覆盖仓库中的 v01。

### Task 2: 验收三视图候选图

**Files:**
- Inspect: GPT 返回的原始 PNG
- Compare: `zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v01.png`
- Compare: 用户确认的新版身份主卡 PNG

**Interfaces:**
- Consumes: Task 1 的候选图。
- Produces: accepted 或 rejected 的明确验收结论。

- [ ] **Step 1: 验收正面**

Expected: 胸部丰满度和抹胸高度与新版身份主卡一致；体积自然、左右对称、覆盖充分。

- [ ] **Step 2: 验收右侧面**

Expected: 同步相同幅度的前突与下缘弧度，具有真实重力；抹胸完整覆盖侧胸。

- [ ] **Step 3: 验收背面**

Expected: 抹胸后缘与正侧面高度连续；不生成正面胸部结构；薄纱、肩背和高马尾无穿模。

- [ ] **Step 4: 验收未授权漂移**

Expected: 三个人物的脸、发型、发冠、高度、间距、肩宽、腰胯、四肢、腿型、长裙、薄纱、腰带、鞋履、背景和光线与 v01 一致。

- [ ] **Step 5: 验收尺度和生成缺陷**

Expected: 无球形假体感、强烈上托、悬浮、挤压、明显深胸沟、侧胸、下胸、现代内衣感、薄纱消失或衣料穿模。

- [ ] **Step 6: 给出验收结论**

任何视图不同步、身份漂移、人体比例变化或服装变化都判定为 rejected，并重新基于 v01 编辑。只有五类检查全部通过才判定为 accepted。

### Task 3: 验收后归档 v02

**Files:**
- Create: `zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v02.png`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 2 判定为 accepted 的原始 PNG。
- Produces: 新的 approved 全身比例母板和可追溯的 superseded v01 记录。

- [ ] **Step 1: 原样保存已验收 PNG 到 v02 路径**

不得重采样、裁切、调色或覆盖 v01。

- [ ] **Step 2: 验证格式和尺寸**

Run:

```bash
sips -g format -g pixelWidth -g pixelHeight zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v02.png
```

Expected: `format: png`，宽高为有效 9:16 竖屏尺寸。

- [ ] **Step 3: 更新资产清单**

将 v01 全身比例卡状态改为 `superseded` 并保留原文件；新增唯一 v02 记录并标记为 `approved`。

- [ ] **Step 4: 验证资产引用**

使用 Python 标准库 `csv` 验证 v01 与 v02 各有且仅有一条记录，状态分别为 `superseded` 和 `approved`，两条图片路径均存在。

- [ ] **Step 5: 只提交 v02 与资产清单**

```bash
git add zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v02.png zhixia-feihualing/assets/inventory.csv
git commit -m "资产：定稿栀夏全身比例卡上身体态同步版"
```
