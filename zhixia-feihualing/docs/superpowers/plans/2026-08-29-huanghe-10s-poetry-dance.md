# 《黄河之水天上来》10 秒舞蹈诗境 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将“定式不得早于最后 0.3 秒”写入后续诗境全局规则，并生成《黄河之水天上来》可直接提交 Seedance 2.0 的最终提示词。

**Architecture:** 三份全局制作文档共同承担结尾动作约束；独立提示词检查器通过合法与提前定式样例验证可观察的结尾行为，再检查真实单集提示词。单集目录独立保存事实说明和纯自然语言 Seedance 提示词。本次只影响未来诗境和新单集，不回改已完成的《惊涛》提示词。

**Tech Stack:** Markdown、Zsh、项目规则门禁

## Global Constraints

- 栀夏必须在 1.000 秒内进入主体舞段。
- 后续诗境默认优先持续舞动至画面结束；需要定式时只能在最后 0.300 秒完成。
- 9.700 秒前必须仍有明确脚步、重心、躯干或上肢主动作，不能只靠头发、衣袖、特效或摄影机制造运动感。
- 《黄河之水天上来》选择无定式结尾，最后一帧仍在有效舞动中结束。
- 输入只有栀夏、阿砚两张角色母版和纯文字提示词，不使用状态卡。
- 提示词必须声明两个角色均为项目原创虚构角色，不得出现项目镜头代码、动作代码或模板字段名。
- 阿砚足底至耳尖约 40 厘米，保持外扩纸纤维，不做普通猫毛，不安排特写。

---

### Task 1: 建立延迟定式规则门禁

**Files:**
- Create: `scripts/validate_late_pose_prompt.py`
- Create: `tests/fixtures/late-pose-prompt-valid.txt`
- Create: `tests/fixtures/late-pose-prompt-early-pose.txt`
- Create: `tests/test_late_pose_ending_rules.sh`
- Test: `tests/test_late_pose_ending_rules.sh`

**Interfaces:**
- Consumes: 合法连续结尾样例、8 秒提前定式样例和《黄河之水天上来》最终提示词。
- Produces: `validate_late_pose_prompt.py <prompt-file>`，对第一秒起舞、9.700 秒动作下限、无定式模式和最后一帧运动状态进行验证。

- [x] **Step 1: 写入失败测试**

测试先要求提示词检查器存在，再要求合法连续结尾样例通过、8 秒提前定式样例失败，最后要求真实《黄河》提示词通过。

- [x] **Step 2: 运行测试并确认正确失败**

Run: `zsh tests/test_late_pose_ending_rules.sh`

Expected: FAIL，指出提示词检查器尚不存在。

- [x] **Step 3: 实现提示词检查器**

检查器读取 UTF-8 提示词，要求 1 秒内进入主体舞段、9.700 秒前保持人物主动作、明确无定式模式且最后一帧在运动中结束，并拒绝早于 9.700 秒完成定式、定格或站定。

### Task 2: 更新未来诗境的结尾动作规范

**Files:**
- Modify: `docs/production-workflow.md`
- Modify: `docs/realistic-visual-style.md`
- Modify: `docs/zhixia-poetry-dance-composer.md`
- Test: `tests/test_late_pose_ending_rules.sh`

**Interfaces:**
- Consumes: 已确认的 9.700 秒动作下限和 0.300 秒定式窗口。
- Produces: 后续所有新诗境共同使用的舞蹈结尾默认规则。

- [x] **Step 1: 更新制作流程**

在动作检查和提示词自检段落写明：优先保持有效舞动至切断；若诗意需要定式，只能在最后 0.300 秒完成；10 秒视频在 9.700 秒前不得提前站定。

- [x] **Step 2: 更新写实视觉规则**

把“结尾可以收势或继续舞动”改为可观察时序：收势前必须持续存在脚步、重心、躯干或上肢主动作；头发、衣袖、特效和摄影机运动不能代替人物主动作。

- [x] **Step 3: 更新自动编舞组合器**

在结束方式选择中加入两种合法结果：无定式并在运动中切断；或最后 0.300 秒同步完成定式。组合器不得为封面或展示时长提前留静止段。

### Task 3: 编写《黄河之水天上来》最终提示词

**Files:**
- Create: `episodes/huanghe/README.md`
- Create: `episodes/huanghe/prompts/seedance-v01.md`
- Modify: `operations/dance-design-history.csv`
- Test: `tests/test_late_pose_ending_rules.sh`

**Interfaces:**
- Consumes: 两张角色母版和 `docs/superpowers/specs/2026-08-29-huanghe-10s-poetry-dance-design.md`。
- Produces: 可直接复制到 Seedance 2.0 的中文自然语言提示词。

- [x] **Step 1: 建立单集事实说明**

记录诗句、输入图片映射、场景、舞蹈结构、摄影机路径、阿砚外观、对白计划和“无定式、运动中结束”的本集决定。

- [x] **Step 2: 写入最终提示词**

提示词首句声明双角色为原创虚构角色，随后映射图片 1 栀夏、图片 2 阿砚。正文按 0—1、1—4、4—7、7—10 秒描述高山黄河、逆流舞蹈、真实河雾水滴和单一路径摄影机，并明确 9.700 秒前持续主动作、最后一帧运动中结束。声音只允许无人声国风音乐与环境声。

- [x] **Step 3: 运行规则门禁**

Run: `zsh tests/test_late_pose_ending_rules.sh`

Expected: `PASS: late-pose ending rules and Huanghe prompt are ready`

- [x] **Step 4: 登记舞蹈去重台账**

记录横向疾行回身起袖、赭黄河滩横向推进、跨步翻身行进旋转、贴水侧向平行跟拍、无定式运动中结束，并注明与《惊涛》去重。

### Task 4: 最终验证与提交

**Files:**
- Modify: `docs/superpowers/plans/2026-08-29-huanghe-10s-poetry-dance.md`
- Test: `tests/test_late_pose_ending_rules.sh`

**Interfaces:**
- Consumes: 已通过门禁的全局规则和单集提示词。
- Produces: 可追溯的实现提交与用户可复制提示词。

- [x] **Step 1: 逐项人工复核提示词**

确认没有内部代码、状态卡、动作套路名、无来源天河、额外角色、普通猫毛、提前定式、生成对白或长时间遮脸；确认诗句、角色尺寸和时间边界准确。

- [x] **Step 2: 运行最终验证**

Run: `zsh tests/test_late_pose_ending_rules.sh && git diff --check`

Expected: 门禁 PASS，差异检查无输出，命令退出码为 0。

- [x] **Step 3: 提交实现**

Run:

```bash
git add zhixia-feihualing/docs/production-workflow.md \
  zhixia-feihualing/docs/realistic-visual-style.md \
  zhixia-feihualing/docs/zhixia-poetry-dance-composer.md \
  zhixia-feihualing/docs/superpowers/specs/2026-08-29-huanghe-10s-poetry-dance-design.md \
  zhixia-feihualing/docs/superpowers/plans/2026-08-29-huanghe-10s-poetry-dance.md \
  zhixia-feihualing/scripts/validate_late_pose_prompt.py \
  zhixia-feihualing/tests/fixtures/late-pose-prompt-valid.txt \
  zhixia-feihualing/tests/fixtures/late-pose-prompt-early-pose.txt \
  zhixia-feihualing/tests/test_late_pose_ending_rules.sh \
  zhixia-feihualing/operations/dance-design-history.csv \
  zhixia-feihualing/episodes/huanghe/README.md \
  zhixia-feihualing/episodes/huanghe/prompts/seedance-v01.md
git commit -m "落实舞蹈起止时序并编写黄河诗境提示词"
```

Expected: 只提交延迟定式规则和《黄河之水天上来》相关文件，不包含工作区其他未提交修改。
