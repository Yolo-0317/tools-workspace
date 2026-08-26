# 阿砚电影级半写实身份主卡 GPT 生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以庐山场景中的阿砚为固定外观，生成并归档一张删除铃铛、改用平面浅金纹样且尾巴比例平衡的电影级半写实身份主卡。

**Architecture:** 庐山近景场景卡只负责锁定角色外观，生成时禁止重新设计脸、眼睛、耳朵和体态。先完成铃铛到平面花纹的局部替换，再以当前候选图为底图修正尾巴；通过人工验收后原样归档，并将旧版角色卡降级为历史参考。

**Tech Stack:** GPT 图像编辑、PNG、Markdown 设计规格、CSV 资产清单、macOS `sips`、SHA-256、Git。

## Global Constraints

- 设计依据为 `docs/superpowers/specs/2026-08-26-ayan-cinematic-identity-master-design.md`。
- 外观基准为 `episodes/lushan/assets/scene-cards/01-mist-impact-close.png` 中的阿砚。
- 只允许删除铃铛、将原位置改为平面浅暖金花纹，并把尾巴修正为长度适中、略显丰润的开放式 S 形。
- 保持庐山版脸、眼睛、口鼻、双耳、朱砂印、头身比例、四肢和纸墨绒羽质感。
- 输出为 941×1672 PNG、单张 9:16、单角色、完整全身、三分之四站姿。
- 候选通过用户验收后保存为 `assets/characters/阿砚角色卡电影半写实-v01.png`。

---

### Task 1: 从庐山形象生成身份主卡候选

**Files:**
- Reference: `zhixia-feihualing/episodes/lushan/assets/scene-cards/01-mist-impact-close.png`
- Candidate: GPT 返回的原始 PNG

**Interfaces:**
- Consumes: 庐山近景场景卡和局部替换提示词。
- Produces: 保留庐山版阿砚外观、无铃铛的单角色身份主卡。

- [x] **Step 1: 只上传庐山近景场景卡**

不上传失败的尖锐纸雕版本、旧设定卡、栀夏身份卡或其他动物图。

- [x] **Step 2: 锁定庐山版角色外观**

提示词明确要求保持头脸、琥珀眼、口鼻、双耳、体态、四肢、朱砂印、纸墨绒羽材质和身体浅金纹样，不重新设计物种。

- [x] **Step 3: 将铃铛替换为平面花纹**

删除肩胸交界处的金属铃铛和悬挂结构，在原位置生成与身体其他纹样一致的浅暖金回旋云纹；花纹不凸起、不发光、不像胸针。

- [x] **Step 4: 下载原始 9:16 PNG**

不截图、不裁切、不调色、不添加文字、不二次压缩。

### Task 2: 修正尾巴比例

**Files:**
- Edit base: Task 1 当前候选 PNG
- Candidate: GPT 返回的尾巴修正版 PNG

**Interfaces:**
- Consumes: 已通过脸、身体、花纹和背景验收的当前候选。
- Produces: 其余画面不变、尾巴比例平衡的最终候选。

- [x] **Step 1: 识别第一版尾巴问题**

第一版尾巴卷曲过紧并接近封闭圆环，视觉长度偏短。

- [x] **Step 2: 延长并放松尾巴**

只编辑尾巴，将其改成开放式 S 形；其余角色和背景保持不变。

- [x] **Step 3: 识别第二版尾巴问题**

第二版尾巴过长、过细、向左上延伸过高，像细长烟带并抢夺耳朵焦点。

- [x] **Step 4: 缩短并适度增粗**

在第二版基础上缩短约 20% 至 25%，尾根与中段增粗约 20%，最高点降至头顶附近并低于耳尖；只在最后一小段收细。

- [x] **Step 5: 下载最终原始 PNG**

保存用户最终确认的原图，不重采样、不裁切、不调色、不加字。

### Task 3: 验收最终候选

**Files:**
- Inspect: 用户最终确认的 941×1672 PNG
- Compare: `zhixia-feihualing/episodes/lushan/assets/scene-cards/01-mist-impact-close.png`
- Spec: `zhixia-feihualing/docs/superpowers/specs/2026-08-26-ayan-cinematic-identity-master-design.md`

**Interfaces:**
- Consumes: Task 2 最终候选。
- Produces: accepted 或 rejected 的明确结论。

- [x] **Step 1: 检查身份和结构**

Expected: 庐山版脸、眼睛、口鼻、双耳、朱砂印、体态和四足稳定；只有一个头、两耳、四足和一尾。

- [x] **Step 2: 检查花纹替换**

Expected: 铃铛和悬挂结构完全消失；原位置为平面浅暖金回旋云纹，并与身体纹样自然融合。

- [x] **Step 3: 检查尾巴**

Expected: 唯一尾巴长度适中，尾根与中段有分量，尾梢自然收细；开放 S 形连续清楚，最高点低于耳尖，不形成圆环或细长烟带。

- [x] **Step 4: 检查构图和环境**

Expected: 阿砚完整入镜；湿润青石接触阴影、虚化山林晨光、景深和低饱和电影调色可信；无文字、版式、其他角色或水印。

- [x] **Step 5: 记录用户结论**

用户于 2026-08-26 明确确认最终候选可定稿。

### Task 4: 归档身份母板

**Files:**
- Create: `zhixia-feihualing/assets/characters/阿砚角色卡电影半写实-v01.png`
- Preserve: `zhixia-feihualing/assets/characters/阿砚角色卡新.png`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 3 已验收原始 PNG。
- Produces: approved 的阿砚 identity-master 记录和 superseded 的旧版参考记录。

- [ ] **Step 1: 原样保存最终 PNG**

将最终候选复制为 `assets/characters/阿砚角色卡电影半写实-v01.png`，复制后使用 `cmp` 验证与用户原始文件逐字节一致。

- [ ] **Step 2: 验证格式、尺寸和指纹**

```bash
sips -g format -g pixelWidth -g pixelHeight zhixia-feihualing/assets/characters/阿砚角色卡电影半写实-v01.png
shasum -a 256 zhixia-feihualing/assets/characters/阿砚角色卡电影半写实-v01.png
```

Expected: `format: png`、`pixelWidth: 941`、`pixelHeight: 1672`、SHA-256 为 `66ef9485c29443a8d447a801b0d88c51e1ad3c1f79e045f3191209090c20ffe9`。

- [ ] **Step 3: 登记新旧资产**

在 `assets/inventory.csv` 新增：

```csv
ayan-identity-legacy-reference,character,阿砚,identity-legacy,assets/characters/阿砚角色卡新.png,superseded,ChatGPT generated image,original AI-assisted asset,旧版角色设定卡；仅保留历史参考；不得继续作为角色绑定母板
ayan-identity-cinematic-semi-real-v01,character,阿砚,identity-master,assets/characters/阿砚角色卡电影半写实-v01.png,approved,ChatGPT web image generation,original AI-assisted asset,941×1672；庐山版阿砚外观；铃铛替换为平面浅暖金花纹；唯一开放式S形墨尾；后续角色制作唯一身份依据
```

不得修改或暂存无关资产记录，也不得把现有 `ayan-final` 占位记录误认成本地旧版角色卡。

- [ ] **Step 4: 验证资产路径、唯一性和状态**

使用 Python 标准库 `csv` 验证两个新 ID 各出现一次、路径存在、新版为 `approved` 和 `identity-master`、旧版为 `superseded`。

- [ ] **Step 5: 只提交本轮规范与资产**

```bash
git add zhixia-feihualing/docs/character-bible.md
git add zhixia-feihualing/docs/superpowers/specs/2026-08-26-ayan-cinematic-identity-master-design.md
git add zhixia-feihualing/docs/superpowers/plans/2026-08-26-ayan-cinematic-identity-master-gpt-generation.md
git add zhixia-feihualing/assets/characters/阿砚角色卡新.png
git add zhixia-feihualing/assets/characters/阿砚角色卡电影半写实-v01.png
git add -p zhixia-feihualing/assets/inventory.csv
git commit -m "资产：定稿阿砚电影半写实身份主卡"
```

交互暂存 `assets/inventory.csv` 时，只选择本计划新增的两条阿砚记录，不暂存其他任务的改动。
