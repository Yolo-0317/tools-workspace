# 栀夏身份主卡 v02 GPT 生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 GPT 将栀夏现有身份主卡的交领常服替换为全身比例卡中的盛唐抹胸、敞开薄纱大袖衫、浅粉腰带和浅青高腰长裙上缘，同时保持身份、构图和瀑布场景不变。

**Architecture:** 用户在 GPT 中按固定顺序上传两张参考图，图一作为唯一编辑底图，图二只提供服装结构。GPT 输出候选图后先进行身份、场景和服装三类视觉验收；通过后再保存为 v02 并更新资产清单，v01 文件保留用于追溯。

**Tech Stack:** GPT 图像生成、PNG、Markdown 设计规格、CSV 资产清单、macOS `sips`、Git。

## Global Constraints

- 图一必须是 `assets/characters/栀夏角色卡电影半写实-v01.png`，负责脸、表情、发型、发冠、构图、瀑布背景和光线。
- 图二必须是 `assets/characters/栀夏全身比例卡电影半写实-v01.png`，只负责服装结构、配色和材质。
- 只替换服装，不修改身份、人物位置、镜头、背景或光线。
- 输出为单张 9:16 胸腰以上近景，不生成三视图、全身图、文字或设定版式。
- 候选文件使用 `assets/characters/栀夏角色卡电影半写实-v02.png`，不得覆盖 v01。
- v02 未经用户验收不得登记为 approved，也不得把 v01 标记为 superseded。

---

### Task 1: 在 GPT 中生成服装统一候选图

**Files:**
- Reference 1: `zhixia-feihualing/assets/characters/栀夏角色卡电影半写实-v01.png`
- Reference 2: `zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v01.png`
- Candidate: 用户从 GPT 返回的 PNG

**Interfaces:**
- Consumes: 两张已批准角色母板和已确认服装统一规格。
- Produces: 单张胸腰以上身份主卡候选图。

- [ ] **Step 1: 按顺序上传两张参考图**

先上传身份主卡，再上传全身比例卡。不要添加第三张参考图。

- [ ] **Step 2: 粘贴完整生成提示词**

提示词必须明确图一为编辑底图、图二只负责衣服，并重复“除服装外不做任何变化”。

- [ ] **Step 3: 保存 GPT 原始输出**

下载原始 PNG，不截图、不裁切、不调色、不二次压缩。此时先使用临时候选文件，不覆盖仓库中的 v01。

### Task 2: 验收候选图

**Files:**
- Inspect: GPT 返回的原始 PNG
- Compare: `zhixia-feihualing/assets/characters/栀夏角色卡电影半写实-v01.png`
- Compare: `zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v01.png`

**Interfaces:**
- Consumes: Task 1 的候选图。
- Produces: accepted 或 rejected 的明确验收结论。

- [ ] **Step 1: 检查身份一致性**

Expected: 脸型、五官、年龄、肤色、表情、眼神、发际线、高马尾、碎发和发冠与 v01 一致。

- [ ] **Step 2: 检查构图和场景一致性**

Expected: 保留相同胸腰近景、人物位置、瀑布、岩壁、植物、水雾、自然侧光、景深和低饱和调色。

- [ ] **Step 3: 检查服装一致性**

Expected: 旧交领完全消失；月白抹胸、敞开薄纱大袖衫、浅粉腰带和少量浅青高腰长裙上缘清楚可辨，并与全身比例卡一致。

- [ ] **Step 4: 检查公开视频尺度与生成缺陷**

Expected: 抹胸覆盖充分，无明显胸沟、侧胸和现代内衣感；薄纱不贴身、不湿身、不穿模；画面无文字、Logo、水印或额外人物。

- [ ] **Step 5: 给出验收结论**

任何身份或背景漂移都应判定为 rejected，并基于原图重新做局部服装替换，不在错误候选图上连续修补。只有四类检查全部通过才判定为 accepted。

### Task 3: 验收后归档 v02

**Files:**
- Create: `zhixia-feihualing/assets/characters/栀夏角色卡电影半写实-v02.png`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 2 判定为 accepted 的原始 PNG。
- Produces: 新的 approved 身份主卡和可追溯的 superseded v01 记录。

- [ ] **Step 1: 原样复制已验收 PNG 到 v02 路径**

不得重采样、裁切、调色或覆盖 v01。

- [ ] **Step 2: 验证图片格式和尺寸**

Run:

```bash
sips -g format -g pixelWidth -g pixelHeight zhixia-feihualing/assets/characters/栀夏角色卡电影半写实-v02.png
```

Expected: `format: png`，宽高为 9:16 竖屏有效尺寸。

- [ ] **Step 3: 更新资产清单**

将 `zhixia-cinematic-semi-real-v01` 的状态改为 `superseded`，保留原文件；新增唯一 v02 记录并标记为 `approved`，说明服装已与全身比例卡统一。

- [ ] **Step 4: 验证资产 ID、路径和状态**

使用 Python 标准库 `csv` 验证 v01 与 v02 各有且仅有一条记录，v01 为 `superseded`、v02 为 `approved`，两条路径均存在。

- [ ] **Step 5: 只提交 v02 和资产清单**

```bash
git add zhixia-feihualing/assets/characters/栀夏角色卡电影半写实-v02.png zhixia-feihualing/assets/inventory.csv
git commit -m "资产：定稿栀夏统一服装身份主卡"
```
