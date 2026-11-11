# 栀夏 15 秒舞蹈三次同强度高潮 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已确认的“15 秒三次同等强度高潮”规范落实到自动编舞器、视觉规范、生产流程、历史台账与自动测试中。

**Architecture:** 以 `zhixia-poetry-dance-composer.md` 作为编舞真源，`realistic-visual-style.md` 与 `production-workflow.md` 只同步面向生产和验收的规则。历史 CSV 在原 20 列后追加 5 个三高潮序列字段，旧行保留原值并补空列，保证现有按字段名读取的集数测试继续工作。

**Tech Stack:** Markdown、CSV、Zsh、ripgrep、awk、现有 shell 测试套件。

## Global Constraints

- 新规则只用于新设计或尚未生成的 15 秒舞蹈；已确认、生成或发布的视频不追溯重做。
- 15 秒内必须有三次同等强度高潮，分别形成纵向、横向和纵深主导差异。
- 第一高潮不晚于 1.800 秒，第二高潮位于 4.800—7.000 秒，第三高潮位于 10.000—13.000 秒，13.000—15.000 秒保持高能量余势。
- 每次高潮必须同时具备身体发力、轮廓变化、空间变化、承接物轨迹和镜头反馈。
- 全片只使用一个核心自然元素或视觉机制，以及一条摄影机主路径。
- 三次高潮不得用同一连续旋转、特效爆发、抖镜头、普通走路、持续奔跑或站立等待凑数。
- 10 秒视频继续允许一个主高潮，不强制套用三高潮时间结构。
- 旧历史记录不回填、不改写；新增字段允许旧行留空。

---

### Task 1: 建立三高潮回归测试

**Files:**
- Create: `zhixia-feihualing/tests/test_three_equal_climaxes_rules.sh`
- Modify: `zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh`
- Modify: `zhixia-feihualing/tests/test_choreography_diversity_v2_rules.sh`

**Interfaces:**
- Consumes: 编舞器、视觉规范、生产流程和历史 CSV 的文本结构。
- Produces: 可执行测试，检查三高潮时间、五项判定、三方向、单一特效、单一运镜和 25 列兼容台账。

- [x] **Step 1: 新建失败测试**

新测试逐文件要求以下短语：`15 秒三次同等强度高潮`、`0.000—1.800 秒`、`4.800—7.000 秒`、`10.000—13.000 秒`、`13.000—15.000 秒`、`纵向、横向和纵深`、`身体发力`、`轮廓变化`、`空间变化`、`承接物轨迹`、`镜头反馈`、`一个核心自然元素`、`一条摄影机主路径`、`不追溯重做`。

新测试固定台账表头为：

```text
episode,poem,opening,movement,climax_family,rotation,body_level,opening_silhouette,arm_path,leg_silhouette,carrier,carrier_shape,effect,effect_shape,climax_window,camera_reaction,camera_climax,ending,status,notes,peak_sequence,peak_directions,peak_windows,carrier_trajectories,camera_peak_reactions
```

并使用 `awk -F,` 验证所有行均为 25 列、旧 20 个字段继续存在。

- [x] **Step 2: 运行新测试确认失败**

Run:

```bash
zsh zhixia-feihualing/tests/test_three_equal_climaxes_rules.sh
```

Expected: FAIL，首先报告编舞器缺少 `15 秒三次同等强度高潮` 或台账表头仍为 20 列。

- [x] **Step 3: 更新旧测试的兼容表头**

把两个旧测试中的 20 列 `expected_header` 更新为 25 列；保留旧字段完整性断言，并把 `NF != 20` 更新为 `NF != 25`，不要求旧行的新增字段非空。

### Task 2: 实现三高潮编舞规则与兼容台账

**Files:**
- Modify: `zhixia-feihualing/docs/zhixia-poetry-dance-composer.md`
- Modify: `zhixia-feihualing/docs/realistic-visual-style.md`
- Modify: `zhixia-feihualing/docs/production-workflow.md`
- Modify: `zhixia-feihualing/operations/dance-design-history.csv`
- Test: `zhixia-feihualing/tests/test_three_equal_climaxes_rules.sh`
- Test: `zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh`
- Test: `zhixia-feihualing/tests/test_choreography_diversity_v2_rules.sh`
- Test: `zhixia-feihualing/tests/test_zhixia_dance_not_running_rules.sh`
- Test: `zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh`

**Interfaces:**
- Consumes: 已确认设计规范和 Task 1 的失败测试。
- Produces: 面向所有未来 15 秒提示词的三高潮编舞真源，以及兼容旧记录的 25 列台账。

- [x] **Step 1: 修改自动编舞器**

加入独立的“15 秒三次同等强度高潮”章节，明确五段时间结构、五项合格判定、纵向/横向/纵深差异、进入/发展/离开、单一自然元素三次差异响应、同一主路径三次镜头反馈、13—15 秒余势和失败降级。把自动组合顺序与最终提示词转换改为 15 秒选三种高潮动作链，10 秒仍选一个主高潮。

- [x] **Step 2: 同步视觉规范和生产流程**

在两个文档中加入同样的 15 秒硬门槛与验收标准；把“最多两次动作触发反应”明确限定为 10 秒结构，15 秒允许沿同一主路径的三次高潮反应。

- [x] **Step 3: 扩展历史台账**

在原表头后追加 `peak_sequence`、`peak_directions`、`peak_windows`、`carrier_trajectories`、`camera_peak_reactions`。每个旧行末尾追加五个空字段，不改变原 20 列内容。

- [x] **Step 4: 运行定向测试**

Run:

```bash
zsh zhixia-feihualing/tests/test_three_equal_climaxes_rules.sh
zsh zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh
zsh zhixia-feihualing/tests/test_choreography_diversity_v2_rules.sh
zsh zhixia-feihualing/tests/test_zhixia_dance_not_running_rules.sh
zsh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
```

Expected: 五项测试全部输出 `PASS` 并以 0 退出。

- [x] **Step 5: 运行相关测试集合**

运行所有引用编舞器或舞蹈历史台账的测试脚本。Expected: 全部以 0 退出；旧集数仍按原字段读取，不要求追溯改写提示词。

- [x] **Step 6: 检查差异与提交**

运行 `git diff --check`，确认只修改本计划列出的规则、台账与测试；使用中文提交信息：

```bash
git commit -m '实施十五秒舞蹈三次同强度高潮规则'
```
