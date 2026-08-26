# 阿砚全身比例卡 GPT 生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 GPT 和阿砚新版身份主卡生成一张正面、严格右侧面、背面三列全身比例制作母板。

**Architecture:** 只上传新版身份主卡，通过固定三列顺序、统一地面线和逐视图结构约束生成三视图。候选图先按身份一致性、视角准确性、四足与唯一尾巴、花纹连续性和版式洁净度验收；通过后原样归档并登记为 full-body-master。

**Tech Stack:** GPT 图像生成、PNG、Markdown 设计规格、CSV 资产清单、macOS `sips`、SHA-256、Git。

## Global Constraints

- 设计依据为 `docs/superpowers/specs/2026-08-26-ayan-full-body-proportion-master-design.md`。
- 唯一参考图为 `assets/characters/阿砚角色卡电影半写实-v01.png`。
- 不上传旧版角色卡、庐山场景卡、栀夏角色卡、其他动物图或失败候选。
- 输出为单张 9:16、三列等宽、正面—严格右侧面—背面三视图。
- 三个视图等高、脚底齐平、比例一致、完整入镜且互不重叠。
- 每个视图严格只有一个头、两只耳朵、四条腿和一条尾巴。
- 保持新版身份主卡的脸、琥珀眼、朱砂印、双耳、紧凑体态、纸墨绒羽材质、浅金纹样和唯一开放式 S 形尾巴。
- 肩胸位置始终为平面浅暖金回旋云纹，不得恢复铃铛或任何立体饰品。
- 背景为简洁浅暖灰影棚与浅灰地面，无文字、标签、标尺、边框、分隔线、Logo 或水印。
- 候选文件为 `assets/characters/阿砚全身比例卡电影半写实-v01.png`，用户验收前不得登记为 approved。

---

### Task 1: 在 GPT 中生成三视图候选图

**Files:**
- Reference: `zhixia-feihualing/assets/characters/阿砚角色卡电影半写实-v01.png`
- Candidate: GPT 返回的原始 PNG

**Interfaces:**
- Consumes: 新版身份主卡、已确认设计规范和下方完整提示词。
- Produces: 单张无文字 9:16 三列全身比例卡候选图。

- [ ] **Step 1: 只上传新版身份主卡**

不要附加旧版角色卡、庐山场景卡、栀夏角色卡、其他动物或额外风格参考。

- [ ] **Step 2: 粘贴完整生成提示词**

```text
请严格参考我上传的新版阿砚身份主卡，生成一张“阿砚电影级半写实全身比例卡”。这是一张角色制作母板，不是重新设计角色，也不是剧情场景图。

参考图是唯一身份依据。三个视图中的阿砚必须与参考图完全是同一个角色：保持相同的庐山版亲和脸型、暖琥珀大眼、小巧口鼻、额心固定朱砂印、两只高耸水墨笔锋长耳、轻巧紧凑的头身比例、四肢长度、足爪形状、柔软细腻的宣纸纤维与纸墨绒羽质感、身体浅暖金回旋纹样，以及唯一一条长度适中、略显丰润的开放式 S 形水墨尾巴。不得换脸、不得缩小或放大眼睛、不得拉长脸、躯干或四肢、不得恢复铃铛。

输出单张 9:16 竖屏图片，采用三列等宽布局。从左到右严格依次排列：正面、严格右侧面、背面。三个阿砚都以自然中立四足站姿完整入镜，从足底到耳尖等高，脚底位于同一条水平地面线上，头部大小、身体长度、腿长、耳朵长度和尾巴粗细完全一致。三个视图之间保留充分空隙，耳朵、身体和尾巴互不重叠。不要添加文字、视图名称、编号、标尺、网格、边框或分隔线。

左列为严格正面：身体和头部正对镜头，姿态左右对称。两只水墨笔锋长耳完整可见并自然对称；两只暖琥珀眼、额心朱砂印、小巧口鼻、胸腹轮廓和两条前腿清楚。两条后腿应在合理位置部分可见，不能消失、融合或变成只有两条腿。唯一尾巴只从身体后方偏一侧自然露出，证明尾巴存在，但不能产生第二条尾巴的错觉。肩胸交界处的平面浅暖金回旋云纹必须清楚，不得变成铃铛、胸针或凸起饰品。

中列为严格右侧面：头、颈、躯干和四肢形成准确的右侧轮廓，不能使用三分之四角度。近侧一只暖琥珀眼清楚可见，远侧眼睛不得穿透侧脸显示，禁止侧脸出现两只完整眼睛。两只长耳自然前后错位，但仍然只能有两只耳朵。近侧前腿和后腿完整清楚，远侧两腿通过轻微自然错位部分可见，使四条腿都能被辨认，不能融合或缺失。唯一尾巴从臀部尾根真实连接，形成长度适中、略显丰润的开放式 S 曲线；黑、灰、白水墨飞白清楚，尾根和中段有分量，尾梢自然收细，最高点低于耳尖。右侧身体浅暖金纹样与参考图一致，不新增复杂图腾。

右列为严格背面：身体、头部和四足完全背向镜头，不能回头，不能露出正脸、口鼻或完整眼睛。清楚呈现两只笔锋长耳的背面、后脑、颈背、背线、臀部和四足落点。两条后腿完整分开，两条前腿以合理位置部分可见，仍能确认严格四足。唯一尾巴从正确尾根位置连接并向一侧自然展开，完整呈现开放式 S 形，不遮住整个背部、臀部或两条后腿。尾巴长度、粗细、墨色和飞白必须与中列侧面一致。背面浅暖金纹样克制连续，不得出现铃铛、项圈或新饰品。

三个视图必须严格保持：一个头、一个躯干、两只耳朵、两条前肢、两条后肢、唯一一条尾巴。阿砚设定站立高度约 8 至 10 厘米，但本图不添加数字或标尺。三视图必须像同一只阿砚在同一摄影棚中原地转身拍摄，而不是三个不同个体。

背景使用干净、简洁的浅暖灰影棚背景和浅灰地面。三个视图使用完全一致的柔和正侧上方影棚光、白平衡、曝光和真实接触阴影。保持电影级半写实材质与细腻纸墨纤维，但不要使用明显景深虚化，不要让任何一个视图模糊。背景不出现湿石、竹林、瀑布、水雾、植物、道具或剧情元素。

严格禁止：多头、多耳、三条腿、五条腿、肢体融合、肢体残影、多尾、分叉尾；正面不对称；侧面出现两只完整眼睛；背面回头露脸；三个视图大小不同、脚底不齐、比例变化、不同脸或不同花纹；铃铛、项圈、金属圆饰、绳带、悬挂结构、胸针、宝石、护甲、发光符文；普通猫、兔、狐狸或鹿的物种漂移；长腿尖脸异兽、极端大头萌宠、硬质纸雕、折纸、陶瓷、塑料 3D、动漫化；文字、标签、编号、标尺、网格、边框、分隔线、色卡、Logo、水印和其他角色。

请直接输出一张干净的 9:16 竖屏三视图原图，不添加任何说明文字。
```

- [ ] **Step 3: 下载 GPT 原始 PNG**

不截图、不裁切、不调色、不添加标签、不二次压缩。

### Task 2: 验收三视图候选

**Files:**
- Inspect: GPT 返回的原始 PNG
- Compare: `zhixia-feihualing/assets/characters/阿砚角色卡电影半写实-v01.png`
- Spec: `zhixia-feihualing/docs/superpowers/specs/2026-08-26-ayan-full-body-proportion-master-design.md`

**Interfaces:**
- Consumes: Task 1 候选图。
- Produces: accepted 或 rejected 的明确结论；rejected 时输出只针对失败项的局部修改提示词。

- [ ] **Step 1: 检查版式和视角**

Expected: 单张 9:16；从左到右准确为正面、严格右侧面、背面；三列等宽、角色等高、脚底齐平、完整无遮挡。

- [ ] **Step 2: 检查身份一致性**

Expected: 三视图与身份主卡保持同一脸、琥珀眼、朱砂印、双耳、头身比例、四肢、足爪、材质和浅金纹样；看起来是同一个体原地转身。

- [ ] **Step 3: 检查结构数量**

Expected: 每个视图严格只有一个头、两耳、四足和一尾；无肢体融合、残影、额外足、多尾或分叉尾。

- [ ] **Step 4: 检查逐视图规则**

Expected: 正面对称且后腿合理可见；侧面只有近侧眼清楚，远侧四肢自然错位；背面不露脸，后腿和尾根清楚。

- [ ] **Step 5: 检查尾巴和花纹**

Expected: 三视图的唯一尾巴长度、粗细、墨色与开放 S 形一致；肩胸均无铃铛，平面浅暖金花纹连续可信。

- [ ] **Step 6: 检查背景和洁净度**

Expected: 浅暖灰影棚、统一光线、接触阴影清楚；无场景元素、文字、标签、标尺、边框、分隔线、Logo 或水印。

- [ ] **Step 7: 给出验收结论**

任一视角错误、身份漂移、腿数错误、多尾、背面露脸或铃铛复现均判定为 rejected。只有六类检查全部通过才判定为 accepted。

### Task 3: 验收后归档全身比例母板

**Files:**
- Create: `zhixia-feihualing/assets/characters/阿砚全身比例卡电影半写实-v01.png`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 2 判定为 accepted 的原始 PNG。
- Produces: approved 的阿砚 full-body-master 资产记录。

- [ ] **Step 1: 原样保存已验收 PNG**

不得重采样、裁切、调色或添加标签。

- [ ] **Step 2: 验证格式、尺寸和指纹**

```bash
sips -g format -g pixelWidth -g pixelHeight zhixia-feihualing/assets/characters/阿砚全身比例卡电影半写实-v01.png
shasum -a 256 zhixia-feihualing/assets/characters/阿砚全身比例卡电影半写实-v01.png
```

Expected: `format: png`、有效 9:16 竖屏尺寸，并记录唯一 SHA-256。

- [ ] **Step 3: 新增唯一资产记录**

在 `assets/inventory.csv` 新增：

```csv
ayan-full-body-cinematic-semi-real-v01,character,阿砚,full-body-master,assets/characters/阿砚全身比例卡电影半写实-v01.png,approved,ChatGPT web image generation,original AI-assisted asset,正面—严格右侧面—背面三视图；三视图等高且脚底齐平；严格四足与唯一开放式S形墨尾
```

- [ ] **Step 4: 验证资产路径和唯一性**

Run:

```bash
awk -F, '$1=="ayan-full-body-cinematic-semi-real-v01"{count++; if($4!="full-body-master" || $6!="approved" || $5!="assets/characters/阿砚全身比例卡电影半写实-v01.png") exit 11} END{if(count!=1) exit 12}' zhixia-feihualing/assets/inventory.csv
test -f zhixia-feihualing/assets/characters/阿砚全身比例卡电影半写实-v01.png
```

Expected: 两条命令均以状态码 0 结束。

- [ ] **Step 5: 只提交本轮资产和清单行**

```bash
git add zhixia-feihualing/assets/characters/阿砚全身比例卡电影半写实-v01.png
git add -p zhixia-feihualing/assets/inventory.csv
git commit -m "资产：定稿阿砚全身比例三视图"
```

交互暂存资产清单时，只选择本轮新增的阿砚全身比例卡记录，不暂存其他任务的改动。
