# 栀夏·九天云海舞仙角色母板 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一张可长期锁定栀夏仙侠系列面容、168cm 身高比例、妆发、服装与配饰的纵向角色母板，并导出 Seedance 上传版与固定说明。

**Architecture:** 使用三张参考图分工约束生成：日常栀夏 v04 只负责身份脸，仙侠单人形象 v02 只负责妆发、服装、体态和色彩，敦煌十六舞 v03 只负责纵向档案卡版式。先生成单张高写实候选母板，按身份、三视图、比例、服化道和文字区域逐项验收；用户确认后再归档正式版、导出上传版并编写固定说明。

**Tech Stack:** OpenAI 内置 ImageGen、`view_image`、macOS `sips`、Markdown、Git。

## Global Constraints

- 角色名称固定为“栀夏·九天云海舞仙”，角色固定为 18 岁。
- 身高固定为 168cm，整体约 7.7 头身；不得超过八头身。
- 日常栀夏 v04 是唯一身份脸来源；仙侠 v02 不得重新定义身份脸。
- 角色卡采用敦煌十六舞 v03 的三视图加单张大型正面头肩面容基准结构。
- 不设置表情组、口型组、情绪小图或可选法器区。
- 固定九天仙家云髻、镂空白玉仙冠、淡金流云簪与少量珍珠流苏。
- 固定无肩带月白浅弧抹胸、自然丰满但克制的胸部比例、月白至浅青仙裙、单组双臂长披帛与平底舞履。
- 角色卡使用米白档案背景，不使用云海、宫殿、浮空山或其他仙境场景。
- 用户可见文案与 Git 提交信息使用中文，不使用 emoji。
- 不覆盖现有资产；所有新文件使用 `v01` 版本名。

---

### Task 1: 固化角色母板生成提示词

**Files:**
- Create: `zhixia-feihualing/assets/characters/work/栀夏九天云海舞仙角色母板-v01-生成提示词.md`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-09-01-zhixia-cloud-sea-xianxia-character-masterboard-design.md`
- Reference: `zhixia-feihualing/assets/characters/栀夏角色母板高写实CG-v04-完整档案增彩版-Seedance上传版.jpg`
- Reference: `zhixia-feihualing/assets/characters/栀夏仙侠形象-九天仙家云髻-v02.png`
- Reference: `zhixia-feihualing/assets/characters/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-Seedance上传版.jpg`

**Interfaces:**
- Consumes: 已确认设计规范与三张职责互斥的参考图。
- Produces: 一份可直接交给内置 ImageGen 的完整提示词，包含参考图角色、版式、人物、服化道、禁止项和验收目标。

- [ ] **Step 1: 写入提示词头部与参考图职责**

  明确写入：图 1 是身份脸真源，图 2 是仙侠服化道真源，图 3 只提供档案卡版式；三者不得互相覆盖职责。

- [ ] **Step 2: 写入人物与三视图约束**

  明确写入 168cm、7.7 头身、正面、严格右侧面、背面使用同一身高线、同一服装和同一发髻，头冠到鞋底完整入镜。

- [ ] **Step 3: 写入大型面容基准约束**

  明确写入右侧唯一大型正面头肩像、平静闭嘴、直视镜头、无笑容、无表情组，且身份必须来自图 1。

- [ ] **Step 4: 写入服化道与平台安全约束**

  明确写入仙家云髻、白玉仙冠、浅弧抹胸、自然克制的胸部比例、单组披帛和月白浅青仙裙；禁止深胸沟、肩带、走光感、武器、法器与仙境背景。

- [ ] **Step 5: 检查提示词无占位符且覆盖设计规范**

  Run: `rg -n 'TBD|TODO|待定|待确认' zhixia-feihualing/assets/characters/work/栀夏九天云海舞仙角色母板-v01-生成提示词.md`

  Expected: 无输出。

- [ ] **Step 6: 提交提示词**

  ```bash
  git add -- zhixia-feihualing/assets/characters/work/栀夏九天云海舞仙角色母板-v01-生成提示词.md
  git commit -m "编写栀夏九天云海舞仙角色母板提示词"
  ```

### Task 2: 生成并验收角色母板候选图

**Files:**
- Create: `zhixia-feihualing/assets/characters/work/栀夏九天云海舞仙角色母板-v01-候选版.png`
- Read: `zhixia-feihualing/assets/characters/work/栀夏九天云海舞仙角色母板-v01-生成提示词.md`

**Interfaces:**
- Consumes: Task 1 的完整提示词与三张参考图。
- Produces: 一张纵向高写实角色母板候选图，供用户目视确认。

- [ ] **Step 1: 使用内置 ImageGen 生成单张候选图**

  将三张参考图按提示词中定义的顺序传入；生成目标为纵向角色母板，不生成单人场景照。

- [ ] **Step 2: 将生成结果非破坏性复制到工作目录**

  Copy to: `zhixia-feihualing/assets/characters/work/栀夏九天云海舞仙角色母板-v01-候选版.png`

- [ ] **Step 3: 使用 `view_image` 检查身份与版式**

  必须逐项确认：唯一大型正面脸、无表情组、三张全身视图、无仙境背景、无多人或重复身体。

- [ ] **Step 4: 检查身高与服化道一致性**

  必须逐项确认：三视图同一头顶线与脚底线、约 7.7 头身、云髻和仙冠一致、无肩带浅弧抹胸、披帛数量一致、裙装和鞋履一致。

- [ ] **Step 5: 若只存在一个局部缺陷，执行一次定向图像编辑**

  编辑提示必须列出所有不变量，只修改一个问题；若身份脸、三视图或版式整体失败，则重新生成而不是叠加多轮局部修补。

- [ ] **Step 6: 向用户展示候选图并等待确认**

  用户确认前，不归档为正式版，不制作 Seedance 上传版。

### Task 3: 归档正式版并制作 Seedance 上传版

**Files:**
- Create: `zhixia-feihualing/assets/characters/归档/栀夏九天云海舞仙角色母板-v01-正式版.png`
- Create: `zhixia-feihualing/assets/characters/栀夏九天云海舞仙角色母板-v01-Seedance上传版.jpg`
- Read: `zhixia-feihualing/assets/characters/work/栀夏九天云海舞仙角色母板-v01-候选版.png`

**Interfaces:**
- Consumes: 用户确认的候选 PNG。
- Produces: 无损正式归档 PNG 与单张 Seedance 上传 JPEG。

- [ ] **Step 1: 复制确认图为无损正式版**

  保留候选图，不覆盖或删除工作文件。

- [ ] **Step 2: 导出 Seedance 上传版 JPEG**

  使用 `sips` 保持纵向比例，将长边限制在适合上传的尺寸内并采用高质量 JPEG；不得裁切角色卡内容。

- [ ] **Step 3: 核对正式版与上传版尺寸和文件类型**

  Run: `sips -g pixelWidth -g pixelHeight -g format zhixia-feihualing/assets/characters/归档/栀夏九天云海舞仙角色母板-v01-正式版.png zhixia-feihualing/assets/characters/栀夏九天云海舞仙角色母板-v01-Seedance上传版.jpg`

  Expected: 两张图纵横比一致；正式版为 PNG，上传版为 JPEG。

### Task 4: 编写 Seedance 固定说明并完成交付验证

**Files:**
- Create: `zhixia-feihualing/assets/characters/栀夏九天云海舞仙角色母板-v01-Seedance固定说明.md`
- Read: `zhixia-feihualing/docs/superpowers/specs/2026-09-01-zhixia-cloud-sea-xianxia-character-masterboard-design.md`

**Interfaces:**
- Consumes: 用户确认的正式母板及已确认设计规范。
- Produces: 后续每条仙侠视频可复用的身份锁定前缀、服化道约束和禁止项。

- [ ] **Step 1: 写明版本状态与上传规则**

  指定本母板是“一舞一愿”仙境篇唯一角色真源；每次只上传仙侠 v01，不与日常、敦煌或九歌母板混用。

- [ ] **Step 2: 写明面容、身高与服化道固定项**

  固定大型面容基准、18 岁、168cm、7.7 头身、仙家云髻、白玉仙冠、浅弧抹胸、仙裙、披帛和舞履。

- [ ] **Step 3: 写入视频提示词固定前缀与禁止项**

  前缀明确只锁定角色身份与造型，不复刻档案卡排版和文字；禁止改变脸、身高比例、发髻、冠饰、胸衣、披帛、裙装、鞋履与主色。

- [ ] **Step 4: 执行完整性检查**

  Run: `rg -n '唯一|面部基准|18 岁|168cm|7.7 头身|九天仙家云髻|白玉仙冠|浅弧形抹胸|不得' zhixia-feihualing/assets/characters/栀夏九天云海舞仙角色母板-v01-Seedance固定说明.md`

  Expected: 每个固定要求至少命中一次。

- [ ] **Step 5: 检查只暂存本任务文件并提交**

  ```bash
  git add -- \
    zhixia-feihualing/assets/characters/归档/栀夏九天云海舞仙角色母板-v01-正式版.png \
    zhixia-feihualing/assets/characters/栀夏九天云海舞仙角色母板-v01-Seedance上传版.jpg \
    zhixia-feihualing/assets/characters/栀夏九天云海舞仙角色母板-v01-Seedance固定说明.md
  git diff --cached --check
  git commit -m "固化栀夏九天云海舞仙角色母板"
  ```
