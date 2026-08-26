# 阿砚电影级半写实身份主卡 GPT 生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 GPT 将旧版阿砚重塑为原创宣纸水墨生命，并生成一张可供后续全身比例卡与表演综合卡绑定的电影级半写实身份主卡。

**Architecture:** 只上传旧版阿砚角色卡作为有限身份参考，通过正向结构描述和明确废弃项阻断猫系萌宠特征。GPT 返回候选图后，先按物种、结构、材质、构图和电影融合度逐项验收；只有通过验收的原始 PNG 才归档并登记为新版身份母板。

**Tech Stack:** GPT 图像生成、PNG、Markdown 设计规格、CSV 资产清单、macOS `sips`、SHA-256、Git。

## Global Constraints

- 设计依据为 `docs/superpowers/specs/2026-08-26-ayan-cinematic-identity-master-design.md`。
- 唯一上传参考图为 `assets/characters/阿砚角色卡新.png`。
- 旧图只提供宣纸白、笔锋双耳、暖琥珀眼、极小朱砂印和唯一 S 形墨尾；不得继承猫系脸型、萌宠比例、毛发、铃铛、金属饰品、卷草金纹、文字或设定卡版式。
- 输出为单张 9:16 竖屏、单角色、完整全身、三分之四站姿的电影级半写实身份主卡。
- 阿砚严格为一个头、一个躯干、两耳、四足和一尾，设定站立高度约 8 至 10 厘米。
- 身体材质是暖象牙白手工宣纸与水墨，不是动物毛发、皮肤、折纸、陶瓷或塑料。
- 背景固定为真实湿润青石台和虚化竹林晨光，不出现文字、版式、道具、其他角色或魔法效果。
- 候选文件为 `assets/characters/阿砚角色卡电影半写实-v01.png`，用户验收前不得登记为 approved。

---

### Task 1: 在 GPT 中生成新版身份主卡候选图

**Files:**
- Reference: `zhixia-feihualing/assets/characters/阿砚角色卡新.png`
- Candidate: GPT 返回的原始 PNG

**Interfaces:**
- Consumes: 旧版阿砚角色卡、已确认设计规范和下方完整提示词。
- Produces: 单张无文字的 9:16 新版阿砚身份主卡候选图。

- [ ] **Step 1: 只上传旧版阿砚角色卡**

不要上传栀夏角色卡、场景卡、其他动物图、设定集拼图或额外风格参考。

- [ ] **Step 2: 粘贴完整生成提示词**

```text
请参考我上传的旧版“阿砚”角色卡，重新设计并生成一张新版阿砚电影级半写实身份主卡。不要制作旧图的小修版，而要重塑为真正原创的东方宣纸水墨生命。

参考图的使用范围非常有限：只继承暖象牙宣纸白主体、两只笔锋状长耳、偏小的暖琥珀眼、额头中央极小且固定的朱砂红印记，以及唯一一条 S 形水墨尾巴。旧图中的猫系脸型、猫嘴、大头短腿萌宠比例、水汪汪大眼、动物毛发、肩部铃铛、金属圆饰、全身金色卷草纹、文字、色卡、多视图和卡片版式全部废弃，禁止继承。

新版阿砚是站立高度约 8 至 10 厘米的原创东方纸墨灵，不对应猫、兔、狐狸、鹿或任何现实动物。它只有一个头、一个略修长的轻薄躯干、两只耳朵、两条前肢、两条后肢和一条尾巴，严格四足。头部比旧版明显缩小，轮廓清秀克制；口鼻短而简洁，但不能形成猫嘴或明确兽类鼻口。眼睛是偏小、清澈、克制的暖琥珀色杏仁眼，不做动漫大眼、星星眼或水汪汪宠物眼。

躯干轻薄略修长，胸廓自然，腰腹轻收，四肢纤细修长且关节可信。足端小巧，像书法收笔形成的纸质足爪，但必须能够真实承重。两只高而修长的耳朵从宣纸白自然过渡为淡墨、浓墨和飞白，末端明确收成毛笔笔锋。只保留一条稳定、克制的单一 S 形墨尾；尾巴像具有稳定厚度与重量的立体水墨笔画，不是蓬松兽尾、烟雾、火焰或分叉尾。额头中央只有一枚极小、哑光、固定形态的朱砂印，不发光、不变形、不变成宝石、火焰、花或复杂图腾。

身体表面是具有柔和体积的暖象牙白手工宣纸，绝对不是动物毛发或皮肤。近看可见极细纸纤维、轻微纸层与自然折光，但不能像硬质折纸、纸雕、陶瓷或塑料。纸面颜色由克制的二维手绘色块组织，真实体积来自自然光影、遮挡和接触关系。淡墨像墨汁自然渗入纸纤维；深墨耳尖和墨尾具有浓淡、干湿与飞白变化，同时保持稳定空间结构。暖金只能是几乎不可察觉的纸缘细色，不能形成装饰纹样、符文或饰品。

构图为单张 9:16 竖屏电影级半写实身份主卡。使用接近石面的微距低机位、自然镜头透视和三分之四侧视角。阿砚完整全身入镜，约占画面高度 55% 至 60%，耳尖、四只足爪、整条尾巴和尾梢全部保留，不能裁切。身体三分之四侧向镜头稳定站立，头部轻微转回镜头附近。它像刚察觉到一处细微异常：两只长耳略向前收拢，琥珀眼专注观察镜头附近，嘴巴自然闭合，尾巴保持单一 S 曲线。神态聪慧、独立、克制、好奇，带一点轻微试探感；不笑、不凶、不卖萌。

阿砚站在真实湿润的青石台面上，背景是浅景深虚化的竹林晨景，整体为低饱和青灰绿色。石面只有少量水汽与柔和反光，不出现瀑布、强雾、水花或复杂道具。左上方自然晨光勾勒耳缘、背部宣纸纤维和墨尾层次；四只足爪下方必须有清楚但柔和的接触阴影，并带可信的青石环境反光，让它真实地站在石面上。使用克制锐度、细腻阴影、真实动态范围和极轻微电影颗粒。

整体必须是高成本东方幻想电影质感：理想化、精致、半写实的原创纸墨灵与高度写实自然环境可信融合。不是现实动物写真，不是动漫、二次元、国漫立绘、游戏宠物界面、塑料 3D 或仙侠发光灵宠。

严格禁止：猫化、兔化、狐化、鹿化、宠物化；大头、短腿、圆胖身体；多头、多耳、少腿、多腿、肢体重影、多尾、分叉尾；动物毛发、绒毛、羽毛、鳞片、蓬松尾巴；铃铛、项圈、金属饰品、盔甲、卷草金纹、飘带；发光朱砂印、发光眼睛、魔法粒子、仙侠神光；文字、标题、标签、边框、信息框、色卡、多视图、Logo、水印；其他人物、动物或纸灵。

请直接输出一张干净的 9:16 竖屏原图，不添加任何说明文字。
```

- [ ] **Step 3: 下载 GPT 返回的原始 PNG**

不截图、不裁切、不调色、不添加文字、不二次压缩。若 GPT 生成多张候选，只下载最符合结构要求的一张进入验收。

### Task 2: 验收候选身份主卡

**Files:**
- Inspect: GPT 返回的原始 PNG
- Compare: `zhixia-feihualing/assets/characters/阿砚角色卡新.png`
- Spec: `zhixia-feihualing/docs/superpowers/specs/2026-08-26-ayan-cinematic-identity-master-design.md`

**Interfaces:**
- Consumes: Task 1 候选图。
- Produces: accepted 或 rejected 的明确结论，以及 rejected 时只针对失败项的修改提示词。

- [ ] **Step 1: 检查物种与轮廓**

Expected: 第一眼是原创纸墨生命；头小、躯干与四肢略修长，不像猫、兔、狐狸、鹿、普通宠物或混种兽。

- [ ] **Step 2: 检查结构数量**

Expected: 准确为一个头、一个躯干、两耳、两前肢、两后肢和一尾；无残肢、重影、隐藏足、多余耳朵、多尾或分叉尾。

- [ ] **Step 3: 检查固定识别点**

Expected: 两只笔锋长耳、偏小暖琥珀杏仁眼、额心极小固定朱砂印和唯一 S 形墨尾清楚稳定；朱砂印不发光。

- [ ] **Step 4: 检查材质**

Expected: 身体为暖象牙白宣纸，能看见克制纸纤维与纸层；墨色有渗化、浓淡、干湿和飞白；无毛发、绒感、皮肤感、折纸硬边、陶瓷感或塑料感。

- [ ] **Step 5: 检查构图与接触关系**

Expected: 单张 9:16；三分之四完整站姿；耳尖、四足、整尾均未裁切；四足真实接触湿润青石并形成柔和阴影，尾巴具有重量和空间遮挡。

- [ ] **Step 6: 检查神态与电影融合度**

Expected: 聪慧、独立、克制、好奇且略带试探；不卖萌、不凶。竹林晨光、浅景深、低饱和调色和宣纸角色自然融合，无贴图感、抠图感或仙侠光效。

- [ ] **Step 7: 检查画面洁净度**

Expected: 无铃铛、项圈、金属饰品、卷草金纹、额外道具、文字、卡片版式、色卡、多视图、Logo、水印、其他人物或动物。

- [ ] **Step 8: 给出验收结论**

任一物种、肢体数量、宣纸材质或完整构图要求失败，均判定为 rejected。只有七类检查全部通过才判定为 accepted。修改提示词必须要求在当前候选图上局部纠正，且列明其余已通过内容保持不变。

### Task 3: 验收后归档新版身份母板

**Files:**
- Create: `zhixia-feihualing/assets/characters/阿砚角色卡电影半写实-v01.png`
- Preserve: `zhixia-feihualing/assets/characters/阿砚角色卡新.png`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 2 判定为 accepted 的原始 PNG。
- Produces: approved 的阿砚 identity-master 资产记录，并保留旧版历史参考。

- [ ] **Step 1: 原样保存已验收 PNG**

将用户提供的 GPT 原始 PNG 保存为 `assets/characters/阿砚角色卡电影半写实-v01.png`，不得重采样、裁切、调色或加字。

- [ ] **Step 2: 验证格式、尺寸和文件指纹**

Run:

```bash
sips -g format -g pixelWidth -g pixelHeight zhixia-feihualing/assets/characters/阿砚角色卡电影半写实-v01.png
shasum -a 256 zhixia-feihualing/assets/characters/阿砚角色卡电影半写实-v01.png
```

Expected: `format: png`，宽高为有效 9:16 竖屏尺寸，并记录唯一 SHA-256。

- [ ] **Step 3: 登记新旧资产状态**

在 `assets/inventory.csv` 新增：

```csv
ayan-identity-cinematic-semi-real-v01,character,阿砚,identity-master,assets/characters/阿砚角色卡电影半写实-v01.png,approved,ChatGPT web image generation,original AI-assisted asset,新版电影级半写实身份母板；宣纸水墨本体；后续全身比例卡与表演综合卡唯一身份依据
```

如果 `阿砚角色卡新.png` 尚无独立记录，则同时新增：

```csv
ayan-identity-legacy-reference,character,阿砚,identity-legacy,assets/characters/阿砚角色卡新.png,superseded,ChatGPT generated image,original AI-assisted asset,旧版猫系设定卡；仅保留历史参考；不得继续作为角色绑定母板
```

不得修改无关资产记录，也不得把现有 `ayan-final` 的占位记录误认成这两个本地文件。

- [ ] **Step 4: 验证路径、唯一性与状态**

使用 Python 标准库 `csv` 验证：两个新资产 ID 各出现一次；新版状态为 `approved`；旧版状态为 `superseded`；两条路径均存在；新版 shot 为 `identity-master`。

- [ ] **Step 5: 只提交本轮角色资产与清单行**

```bash
git add zhixia-feihualing/assets/characters/阿砚角色卡电影半写实-v01.png zhixia-feihualing/assets/characters/阿砚角色卡新.png
git add -p zhixia-feihualing/assets/inventory.csv
git commit -m "资产：定稿阿砚电影半写实身份主卡"
```

交互暂存 `assets/inventory.csv` 时，只选择本计划新增的阿砚资产行，不暂存其他任务的改动。
