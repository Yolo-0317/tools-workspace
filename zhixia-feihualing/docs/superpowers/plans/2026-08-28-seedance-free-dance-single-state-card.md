# Seedance 自由舞蹈与单状态卡 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将“每支诗境只保留一张开场状态卡，舞蹈只限定中国古典舞身韵、轻盈克制、连续自然、不遮脸，其余由 Seedance 自由发挥”写入长期项目记忆，并同步改造当前白雪诗境。

**Architecture:** `memory-workspace.mdc` 保存长期决策，`realistic-visual-style.md` 保存当前制作规范，既有古典舞动作库降级为历史参考。白雪单集只保留开场状态卡，最终 Seedance 提示词继续硬锁镜头、身份、雪花、声音和真实音频时间轴，但删除所有自创舞步、Dxx 编号、转身角度与固定收势。

**Tech Stack:** Markdown、Zsh、Ripgrep、现有静态规则测试。

## Global Constraints

- 每支诗境只保留一张状态卡，并且只制作开场状态卡。
- 不再为单集自创舞蹈动作母题，不再指定 Dxx 动作。
- 视频提示词中的舞蹈约束完整且仅为：`中国古典舞身韵、轻盈克制、连续自然、不遮脸`。
- 镜头路径、真实音频时间轴、角色身份、无声口型、场景变化、唯一视觉承接物、声音隔离和非舞蹈画面禁止项继续保留。
- 白雪单集删除 D01、沉转提、立圆、云手、山膀、圆场步、转身角度和固定收势要求。
- 既有动作库与旧设计文档保留为历史资料，不删除；新规则优先。
- 本轮不调用 TTS、图片或视频生成服务，不修改本地四段白雪音频。
- 全部用户可见内容、终端汇报和提交信息不使用 emoji。
- Git 提交显式限定计划内路径，保留工作区其他改动；提交信息使用中文。

---

## Task 1: 将现有规则门禁改为单状态卡与自由舞蹈

**Files:**

- Modify: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-08-28-seedance-free-dance-single-state-card-design.md`

**Interfaces:**

- Shell test exit code `0` means current style rules and白雪资产符合新决策。
- 历史动作库仍需存在并包含 12 个 Dxx 条目，但不得再被当前规范或白雪最终提示词选为默认动作。

- [ ] **Step 1: Rewrite the existing policy test before changing production documents**

保留对 `docs/zhixia-classical-dance-library.md` 文件存在和 12 个历史条目的检查，删除以下旧断言：

```text
只选择一个 Dxx 动作母题
三张状态卡
D01“雪醒梨开”
沉转提
约 135 度
状态图 02
状态图 03
```

新增这些当前规则断言：

```text
每支诗境只保留一张状态卡
只制作开场状态卡
不再为单集自创舞蹈动作母题
中国古典舞身韵、轻盈克制、连续自然、不遮脸
Seedance 自由发挥
历史参考
```

对 `episodes/baixue/prompts/scene-cards.md` 断言：

```zsh
test "$(rg -c '^## 状态图 01：' "$scene_cards")" = "1"
test "$(rg -c '^## 状态图 0[2-9]：' "$scene_cards" || true)" = "0"
```

新增 `final_prompt="$project_dir/episodes/baixue/prompts/seedance-v01.md"`，提取两个 Seedance 边界注释之间的正文，要求包含精确短语 `中国古典舞身韵、轻盈克制、连续自然、不遮脸`，并禁止：

```text
D01
沉转提
立圆
云手
山膀
圆场
135 度
90 度
```

继续检查白雪 README 包含 M02、H05、一片真实雪花、最终音频时间轴和“不生成图片或视频”。

- [ ] **Step 2: Run the revised test and verify the expected red state**

```bash
cd zhixia-feihualing
zsh tests/test_classical_dance_library_rules.sh
```

Expected: exit code non-zero，因为当前规范仍要求 Dxx、白雪仍有三张卡且最终提示词仍包含具体舞步。

- [ ] **Step 3: Commit only the red policy test**

```bash
git add zhixia-feihualing/tests/test_classical_dance_library_rules.sh
git commit --only zhixia-feihualing/tests/test_classical_dance_library_rules.sh -m "测试单状态卡自由舞蹈规则"
```

---

## Task 2: 写入长期记忆并更新全局视觉规范

**Files:**

- Modify: `.cursor/rules/project-memory.mdc`
- Modify: `.cursor/rules/memory-workspace.mdc`
- Modify: `zhixia-feihualing/docs/realistic-visual-style.md`
- Modify: `zhixia-feihualing/docs/zhixia-classical-dance-library.md`
- Test: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

**Interfaces:**

- `project-memory.mdc` 将“栀夏、飞花令、诗境、Seedance”路由到 `memory-workspace.mdc`。
- `memory-workspace.mdc` 提供后续任务应优先读取的稳定决策。
- `realistic-visual-style.md` 是当前视频提示词制作规范。
- `zhixia-classical-dance-library.md` 仅为历史动作资料，不再提供默认工作流。

- [ ] **Step 1: Add a dedicated memory route**

在 `.cursor/rules/project-memory.mdc` 的 Memory 路由表新增：

```markdown
| 栀夏、飞花令、诗境、Seedance | `.cursor/rules/memory-workspace.mdc` |
```

- [ ] **Step 2: Append the durable project memory**

在 `.cursor/rules/memory-workspace.mdc` 追加：

```markdown
### 2026-08-28 栀夏诗境 · 单状态卡 + Seedance 自由舞蹈

- **Context**: 用户决定不再为每支诗境自创舞蹈动作，也不再制作起、中、末三张舞蹈状态卡，希望让 Seedance 在稳定镜头与角色框架内自由完成舞蹈。
- **Pitfall/Error**: Dxx 动作母题、具体身韵术语、转身角度与多张状态卡会过度限制视频模型，增加提示词复杂度和前置制图成本；旧动作库与三卡规范不得继续作为新诗境默认规则。
- **Solution/Rule**:
  - 每支诗境只保留一张状态卡，只制作开场状态。
  - 不再为单集自创或指定具体舞蹈动作；现有动作库仅作历史参考。
  - 视频提示词的舞蹈约束完整且仅为：`中国古典舞身韵、轻盈克制、连续自然、不遮脸`；具体动作、连接与收势由 Seedance 自由发挥。
  - 镜头时间轴、角色身份、无声口型、场景变化、唯一视觉承接物、声音隔离与非舞蹈画面禁止项仍需明确锁定。
  - 本规则适用于所有尚未生成的新诗境，也适用于已设计但尚未生成状态卡或视频的单集；已发布成片不返工。
  - 真源：`zhixia-feihualing/docs/superpowers/specs/2026-08-28-seedance-free-dance-single-state-card-design.md`。
```

- [ ] **Step 3: Replace the active dance workflow in the realistic style guide**

在 `docs/realistic-visual-style.md` 中找到引用 `zhixia-classical-dance-library.md`、Dxx 和三张状态卡的当前舞蹈规则，替换为：

```markdown
- 每支诗境只保留一张开场状态卡，只锁定开场构图、角色身份、服装、比例、场景拓扑、光向、风向与核心视觉承接物。
- 不再为单集自创或指定具体舞蹈动作。视频提示词的舞蹈约束完整且仅为“中国古典舞身韵、轻盈克制、连续自然、不遮脸”，具体动作、连接与收势由 Seedance 自由发挥。
- 镜头路径、角色身份重锚、声音隔离与非舞蹈画面禁止项仍按本规范执行。
```

- [ ] **Step 4: Mark the old dance library as historical**

在 `docs/zhixia-classical-dance-library.md` 标题下加入醒目标注：

```markdown
> 历史参考：本动作库不再作为新诗境默认工作流。当前规则是每支诗境只制作一张开场状态卡，视频提示词只限定“中国古典舞身韵、轻盈克制、连续自然、不遮脸”，具体舞蹈由 Seedance 自由发挥。
```

保留全部 12 个 Dxx 条目，不删除历史资料。

- [ ] **Step 5: Run the policy test and identify the remaining white-episode failures**

```bash
cd zhixia-feihualing
zsh tests/test_classical_dance_library_rules.sh
```

Expected: 全局记忆与视觉规范相关断言通过，测试仍因白雪保留三张状态卡和具体舞步而失败。

- [ ] **Step 6: Commit only memory and global documentation**

```bash
git add .cursor/rules/project-memory.mdc .cursor/rules/memory-workspace.mdc zhixia-feihualing/docs/realistic-visual-style.md zhixia-feihualing/docs/zhixia-classical-dance-library.md
git commit --only .cursor/rules/project-memory.mdc .cursor/rules/memory-workspace.mdc zhixia-feihualing/docs/realistic-visual-style.md zhixia-feihualing/docs/zhixia-classical-dance-library.md -m "记忆栀夏单状态卡自由舞蹈规则"
```

---

## Task 3: 将白雪改为单张开场状态卡

**Files:**

- Modify: `zhixia-feihualing/episodes/baixue/prompts/scene-cards.md`
- Modify: `zhixia-feihualing/episodes/baixue/README.md`
- Test: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

**Interfaces:**

- `scene-cards.md` 只输出一张“状态图 01：雪晶沉势钩子”。
- README 将单张状态卡列为视频生成前唯一图片输入，不再引用 D01。

- [ ] **Step 1: Reduce scene-cards.md to the opening card**

保留状态图 01 的雪晶微距、栀夏沉势、阿砚低位和同一雪林规则。删除状态图 02 与状态图 03 的输入、提示词和验收重点。

将标题与使用规则改成单数，并明确：

```markdown
- 本文件只用于生成和审阅一张开场状态图。
- 开场状态图只锁定起镜构图、角色身份、服装、比例、雪林拓扑、光向、风向和唯一雪花，不锁定后续舞蹈动作或结束姿态。
- 视频中段舞蹈只限定“中国古典舞身韵、轻盈克制、连续自然、不遮脸”，具体动作由 Seedance 自由发挥。
```

从状态图 01 删除 D01、沉转提或任何暗示后续固定舞步的内容；可以保留静态“呼气微沉”作为开场人物状态。

- [ ] **Step 2: Update the episode README**

- 删除“动作：D01‘雪醒梨开’”和三张状态卡表述。
- 改为“舞蹈：只限定中国古典舞身韵、轻盈克制、连续自然、不遮脸，具体动作由 Seedance 自由发挥”。
- 将关联链接改为“单张开场状态卡提示词”。
- 当前状态改为“等待生成并验收一张开场状态卡”。
- 保留 M02、H05、唯一真实雪花、四段 TTS 与 0.000—10.000 秒真实时间轴。

- [ ] **Step 3: Run the policy test and confirm only the final video prompt remains red**

```bash
cd zhixia-feihualing
zsh tests/test_classical_dance_library_rules.sh
```

Expected: 单状态卡与 README 断言通过，测试仍因 `seedance-v01.md` 含具体舞步而失败。

- [ ] **Step 4: Commit only the white state card and README**

```bash
git add zhixia-feihualing/episodes/baixue/prompts/scene-cards.md zhixia-feihualing/episodes/baixue/README.md
git commit --only zhixia-feihualing/episodes/baixue/prompts/scene-cards.md zhixia-feihualing/episodes/baixue/README.md -m "精简白雪诗境为单张状态卡"
```

---

## Task 4: 精简白雪 Seedance 最终提示词

**Files:**

- Modify: `zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md`
- Modify: `zhixia-feihualing/episodes/baixue/prompts/seedance-structure-v01.md`
- Test: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

**Interfaces:**

- 最终提示词继续使用现有 `<!-- SEEDANCE_PROMPT_START -->` 与 `<!-- SEEDANCE_PROMPT_END -->` 边界。
- 精确时间边界保持：0.000、0.500、1.724、1.850、3.482、3.600、6.048、6.200、9.032、10.000 秒。
- 后期音频起点保持：0.500、1.850、3.600、6.200 秒。

- [ ] **Step 1: Remove all fixed choreography from seedance-v01.md**

保留九段真实时间轴、M02 镜头、H05 唯一雪花、阿砚与栀夏身份重锚、无声口型、雪林扩展、无人声音乐与环境声。

将舞蹈段落改为：

```markdown
3.482—3.600 秒，入舞呼吸：栀夏自然闭唇，呼气微沉，从回应无缝进入舞蹈；阿砚保持闭唇和低位观察。

3.600—6.048 秒，自由舞蹈第一段：栀夏在后期第一段诗句音频期间跟随唯一雪花起舞。舞蹈完整且仅限定为中国古典舞身韵、轻盈克制、连续自然、不遮脸，具体动作由 Seedance 自由发挥。M02 从 85mm 微距连续拉到 50mm 双角色中近景，完成全片唯一一次跨景别变化；唯一雪花经过栀夏脸侧安全区，阿砚保持左下低位完整结构并安静追随。

6.200—9.032 秒，自由舞蹈第二段与雪林揭示：栀夏继续以中国古典舞身韵、轻盈克制、连续自然、不遮脸的方式跟随唯一雪花起舞，具体动作与连接由 Seedance 自由发挥。摄影机沿雪花连续拉开并小幅侧移，真实积雪从近处枝梢扩展到远林。音频结束处栀夏自然结束舞动，阿砚停在她左侧前方，双角色共同望向雪林；不限定具体收势。
```

删除全文中的 D01、沉转提、立圆、云手、山膀、圆场、135 度、90 度和舞步失败降级。保留角色、手脚数量、遮脸、雪花穿模、物种漂移等非编舞安全约束，但不得新增第五项舞蹈风格限制。

- [ ] **Step 2: Archive the obsolete structure draft explicitly**

将 `seedance-structure-v01.md` 顶部状态改为：

```markdown
- 本文件记录旧版指定舞步方案，仅作历史参考，不得用于生成。
- 当前单状态卡与自由舞蹈版本以 `seedance-v01.md` 为准。
```

不必机械重写整份历史草稿。

- [ ] **Step 3: Run the policy test to green**

```bash
cd zhixia-feihualing
zsh tests/test_classical_dance_library_rules.sh
```

Expected:

```text
PASS: Zhixia single-state-card free-dance rules are enforced
```

- [ ] **Step 4: Commit only the final and archived prompt files**

```bash
git add zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md zhixia-feihualing/episodes/baixue/prompts/seedance-structure-v01.md
git commit --only zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md zhixia-feihualing/episodes/baixue/prompts/seedance-structure-v01.md -m "放开白雪诗境舞蹈编排"
```

---

## Task 5: 回归验证与范围审计

**Files:**

- Verify: `.cursor/rules/project-memory.mdc`
- Verify: `.cursor/rules/memory-workspace.mdc`
- Verify: `zhixia-feihualing/docs/realistic-visual-style.md`
- Verify: `zhixia-feihualing/episodes/baixue/README.md`
- Verify: `zhixia-feihualing/episodes/baixue/prompts/scene-cards.md`
- Verify: `zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md`
- Verify: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

**Interfaces:**

- 白雪最终提示词时间轴从 0.000 到 10.000 秒连续覆盖。
- 四段人声原文继续与 Seedance 正文隔离。
- 本地白雪音频时长与字幕文件不变化。

- [ ] **Step 1: Run focused rule and audio timeline tests**

```bash
cd zhixia-feihualing
zsh tests/test_classical_dance_library_rules.sh
zsh tests/test_baixue_10s_assets.sh
zsh tests/test_realistic_visual_style_rules.sh
zsh tests/test_cinematic_vfx_library_rules.sh
python3 -m unittest discover -s tests -p 'test_zhixia_tts_manifest.py'
python3 -m unittest discover -s tests -p 'test_generate_episode_audio.py'
```

Expected: all commands return exit code `0`。

- [ ] **Step 2: Audit the final prompt mechanically**

提取 Seedance 正文并确认：

- 九段时间窗连续覆盖 0.000—10.000 秒。
- 包含精确短语 `中国古典舞身韵、轻盈克制、连续自然、不遮脸`。
- 不包含 D01、沉转提、立圆、云手、山膀、圆场、135 度、90 度。
- 不包含两句对白或两句诗原文。

- [ ] **Step 3: Audit memory, media and Git scope**

```bash
rg -n "单状态卡|Seedance 自由舞蹈|中国古典舞身韵、轻盈克制、连续自然、不遮脸" .cursor/rules/project-memory.mdc .cursor/rules/memory-workspace.mdc zhixia-feihualing/docs/realistic-visual-style.md
git diff --check -- \
  .cursor/rules/project-memory.mdc \
  .cursor/rules/memory-workspace.mdc \
  zhixia-feihualing/docs/realistic-visual-style.md \
  zhixia-feihualing/docs/zhixia-classical-dance-library.md \
  zhixia-feihualing/episodes/baixue/README.md \
  zhixia-feihualing/episodes/baixue/prompts/scene-cards.md \
  zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md \
  zhixia-feihualing/episodes/baixue/prompts/seedance-structure-v01.md \
  zhixia-feihualing/tests/test_classical_dance_library_rules.sh
```

确认 `assets/audio/baixue/` 中四段 MP3 与 `audio-metadata.json` 未被修改，没有新增图片或视频。

- [ ] **Step 4: Report the new durable rule**

交付时明确：规则已经写入项目记忆，后续诗境默认只制作一张开场状态卡；舞蹈提示词只保留四项约束，具体动作由 Seedance 自由发挥。下一步若要生成白雪开场状态卡，仍需用户明确下达生成图片指令。
