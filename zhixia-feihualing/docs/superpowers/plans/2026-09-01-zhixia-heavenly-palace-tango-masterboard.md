# 栀夏·天宫探戈角色母板 Implementation Plan

> **For agentic workers:** Execute this plan task by task in the current task. Do not delegate unless the user explicitly requests delegation.

**Goal:** 以九天云海舞仙正式母板锁定栀夏面容，以天宫探戈正式形象锁定服装，制作一张可供 Seedance 使用的单张大脸锁定版角色母板。

**Architecture:** 两张输入图职责严格分离：图片 1 只定义面容、年龄、比例、妆发和冠饰；图片 2 只定义天宫探戈抹胸、裹身高开衩裙、高跟鞋、宽大飘带与材质。先固化完整 ImageGen 提示词，再生成单张纵向候选，完成文件与视觉验收后交用户确认；确认前不归档、不制作上传版。

**Tech Stack:** OpenAI 内置 ImageGen、`view_image`、macOS `sips`、Markdown、Git。

## Global Constraints

- 设计真源固定为 `zhixia-feihualing/docs/superpowers/specs/2026-09-01-zhixia-heavenly-palace-tango-masterboard-design.md`。
- 图片 1 固定为 `zhixia-feihualing/assets/characters/归档/栀夏九天云海舞仙角色母板-v01-正式版.png`，其面容身份优先级最高。
- 图片 2 固定为 `zhixia-feihualing/assets/characters/归档/栀夏天宫探戈形象-v01-正式版.png`，只锁定已确认的探戈造型。
- 当前只制作一张暖米白档案背景的角色母板，不生成天宫场景、舞蹈动作或视频。
- 三视图固定为正面、严格右侧面、背面中性站姿；右侧只有一张大型正面面容基准。
- 裙装必须是连续不透明裹身结构，右侧单一高开衩露至大腿中段，不出现安全裤、横向裤脚线或内衣边缘。
- 飘带固定为左右上臂后外侧各一片宽大扇形薄纱，允许略低于膝部，但不得拖地、缠腿、入手或遮脸。
- 用户确认候选图前不得归档正式版、制作 Seedance 上传版或写固定说明。
- 工作区存在其他改动；每次提交只显式暂存本任务文件。

---

### Task 1: 固化角色母板生成提示词

**Files:**
- Create: `zhixia-feihualing/assets/characters/work/栀夏天宫探戈角色母板-v01-生成提示词.md`
- Read: `zhixia-feihualing/docs/superpowers/specs/2026-09-01-zhixia-heavenly-palace-tango-masterboard-design.md`
- Reference: 两张正式输入图

- [ ] **Step 1: 写清两图职责与优先级**

  明确图片 1 锁定同一张脸、18 岁、168cm、约 7.7 头身、云髻和冠饰；图片 2 只锁定已确认的探戈服装、鞋履、宽大飘带、纹样、材质和色彩。

- [ ] **Step 2: 展开三视图和大型面容基准要求**

  固定 FRONT、严格 RIGHT SIDE、BACK 三个完整全身中性站姿和唯一大型正面闭嘴面容基准，不得复制动态探戈姿势。

- [ ] **Step 3: 展开服装拓扑和禁止项**

  写明低 2—3cm 浅心形抹胸、连续不透明裹身裙、右侧单一高开衩、左侧长裙片、背后燕尾、隐藏内衬、两片宽大飘带和 5.5cm 包头舞鞋。

- [ ] **Step 4: 展开档案卡版式与可见文字**

  固定暖米白背景、淡金细线、左侧三视图、右侧大脸、下方服化道拆解和允许的短标签；禁止场景背景、宣传文案和乱码。

- [ ] **Step 5: 检查覆盖范围并提交提示词**

  检查无任何占位标记或未决内容，并逐项命中两图职责、严格右侧面、面容基准、高开衩、隐藏内衬、宽大飘带、包头高跟鞋及版式要求。只提交提示词文件。

### Task 2: 生成并验收单张角色母板候选图

**Files:**
- Read: `zhixia-feihualing/assets/characters/work/栀夏天宫探戈角色母板-v01-生成提示词.md`
- Reference: 两张正式输入图
- Create: `zhixia-feihualing/assets/characters/work/栀夏天宫探戈角色母板-v01-候选版.png`

- [ ] **Step 1: 使用两张正式参考图生成候选**

  将两张正式图同时传入 ImageGen，只生成一张纵向角色母板候选；提示词中重复强调图片 1 的面容优先级和图片 2 的服装职责。

- [ ] **Step 2: 保存候选并核对文件属性**

  非破坏性复制到固定候选路径，使用 `sips` 确认 PNG、纵向构图和足够分辨率。

- [ ] **Step 3: 完成逐项目视验收**

  使用 `view_image` 核对同脸、唯一大脸、三视图完整、严格右侧面、服装拓扑一致、右侧露腿尺度、无明显安全裤、两片宽大飘带、高跟鞋一致、无场景背景和无明显乱码。

- [ ] **Step 4: 提交候选并执行用户确认门禁**

  只提交提示词和候选图相关文件，向用户展示候选及可见偏差。用户确认前不进入正式归档。

### Task 3: 用户确认后制作正式交付

**Files:**
- Create: `zhixia-feihualing/assets/characters/归档/栀夏天宫探戈角色母板-v01-正式版.png`
- Create: Seedance 上传版与固定说明文档
- Modify: `zhixia-feihualing/assets/inventory.csv`（仅在能安全隔离本任务记录时提交）

- [ ] **Step 1: 无损归档用户确认图**

  候选与正式版保持完全相同的 SHA-256，不重新编码、不裁切、不调色。

- [ ] **Step 2: 制作 Seedance 上传版和固定说明**

  按项目既有命名与尺寸规范制作上传资产，并写明该母板锁定的身份、服装和不可变更项。

- [ ] **Step 3: 登记资产并验证**

  检查格式、尺寸、哈希、上传版可读性和固定说明；资产表存在其他改动时只保留未暂存登记，不混入提交。

- [ ] **Step 4: 只提交本任务正式产物**

  提交中不得包含工作区其他任务文件或来源不明的资产表改动。
