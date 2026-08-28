# Seedance Public Prompt Case Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一套含 60–80 个可回源公开案例、覆盖人物与风景等九类主题，并能为栀夏诗境提供可追溯句式的 Seedance 案例库。

**Architecture:** 使用一个总索引、九个互斥主收录专题和两个只引用 A/B 级案例的句式库。每个案例拥有唯一编号和统一字段；静态检查负责验证文件、编号、数量、字段、链接、等级和句式反向引用，人工复核负责判断来源真实性、推断边界与版权合规。

**Tech Stack:** Markdown、Bash、`rg`、`awk`、Git、公开网页与官方文档。

## Global Constraints

- 首版唯一案例不少于 60 个，目标约 80 个；可靠来源不足时如实记录缺口，不用低质量条目机械凑数。
- 来源优先级为 Seedance/字节 Seed/火山引擎官方、公开可复核社区成片、公开工作流与仓库、仅有词汇的公开材料。
- A 级为官方且有结果，B 级为社区可复核案例，C 级仅供词汇参考。
- 每个案例必须包含公开链接、证据等级、输入方式、中文结构化改写、可复用写法、失败风险和栀夏适用性。
- 缺失信息写“来源未披露”，不得根据成片反向臆造原提示词。
- 不大段复制公开页面原文；保留来源链接并采用中文结构化改写。
- 明确区分来源陈述、成片观察和项目适配建议；推断必须标注为推断。
- 句式库只允许引用 A/B 级案例，并反向链接唯一案例编号。
- 本阶段不修改现有全局提示词规范、角色圣经或单集提示词。
- 不调用付费模型，不下载或转载社区作者的视频文件。
- 用户可见文档禁止 emoji，不把项目内部镜头代码写入模型提示词。

---

### Task 1: 案例库骨架与静态检查

**Files:**
- Create: `zhixia-feihualing/docs/seedance-case-library/README.md`
- Create: `zhixia-feihualing/docs/seedance-case-library/01-characters-and-portraits.md`
- Create: `zhixia-feihualing/docs/seedance-case-library/02-multi-character-interaction.md`
- Create: `zhixia-feihualing/docs/seedance-case-library/03-dance-and-body-movement.md`
- Create: `zhixia-feihualing/docs/seedance-case-library/04-action-and-performance.md`
- Create: `zhixia-feihualing/docs/seedance-case-library/05-landscape-and-environment.md`
- Create: `zhixia-feihualing/docs/seedance-case-library/06-camera-and-one-take.md`
- Create: `zhixia-feihualing/docs/seedance-case-library/07-effects-and-physics.md`
- Create: `zhixia-feihualing/docs/seedance-case-library/08-sound-dialogue-and-rhythm.md`
- Create: `zhixia-feihualing/docs/seedance-case-library/09-multimodal-reference.md`
- Create: `zhixia-feihualing/docs/seedance-case-library/camera-phrases.md`
- Create: `zhixia-feihualing/docs/seedance-case-library/character-dance-phrases.md`
- Create: `zhixia-feihualing/tests/test_seedance_case_library_rules.sh`
- Modify: `zhixia-feihualing/README.md`

**Interfaces:**
- Consumes: 已确认设计 `docs/superpowers/specs/2026-08-28-seedance-public-prompt-case-library-design.md`。
- Produces: 案例标题格式 `## CASE-[0-9]{3}`；等级字段 `- **证据等级：** [ABC]`；来源字段 `- **来源：** [标题](https://...)`；两个句式库统一引用格式 ``来源案例：`CASE-001` ``。

- [ ] **Step 1: 写入会失败的结构检查**

在 `tests/test_seedance_case_library_rules.sh` 中列出 12 个必需文档，检查每个文件存在；再检查案例编号唯一、每个案例块含“来源、证据等级、输入方式、中文结构化改写、可复用写法、失败风险、栀夏适用性”七个字段，并要求唯一案例总数至少 60。脚本必须以 `set -euo pipefail` 开头，在错误时打印具体文件或案例编号。

- [ ] **Step 2: 运行检查并确认失败**

Run: `bash zhixia-feihualing/tests/test_seedance_case_library_rules.sh`

Expected: FAIL，首个错误为 `docs/seedance-case-library/README.md` 或专题文件不存在。

- [ ] **Step 3: 建立最小文档骨架**

创建 12 个文档。`README.md` 写明等级、统一字段、来源与改写规则、分类导航和统计区；九个专题只写职责、案例目录占位说明和交叉引用规则；两个句式库写明只接受 A/B 级案例及固定字段。修改项目 `README.md` 的“文档导航”，增加案例库入口。

- [ ] **Step 4: 将数量门槛拆成可阶段验证的检查模式**

让测试脚本支持 `CASE_LIBRARY_PHASE=scaffold`：骨架阶段跳过 60 条数量门槛，但继续检查 12 个文件与导航；默认模式仍要求全部字段和 60 条唯一案例。不得在脚本中降低最终门槛。

- [ ] **Step 5: 验证骨架阶段通过、最终阶段仍失败**

Run: `CASE_LIBRARY_PHASE=scaffold bash zhixia-feihualing/tests/test_seedance_case_library_rules.sh`

Expected: PASS。

Run: `bash zhixia-feihualing/tests/test_seedance_case_library_rules.sh`

Expected: FAIL，提示唯一案例少于 60。

- [ ] **Step 6: 提交骨架**

```bash
git add zhixia-feihualing/README.md zhixia-feihualing/docs/seedance-case-library zhixia-feihualing/tests/test_seedance_case_library_rules.sh
git commit -m "文档：建立Seedance案例库骨架"
```

### Task 2: 官方人物、动作与多模态案例

**Files:**
- Modify: `zhixia-feihualing/docs/seedance-case-library/01-characters-and-portraits.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/02-multi-character-interaction.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/03-dance-and-body-movement.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/04-action-and-performance.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/09-multimodal-reference.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/README.md`

**Interfaces:**
- Consumes: Task 1 的统一案例字段和编号格式。
- Produces: `CASE-001` 起的 A 级官方案例；每个案例只在一个主要专题完整出现，其他专题使用 Markdown 链接交叉引用。

- [ ] **Step 1: 建立官方来源清单**

从 Seedance/字节 Seed官方发布页和火山引擎官方指南开始，记录页面标题、机构、URL、访问日期、可见输入、公开结果和可确认模型版本。优先覆盖花样滑冰、查尔斯顿舞、武侠交锋、骑马下马、人物跨场景、肖像唤醒、角色替换和多参考素材控制。

- [ ] **Step 2: 收录人物与互动案例**

向 `01`、`02` 写入官方人物、首次亮相、双人/多人关系案例。每条必须区分官方页面明确说明与根据结果页面可观察到的画面；没有公开声音信息时写“来源未披露”。

- [ ] **Step 3: 收录舞蹈与动作案例**

向 `03`、`04` 写入官方花样滑冰、查尔斯顿舞、武侠、骑乘等案例。中文结构化改写必须包含具体动作过程、重心或节拍、摄影机如何响应，以及衣料、雨水或场景的物理反馈。

- [ ] **Step 4: 收录官方多模态案例**

向 `09` 写入图片、视频、音频及多参考组合案例，明确每种输入实际控制的是角色、构图、动作、运镜、声音还是风格，不将“可以参考”扩写为“必然稳定复刻”。

- [ ] **Step 5: 更新索引统计并检查字段**

更新 `README.md` 中 A/B/C 数量和专题数量。逐个案例检查公开链接、访问日期、模型版本或“未确认”、输入方式和栀夏适用性。

- [ ] **Step 6: 运行阶段检查**

Run: `CASE_LIBRARY_PHASE=scaffold bash zhixia-feihualing/tests/test_seedance_case_library_rules.sh`

Expected: PASS，且编号唯一。

- [ ] **Step 7: 提交官方案例**

```bash
git add zhixia-feihualing/docs/seedance-case-library
git commit -m "文档：收录Seedance官方人物动作案例"
```

### Task 3: 社区人物、舞蹈与表演案例

**Files:**
- Modify: `zhixia-feihualing/docs/seedance-case-library/01-characters-and-portraits.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/02-multi-character-interaction.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/03-dance-and-body-movement.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/04-action-and-performance.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/09-multimodal-reference.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/README.md`

**Interfaces:**
- Consumes: Task 1 字段格式与 Task 2 已用编号。
- Produces: 至少 20 个 B/C 级社区案例；复杂舞蹈案例明确标注纯文字、分镜板、动作参考视频或音频输入差异。

- [ ] **Step 1: 筛选公开可复核社区来源**

优先检查有提示词/工作流和成片或关键帧的作者原帖、GitHub 仓库和公开教程。记录是否披露原始输入；转载站只作为定位线索，最终链接尽量指向原作者或原仓库。

- [ ] **Step 2: 收录人物与双角色案例**

至少补足人物肖像与首次亮相 8 个、双人/多人互动 6 个的分类下限。特别记录换脸、比例漂移、人物遮挡、角色互换和参考图被误当首帧等风险。

- [ ] **Step 3: 收录舞蹈案例**

至少收录 10 个舞蹈案例，其中至少 4 个明确包含脚步、重心、方向变化或节拍节点。分别覆盖纯文字舞句、固定全身镜头、逐步分镜板、合法动作视频迁移和音频节拍同步；不得把现代舞动作直接改名为中国古典舞。

- [ ] **Step 4: 收录动作与表演案例**

补足动作与表演 8 个的分类下限。重点提炼“人物动作发生—摄影机响应—环境产生结果”的因果写法，并标注公开评论或成片中暴露的肢体、连贯性和物理失败。

- [ ] **Step 5: 复核证据等级**

只有提示词、没有成片或输入披露不足的条目降为 C 级；有完整输入和结果的社区案例才标 B 级。每个推断以“项目观察：”或“适配建议：”开头。

- [ ] **Step 6: 运行阶段检查并提交**

Run: `CASE_LIBRARY_PHASE=scaffold bash zhixia-feihualing/tests/test_seedance_case_library_rules.sh`

Expected: PASS。

```bash
git add zhixia-feihualing/docs/seedance-case-library
git commit -m "文档：补充Seedance社区人物舞蹈案例"
```

### Task 4: 风景、运镜与物理特效案例

**Files:**
- Modify: `zhixia-feihualing/docs/seedance-case-library/05-landscape-and-environment.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/06-camera-and-one-take.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/07-effects-and-physics.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/README.md`

**Interfaces:**
- Consumes: 已建立的唯一编号序列与统一字段。
- Produces: 风景至少 14 个、运镜至少 12 个、物理特效至少 8 个案例；运镜覆盖至少 8 类不同路径。

- [ ] **Step 1: 收录自然与天气风景**

覆盖山水、森林、花海、雪景、雨景、雾、沙漠、海洋等自然环境。每条写清环境自身如何变化、是否有人物作为尺度参照、摄影机怎样揭示空间层次，以及天气和材质反馈。

- [ ] **Step 2: 收录建筑与城市风景**

覆盖古建筑、室内空间、夜景城市、街道和跨空间变换。重点记录前景遮挡、透视、反射、窗口/门洞穿越和建筑结构稳定风险。

- [ ] **Step 3: 收录运镜案例**

至少覆盖缓推、后拉揭示、横移视差、人物跟随、弧形绕行、升降、穿越前景、甩镜、焦点转移和连续长镜头中的 8 类。每条写齐起始景别、角度、路径、速度、前景或揭示目标，不把术语列表当成完整提示词。

- [ ] **Step 4: 收录物理特效案例**

覆盖风、雪、雨、水、火、烟雾、花瓣、衣袖、发丝、破碎或材质变化中的至少 8 类案例。每条明确触发原因、运动方向、尺度和环境反应，区分物理效果与抽象图形特效。

- [ ] **Step 5: 去除重复并建立交叉引用**

同一官方或社区成片只保留一个完整 `CASE-xxx`；如果同时属于风景、运镜和特效，在其他专题用“相关案例”链接指向主条目，不复制案例字段。

- [ ] **Step 6: 运行阶段检查并提交**

Run: `CASE_LIBRARY_PHASE=scaffold bash zhixia-feihualing/tests/test_seedance_case_library_rules.sh`

Expected: PASS，且专题数量达到设计下限或在索引中列出可靠来源缺口。

```bash
git add zhixia-feihualing/docs/seedance-case-library
git commit -m "文档：补充Seedance风景运镜特效案例"
```

### Task 5: 声音、节拍与句式库

**Files:**
- Modify: `zhixia-feihualing/docs/seedance-case-library/08-sound-dialogue-and-rhythm.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/09-multimodal-reference.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/camera-phrases.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/character-dance-phrases.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/README.md`

**Interfaces:**
- Consumes: Tasks 2–4 的 A/B 级案例编号。
- Produces: 声音与节拍至少 6 个、多模态至少 8 个案例；两份句式库中的每条句式都反向引用 A/B 级 `CASE-xxx`。

- [ ] **Step 1: 收录声音与节拍案例**

覆盖环境声、动作音效、音乐节拍、对白或口型、画外音和音画同步。每条标明声音是模型生成、上传参考还是后期设计；来源未披露时不得推测。

- [ ] **Step 2: 补齐多模态覆盖**

确保图片、动作视频、运镜视频、音频和分镜板输入均有案例。写明素材权利要求：动作或运镜迁移只建议使用自有或获授权视频。

- [ ] **Step 3: 提炼运镜句式库**

只从 A/B 级案例提炼句式。每条包含最小表达、主体/方向/速度/前景/揭示目标等槽位、适合时长与输入、不应叠加的目标、栀夏改写示例和来源案例编号。

- [ ] **Step 4: 提炼人物与舞蹈句式库**

分别提供人物亮相、双角色空间关系、完整舞句、脚步与重心、节拍节点、动作—镜头联动等句式。明确标出哪些句式需要全身构图、分镜板、动作视频或音频，避免将参考输入带来的效果错误归功于文字。

- [ ] **Step 5: 扩展静态检查的句式等级校验**

在测试脚本中解析句式库引用的 `CASE-xxx`，确认编号存在且对应等级为 A 或 B；发现 C 级或不存在的编号时打印句式文件和编号并失败。

- [ ] **Step 6: 运行检查并提交**

Run: `CASE_LIBRARY_PHASE=scaffold bash zhixia-feihualing/tests/test_seedance_case_library_rules.sh`

Expected: PASS，句式引用全部可追溯到 A/B 级案例。

```bash
git add zhixia-feihualing/docs/seedance-case-library zhixia-feihualing/tests/test_seedance_case_library_rules.sh
git commit -m "文档：整理Seedance声音与可复用句式"
```

### Task 6: 全库核验与交付

**Files:**
- Modify: `zhixia-feihualing/docs/seedance-case-library/README.md`
- Modify: `zhixia-feihualing/docs/seedance-case-library/*.md`
- Modify: `zhixia-feihualing/tests/test_seedance_case_library_rules.sh`

**Interfaces:**
- Consumes: Tasks 1–5 的全部文档和静态检查。
- Produces: 通过最终门槛的首版案例库与准确统计。

- [ ] **Step 1: 运行最终静态检查并记录失败项**

Run: `bash zhixia-feihualing/tests/test_seedance_case_library_rules.sh`

Expected: 若案例不足、字段缺失、编号重复、链接格式错误或句式引用不合格则 FAIL，并列出具体位置。

- [ ] **Step 2: 修复所有结构失败**

补齐缺失字段、修正重复编号和交叉链接；若可靠案例不足，不新增虚构条目，而是在达到至少 60 个唯一案例后于索引记录未达到约 80 个目标的具体分类和原因。

- [ ] **Step 3: 人工回源抽查**

逐条打开全部 A 级来源；抽查至少一半 B 级来源和全部 C 级原始页面。确认链接直达、作者/机构正确、模型版本没有被夸大、中文改写没有加入来源未披露的信息。

- [ ] **Step 4: 版权与推断检查**

搜索连续长引文、整段英文提示词和未标注的结论性措辞。将非必要原文改成中文结构化转述；为观察与推断补充“成片观察”或“项目适配建议”标签。

- [ ] **Step 5: 更新最终统计**

在 `README.md` 写入唯一案例总数、A/B/C 数量、九个专题数量、运镜路径覆盖数、舞蹈中包含脚步/重心/节拍信息的数量，以及最后核验日期。

- [ ] **Step 6: 运行全部相关验证**

Run: `bash zhixia-feihualing/tests/test_seedance_case_library_rules.sh`

Expected: PASS。

Run: `git diff --check -- zhixia-feihualing/README.md zhixia-feihualing/docs/seedance-case-library zhixia-feihualing/tests/test_seedance_case_library_rules.sh`

Expected: 无输出，退出码 0。

- [ ] **Step 7: 审查变更范围**

Run: `git status --short`

Expected: 案例库相关文件为本计划变更；已有 `.cursor/rules/memory-python.mdc`、`.cursor/rules/memory-workspace.mdc` 或其他用户改动不进入本次提交。

- [ ] **Step 8: 提交最终核验**

```bash
git add zhixia-feihualing/README.md zhixia-feihualing/docs/seedance-case-library zhixia-feihualing/tests/test_seedance_case_library_rules.sh
git commit -m "文档：完成Seedance公开提示词案例库"
```
