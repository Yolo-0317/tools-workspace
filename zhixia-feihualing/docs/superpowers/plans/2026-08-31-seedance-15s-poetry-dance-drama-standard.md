# Seedance 15 秒诗舞剧提示词规范 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一份可直接复用、可自动校验的 Seedance 15 秒诗舞剧提示词规范，并把项目当前文档从“纯舞蹈展示／Seedance 原生朗诵”统一迁移到“单事件诗舞剧／现有栀夏后期 TTS”。

**Architecture:** 新建项目级规范作为唯一写作真源，新建可复制模板作为每集提示词起点，并用一条轻量规则测试校验时间窗、单事件结构和声音分工。现有编舞器、生产流程、写实规范、文化路线与《九歌》研究文档只保存规则摘要并链接真源；尚未生成的《九歌》第 3—11 篇先撤销原生朗诵并标记为待按诗舞剧规范重写，避免被直接付费生成。

**Tech Stack:** Markdown、Zsh、Python 3、现有 Seedance 提示词与文档测试体系

## Global Constraints

- 《敦煌十六舞》从第 8 舞生效；《九歌祭舞》从第 3 篇《湘君》生效。
- 历史成片、历史 `docs/superpowers/specs/`、历史 `docs/superpowers/plans/` 和已确认单集提示词不追溯重写。
- 每支新片固定为一位核心人物、一个事件、一个视觉象征、一个连续空间和一条摄影机主路径。
- 三个舞蹈高潮固定在 `0.000—1.800`、`4.800—7.000`、`10.000—13.200` 秒，分别承担建立、行动和结果；第三高潮主要爆发最晚在 `12.800` 秒完成。
- Seedance 不生成可辨识人声、字幕和说话口型；正式朗诵使用当前 `zhixia` 豆包声线后期生成。
- 栀夏仍是唯一核心人物并全程保持连续身体表演；舞蹈不退化为插入片段、普通走路、奔跑或光效替身。
- 不修改 `.env`、角色母板、既有音频、视频、字幕或发布内容。

---

### Task 1: 建立规范真源、可复制模板和失败门禁

**Files:**
- Create: `docs/seedance-15s-poetry-dance-drama-standard.md`
- Create: `assets/prompts/templates/seedance-15s-poetry-dance-drama.md`
- Create: `tests/test_seedance_poetry_dance_drama_rules.sh`
- Modify: `README.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-31-seedance-15s-poetry-dance-drama-standard-design.md`。
- Produces: 后续单集设计可以引用的规范真源、复制后填写的提示词模板、可重复运行的规则检查。

- [ ] **Step 1: 写出失败规则测试**

创建 `tests/test_seedance_poetry_dance_drama_rules.sh`，要求四个入口文件存在，并用 `rg -qF` 校验以下契约：

```zsh
#!/bin/zsh
set -euo pipefail

project_dir=${0:A:h:h}
standard="$project_dir/docs/seedance-15s-poetry-dance-drama-standard.md"
template="$project_dir/assets/prompts/templates/seedance-15s-poetry-dance-drama.md"
composer="$project_dir/docs/zhixia-poetry-dance-composer.md"
workflow="$project_dir/docs/production-workflow.md"

for target in "$standard" "$template" "$composer" "$workflow"; do
  [[ -s "$target" ]] || { print -u2 "FAIL: missing $target"; exit 1; }
done

for phrase in \
  "一位核心人物" \
  "一个事件" \
  "一个视觉象征" \
  "一个连续空间" \
  "一条摄影机主路径" \
  "栀夏为什么起舞" \
  "舞后发生什么变化" \
  "0.000—1.800 秒" \
  "4.800—7.000 秒" \
  "10.000—13.200 秒" \
  "建立—行动—结果" \
  "当前 zhixia 声线"; do
  rg -qF "$phrase" "$standard" || { print -u2 "FAIL: missing $phrase"; exit 1; }
done

for phrase in \
  "【唯一事件】" \
  "【核心视觉象征】" \
  "【0.000—1.800 秒｜第一高潮与诗意钩子】" \
  "【4.800—7.000 秒｜第二高潮与行动决定】" \
  "【10.000—13.200 秒｜第三高潮与最终变化】" \
  "Seedance 不生成可辨识人声" \
  "后期栀夏朗诵"; do
  rg -qF "$phrase" "$template" || { print -u2 "FAIL: template missing $phrase"; exit 1; }
done

for target in "$standard" "$template" "$composer" "$workflow"; do
  if rg -q "优先使用 Seedance 原生画外朗诵|默认由 Seedance 原生生成" "$target"; then
    print -u2 "FAIL: active file still defaults to native recitation: $target"
    exit 1
  fi
done

rg -qF "docs/seedance-15s-poetry-dance-drama-standard.md" "$project_dir/README.md" \
  || { print -u2 "FAIL: README missing standard link"; exit 1; }

print "PASS: Seedance 15-second poetry-dance drama standard is enforced"
```

- [ ] **Step 2: 运行测试并确认先失败**

Run: `zsh tests/test_seedance_poetry_dance_drama_rules.sh`

Expected: FAIL，首先报告缺少 `docs/seedance-15s-poetry-dance-drama-standard.md`。

- [ ] **Step 3: 创建项目级规范真源**

创建 `docs/seedance-15s-poetry-dance-drama-standard.md`，用正式执行语言收录以下完整章节：

1. 定位与生效边界。
2. “一人、一事、一象征、一变化”设计门禁。
3. 内部诗舞剧设计卡字段。
4. 六段固定时间结构。
5. 三高潮的身体与戏剧双重判定。
6. 单空间、单象征、单主路径的场景因果。
7. 栀夏身份、敦煌与九歌文化边界。
8. Seedance 无人声／后期当前栀夏 TTS 分工。
9. 提示词正文顺序、禁止项和失败降级。
10. 生成前检查与验收清单。

执行内容以已批准设计稿为准，但改成“必须／禁止／仅允许”的规范语气，并明确规范文件是后续当前真源。

- [ ] **Step 4: 创建可复制提示词模板**

创建 `assets/prompts/templates/seedance-15s-poetry-dance-drama.md`。模板外层包含填写说明，代码块内固定以下结构：

```text
【原创角色与作品定位】
上传图片中的栀夏是本项目原创虚构数字角色……本片为15秒、9:16、同一连续镜头的单场景诗舞剧。

【唯一事件】
栀夏正在：〔可观察处境〕
她想要：〔唯一目标〕
最终发生：〔唯一结果〕

【核心视觉象征】
唯一象征：〔云／光／风／水／花／影之一〕
初始状态：〔可观察状态〕
最终状态：〔可观察状态〕

【0.000—1.800 秒｜第一高潮与诗意钩子】
〔完整全身发力、初始处境、第一次环境响应、第一次镜头反馈〕

【1.800—4.800 秒｜处境与动机】
〔舞蹈化连接、视线和重心变化〕

【4.800—7.000 秒｜第二高潮与行动决定】
〔第二个同强度发力链、决定、象征改变、第二次镜头反馈〕

【7.000—10.000 秒｜变化扩散】
〔同一变化机制继续扩散，人物持续表演〕

【10.000—13.200 秒｜第三高潮与最终变化】
〔第三个同强度发力链、最终状态、第三次镜头反馈〕

【13.200—15.000 秒｜动态结果】
〔半步换重、非对称身体变化、动作余势中结束〕

【场景、材质与摄影机】
〔一个连续空间、一条主路径、真实材质、固定光源与空间锚点〕

【声音分工】
Seedance 不生成可辨识人声……只生成无人声音乐、环境声、动作声和三个同强度声音卡点，为后期栀夏朗诵保留中频空间。

【禁止项】
〔无文字、无口型、无第二事件、无第二场景、无第二角色解释、无手持、无第四高潮、无无因光效〕
```

模板说明明确：方括号是填写占位，不得原样提交；原作核验、生活映射分析和后期逐字时间轴只留在设计卡，不进入 Seedance 正文。

- [ ] **Step 5: 在 README 增加当前规范入口**

在“文档导航”中增加：

```markdown
- [Seedance 15秒诗舞剧提示词规范](docs/seedance-15s-poetry-dance-drama-standard.md)
```

链接放在公开提示词案例库之前，使规范真源先于案例参考。

- [ ] **Step 6: 运行测试，确认缺口已推进到现有编舞器或流程文档**

Run: `zsh tests/test_seedance_poetry_dance_drama_rules.sh`

Expected: 仍 FAIL，但不再报告规范、模板或 README 缺失；失败落在尚未迁移的 `composer` 或 `workflow`。

### Task 2: 把当前规则文档统一迁移为诗舞剧

**Files:**
- Modify: `docs/zhixia-poetry-dance-composer.md`
- Modify: `docs/production-workflow.md`
- Modify: `docs/realistic-visual-style.md`
- Modify: `docs/cultural-poetry-dance-roadmap.md`
- Modify: `docs/jiuge-dance-research-and-design.md`
- Modify: `docs/seedance-case-library/08-sound-dialogue-and-rhythm.md`
- Modify: `docs/seedance-case-library/09-multimodal-reference.md`
- Modify: `assets/prompts/templates/seedance-native-offscreen-recitation.md`

**Interfaces:**
- Consumes: Task 1 的项目级规范真源。
- Produces: 所有当前规则入口使用一致的诗舞剧结构与后期声音分工。

- [ ] **Step 1: 升级自动编舞组合器**

在 `docs/zhixia-poetry-dance-composer.md` 顶部把用途改为“诗舞剧组合器”，并新增“诗舞剧事件门禁”：

```markdown
## 诗舞剧事件门禁

从敦煌十六舞第8舞和九歌第3篇《湘君》开始，每支15秒新视频先回答：栀夏为什么起舞，舞后发生什么变化。设计只允许一位核心人物、一个事件、一个视觉象征、一个连续空间和一条摄影机主路径。

三个同等强度舞蹈高潮分别承担“建立—行动—结果”；连接段负责处境、动机和变化扩散。三个高潮仍执行身体发力、轮廓变化、空间变化、承接物轨迹和镜头反馈五项硬门槛，戏剧功能不能代替舞蹈强度。
```

自动组合顺序改为先填写原作关系、当代映射、唯一事件、人物目标、象征初态与终态，再选择三段动作。最终提示词转换增加“动作先发生、环境后回应”和“不得把生活映射分析复制进 Seedance 正文”。

- [ ] **Step 2: 更新生产流程**

在 `docs/production-workflow.md` 的设计与视频生成阶段加入设计卡门禁和生效边界；把检查项改为：

- 只有一个事件、视觉象征、空间和主路径。
- 三高潮同时满足动作强度与“建立—行动—结果”因果。
- 第一高潮本身就是 3 秒钩子，不加文字片头或第四高潮。
- Seedance 只生成无人声音乐、环境声和动作声。
- 后期使用当前 `zhixia` 豆包音色生成原作与当代映射连续朗诵。

删除“从《湘君》开始优先 Seedance 原生画外朗诵”的当前规则段落、复制原生朗诵模板的指令，以及“音色允许篇章间轻微差异”的默认。保留自然语速、禁止机械慢放、音乐为人声让位和历史不返工规则。

- [ ] **Step 3: 更新写实视觉规范与文化路线**

在 `docs/realistic-visual-style.md` 增加单事件、单象征、单空间的写实因果，并把当前声音规则统一为后期固定栀夏 TTS；删除仍把 Seedance 原生朗诵设为默认的条款。

在 `docs/cultural-poetry-dance-roadmap.md` 增加“15秒诗舞剧生效边界”，明确：

- 敦煌第8舞、九歌《湘君》开始执行。
- 栀夏仍是舞者／祭舞者，不改成对白演员。
- 每篇只演原作中的一个瞬间，不复述完整故事。
- 三高潮从独立炫技升级为同一事件的建立、行动和结果。

- [ ] **Step 4: 更新《九歌》研究与设计当前结论**

在 `docs/jiuge-dance-research-and-design.md` 顶部增加新规则覆盖说明；从《湘君》开始，每篇用“唯一事件、祭舞目标、视觉象征初态、视觉象征终态”补充原有设计卡。保留栀夏为同一楚地祭舞者、三高潮动作、无手持和十一篇差异门禁。

把声音章节和表格从“原生画外朗诵模式”改为“后期栀夏朗诵情绪层”，并删除 Seedance 原生朗诵默认。

- [ ] **Step 5: 收口声音案例建议和旧模板**

在 `docs/seedance-case-library/08-sound-dialogue-and-rhythm.md` 与 `09-multimodal-reference.md` 中，把“后续诗舞优先使用 Seedance 原生画外朗诵”改为：

```markdown
后续诗舞由 Seedance 生成无人声音乐、环境声和动作声；准确诗文与当代映射使用当前栀夏固定音色后期生成，画中人物不做朗诵口型。
```

在 `assets/prompts/templates/seedance-native-offscreen-recitation.md` 顶部增加停用声明：

```markdown
> 历史模板，已停用。自敦煌十六舞第8舞和九歌第3篇《湘君》起，不得复制本模板；当前声音分工以 `docs/seedance-15s-poetry-dance-drama-standard.md` 为准。
```

保留原模板正文用于历史追溯，不删除文件。

- [ ] **Step 6: 运行新规范测试与既有规则测试**

Run:

```bash
zsh tests/test_seedance_poetry_dance_drama_rules.sh
zsh tests/test_three_equal_climaxes_rules.sh
zsh tests/test_zhixia_dance_not_running_rules.sh
zsh tests/test_seedance_case_library_rules.sh
```

Expected: 四条命令均 PASS；新规范测试不再发现当前文档默认原生朗诵，既有三高潮、非跑步和案例库结构规则仍成立。

### Task 3: 阻止尚未生成的《九歌》旧提示词被直接使用

**Files:**
- Modify: `assets/prompts/jiuge/03-xiangjun-15s.md`
- Modify: `assets/prompts/jiuge/04-xiangfuren-15s.md`
- Modify: `assets/prompts/jiuge/05-dasiming-15s.md`
- Modify: `assets/prompts/jiuge/06-shaosiming-15s.md`
- Modify: `assets/prompts/jiuge/07-dongjun-15s.md`
- Modify: `assets/prompts/jiuge/08-hebo-15s.md`
- Modify: `assets/prompts/jiuge/09-shangui-15s.md`
- Modify: `assets/prompts/jiuge/10-guoshang-15s.md`
- Modify: `assets/prompts/jiuge/11-lihun-15s.md`
- Modify: `scripts/validate_jiuge_dance_design.py`
- Modify: `tests/test_validate_jiuge_dance_design.py`
- Modify: `tests/test_jiuge_dance_design_rules.sh`

**Interfaces:**
- Consumes: Task 1 的规范真源与 Task 2 的《九歌》当前规则。
- Produces: 第 3—11 篇旧稿明确不可直接生成，且不再含有效的 Seedance 原生朗诵指令。

- [ ] **Step 1: 把《九歌》测试改成后期声音与重写门禁并确认失败**

在 `tests/test_validate_jiuge_dance_design.py` 中把 `future_prompt_text()` 改为包含：

```text
> 状态：待按15秒诗舞剧规范重写，不得直接付费生成。
Seedance 不生成可辨识人声，只生成无人声音乐、环境声和动作声。
栀夏不张嘴说话、不做朗诵口型。
准确诗文与当代映射使用当前栀夏固定音色后期生成。
```

测试行为改为：

1. 接受含待重写标记与后期声音分工的第 3 篇草案。
2. 拒绝缺少待重写标记的第 3—11 篇草案。
3. 拒绝“年轻中国女性的画外朗诵”“只朗诵这些文字”等原生朗诵指令。
4. 拒绝缺少“不得生成可辨识人声”或“后期生成”的草案。
5. 保留无手持、视线与表情设计卡测试。

Run: `python3 -m unittest tests.test_validate_jiuge_dance_design -v`

Expected: FAIL，因为验证器仍要求原生画外朗诵。

- [ ] **Step 2: 修改《九歌》验证器**

在 `scripts/validate_jiuge_dance_design.py` 中：

- 把 `NATIVE_RECITATION_FROM_ORDER` 改成 `POETRY_DRAMA_REWRITE_FROM_ORDER = 3`。
- 删除 `RECITATION_CONTRACTS`、末句时间和原生朗诵必选短语。
- 新增：

```python
POETRY_DRAMA_PENDING_MARKER = "待按15秒诗舞剧规范重写，不得直接付费生成"
POST_TTS_REQUIRED = (
    "不得生成可辨识人声",
    "不做朗诵口型",
    "后期生成",
)
NATIVE_AUDIO_FORBIDDEN = (
    "年轻中国女性的画外朗诵",
    "只朗诵这些文字",
    "约第13.4秒才说出末尾短句",
)
```

- 第 3—11 篇必须含待重写标记和三条后期声音短语；含任一原生指令立即失败。
- 验证器最终输出改为：`PASS: Jiuge future prompts are blocked pending poetry-dance drama rewrites`。

- [ ] **Step 3: 批量收口第 3—11 篇声音段**

对九个尚未生成文件逐一执行相同的机械变更：

1. 标题后加入待重写标记。
2. 删除原生朗诵声音段、引号内朗诵任务和第 13.4 秒末句指令。
3. 替换为以下固定段落：

```text
声音分工：Seedance 不得生成可辨识人声，只生成无人声电影感国风音乐、自然环境声和动作声。栀夏不张嘴说话、不做朗诵口型。准确诗文与当代映射使用当前栀夏固定音色后期生成；音乐持续为后期人声保留中频空间。
```

不修改九篇现有动作、场景和研究内容；完整诗舞剧重写留给对应篇章进入制作时完成。

- [ ] **Step 4: 更新验证入口并运行测试**

把 `tests/test_jiuge_dance_design_rules.sh` 的期望输出更新为新字符串，然后运行：

```bash
python3 -m unittest tests.test_validate_jiuge_dance_design -v
zsh tests/test_jiuge_dance_design_rules.sh
```

Expected: 全部 PASS；第 3—11 篇均被明确阻止直接付费生成，且不包含有效原生朗诵任务。

### Task 4: 全量验证、范围复核与提交

**Files:**
- Inspect: 本计划涉及的全部文件
- Inspect: `git diff` 与 `git status`

**Interfaces:**
- Consumes: Task 1—3 的文档、模板、验证器和测试。
- Produces: 可复用、无相反默认、不会误生成未来旧稿的完整 Seedance 诗舞剧规范。

- [ ] **Step 1: 运行完整相关验证**

Run:

```bash
zsh tests/test_seedance_poetry_dance_drama_rules.sh
zsh tests/test_three_equal_climaxes_rules.sh
zsh tests/test_zhixia_dance_not_running_rules.sh
zsh tests/test_seedance_evidence_tiered_prompt_rules.sh
zsh tests/test_realistic_visual_style_rules.sh
zsh tests/test_seedance_case_library_rules.sh
python3 -m unittest tests.test_validate_jiuge_dance_design -v
zsh tests/test_jiuge_dance_design_rules.sh
```

Expected: 所有命令 exit code 0，无失败或错误。

- [ ] **Step 2: 检查当前规则中的声音冲突**

Run:

```bash
rg -n "优先使用 Seedance 原生画外朗诵|默认由 Seedance 原生生成|从《九歌·湘君》开始，Seedance 诗舞优先原生生成" \
  README.md \
  docs/seedance-15s-poetry-dance-drama-standard.md \
  docs/zhixia-poetry-dance-composer.md \
  docs/production-workflow.md \
  docs/realistic-visual-style.md \
  docs/cultural-poetry-dance-roadmap.md \
  docs/jiuge-dance-research-and-design.md \
  docs/seedance-case-library/08-sound-dialogue-and-rhythm.md \
  docs/seedance-case-library/09-multimodal-reference.md
```

Expected: 无输出。历史 specs、plans 和停用模板不纳入此检查。

- [ ] **Step 3: 检查格式与改动范围**

Run:

```bash
git diff --check
git status --short
git diff --stat
```

Expected: 无空白错误；只汇报本计划相关文件，不覆盖工作区已有其他改动。

- [ ] **Step 4: 分两次提交**

第一笔提交规范和当前文档：

```bash
git add \
  zhixia-feihualing/README.md \
  zhixia-feihualing/docs/seedance-15s-poetry-dance-drama-standard.md \
  zhixia-feihualing/assets/prompts/templates/seedance-15s-poetry-dance-drama.md \
  zhixia-feihualing/tests/test_seedance_poetry_dance_drama_rules.sh \
  zhixia-feihualing/docs/zhixia-poetry-dance-composer.md \
  zhixia-feihualing/docs/production-workflow.md \
  zhixia-feihualing/docs/realistic-visual-style.md \
  zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md \
  zhixia-feihualing/docs/jiuge-dance-research-and-design.md \
  zhixia-feihualing/docs/seedance-case-library/08-sound-dialogue-and-rhythm.md \
  zhixia-feihualing/docs/seedance-case-library/09-multimodal-reference.md \
  zhixia-feihualing/assets/prompts/templates/seedance-native-offscreen-recitation.md
git commit -m "建立Seedance十五秒诗舞剧规范"
```

第二笔提交《九歌》未来稿安全门禁：

```bash
git add \
  zhixia-feihualing/assets/prompts/jiuge/0[3-9]-*.md \
  zhixia-feihualing/assets/prompts/jiuge/1[01]-*.md \
  zhixia-feihualing/scripts/validate_jiuge_dance_design.py \
  zhixia-feihualing/tests/test_validate_jiuge_dance_design.py \
  zhixia-feihualing/tests/test_jiuge_dance_design_rules.sh
git commit -m "阻止九歌旧提示词直接生成"
```

- [ ] **Step 5: 最终交付**

向用户提供项目级规范、可复制模板和设计稿的绝对路径链接；说明生效边界、声音分工、三个高潮是否保留、测试结果和两笔提交号。明确本次没有调用 Seedance、没有生成视频，也没有重写具体第 8 舞或《湘君》的正式单集提示词。
