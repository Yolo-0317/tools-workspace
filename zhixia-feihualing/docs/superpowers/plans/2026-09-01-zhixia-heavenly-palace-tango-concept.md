# 栀夏·天宫探戈形象概念图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以已确认的九天云海舞仙母板锁定栀夏身份，生成并归档一张右腿高开衩、低 2—3cm 浅心形抹胸、月白高跟舞鞋和天宫独舞探戈急停姿态的高写实全身形象图。

**Architecture:** 本任务只制作形象概念图，不提前制作角色卡或视频。先把完整 ImageGen 提示词固化为独立文件，再使用九天云海舞仙正式母板作为唯一图片参考生成单张候选；候选经过本地尺寸检查、逐项目视验收和用户确认后，才归档为正式图并登记资产。

**Tech Stack:** OpenAI 内置 ImageGen、`view_image`、macOS `sips`、Markdown、CSV、Git。

## Global Constraints

- 设计真源固定为 `zhixia-feihualing/docs/superpowers/specs/2026-09-01-zhixia-heavenly-palace-tango-concept-design.md`。
- 唯一图片参考固定为 `zhixia-feihualing/assets/characters/归档/栀夏九天云海舞仙角色母板-v01-正式版.png`；它锁定同一张脸、18 岁年龄感、168cm、约 7.7 头身、九天仙家云髻、白玉仙冠和金玉配饰。
- 当前任务只生成一张单人全身形象概念图，不生成角色卡、三视图、视频提示词或成片。
- 右侧高开衩静止时露至大腿中段，内层月白安全短舞裙完整包覆；不得暴露臀线、内衣边缘或形成走光观感。
- 抹胸相对原正式母板下调约 2—3cm，固定为不透明、有真实支撑的浅心形弧线；不得生成深 V、透明胸衣或内衣式罩杯。
- 高跟鞋固定为月白丝缎包头、浅金交叉脚背带、约 5.5cm 浅金微喇叭跟；双脚必须完整可见并真实接触白玉地面。
- 外层裙装固定为右侧高开衩、左侧小腿长裙片和背后脚踝长燕尾裙摆；缩短垂纱固定在左右上臂后外侧且末端不低于膝部。
- 全图只有一个栀夏，无男舞伴、无道具、无文字、无角色卡排版、无西式舞厅、无魔法阵、无翅膀和无平台界面。
- 用户确认候选图前不得归档为正式版；局部偏差优先定向编辑，不重新生成另一张脸或另一套服装。
- 工作区存在其他任务改动；每次提交只显式暂存本任务文件，不清理、不覆盖、不暂存其他改动。

---

### Task 1: 固化天宫探戈形象生成提示词

**Files:**
- Create: `zhixia-feihualing/assets/characters/work/栀夏天宫探戈形象-v01-生成提示词.md`
- Read: `zhixia-feihualing/docs/superpowers/specs/2026-09-01-zhixia-heavenly-palace-tango-concept-design.md`
- Reference: `zhixia-feihualing/assets/characters/归档/栀夏九天云海舞仙角色母板-v01-正式版.png`

**Interfaces:**
- Consumes: 已确认设计中的身份、服装、鞋履、姿态、天宫场景、构图与禁止项。
- Produces: 一份可直接交给 ImageGen 的完整中文提示词；图片 1 的职责、目标画面、硬约束和负面约束均在正文内展开。

- [ ] **Step 1: 写图片职责与身份前缀**

  在提示词开头明确：图片 1 是本项目原创虚构数字角色栀夏的九天云海舞仙正式母板，只锁定同一张脸、18 岁年龄感、168cm、约 7.7 头身、九天仙家云髻、白玉仙冠、淡金流云簪、珍珠流苏和月白浅青淡金材质体系；不得复制档案卡排版、文字、三视图、拆解区或米白背景。

- [ ] **Step 2: 写探戈专用服装和鞋履正文**

  正文逐项写清浅心形低领抹胸、自然束腰、月白安全短舞裙、右腿高开衩、左侧长裙片、背后燕尾裙摆、缩短垂纱、月白包头舞鞋、浅金交叉脚背带和 5.5cm 微喇叭跟；不得只用“性感探戈裙”概括。

- [ ] **Step 3: 写单人探戈急停姿态与天宫构图**

  明确左脚承重、右腿斜向前外侧微屈并以前掌触地、腰胯与肩线反向拧转、一臂斜上展开、另一臂收于胸腰之间、三分之四侧脸看向画外；摄影机位于人物左前方三分之四角度，人物从仙冠到鞋底完整入画，占画面高度约 75%—82%。

- [ ] **Step 4: 写材质、场景和完整禁止项**

  场景固定为暮色云海上方的白玉天宫露台，云海只在栏外，冷月主光与少量暖金宫灯形成轮廓；禁止额外人物、男舞伴、道具、文字、角色卡版式、西式舞厅、红幕、现代聚光灯、魔法阵、翅膀、巨大月轮、低角度窥视、走光、畸形手脚和裁切鞋履。

- [ ] **Step 5: 检查提示词覆盖设计且没有占位符**

  Run:

  ```bash
  rg -n 'TBD|TODO|待定|待确认|占位' zhixia-feihualing/assets/characters/work/栀夏天宫探戈形象-v01-生成提示词.md
  ```

  Expected: 无输出，退出码为 1。

  Run:

  ```bash
  rg -n '图片 1|18 岁|168cm|7.7 头身|右侧高开衩|大腿中段|2—3cm|安全短舞裙|5.5cm|微喇叭跟|左脚承重|白玉天宫露台|无男舞伴' zhixia-feihualing/assets/characters/work/栀夏天宫探戈形象-v01-生成提示词.md
  ```

  Expected: 每个固定要求至少命中一次。

- [ ] **Step 6: 提交生成提示词**

  ```bash
  git add -- zhixia-feihualing/assets/characters/work/栀夏天宫探戈形象-v01-生成提示词.md
  git diff --cached --check
  git commit -m "文档：编写栀夏天宫探戈形象提示词"
  ```

### Task 2: 生成并验收单张形象候选图

**Files:**
- Read: `zhixia-feihualing/assets/characters/work/栀夏天宫探戈形象-v01-生成提示词.md`
- Reference: `zhixia-feihualing/assets/characters/归档/栀夏九天云海舞仙角色母板-v01-正式版.png`
- Create: `zhixia-feihualing/assets/characters/work/栀夏天宫探戈形象-v01-候选版.png`

**Interfaces:**
- Consumes: Task 1 的完整提示词与唯一参考母板。
- Produces: 一张纵向、单人、完整全身、高写实天宫探戈形象候选 PNG，供逐项验收和用户目视确认。

- [ ] **Step 1: 使用内置 ImageGen 生成单张候选图**

  将九天云海舞仙正式母板作为唯一 `referenced_image_paths` 输入，完整传入 Task 1 提示词。只请求一张候选，不同时加入日常、敦煌、九歌、真人舞者或探戈礼服参考图。

- [ ] **Step 2: 保存候选图到固定工作路径**

  将 ImageGen 返回的 PNG 非破坏性复制到：

  ```text
  zhixia-feihualing/assets/characters/work/栀夏天宫探戈形象-v01-候选版.png
  ```

  不覆盖九天云海舞仙正式母板、上传版或任何既有候选图。

- [ ] **Step 3: 核对文件类型和尺寸**

  Run:

  ```bash
  sips -g pixelWidth -g pixelHeight -g format zhixia-feihualing/assets/characters/work/栀夏天宫探戈形象-v01-候选版.png
  ```

  Expected: `format: png`，高度大于宽度，长边不低于 1536px。

- [ ] **Step 4: 使用 view_image 完成逐项目视验收**

  必须同时确认：同一张脸与年龄感；单人完整全身；仙冠和两只鞋均未裁切；右腿露至大腿中段且有安全短舞裙；浅心形领口比原版低但无深 V 或走光；左侧长裙片和脚踝燕尾清楚；缩短垂纱固定在上臂；月白包头鞋和浅金微喇叭跟一致；左脚承重、右脚前掌触地；白玉地面有接触阴影；天宫、云海、冷月与宫灯没有吞没主体。

- [ ] **Step 5: 执行候选图用户确认门禁**

  把候选图展示给用户，并同时报告已经确认的项目和任何可见偏差。用户确认前不把候选图移动到 `归档/`，不写正式版名称，不开始制作角色卡。

### Task 3: 归档用户确认的天宫探戈正式形象

**Files:**
- Read: `zhixia-feihualing/assets/characters/work/栀夏天宫探戈形象-v01-候选版.png`
- Create: `zhixia-feihualing/assets/characters/归档/栀夏天宫探戈形象-v01-正式版.png`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 2 中用户明确确认的候选 PNG。
- Produces: 无损正式形象 PNG 和一条可追溯的资产登记记录，作为后续天宫探戈角色卡设计的唯一造型输入。

- [ ] **Step 1: 复制确认图为无损正式版**

  将用户确认的候选 PNG 原样复制到：

  ```text
  zhixia-feihualing/assets/characters/归档/栀夏天宫探戈形象-v01-正式版.png
  ```

  不重新编码、不裁切、不调色，不删除工作候选图。

- [ ] **Step 2: 登记资产清单**

  先读取 `zhixia-feihualing/assets/inventory.csv` 的表头和末尾现有记录，再按既有列顺序追加一行；名称使用“栀夏天宫探戈形象 v01 正式版”，路径使用正式 PNG 的项目相对路径，来源注明内置 ImageGen 与九天云海舞仙正式母板，状态注明“用户确认”。不得覆盖、重排或修改既有记录。

- [ ] **Step 3: 验证正式图与候选图一致**

  Run:

  ```bash
  shasum -a 256 zhixia-feihualing/assets/characters/work/栀夏天宫探戈形象-v01-候选版.png zhixia-feihualing/assets/characters/归档/栀夏天宫探戈形象-v01-正式版.png
  ```

  Expected: 两个文件的 SHA-256 完全一致。

- [ ] **Step 4: 复核资产登记仅新增本任务记录**

  Run:

  ```bash
  rg -n '栀夏天宫探戈形象 v01 正式版|栀夏天宫探戈形象-v01-正式版.png' zhixia-feihualing/assets/inventory.csv
  ```

  Expected: 正式名称与正式路径命中同一条新增记录；既有记录保持不变。

- [ ] **Step 5: 只提交本任务产物**

  `assets/inventory.csv` 当前可能包含其他任务改动。提交前先检查完整差异，并使用精确暂存方式确保索引中只包含本任务新增记录；无法可靠隔离时，停止提交并保留未暂存登记，不得把其他改动一并带入。

  ```bash
  git add -- zhixia-feihualing/assets/characters/work/栀夏天宫探戈形象-v01-候选版.png zhixia-feihualing/assets/characters/归档/栀夏天宫探戈形象-v01-正式版.png
  git diff --cached --check
  git diff --cached --stat
  git commit -m "素材：归档栀夏天宫探戈正式形象"
  ```

  Expected: 提交中只包含已确认的候选图、正式图，以及能够被安全隔离时的本任务资产登记；不包含其他任务文件或来源不明的 `inventory.csv` 改动。

### Task 4: 为后续角色卡建立清晰交接

**Files:**
- Read: `zhixia-feihualing/assets/characters/归档/栀夏天宫探戈形象-v01-正式版.png`
- Read: `zhixia-feihualing/docs/superpowers/specs/2026-09-01-zhixia-heavenly-palace-tango-concept-design.md`

**Interfaces:**
- Consumes: 用户确认并归档的正式形象图。
- Produces: 下一轮角色卡设计的明确输入边界；不在本任务中创建角色卡文件。

- [ ] **Step 1: 回报正式图路径和验证证据**

  向用户提供正式图的可点击绝对路径、候选与正式版一致的 SHA-256 结果、实际尺寸和格式，并说明角色卡尚未开始。

- [ ] **Step 2: 明确下一轮角色卡输入规则**

  下一轮只使用“天宫探戈正式形象图”锁定探戈服装、露腿尺度、高跟鞋和色彩，同时使用“九天云海舞仙正式母板”的大型面容基准锁定同一张脸；角色卡恢复中性正面、严格右侧面与背面三视图，不复制概念图的天宫背景和动态急停姿态。

- [ ] **Step 3: 停在角色卡设计门禁**

  不直接生成角色卡。先向用户确认进入角色卡设计，再为角色卡另写独立设计规范和实施计划。
