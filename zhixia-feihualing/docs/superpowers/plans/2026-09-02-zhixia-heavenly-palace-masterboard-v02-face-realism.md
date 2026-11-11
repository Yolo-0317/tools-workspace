# 栀夏天宫探戈角色母板 v02 真人面容修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一张保留天宫探戈 v01 全部造型与版式、但直接采用单人正式照真人面容的 v02 候选角色卡，并在用户确认后形成可供 Seedance 单图上传的正式资产。

**Architecture:** 使用一次定向图片编辑完成修复：单人正式照是唯一面容与皮肤真源，v01 角色母板是唯一版式与服化道真源，不生成任何中间面部图。候选图先进入 `assets/characters/work/` 并接受文件与视觉双重验收；只有用户明确确认后才派生正式版、上传版和固定说明，再另行确认是否进行 Seedance 对照测试。

**Tech Stack:** 内置 imagegen、PNG、JPEG、macOS `sips`、FFmpeg、SHA-256、人工视觉核对。

## Global Constraints

- 图 1 `assets/characters/归档/栀夏天宫探戈形象-v01-正式版.png` 是唯一面容与皮肤真源，优先级最高。
- 图 2 `assets/characters/归档/栀夏天宫探戈角色母板-v01-正式版.png` 只提供版式、三视图、服装、发型发饰、飘带、鞋履、拆解区、材质区和文字结构。
- 不输入九天云海舞仙角色母板、日常栀夏 v04、其他角色卡、旧候选图或额外人脸参考。
- 不生成独立面部图或中间锚点图；只允许一次直接角色卡修复。
- v02 保持同一位 18 岁成年栀夏，不幼化，不网红化，不使用放大黑亮瞳孔、尖锐 V 脸、瓷白磨皮、蜡像皮、油润塑料感或数字微笑。
- 保持 `ZHI XIA / 栀夏 / 天宫探戈`、角色卡版式、三视图、大头像、天宫云髻、金白发冠、长黑发、白金抹胸舞服、宽幅飘带、单侧开衩长裙、白金高跟舞鞋、168 厘米高挑比例和全部拆解区。
- 首轮只创建候选版；用户确认前不得覆盖、删除或替换 v01，不得提前创建正式版和 Seedance 上传版。
- 任何外部或付费 Seedance 测试必须再次取得用户明确确认。

---

### Task 1: 核验两张唯一输入

**Files:**
- Inspect: `zhixia-feihualing/assets/characters/归档/栀夏天宫探戈形象-v01-正式版.png`
- Inspect: `zhixia-feihualing/assets/characters/归档/栀夏天宫探戈角色母板-v01-正式版.png`

**Interfaces:**
- Consumes: 已确认的 v02 真人面容修复设计规范。
- Produces: 两个经过视觉检查、可安全传给 imagegen 的绝对本地路径。

- [ ] **Step 1: 校验文件存在、格式可读与哈希**

Run:

```bash
file zhixia-feihualing/assets/characters/归档/栀夏天宫探戈形象-v01-正式版.png zhixia-feihualing/assets/characters/归档/栀夏天宫探戈角色母板-v01-正式版.png
shasum -a 256 zhixia-feihualing/assets/characters/归档/栀夏天宫探戈形象-v01-正式版.png zhixia-feihualing/assets/characters/归档/栀夏天宫探戈角色母板-v01-正式版.png
```

Expected: 两个文件均被识别为可读 PNG，哈希各有一条完整结果。

- [ ] **Step 2: 分别用原始清晰度查看两张输入**

检查图 1 的脸型、眼睛、鼻唇、皮肤明暗与成年骨相；检查图 2 的标题、三视图、大头像、服装、发冠、飘带、鞋履、拆解区和色板。若任一文件与职责不符，停止生成并报告具体差异。

- [ ] **Step 3: 固定输入顺序**

调用 imagegen 时按以下绝对路径顺序传入：

```text
1. /Users/huan.yu/dev/tools-workspace/zhixia-feihualing/assets/characters/归档/栀夏天宫探戈形象-v01-正式版.png
2. /Users/huan.yu/dev/tools-workspace/zhixia-feihualing/assets/characters/归档/栀夏天宫探戈角色母板-v01-正式版.png
```

不得添加第三张参考图。

### Task 2: 一次性生成 v02 真人面容修复候选卡

**Files:**
- Reference: `zhixia-feihualing/assets/characters/归档/栀夏天宫探戈形象-v01-正式版.png`
- Edit target: `zhixia-feihualing/assets/characters/归档/栀夏天宫探戈角色母板-v01-正式版.png`
- Create: `zhixia-feihualing/assets/characters/work/栀夏天宫探戈角色母板-v02-真人面容修复-候选版.png`

**Interfaces:**
- Consumes: Task 1 固定的两个绝对路径与顺序。
- Produces: 一张未经归档的原始 PNG 候选角色卡。

- [ ] **Step 1: 读取 imagegen Skill 并执行一次定向编辑**

使用两个 `referenced_image_paths`，不得使用最近对话图片代替本地文件。完整生成提示词如下：

```text
编辑第二张图片，保持它仍是一张完整的竖版高写实角色设定卡。第一张图片是唯一且最高优先级的面容身份与真实皮肤参考；第二张图片只是编辑目标，并且只提供角色卡版式、三视图、服装、发型发饰、飘带、鞋履、拆解区、材质区和文字结构。

把第二张角色卡中所有可见的栀夏面部统一修复为第一张单人正式照中的同一位 18 岁成年女性：包括右侧大头像、正面全身视图和严格右侧面全身视图。背面视图不出现脸。必须直接继承第一张图的脸型、五官比例、成年骨相、眼神、鼻唇结构、自然肤色与可辨识身份；不要继承第二张图原有大头像的面部几何。

真人面容要求：保留双眉、双眼、鼻翼和唇角的轻微自然不对称；眼球大小、虹膜比例、眼白面积真实，高光克制；皮肤有非常细微的毛孔、轻微色差和自然明暗过渡，眼下、鼻翼、面颊与唇周可有克制的真实肤色变化；下颌与下巴自然。右侧大头像保持正面、中性闭口、目光放松，不露齿，不做营业微笑。

禁止放大黑亮瞳孔、玻璃眼、动漫眼、尖锐 V 脸、网红脸、幼态脸、镜像式完全对称、瓷白磨皮、蜡像皮、油润塑料皮、过度锐化、美颜滤镜和数字微笑。

除面容与皮肤真实性外，严格冻结第二张图片：保留 ZHI XIA、栀夏、天宫探戈文字；保留暖白金色底板、全部分栏、三视图、大头像、服装拆解、飘带与手臂结构、鞋履、发饰结构、细节特写、色彩材质区；保留天宫云髻、金白发冠、长黑发、白金抹胸舞服、宽幅飘带、单侧开衩长裙、白金高跟舞鞋、168 厘米高挑比例和仙家气质。不要增加表情宫格、额外人物、宠物、道具、场景、新文字分区或装饰。输出高分辨率完整角色卡，不能裁切边缘。
```

- [ ] **Step 2: 保存工具原始输出**

将原始 PNG 保存为：

```text
zhixia-feihualing/assets/characters/work/栀夏天宫探戈角色母板-v02-真人面容修复-候选版.png
```

不得先经过 JPEG 压缩、锐化、降噪或二次放大，也不得覆盖 v01。

### Task 3: 文件与视觉验收候选卡

**Files:**
- Inspect: `zhixia-feihualing/assets/characters/work/栀夏天宫探戈角色母板-v02-真人面容修复-候选版.png`

**Interfaces:**
- Consumes: Task 2 的原始 PNG 候选卡。
- Produces: 文件校验结果、逐区视觉结论，以及展示给用户的候选图。

- [ ] **Step 1: 校验候选文件可解码、非空且尺寸合理**

Run:

```bash
file zhixia-feihualing/assets/characters/work/栀夏天宫探戈角色母板-v02-真人面容修复-候选版.png
sips -g pixelWidth -g pixelHeight zhixia-feihualing/assets/characters/work/栀夏天宫探戈角色母板-v02-真人面容修复-候选版.png
ffmpeg -v error -i zhixia-feihualing/assets/characters/work/栀夏天宫探戈角色母板-v02-真人面容修复-候选版.png -f null -
shasum -a 256 zhixia-feihualing/assets/characters/work/栀夏天宫探戈角色母板-v02-真人面容修复-候选版.png
```

Expected: PNG 可完整解码，宽高均大于 0，保持竖版角色卡比例，并产生唯一 SHA-256。

- [ ] **Step 2: 用原始清晰度逐区视觉检查**

逐项记录通过或失败：

1. 大头像第一眼能认出图 1 中的栀夏，且比 v01 更接近真人拍摄。
2. 大头像、正面全身和严格右侧面属于同一人，年龄、骨相、眼距、鼻唇与肤色一致。
3. 没有放大黑亮眼、尖下巴、瓷白磨皮、蜡像油润感或僵硬数字微笑。
4. 皮肤保留克制纹理与色调变化，同时没有粗糙、衰老或脏污。
5. 标题、版式、三视图、发型发饰、服装、飘带、鞋履、拆解区与色板没有实质性漂移。
6. 没有表情宫格、额外人物、无关装饰、裁切边缘或明显文字错乱。

- [ ] **Step 3: 失败时只允许一次同目标定向迭代**

如果身份不准或 AI 感仍强，只在原提示词末尾追加具体失败项，例如“缩小虹膜并恢复自然眼白面积”“恢复第一张图较自然的下颌宽度”“去除鼻翼和面颊的塑料高光”。仍以图 1 和图 2 为输入重新编辑，不允许把失败候选图作为新的身份源，也不允许新增第三张参考图。

- [ ] **Step 4: 展示候选版并等待用户确认**

向用户展示候选图，同时报告六项验收结果。用户没有明确确认前停止，不执行 Task 4。

### Task 4: 用户确认后派生正式资产

**Files:**
- Copy from: `zhixia-feihualing/assets/characters/work/栀夏天宫探戈角色母板-v02-真人面容修复-候选版.png`
- Create: `zhixia-feihualing/assets/characters/归档/栀夏天宫探戈角色母板-v02-真人面容修复-正式版.png`
- Create: `zhixia-feihualing/assets/characters/栀夏天宫探戈角色母板-v02-真人面容修复-Seedance上传版.jpg`
- Create: `zhixia-feihualing/assets/characters/栀夏天宫探戈角色母板-v02-真人面容修复-Seedance固定说明.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: 用户明确确认的候选 PNG 与其 SHA-256。
- Produces: 正式 PNG、Seedance JPEG、固定说明和资产登记。

- [ ] **Step 1: 无损复制确认候选为正式版**

使用明确的源路径和目标路径复制文件，并用 `shasum -a 256` 确认候选版与正式版哈希一致。不得覆盖 v01。

- [ ] **Step 2: 派生 Seedance 上传版**

使用 `sips` 从正式 PNG 派生高质量 JPEG，保持纵横比，不拉伸、不裁切、不锐化、不美颜；随后用 `file`、`sips -g pixelWidth -g pixelHeight` 与 FFmpeg 解码检查验证。

- [ ] **Step 3: 写入固定说明**

固定说明必须写明：该 JPEG 是天宫限定栀夏的唯一 Seedance 角色上传图；面容以 v02 真人修复正式版为准；视频中不得放大瞳孔、收尖下巴、增加磨皮或持续数字微笑；服装、发饰、飘带、鞋履和身高比例以角色卡为准；日常制片不再同时上传单人照和旧 v01 角色卡。

- [ ] **Step 4: 登记资产且只提交本任务文件**

在 `assets/inventory.csv` 新增正式 PNG、上传 JPEG 和固定说明三条记录。先检查该文件已有未提交改动，只追加本任务行；使用逐文件 `git add`，不得使用 `git add .` 或 `git add -A`。提交信息使用：

```text
生成：固化栀夏天宫角色卡真人面容修复版
```

- [ ] **Step 5: 回读正式资产**

回读提交 SHA、文件统计、三项资产路径和哈希；确认 v01 仍存在且没有被修改或删除。

### Task 5: 另行确认后进行 Seedance 单变量对照测试

**Files:**
- Reference: `zhixia-feihualing/assets/characters/栀夏天宫探戈角色母板-v02-真人面容修复-Seedance上传版.jpg`
- Reference: 上一版天宫恰恰视频使用的原始提示词记录。
- Create: 由后续单独确认的测试目录与结果文件。

**Interfaces:**
- Consumes: Task 4 的唯一上传图和上一版原始恰恰提示词。
- Produces: 一段短时长对照视频及“角色卡改善幅度”的结论。

- [ ] **Step 1: 在任何生成前取得用户明确确认**

说明测试时长、预计消耗、上传图和提示词均保持哪些变量；未确认则不调用 Seedance。

- [ ] **Step 2: 只替换角色卡，不修改视频提示词**

沿用上一版恰恰提示词的光线、镜头、表情、舞步、构图和节奏，只把上传图替换为 v02，生成一段低成本短测试。

- [ ] **Step 3: 对照真人感**

在相近正面、微笑和暖金光画面中比较 v01 原片与 v02 测试片，重点观察虹膜比例、眼白、鼻翼高光、面颊纹理、下颌宽度和微笑自然度。若改善明显，保留视频提示词；若仍显假，再新建设计单独优化提示词，不同时回改角色卡。
