# Seedance 第一帧空间锚定门禁 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 15 秒诗舞剧规范“后文存在环境、第一帧却无法判断人物站在哪里”的结构缺口，并用《云中君》重制提示词验证新门禁。

**Architecture:** 在当前项目级规范中新增第一帧空间锚定契约，把模板的基础空间段前移到事件与时间轴之前，并在组合器和生产流程中同步生成前检查。新增《云中君》诗舞剧重制提示词而不覆盖已经确认的历史首轮提示词。

**Tech Stack:** Markdown 规范与提示词、Zsh 规则验证、ripgrep、Git。

## Global Constraints

- 第一帧直接进入事件，不新增环境空镜、黑场、标题或第四高潮。
- 第一帧必须能判断人物承重地面、固定纵深锚点、视觉象征来源和去向。
- 全身与脚下落点可见不能替代空间锚定。
- 三个高潮仍位于 0.000—1.800、4.800—7.000、10.000—13.200 秒，并保持同等画面感知强度。
- 仍只有一个事件、一个视觉象征、一个连续空间、一种变化机制和一条摄影机主路径。
- 《云中君》历史首轮提示词不覆盖；重制稿使用单独文件。
- Seedance 不生成可辨识人声、字幕或说话口型；朗诵继续由后期当前栀夏声线完成。

---

### Task 1: 建立第一帧空间锚定回归门禁

**Files:**
- Modify: `zhixia-feihualing/tests/test_seedance_poetry_dance_drama_rules.sh`

**Interfaces:**
- Consumes: 当前规范、模板、组合器、生产流程和《云中君》重制提示词路径。
- Produces: 能在任一当前真源缺少首帧空间锚定或模板顺序倒退时失败的规则测试。

- [ ] **Step 1: 写失败测试**

在现有脚本中增加以下约束：

```zsh
yunzhongjun_remake="$project_dir/assets/prompts/jiuge/02-yunzhongjun-poetry-dance-drama-15s.md"
[[ -s "$yunzhongjun_remake" ]] || exit 1
rg -qF "第一帧空间锚定" "$standard"
rg -qF "【基础空间与第一帧锚点】" "$template"
rg -qF "承重地面" "$composer"
rg -qF "固定纵深锚点" "$workflow"
rg -qF "高山临崖风化石台" "$yunzhongjun_remake"
rg -qF "谷底云海明显低于石台" "$yunzhongjun_remake"
```

并使用行号验证模板中的 `【基础空间与第一帧锚点】` 位于 `【唯一事件】` 和第一高潮之前。

- [ ] **Step 2: 运行测试并确认失败**

Run: `zsh zhixia-feihualing/tests/test_seedance_poetry_dance_drama_rules.sh`

Expected: FAIL，首先报告缺少《云中君》重制提示词或缺少第一帧空间锚定字段。

### Task 2: 修正规范、模板与生产门禁

**Files:**
- Modify: `zhixia-feihualing/docs/seedance-15s-poetry-dance-drama-standard.md`
- Modify: `zhixia-feihualing/assets/prompts/templates/seedance-15s-poetry-dance-drama.md`
- Modify: `zhixia-feihualing/docs/zhixia-poetry-dance-composer.md`
- Modify: `zhixia-feihualing/docs/production-workflow.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-31-seedance-first-frame-spatial-anchor-design.md`。
- Produces: 项目级第一帧空间锚定规则、前移的可复制模板段和生成前检查。

- [ ] **Step 1: 修改当前规范**

在固定十五秒结构、场景因果、正文顺序和生成前检查中明确：第一帧同时交代承重地面、人物落点、一个固定纵深锚点、视觉象征来源与去向；场景段必须位于事件和时间轴之前；不得新增环境空镜。

- [ ] **Step 2: 修改可复制模板**

在作品定位之后、唯一事件之前增加：

```text
【基础空间与第一帧锚点】
全片发生在〔一个连续空间〕。第一帧同时显示〔承重地面与人物落点〕、〔一个固定纵深锚点〕以及〔唯一视觉象征〕相对栀夏的来源、距离和去向。固定环境不参与特效变化；第一帧直接进入事件，不增加环境空镜。
```

保留后部材质与摄影机段，但删除其承担首次空间定义的职责。

- [ ] **Step 3: 同步组合器和生产流程**

在组合器开场规则和生产流程生成前检查中加入相同门禁，明确全身可见不等于空间清楚。

- [ ] **Step 4: 运行规则测试**

Run: `zsh zhixia-feihualing/tests/test_seedance_poetry_dance_drama_rules.sh`

Expected: 仍因《云中君》重制提示词缺失而 FAIL；规范与模板相关检查已经通过。

### Task 3: 归档《云中君》诗舞剧重制提示词

**Files:**
- Create: `zhixia-feihualing/assets/prompts/jiuge/02-yunzhongjun-poetry-dance-drama-15s.md`

**Interfaces:**
- Consumes: 更新后的项目级规范与模板、九歌 v03 角色母板约束、已经确认的“追出一步—转身让路—尽力目送”单一事件。
- Produces: 不覆盖历史首轮稿、可以继续用于付费前审查的《云中君》15 秒诗舞剧重制提示词。

- [ ] **Step 1: 写入完整提示词**

提示词开头先锁定高山临崖风化石台、石台边缘、下方山谷云海、远山地平线、真实接触阴影和崖外云带来源，再写唯一事件、三个高潮、材质摄影机、声音与禁止项。

- [ ] **Step 2: 保持首帧动作与空间同时成立**

第一帧已能判断栀夏站在坚实石台且云从崖外升起；栀夏处于可发力预备态，0.300 秒内踏步追云，不使用环境空镜。

- [ ] **Step 3: 运行规则测试**

Run: `zsh zhixia-feihualing/tests/test_seedance_poetry_dance_drama_rules.sh`

Expected: PASS，输出 `PASS: Seedance 15-second poetry-dance drama standard is enforced`。

### Task 4: 完整验证与提交

**Files:**
- Verify all files from Tasks 1–3.

**Interfaces:**
- Consumes: 已修改规范、模板、组合器、流程、测试和《云中君》重制稿。
- Produces: 新规则不破坏既有三高潮、舞蹈防跑步化、视觉风格和九歌生成门禁的验证证据。

- [ ] **Step 1: 运行相关验证**

```bash
zsh zhixia-feihualing/tests/test_seedance_poetry_dance_drama_rules.sh
zsh zhixia-feihualing/tests/test_three_equal_climaxes_rules.sh
zsh zhixia-feihualing/tests/test_zhixia_dance_not_running_rules.sh
zsh zhixia-feihualing/tests/test_realistic_visual_style_rules.sh
zsh zhixia-feihualing/tests/test_jiuge_dance_design_rules.sh
git diff --check -- zhixia-feihualing
```

Expected: 所有规则测试通过，`git diff --check` 无输出。

- [ ] **Step 2: 检查改动范围**

Run:

```bash
git status --short -- \
  zhixia-feihualing/docs/seedance-15s-poetry-dance-drama-standard.md \
  zhixia-feihualing/assets/prompts/templates/seedance-15s-poetry-dance-drama.md \
  zhixia-feihualing/docs/zhixia-poetry-dance-composer.md \
  zhixia-feihualing/docs/production-workflow.md \
  zhixia-feihualing/tests/test_seedance_poetry_dance_drama_rules.sh \
  zhixia-feihualing/assets/prompts/jiuge/02-yunzhongjun-poetry-dance-drama-15s.md
```

Expected: 只列出本计划涉及文件；用户已有的其他工作区改动不进入提交。

- [ ] **Step 3: 提交实现**

```bash
git add \
  zhixia-feihualing/docs/seedance-15s-poetry-dance-drama-standard.md \
  zhixia-feihualing/assets/prompts/templates/seedance-15s-poetry-dance-drama.md \
  zhixia-feihualing/docs/zhixia-poetry-dance-composer.md \
  zhixia-feihualing/docs/production-workflow.md \
  zhixia-feihualing/tests/test_seedance_poetry_dance_drama_rules.sh \
  zhixia-feihualing/assets/prompts/jiuge/02-yunzhongjun-poetry-dance-drama-15s.md
git commit -m "修正Seedance第一帧空间锚定规则"
```
