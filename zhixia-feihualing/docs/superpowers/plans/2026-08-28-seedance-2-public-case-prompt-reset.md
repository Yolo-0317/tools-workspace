# Seedance 2.0 公开案例导向提示词重建实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将栀夏诗境的默认视频提示词规范改成“单一视觉事件、三段自然过程、一条摄影机路径”，并从空白结构重写白雪 10 秒 Seedance 2.0 提示词。

**Architecture:** 全局规范负责定义可复制提示词的六段结构与最低约束；白雪 README 只保存单集画面事实；`seedance-v01.md` 只保存两张母版输入说明和新的可复制正文。静态测试同时验证新版必须项与旧框架禁入项，防止毫秒轴、唯一雪花和内部代码回流。

**Tech Stack:** Markdown、Zsh、ripgrep、Git。

## Global Constraints

- Seedance 2.0，9:16 竖屏，10 秒，一镜到底。
- 只上传栀夏与阿砚两张原创角色母版，不上传状态卡、首帧图、场景图或动作参考视频。
- 提示词第一句固定声明两名角色均为本项目原创虚构数字角色，并立即完成参考图映射。
- 栀夏是第一视觉主体，并产生开场第一个清楚可见的动作。
- 阿砚足底至耳尖约 40 厘米，保持双耳、四足、单尾、朱砂额印与纸墨材质。
- 舞蹈只限定：`中国古典舞身韵、轻盈克制、连续自然、不遮脸`；具体动作、连接与收势由 Seedance 自由发挥。
- 对白、诗句、字幕与精确口型均不交给视频模型。
- 最终提示词不得出现项目内部代码、资产路径、状态卡术语、唯一引导雪花或逐毫秒音频节点。
- 不调用 Seedance，不生成图片、视频或付费素材。

---

### Task 1: 用静态测试锁定新版边界

**Files:**
- Modify: `zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh`
- Modify: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

**Interfaces:**
- Consumes: 已确认设计 `docs/superpowers/specs/2026-08-28-seedance-2-public-case-prompt-reset-design.md`。
- Produces: 一组验证全局规范、白雪 README 和最终提示词的新结构门禁。

- [ ] **Step 1: 将旧版正向断言改成新版正向断言**

在 `test_zhixia_first_opening_rules.sh` 中要求以下语义：

```zsh
for phrase in \
  "单一视觉事件" \
  "三个宽时间段" \
  "一条连续摄影机路径" \
  "自然因果关系"; do
  rg -qF "$phrase" "$style"
done

for phrase in \
  "0—3 秒" \
  "3—8 秒" \
  "8—10 秒" \
  "枝头粉雪自然落下" \
  "摄影机始终位于栀夏正面偏侧" \
  "阿砚足底至耳尖约40厘米"; do
  print -r -- "$prompt_block" | rg -qF "$phrase"
done
```

- [ ] **Step 2: 增加旧框架禁入断言**

```zsh
if print -r -- "$prompt_block" | rg -n \
  '(^|[^[:alnum:]])[MHDS][0-9]{2}([^[:alnum:]]|$)|唯一雪花|唯一引导雪花|无声.*口型|[0-9]+\.[0-9]{3}—[0-9]+\.[0-9]{3}|assets/|\.png|\.jpg|状态图'; then
  exit 1
fi
```

同时把 `test_classical_dance_library_rules.sh` 对白雪 README 的 `M04`、`H05`、`一片真实雪花`、`最终 10 秒音画时间轴` 断言，替换成“三段自然过程”“一条摄影机路径”“枝头粉雪自然落下”“梨花般的视觉联想”。

- [ ] **Step 3: 运行测试确认 RED**

Run:

```bash
zsh tests/test_zhixia_first_opening_rules.sh
zsh tests/test_classical_dance_library_rules.sh
```

Expected: 两个脚本至少一个退出码非零，因为现有规范、README 和提示词仍使用唯一雪花与毫秒级旧结构。

- [ ] **Step 4: 检查测试脚本格式**

Run: `zsh -n tests/test_zhixia_first_opening_rules.sh tests/test_classical_dance_library_rules.sh`

Expected: exit code 0。

---

### Task 2: 更新全局提示词规范与工作流

**Files:**
- Modify: `zhixia-feihualing/docs/realistic-visual-style.md`
- Modify: `zhixia-feihualing/docs/production-workflow.md`
- Modify: `.cursor/rules/memory-workspace.mdc`

**Interfaces:**
- Consumes: Task 1 的全局规范断言。
- Produces: 后续未生成诗境统一遵循的 Seedance 2.0 提示词结构。

- [ ] **Step 1: 在视觉规范中建立新版默认结构**

把新诗境默认规则改写为以下语义：

```markdown
每条最终提示词围绕一个可观察的视觉事件，只使用三个宽时间段和一条连续摄影机路径。主体动作必须引发可见的环境结果，环境结果再完成诗意揭示，形成自然因果关系。不得为了匹配后期 TTS 把画面拆成逐毫秒节点。
```

删除或降级与新版冲突的强制要求：付费长视频必须上传场景卡、至少一次方向变化、一个 Hxx 主特效、唯一视觉承接物、风险节点逐段身份重锚、10 秒固定互动与朗诵画面节点。

- [ ] **Step 2: 在工作流中把三层旧框架替换成六段可复制结构**

写明顺序：原创声明与图片映射、基础画面条件、三个宽时间段、一条摄影机路径、最短角色稳定约束、声音和高风险禁止项。输入文件路径、内部编号、生产状态与验收说明不得复制进模型正文。

- [ ] **Step 3: 在项目记忆中记录规则替代关系**

在现有“单状态卡 + Seedance 自由舞蹈”条目后增加同日条目，明确：

```markdown
- 新版默认使用单一视觉事件、三个宽时间段、一条连续摄影机路径和自然因果链。
- 旧版九段毫秒轴、唯一雪花、复杂身份重锚和内部镜头/特效框架仅作历史记录，不得作为新提示词模板。
- 只提供两张角色母版时，不要求精确口型或严格对齐每句 TTS。
```

- [ ] **Step 4: 运行全局规则检查**

Run: `zsh tests/test_zhixia_first_opening_rules.sh`

Expected: 仍然 FAIL，但全局规范相关断言已经通过，失败位置转移到白雪 README 或最终提示词。

---

### Task 3: 重建白雪单集事实源与最终提示词

**Files:**
- Modify: `zhixia-feihualing/episodes/baixue/README.md`
- Modify: `zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md`

**Interfaces:**
- Consumes: Task 2 的六段提示词结构和全局约束。
- Produces: 可直接复制到 Seedance 2.0 的白雪新版正文。

- [ ] **Step 1: 重写白雪 README 的画面事实**

保留诗句、双角色身份、两张母版输入、后期声音分工和生成门禁。删除 M04、H05、唯一雪花、无声口型画面安排和逐毫秒音画轴，替换为：

```markdown
0—3 秒：开场立即看见栀夏正面偏侧中景，她先动建立形象，阿砚在身侧雪地保持约 40 厘米体型。
3—8 秒：栀夏自然进入舞蹈，衣袖带起的轻风和脚步震动使附近松枝上的粉雪自然落下。
8—10 秒：逆光穿过落雪，覆雪枝梢形成梨花般的视觉联想；栀夏正面偏侧自然收势，阿砚安静注视。
```

- [ ] **Step 2: 清空并重写 Seedance 可复制正文**

正文必须从固定原创声明开始，并按六段结构重新写作。三个宽时间段使用 `0—3 秒`、`3—8 秒`、`8—10 秒`；镜头只使用“摄影机始终位于栀夏正面偏侧，平滑侧向跟随，并在同一运动中逐渐增加距离”。

角色约束只保留一次：栀夏身份与完整身体；阿砚约 40 厘米、双耳四足单尾、朱砂额印、纸墨材质。雪的因果链只写一次：动作与脚步引起枝头粉雪落下，逆光形成梨花联想。

- [ ] **Step 3: 保留 Markdown 外层生产说明**

保留两张母版上传说明、后期对白字幕说明、付费生成门禁和 `SEEDANCE_PROMPT_START/END` 边界。删除“已验收状态卡”对新正文的影响，不把本地资产路径复制到可复制正文。

- [ ] **Step 4: 运行专项测试确认 GREEN**

Run:

```bash
zsh tests/test_zhixia_first_opening_rules.sh
zsh tests/test_classical_dance_library_rules.sh
zsh tests/test_baixue_10s_assets.sh
```

Expected: 三个脚本全部 PASS。音频测试继续验证后期 TTS 和字幕资产未被改变。

---

### Task 4: 完整验证与提交

**Files:**
- Verify: `.cursor/rules/memory-workspace.mdc`
- Verify: `zhixia-feihualing/docs/realistic-visual-style.md`
- Verify: `zhixia-feihualing/docs/production-workflow.md`
- Verify: `zhixia-feihualing/episodes/baixue/README.md`
- Verify: `zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md`
- Verify: `zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh`
- Verify: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

**Interfaces:**
- Consumes: Tasks 1—3 的全部修改。
- Produces: 已验证、可审阅的最终变更集。

- [ ] **Step 1: 搜索旧框架残留**

Run:

```bash
sed -n '/<!-- SEEDANCE_PROMPT_START -->/,/<!-- SEEDANCE_PROMPT_END -->/p' episodes/baixue/prompts/seedance-v01.md | rg -n '唯一雪花|唯一引导雪花|无声.*口型|[0-9]+\.[0-9]{3}—[0-9]+\.[0-9]{3}|(^|[^[:alnum:]])[MHDS][0-9]{2}([^[:alnum:]]|$)|状态图|assets/'
```

Expected: 无输出，退出码 1。

- [ ] **Step 2: 运行相关测试与格式检查**

Run:

```bash
zsh tests/test_zhixia_first_opening_rules.sh
zsh tests/test_classical_dance_library_rules.sh
zsh tests/test_baixue_10s_assets.sh
git diff --check
```

Expected: 三项测试 PASS；`git diff --check` 无输出。

- [ ] **Step 3: 审阅变更边界**

Run: `git status --short && git diff --stat && git diff -- zhixia-feihualing/docs/realistic-visual-style.md zhixia-feihualing/docs/production-workflow.md zhixia-feihualing/episodes/baixue/README.md zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

Expected: 只包含本计划文件与用户已有的无关工作；不得提交 `.env`、股票文章素材或无关 Memory 修改。

- [ ] **Step 4: 分别提交计划与实现**

```bash
git add zhixia-feihualing/docs/superpowers/plans/2026-08-28-seedance-2-public-case-prompt-reset.md
git commit -m "文档：制定Seedance提示词重建计划"
```

实现提交只暂存本任务文件；`.cursor/rules/memory-workspace.mdc` 若含用户其他未提交修改，使用局部暂存，避免把无关段落带入提交：

```bash
git add zhixia-feihualing/docs/realistic-visual-style.md zhixia-feihualing/docs/production-workflow.md zhixia-feihualing/episodes/baixue/README.md zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh zhixia-feihualing/tests/test_classical_dance_library_rules.sh
git commit -m "规范：重建Seedance诗境提示词框架"
```

Expected: 两次中文提交成功；无关工作仍留在工作区。
