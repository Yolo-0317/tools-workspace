# 栀夏高冲击力诗境舞蹈能力实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将“诗景为叙事基础、栀夏以高冲击力国风舞蹈增强演绎”落实为所有新诗境的默认提示词能力，同时锁定阿砚母版中的外扩纸纤维形象。

**Architecture:** 以全局视觉规范和生产流程作为唯一执行入口，新建纯文字自动编舞组合器与近期去重台账，角色圣经和阿砚固定说明负责身份真源。Shell 规则测试先声明新基线，再修改文档使测试通过；既有已完成诗境保持历史原文，不追溯返工。

**Tech Stack:** Markdown 规范、CSV 设计台账、Zsh + ripgrep 规则测试、Git。

## Global Constraints

- 正式生成默认只上传栀夏与阿砚两张原创虚拟角色母版，并使用纯文字场景提示词。
- 诗中景色、时空和自然事件仍是诗境核心；舞蹈进入、回应并增强诗境，不取代诗景。
- 所有新诗境默认包含舒展有力、节奏鲜明、连续自然的中国古典舞身韵，以及空间移动、完整旋转、重心变化和视觉高潮。
- 衣料、道具或唯一主要特效由身体动作触发并连续跟随；摄影机在旋转和高潮处产生可见反应。
- 结尾按诗意选择，不强制固定收势或封面舞姿。
- 网络舞蹈只用于人工研究，不作为默认生成参考输入，不复刻网络视频、既有剧目或固定套路。
- 阿砚不增加强制特写；每次出现都必须保持母版中的约 40 厘米体型、外扩纸纤维毛束、笔锋双耳和唯一墨尾，禁止顺毛小猫化。
- 最终 Seedance 提示词不得出现内部动作、镜头、特效编号或项目代码。
- 已确认、已合成或已发布的视频不追溯返工。

---

### Task 1: 建立新基线的失败测试

**Files:**
- Create: `zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh`
- Modify: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

**Interfaces:**
- Consumes: 已确认设计 `docs/superpowers/specs/2026-08-28-zhixia-high-impact-poetry-dance-design.md`。
- Produces: 针对全局规则、自动组合器、去重台账和阿砚材质真源的可执行文本契约。

- [ ] **Step 1: 编写失败测试**

新增测试，要求以下文件存在：

```zsh
style="$project_dir/docs/realistic-visual-style.md"
workflow="$project_dir/docs/production-workflow.md"
composer="$project_dir/docs/zhixia-poetry-dance-composer.md"
history="$project_dir/operations/dance-design-history.csv"
ayan_rules="$project_dir/assets/characters/阿砚角色母板-v01-Seedance固定说明.md"
character_bible="$project_dir/docs/character-bible.md"
```

测试必须验证新基线短语：

```zsh
"诗中核心景物"
"动作舒展有力、节奏鲜明、连续自然"
"完整旋转"
"视觉高潮"
"特效由动作触发"
"旋转与高潮"
"不强制形成封面舞姿"
"近期至少五支诗境"
"外扩纸纤维"
"不得变成贴身顺毛"
```

测试还必须拒绝全局规范中的旧基线：

```zsh
for obsolete in \
  "中国古典舞身韵、轻盈克制、连续自然、不遮脸" \
  "承载一个主要视觉事件和中等复杂度以内的舞蹈短句"; do
  if rg -nF "$obsolete" "$style" "$workflow"; then exit 1; fi
done
```

`test_classical_dance_library_rules.sh` 只修改全局新规则的断言；《白雪歌》历史提示词和场景卡仍保留原有验收，不改已生成事实。

- [ ] **Step 2: 运行测试并确认失败原因正确**

Run:

```bash
zsh zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh
```

Expected: FAIL，首先报告缺少 `docs/zhixia-poetry-dance-composer.md` 或 `operations/dance-design-history.csv`，而不是语法错误。

- [ ] **Step 3: 提交测试契约**

```bash
git add zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh zhixia-feihualing/tests/test_classical_dance_library_rules.sh
git commit -m "新增高冲击力诗境舞蹈规则测试"
```

### Task 2: 建立纯文字自动编舞组合器与去重台账

**Files:**
- Create: `zhixia-feihualing/docs/zhixia-poetry-dance-composer.md`
- Create: `zhixia-feihualing/operations/dance-design-history.csv`
- Modify: `zhixia-feihualing/README.md`

**Interfaces:**
- Consumes: 诗句的核心景物、自然事件、情绪和运动意象；近期五支诗境台账。
- Produces: 新诗境的纯文字组合顺序，以及 CSV 字段 `episode,poem,opening,movement,rotation,body_level,carrier,effect,camera_reaction,ending,status,notes`。

- [ ] **Step 1: 编写自动组合器文档**

文档必须按以下顺序定义自动选择流程：

```text
诗意分析 → 核心诗景 → 开场抓眼 → 移动路线 → 旋转进入与离开
→ 重心和高低层次 → 衣料/道具承接物 → 动作触发特效
→ 摄影机主路径与两次反应 → 诗意结束 → 近期五集去重
```

组合器必须提供可观察的选项组，而不是可复制到最终提示词的内部编号。至少覆盖：

- 开场：转身入画、踏步展开、强姿态接移动、道具引出。
- 路线：横向、斜向、前后弧线、小范围绕行。
- 旋转：移动中旋转、沉身后提转、道具牵引转体、连续方向变化后展开。
- 层次：下沉到提起、低位倾身到大幅展开、跨步换重、短暂离地后落定。
- 承接物：衣袖、披帛、裙摆，或诗意匹配的单一道具。
- 特效：明确来源、触发动作、跟随方向、空间层次和归宿。
- 摄影机：一条主路径；旋转和高潮分别触发一次加速、弧移、降低、抬升、推近、拉开或真实前景穿越。
- 结束：人物与景物关系、保持运动、收势或景观揭示，不强制封面姿态。

文档写明：纯文字模式追求原创好看和自由变化，不保证指定套路；生成结果退化时先强化路线、旋转和高潮，结构崩坏时先删减背景、道具或镜头复杂度。

- [ ] **Step 2: 建立空白去重台账**

创建 CSV，只写表头：

```csv
episode,poem,opening,movement,rotation,body_level,carrier,effect,camera_reaction,ending,status,notes
```

规则说明由组合器文档负责：每次新诗境设计完成后追加一行；设计前读取最近五行，不连续复用相同的开场、路线、旋转进入、道具或特效、镜头反应组合和结束方式。

- [ ] **Step 3: 在项目入口增加链接**

在 `README.md` 的核心文档区增加：

```markdown
- [栀夏诗境自动编舞组合器](docs/zhixia-poetry-dance-composer.md)
- [舞蹈设计去重台账](operations/dance-design-history.csv)
```

- [ ] **Step 4: 运行新测试并确认仍因全局规则未更新而失败**

Run:

```bash
zsh zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh
```

Expected: FAIL，缺少全局视觉规范、生产流程或阿砚真源中的新短语。

- [ ] **Step 5: 提交组合器与台账**

```bash
git add zhixia-feihualing/docs/zhixia-poetry-dance-composer.md zhixia-feihualing/operations/dance-design-history.csv zhixia-feihualing/README.md
git commit -m "建立栀夏诗境自动编舞与去重机制"
```

### Task 3: 替换全局舞蹈提示词规则

**Files:**
- Modify: `zhixia-feihualing/docs/realistic-visual-style.md`
- Modify: `zhixia-feihualing/docs/production-workflow.md`
- Modify: `zhixia-feihualing/docs/zhixia-classical-dance-library.md`

**Interfaces:**
- Consumes: `docs/zhixia-poetry-dance-composer.md` 的组合结果。
- Produces: 所有新诗境必须遵守的最终提示词结构与生成验收门禁。

- [ ] **Step 1: 更新全局视觉规范**

替换“中等复杂度”“轻盈克制”和只要求五项动作条件的旧基线，明确：

```text
诗景仍是叙事基础；高冲击力舞蹈增强诗境而不取代景物。
动作舒展有力、节奏鲜明、连续自然，必须有空间移动、完整旋转、重心变化、高低层次和视觉高潮。
衣料、单一道具或唯一主要特效由动作触发并沿同一方向跟随。
摄影机保持一条主路径，在旋转与高潮处分别作出一次可见反应。
结束方式服从诗意，不强制固定收势或封面构图。
```

保留原创角色声明、两张母版纯文字输入、首帧栀夏和 0.5 秒动作、内部代码清除、后期配音字幕边界。

- [ ] **Step 2: 更新生产流程和生成前检查**

把选题检查、输入等级、舞蹈段、摄影机段、视频生成和付费前门禁统一到新组合器；明确设计前读取近期五支台账，生成后登记采用方案。基础级从“中等复杂度短舞句”改为“开放式原创复杂舞蹈观感，不承担指定套路和逐帧复现”。

- [ ] **Step 3: 更新历史动作库边界**

保留 12 个历史动作母题和已完成单集事实，只修改文件开头的执行边界：新诗境不再以“轻盈克制”为固定气质，而是调用自动组合器生成高冲击力原创舞蹈；历史术语和编号不得直接进入最终提示词。

- [ ] **Step 4: 运行规则测试**

Run:

```bash
zsh zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh
zsh zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh
zsh zhixia-feihualing/tests/test_classical_dance_library_rules.sh
zsh zhixia-feihualing/tests/test_realistic_visual_style_rules.sh
```

Expected: 全部 PASS。

- [ ] **Step 5: 提交全局舞蹈规则**

```bash
git add zhixia-feihualing/docs/realistic-visual-style.md zhixia-feihualing/docs/production-workflow.md zhixia-feihualing/docs/zhixia-classical-dance-library.md
git commit -m "升级栀夏诗境高冲击力舞蹈规则"
```

### Task 4: 锁定阿砚外扩纸纤维母版形象

**Files:**
- Modify: `zhixia-feihualing/assets/characters/阿砚角色母板-v01-Seedance固定说明.md`
- Modify: `zhixia-feihualing/docs/character-bible.md`
- Modify: `zhixia-feihualing/docs/realistic-visual-style.md`
- Modify: `zhixia-feihualing/docs/production-workflow.md`

**Interfaces:**
- Consumes: 阿砚当前权威角色母版。
- Produces: 角色圣经、视频固定句、全局提示词和验收一致使用的外扩纸纤维描述。

- [ ] **Step 1: 修正阿砚材质真源**

将“柔软细腻”改写为：宣纸纤维、纸墨绒羽和细小纸片状毛束从脸颊、颈部、胸口、脊背和四肢轮廓向外放射、分叉和翘起，形成蓬松、锐利、带笔锋感的破边轮廓；风动只让末端轻颤，整体体积不被吹平。

固定禁止项增加：贴身顺毛、光滑短毛、圆润幼猫、普通白猫和毛绒玩具轮廓。

- [ ] **Step 2: 同步角色圣经与全局执行入口**

`character-bible.md`、`realistic-visual-style.md` 和 `production-workflow.md` 必须使用相同语义，并明确不增加阿砚强制特写或额外表演；只要求每次出现都贴近母版。

- [ ] **Step 3: 运行规则测试**

Run:

```bash
zsh zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh
zsh zhixia-feihualing/tests/test_realistic_visual_style_rules.sh
zsh zhixia-feihualing/tests/test_ayan_character_masterboard_v01.sh
```

Expected: 全部 PASS。

- [ ] **Step 4: 提交阿砚规则**

```bash
git add zhixia-feihualing/assets/characters/阿砚角色母板-v01-Seedance固定说明.md zhixia-feihualing/docs/character-bible.md zhixia-feihualing/docs/realistic-visual-style.md zhixia-feihualing/docs/production-workflow.md
git commit -m "锁定阿砚外扩纸纤维形象"
```

### Task 5: 更新项目记忆并完成回归验证

**Files:**
- Modify: `.cursor/rules/memory-workspace.mdc`
- Test: `zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh`
- Test: `zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh`
- Test: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`
- Test: `zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh`
- Test: `zhixia-feihualing/tests/test_realistic_visual_style_rules.sh`

**Interfaces:**
- Consumes: 已通过测试的全局规范、组合器和角色真源。
- Produces: 后续任务优先命中的最新项目记忆，以及完整验证证据。

- [ ] **Step 1: 追加覆盖旧结论的项目记忆**

在 `memory-workspace.mdc` 追加一条带日期的新记录，明确覆盖同日较早的“轻盈克制”和“中等复杂度”默认规则：诗景仍为核心，高冲击力舞蹈增强演绎；纯文字允许原创变化但不承诺指定套路；旋转、高潮、动作触发特效和镜头反应成为新基线；结尾不强制封面姿态；阿砚保持外扩纸纤维且不增加特写。

- [ ] **Step 2: 运行完整相关回归**

Run:

```bash
zsh zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh
zsh zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh
zsh zhixia-feihualing/tests/test_classical_dance_library_rules.sh
zsh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
zsh zhixia-feihualing/tests/test_realistic_visual_style_rules.sh
zsh zhixia-feihualing/tests/test_ayan_character_masterboard_v01.sh
git diff --check
```

Expected: 六个测试均输出 `PASS`，`git diff --check` 无输出并返回 0。

- [ ] **Step 3: 检查变更范围**

Run:

```bash
git status --short
git diff --stat
```

Expected: 仅包含本计划列出的栀夏项目文件和既有用户未提交修改；不得暂存 `.cursor/rules/memory-python.mdc`、既有无关的 `memory-workspace.mdc` 行或 `stock-ai/assets/wechat_mp/inline-discussion/`。

- [ ] **Step 4: 提交项目记忆与最终测试调整**

```bash
git add .cursor/rules/memory-workspace.mdc zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh zhixia-feihualing/tests/test_classical_dance_library_rules.sh
git commit -m "落实诗境舞蹈与阿砚视觉新基线"
```

- [ ] **Step 5: 提交后复验**

重新运行 Step 2 的全部命令；只有全部通过后才能报告实施完成。
