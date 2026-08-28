# Seedance Evidence-Tiered Prompt Rules Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 80 条公开案例支持的输入分级、有限自由舞蹈和动作触发运镜规则，替换当前全局规范中过度放任舞蹈与过度限制摄影机的旧结论。

**Architecture:** `docs/realistic-visual-style.md` 继续作为视觉与视频提示词事实源，`docs/production-workflow.md` 负责把规则变成生成步骤和门禁，舞蹈库只保留历史边界。新增一个独立静态检查保护新版核心语义，现有测试拆分“全局规范断言”和“《白雪》旧草案事实检查”，Memory 只追加覆盖关系且不纳入已有无关改动。

**Tech Stack:** Markdown、Zsh/Bash、`rg`、Git。

## Global Constraints

- 默认输入继续是栀夏与阿砚两张原创角色母版加纯文字。
- 基础级、控制级、迁移级三种输入方式必须分别写明适用范围和能力边界。
- “中国古典舞身韵、轻盈克制、连续自然、不遮脸”只作为气质边界，不再作为完整舞蹈指令。
- 基础级舞句必须包含移动或脚步、重心变化、方向或高低层次、上肢与衣料反馈、起止状态。
- 不恢复 Dxx 动作编号、固定动作名称、精确角度或逐拍自创编舞。
- 一镜到底使用一条主路径，并允许最多两次由主体动作或环境事件触发的摄影机反应。
- 镜头契约必须写明起始景别与机位、主路径与速度、视差参照、动作反应和结尾揭示。
- 栀夏首帧可辨认，0.5 秒内第一个清楚动作来自栀夏。
- 阿砚足底至耳尖约 40 厘米，保持双耳、四足、单尾、朱砂额印、琥珀眼、纸墨身体和暖金纹样。
- 原创虚拟角色声明、参考素材唯一职责、声音后期边界和项目内部代码禁令继续保留。
- 三个宽时间段从强制格式降为复杂十秒事件的推荐工具；逐毫秒 TTS 轴继续禁用。
- 本计划不修改《白雪》最终提示词、角色圣经、角色母版、案例库、已发布视频、TTS 或字幕。
- 用户可见文档禁止 emoji。

---

### Task 1: 新版全局规则回归门槛

**Files:**
- Create: `zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh`

**Interfaces:**
- Consumes: 设计文档 `docs/superpowers/specs/2026-08-28-seedance-evidence-tiered-prompt-rules-rewrite-design.md`。
- Produces: 一个运行真实规范文件的静态检查，要求输入三级、舞蹈五项、镜头契约、开场与声音边界存在，并拒绝旧“完全自由发挥”“固定六段”“三个宽时间段强制化”表述。

- [ ] **Step 1: 写入会失败的新版规则检查**

创建 Zsh 脚本并以 `set -euo pipefail` 开头。检查 `realistic-visual-style.md` 和 `production-workflow.md` 同时包含“基础级”“控制级”“迁移级”“移动或脚步”“重心变化”“方向或高低层次”“上肢与衣料反馈”“起止状态”“最多两次”“视差”“动作触发反应”“0.5 秒内”和“约 40 厘米”。检查全局规范不再包含“舞蹈约束完整且仅为”“具体动作、连接与收势由 Seedance 自由发挥”“最终提示词固定使用六段结构”。

- [ ] **Step 2: 运行检查并确认旧规范失败**

Run: `zsh zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh`

Expected: FAIL，首个缺失项应是“基础级”或另一个新版输入分级词，而不是脚本语法错误。

- [ ] **Step 3: 保留失败检查进入后续实现**

失败检查暂不单独提交，避免仓库停留在已知红灯状态；Task 3 达到 GREEN 后与正式规范一起提交。

### Task 2: 重写视觉规范中的 Seedance 核心规则

**Files:**
- Modify: `zhixia-feihualing/docs/realistic-visual-style.md`
- Test: `zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh`

**Interfaces:**
- Consumes: Task 1 的目标短语与设计文档。
- Produces: 全局事实源中的输入三级、有限自由舞蹈、摄影机契约、可裁剪语义顺序和旧规则兼容边界。

- [ ] **Step 1: 替换“Seedance 2.0 当前提示词默认结构”**

把固定“单一事件 + 三个宽时间段 + 一条不变运镜 + 六个连续部分”改为：一个核心视觉事件；复杂事件推荐三个宽时间段，简单事件允许自然顺序；正文按原创映射、画面条件、事件、输入等级与动作、摄影机契约、物理声音约束的语义顺序自然书写并删除无关块。

- [ ] **Step 2: 写入输入控制三级**

在人物/角色规则之前加入基础级、控制级、迁移级。明确两张角色母版只锁身份；动作分镜、场景图和参考视频各自的唯一职责；复杂编舞和严格卡点必须升级输入，不靠增加文字长度解决。

- [ ] **Step 3: 替换完全自由舞蹈规则**

删除“舞蹈约束完整且仅为”和“具体动作、连接与收势由 Seedance 自由发挥”。写入五项可观察条件及默认短舞句示例；保留模型在条件内自然连接动作，不指定动作名、角度或逐拍编舞。

- [ ] **Step 4: 重写摄影规则**

保留一条主路径，新增起点、位置、方向、速度、前景/地面/背景视差、最多两次动作触发反应和结尾揭示。允许小幅推近、后拉、降低、升高、有限弧移及短暂速度变化，但每次必须有主体动作或环境事件作为原因。

- [ ] **Step 5: 保留角色、声音和内部代码边界**

确认原创声明仍为第一句；栀夏首帧可辨认且 0.5 秒内先动；阿砚约 40 厘米；对白、诗句、字幕和精确口型留给后期；项目内部代码、路径、版本号和状态卡编号不进入模型正文。

- [ ] **Step 6: 运行新版检查并观察剩余失败**

Run: `zsh zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh`

Expected: 仍 FAIL，因为 `production-workflow.md` 尚未同步，但 `realistic-visual-style.md` 的新版字段检查通过。

- [ ] **Step 7: 保留视觉规范进入工作流同步**

视觉规范暂不单独提交，因为跨文件检查仍处于预期失败；Task 3 同步工作流并达到 GREEN 后统一提交。

### Task 3: 同步生产流程和舞蹈历史边界

**Files:**
- Modify: `zhixia-feihualing/docs/production-workflow.md`
- Modify: `zhixia-feihualing/docs/zhixia-classical-dance-library.md`
- Test: `zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh`

**Interfaces:**
- Consumes: Task 2 的全局事实源。
- Produces: 生成前可操作的输入选择、提示词编写顺序、动作复杂度升级条件和镜头检查。

- [ ] **Step 1: 替换固定六段工作流**

将“最终提示词固定使用六段结构”改为“按六类语义自然组织并删除无关项”。复杂十秒事件可用三个宽时间段，单一连续动作不强制分段，任何场景都不得恢复逐毫秒 TTS 节点。

- [ ] **Step 2: 增加生成前输入等级选择**

在视频生成步骤中要求先选择基础级、控制级或迁移级，并为每级写出上传素材、允许目标和需要主动放弃的精度。

- [ ] **Step 3: 更新生成前舞蹈检查**

把旧“四项约束 + 完全自由”改为五项可观察身体条件；检查人物没有全程原地摆臂。如果需要动作顺序、跳跃或严格卡点，检查是否已有动作分镜、授权视频或音频参考。

- [ ] **Step 4: 更新生成前摄影检查**

检查一条主路径、起始景别、相对方位、速度、视差参照、最多两次有原因的反应和最终揭示；拒绝无因运镜术语堆叠和绕到栀夏背面。

- [ ] **Step 5: 更新舞蹈库首页边界**

明确 Dxx 条目只作历史与动作研究，不是新提示词默认清单；新版不使用动作编号，也不完全放任动作，而是按全局规范写五项可观察条件或升级参考输入。

- [ ] **Step 6: 运行新版检查并确认通过**

Run: `zsh zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh`

Expected: PASS。

- [ ] **Step 7: 提交工作流与历史边界**

```bash
git add zhixia-feihualing/docs/realistic-visual-style.md zhixia-feihualing/docs/production-workflow.md zhixia-feihualing/docs/zhixia-classical-dance-library.md zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh
git commit -m "规范：重写Seedance证据分级生成规则"
```

### Task 4: 调整既有测试的全局与单集边界

**Files:**
- Modify: `zhixia-feihualing/tests/test_realistic_visual_style_rules.sh`
- Modify: `zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh`
- Modify: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`
- Test: all four Seedance-related rule tests.

**Interfaces:**
- Consumes: Tasks 2–3 的正式规范；《白雪》现有提示词保持不变。
- Produces: 全局测试断言新版规则，单集测试只验证《白雪》当前草案事实，不再反向定义全局默认。

- [ ] **Step 1: 运行既有测试并记录预期失败**

Run: `zsh zhixia-feihualing/tests/test_realistic_visual_style_rules.sh && zsh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh && zsh zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

Expected: 至少一个测试因仍查找“固定六段”或“完全自由发挥”旧全局短语而 FAIL。

- [ ] **Step 2: 更新视觉规范断言**

将旧“一条连续摄影机路径”“不强制方向变化”等断言换成“一条主路径”“动作触发反应”“最多两次”“视差”和“复杂事件推荐三个宽时间段”。继续检查电影级写实、角色持续可辨和付费生成门禁。

- [ ] **Step 3: 更新开场测试的全局部分**

继续检查原创声明、栀夏首帧与 0.5 秒开场、内部代码禁令；把“固定六段”“三个宽时间段强制”和“不变摄影机路径”换成新版语义顺序和摄影机契约。保留对《白雪》现有 prompt block 的事实检查，并在注释中说明它待下一步重写。

- [ ] **Step 4: 更新舞蹈测试的全局部分**

全局规范与舞蹈库改为检查五项可观察条件、有限自由和升级输入；对《白雪》现有文件仍检查其旧四项短语与不含 Dxx，明确这是旧草案兼容测试。

- [ ] **Step 5: 运行四项测试**

Run: `zsh zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh && zsh zhixia-feihualing/tests/test_realistic_visual_style_rules.sh && zsh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh && zsh zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

Expected: 四项全部 PASS。

- [ ] **Step 6: 提交测试调整**

```bash
git add zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh zhixia-feihualing/tests/test_realistic_visual_style_rules.sh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh zhixia-feihualing/tests/test_classical_dance_library_rules.sh
git commit -m "测试：同步Seedance新版全局规范"
```

### Task 5: 追加项目 Memory 覆盖关系

**Files:**
- Modify: `.cursor/rules/memory-workspace.mdc`

**Interfaces:**
- Consumes: 已提交的设计、正式规范和测试结果。
- Produces: 一条 2026-08-28 稳定结论，明确新版覆盖当天早先的“完全自由舞蹈”和“只能单一摄影机运动”结论。

- [ ] **Step 1: 重新检查既有未提交差异**

Run: `git diff -- .cursor/rules/memory-workspace.mdc`

Expected: 仍可见用户已有的“公众号典籍专栏网页写稿”等无关差异；不得覆盖或删除。

- [ ] **Step 2: 使用最小补丁追加 Seedance 条目**

在现有 Seedance 2026-08-28 条目之后追加“证据分级提示词规范”章节，记录输入三级、舞蹈五项可观察条件、主路径加最多两次动作反应、复杂事件才推荐三个宽时间段，以及《白雪》待单独重写。

- [ ] **Step 3: 验证 Memory 新旧覆盖表述**

Run: `rg -n "证据分级提示词规范|基础级|控制级|迁移级|最多两次动作" .cursor/rules/memory-workspace.mdc`

Expected: 新章节包含四项关键词，并明确覆盖当日较早规则。

- [ ] **Step 4: 只暂存新增 Memory hunk**

Run: `git add -p .cursor/rules/memory-workspace.mdc`

Expected: 只选择本计划新增的 Seedance hunk；拒绝用户已有“公众号典籍专栏网页写稿”hunk。暂存后使用 `git diff --cached -- .cursor/rules/memory-workspace.mdc` 核对，未暂存差异仍由 `git diff -- .cursor/rules/memory-workspace.mdc` 保留。

- [ ] **Step 5: 提交 Memory 新增 hunk**

```bash
git commit -m "记忆：更新Seedance证据分级提示词规则"
```

### Task 6: 全量验证与交付

**Files:**
- Verify: `zhixia-feihualing/docs/realistic-visual-style.md`
- Verify: `zhixia-feihualing/docs/production-workflow.md`
- Verify: `zhixia-feihualing/docs/zhixia-classical-dance-library.md`
- Verify: `.cursor/rules/memory-workspace.mdc`
- Verify: four Seedance-related test scripts.

**Interfaces:**
- Consumes: Tasks 1–5 的全部变更。
- Produces: 可回归验证的新全局规范；《白雪》和已有无关工作区改动保持原样。

- [ ] **Step 1: 运行全部相关规则测试**

Run: `zsh zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh && zsh zhixia-feihualing/tests/test_realistic_visual_style_rules.sh && zsh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh && zsh zhixia-feihualing/tests/test_classical_dance_library_rules.sh && bash zhixia-feihualing/tests/test_seedance_case_library_rules.sh`

Expected: 五项全部 PASS。

- [ ] **Step 2: 检查旧全局绝对句式退场**

Run: `if rg -n "舞蹈约束完整且仅为|具体动作、连接与收势由 Seedance 自由发挥|最终提示词固定使用六段结构" zhixia-feihualing/docs/realistic-visual-style.md zhixia-feihualing/docs/production-workflow.md; then exit 1; fi`

Expected: 无输出，退出码 0。

- [ ] **Step 3: 检查《白雪》未被修改**

Run: `git status --short -- zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md`

Expected: 无输出。

- [ ] **Step 4: 检查格式和变更范围**

Run: `git diff --check HEAD~3..HEAD -- zhixia-feihualing/docs zhixia-feihualing/tests .cursor/rules/memory-workspace.mdc`

Expected: 无输出，退出码 0。

Run: `git status --short`

Expected: 用户已有 `.cursor/rules/memory-python.mdc`、`memory-workspace.mdc` 未暂存部分及其他目录内容仍保留；本计划目标文件没有未提交差异。

- [ ] **Step 5: 汇报提交和后续边界**

列出本计划提交、五项验证结果和关键规则变化；明确《白雪》仍需下一步按新版单独重写，不在本轮声称它已经符合新规范。
