# 栀夏诗境一秒强起势 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将“0.3 秒启动、0.8 秒成势、1 秒进入主体舞段”设为所有尚未生成新诗境的固定开场规则。

**Architecture:** 由自动编舞组合器定义唯一动作语义，视觉规范和生产流程分别同步提示词规则与付费前门禁，静态测试跨文件锁定四个时间节点及反例。既有已生成视频和《惊涛》成片提示词不返工。

**Tech Stack:** Markdown 规范、Zsh 静态校验、ripgrep

## Global Constraints

- 第一帧必须是可发力的蓄势舞姿，不能从自然站立开始。
- 0.3 秒内开始明确踏步或换重，并同步启动大幅上肢或躯干轨迹。
- 0.8 秒内形成第一个脸部可见的完整抓眼舞姿。
- 1.0 秒内离开初始落点，进入主体移动或完整旋转准备。
- 微表情、轻微抬臂、衣料自行摆动和摄影机运动不算舞蹈启动。
- 诗景仍是核心；阿砚不抢开场，不增加特写。
- 最终提示词不得出现项目内部代码。

---

### Task 1: 建立一秒强起势回归测试

**Files:**
- Modify: `tests/test_high_impact_poetry_dance_rules.sh`

**Interfaces:**
- Consumes: 三份全局诗舞规范文件。
- Produces: 跨文件检查四个时间节点、反例和旧规则清除的静态门禁。

- [ ] **Step 1: 写入失败测试**

要求组合器、视觉规范和生产流程均包含“蓄势舞姿”“0.3 秒内”“0.8 秒内”“1.0 秒内”“离开初始落点”，并拒绝旧句“0.5 秒内产生第一个清楚动作”。

- [ ] **Step 2: 运行测试并确认正确失败**

Run: `zsh zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh`
Expected: FAIL，提示缺少一秒强起势规则。

- [ ] **Step 3: 保留失败证据后进入实现**

只在确认失败来自规范尚未实现后修改生产文档，不改弱测试条件。

### Task 2: 同步三份全局规范

**Files:**
- Modify: `docs/zhixia-poetry-dance-composer.md`
- Modify: `docs/realistic-visual-style.md`
- Modify: `docs/production-workflow.md`

**Interfaces:**
- Consumes: 设计稿中的四节点动作契约。
- Produces: 新诗境设计、最终提示词转换和付费生成前检查使用的统一规则。

- [ ] **Step 1: 更新自动编舞组合器**

在固定基线、组合顺序和开场抓眼中写入第一帧蓄势、0.3 秒踏步换重并启动大幅轨迹、0.8 秒完整舞姿、1 秒离点进入主体路线或旋转准备；列出不计入起势的微动作。

- [ ] **Step 2: 更新视觉规范**

把所有新诗境的旧“0.5 秒内第一个动作”替换为四节点动作契约，并明确第一秒动作须顺接诗景、移动路线和摄影机主路径。

- [ ] **Step 3: 更新生产流程与门禁**

在选题检查、输入等级、新诗境舞蹈方式、栀夏优先开场和付费前门禁中采用同一规则；不修改已生成单集。

- [ ] **Step 4: 运行回归测试**

Run: `zsh zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh`
Expected: `PASS: high-impact poetry dance and Ayan fiber rules are enforced`

### Task 3: 记录覆盖关系并完成验证

**Files:**
- Modify: `.cursor/rules/memory-workspace.mdc`

**Interfaces:**
- Consumes: 已通过测试的全局规则。
- Produces: 后续任务可检索的最新稳定结论。

- [ ] **Step 1: 追加专项 Memory 条目**

记录新规则覆盖“0.5 秒内第一个动作”最低标准，但不要求返工既有成片。

- [ ] **Step 2: 检查旧规则残留**

Run: `rg -nF "0.5 秒内产生第一个清楚动作" zhixia-feihualing/docs/zhixia-poetry-dance-composer.md zhixia-feihualing/docs/realistic-visual-style.md zhixia-feihualing/docs/production-workflow.md`
Expected: 无输出。

- [ ] **Step 3: 运行相关测试**

Run: `zsh zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh && zsh zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh`
Expected: 两项均 PASS。

- [ ] **Step 4: 审查差异**

确认只修改本规则涉及的规范、测试、设计、计划和 Memory 新条目，保留工作区其他未提交内容。
