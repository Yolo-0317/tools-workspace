# 栀夏固定声音身份 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户确认的栀夏固定声音身份写入角色母版与生产流程，并用回归检查防止后续退回临时“清冷女声”或随集更换基础声线。

**Architecture:** `docs/character-bible.md`作为栀夏声音身份的人读事实源，`docs/production-workflow.md`定义固定基础声线与单集情绪层的使用方式，`config/voices.json`继续只保存当前TTS技术映射且本次不修改。新增zsh规则测试检查长期规范、禁用方向与技术映射边界。

**Tech Stack:** Markdown、JSON、zsh、ripgrep

## Global Constraints

- 栀夏固定为18岁东方少女的自然声线：清透、轻盈、明亮，带少量克制气声和自然书卷气。
- 每集只改变情绪、音量、语速、气息和句尾，不更换基础声线身份。
- 禁止清冷御姐、幼童甜腻、播音主持、机械朗诵、戏曲和夸张古装腔。
- 当前`config/voices.json`中的speaker不因文字设计直接更换；必须经过试听确认才允许改变技术映射。
- 历史音频不追溯替换。
- 不修改与本声音身份无关的用户现有工作区改动。

---

### Task 1: 写入角色母版和生产流程

**Files:**
- Modify: `zhixia-feihualing/docs/character-bible.md`
- Modify: `zhixia-feihualing/docs/production-workflow.md`
- Verify unchanged: `zhixia-feihualing/config/voices.json`

**Interfaces:**
- Consumes: 已确认设计 `docs/superpowers/specs/2026-08-27-zhixia-voice-identity-design.md`和当前speaker ID。
- Produces: 后续单集提示词与TTS导演说明引用的长期声音规则。

- [x] **Step 1: 在角色母版栀夏章节增加“固定声音身份”**

写明固定年龄感、清透轻盈明亮、少量克制气声、自然书卷气、允许变化参数，以及清冷御姐音、幼童音、播音主持与古装腔等禁用方向。明确历史音频不追溯替换。

- [x] **Step 2: 在生产流程声音规范增加双层结构**

写入“固定基础声线＋单集情绪表演层”：固定层来自角色母版；单集层只填写情绪、音量、语速、气息、重音、停顿和句尾。说明未试听确认时不得更换`config/voices.json`中的speaker。

- [x] **Step 3: 核对规范覆盖与speaker未变**

Run:

```bash
rg -n "栀夏固定声音身份|清透、轻盈、明亮|固定基础声线|单集情绪表演层|清冷御姐音|幼童音|播音主持" \
  zhixia-feihualing/docs/character-bible.md \
  zhixia-feihualing/docs/production-workflow.md
jq -r '.zhixia.speaker' zhixia-feihualing/config/voices.json
```

Expected: 所有固定规则均能定位；speaker仍为`zh_female_zhixingnv_uranus_bigtts`。

- [x] **Step 4: 运行既有视觉与特效规则测试**

Run:

```bash
zsh zhixia-feihualing/tests/test_cinematic_vfx_library_rules.sh
zsh zhixia-feihualing/tests/test_realistic_visual_style_rules.sh
```

Expected: both PASS.

- [x] **Step 5: 检查差异边界并提交声音身份落库**

使用`git diff --check`和定向`git status --short`确认格式与范围。只暂存角色母版中新增声音小节、生产流程中新增声音规则和本计划，保留其他既有工作区改动；提交信息使用`固定栀夏角色声音身份`。
