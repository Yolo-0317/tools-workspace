# 同步十秒写实超现实诗境规范 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已确认的 10 秒写实超现实诗境调色、运镜和验收规范同步到长期执行文档。

**Architecture:** `realistic-visual-style.md` 负责所有 Seedance 视频共享的风格与付费生成门禁；`one-character-three-poems-sop.md` 负责每集音频优先、10 秒时间轴和后期工作流。两份文档均链接到专项设计，以避免复制完整镜头库造成规则漂移。

**Tech Stack:** Markdown、ripgrep、git diff。

## Global Constraints

- 默认成片为 10 秒、9:16、一镜到底；两句诗完整朗诵并在最后一个字结束。
- 角色与环境始终电影级高写实CG；运动与空间允许超现实，但不允许瞬移、切镜、结构漂移或无承接换景。
- 默认调色为清透略高饱和、暖冷分层，禁止灰雾脏画面、荧光色和无来源全屏特效。
- 每集只使用一个镜头母题、一个视觉承接物、零或一个辅助特效。
- 先生成真实TTS音频，再根据实际时长安排镜头与字幕；Seedance 永久禁止可辨识人声和中文文字。

---

### Task 1: 更新共享写实风格与生成门禁

**Files:**
- Modify: `docs/realistic-visual-style.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-27-10s-realistic-surreal-poetry-camera-and-color-design.md`。
- Produces: 所有后续 Seedance 提示词可引用的 10 秒视觉基线与生成前检查项。

- [ ] **Step 1: 替换默认低饱和表述**

在全局风格要求中加入“清透略高饱和、暖冷分层、黑位干净”的默认调色，并明确写实材质与超现实位移可以同时成立。

- [ ] **Step 2: 增加十秒镜头与音频优先门禁**

在付费生成前门禁中加入：默认 10 秒、一个 M01—M04 镜头母题、一个视觉承接物、诗句前先生成真实TTS、第一秒钩子与诗句结束收束。

- [ ] **Step 3: 验证共享规则**

```bash
style='docs/realistic-visual-style.md'
rg -q '清透、略高饱和、暖冷分层' "$style"
rg -q '超现实' "$style"
rg -q '10 秒' "$style"
rg -q 'M01—M04' "$style"
rg -q '先生成最终采用的 TTS' "$style"
```

### Task 2: 更新每集诗镜SOP

**Files:**
- Modify: `docs/one-character-three-poems-sop.md`

**Interfaces:**
- Consumes: 10 秒标准节奏与长期 TTS 工作流。
- Produces: 每集按真实音频时长写 10 秒分镜、提示词与验收的操作顺序。

- [ ] **Step 1: 写入默认十秒节奏**

新增或更新时间轴说明：0—2.4 秒为钩子与两句极短互动，2.4 秒后完整朗诵两句诗，最后一个字结束；实际节点以音频时长重排。

- [ ] **Step 2: 写入镜头母题与调色引用**

要求每集在生成前选择 M01—M04 的一个母题与一个视觉承接物；将调色、写实与超现实边界链接到专项设计文档。

- [ ] **Step 3: 验证SOP规则**

```bash
sop='docs/one-character-three-poems-sop.md'
rg -q '10 秒' "$sop"
rg -q '0—2.4 秒' "$sop"
rg -q 'M01—M04' "$sop"
rg -q '最后一个字' "$sop"
rg -q '2026-08-27-10s-realistic-surreal-poetry-camera-and-color-design.md' "$sop"
git diff --check -- "$sop" docs/realistic-visual-style.md
```

### Task 3: 提交同步文档

**Files:**
- Create: `docs/superpowers/plans/2026-08-27-sync-10s-realistic-surreal-poetry-standard.md`
- Modify: `docs/realistic-visual-style.md`
- Modify: `docs/one-character-three-poems-sop.md`

- [ ] **Step 1: 检查没有占位内容**

```bash
! rg -n '[T]ODO|[T]BD|待定' \
  docs/superpowers/plans/2026-08-27-sync-10s-realistic-surreal-poetry-standard.md \
  docs/realistic-visual-style.md \
  docs/one-character-three-poems-sop.md
```

- [ ] **Step 2: 提交文档**

```bash
git add docs/realistic-visual-style.md docs/one-character-three-poems-sop.md \
  docs/superpowers/plans/2026-08-27-sync-10s-realistic-surreal-poetry-standard.md
git commit -m '同步十秒诗境写实超现实规范'
```
