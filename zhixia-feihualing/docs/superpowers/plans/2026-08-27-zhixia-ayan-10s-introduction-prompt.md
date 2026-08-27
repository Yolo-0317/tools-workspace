# 栀夏与阿砚 10 秒庭院出场提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保存一份可直接投喂 Seedance 的 10 秒双角色庭院出场主提示词，并让它可由既定门禁审阅。

**Architecture:** 提示词正文只描述 Seedance 负责的高写实CG画面、无人声音乐、环境声与无声表演；后期对白和文字独立列在正文之后。正文使用标记区间区分可复制内容，并以六段固定结构承载角色映射、永久门禁、场景、运镜、时间轴和结尾禁止项。

**Tech Stack:** Markdown、Seedance 2.0 提示词、ripgrep、git diff。

## Global Constraints

- 输入主卡固定为 `assets/characters/栀夏角色卡高写实CG-v03.png` 与 `assets/characters/阿砚角色卡高写实CG-v01.png`。
- Seedance 正文首段必须说明“原创虚构数字角色”，且不得出现“真人、真人演员、真人照片、真人实拍”。
- 正文前部和结尾各锁定一次永久无人声；不得出现实际对白或诗句原文。
- 画面仅有花冠微距拉远、袖纱连续遮镜、阿砚两次起跳的单一镜头链；不得生成字幕、文字、Logo 或水印。
- 角色、服装、发冠与阿砚结构的验收按 `docs/superpowers/specs/2026-08-27-zhixia-ayan-10s-introduction-prompt-and-gates-design.md` 执行。

---

### Task 1: 创建可投喂的 v03 主提示词

**Files:**
- Create: `episodes/yesu-shansi/prompts/zhixia-ayan-introduction-v03.md`

**Interfaces:**
- Consumes: 两张当前输入主卡和已确认的 10 秒庭院出场设计。
- Produces: `SEEDANCE_PROMPT_START` 与 `SEEDANCE_PROMPT_END` 之间可直接复制的 Seedance 文本，以及正文外的后期对白、字幕与抽帧验收表。

- [ ] **Step 1: 写入六段固定结构**

在可复制正文中依次写入参考映射、永久门禁、场景材质、唯一运镜、0—10 秒时间轴、结尾禁止项与输出规格。时间轴必须明确 8.8 秒起稳定双角色构图，阿砚跃至镜头前方约 0.8 米处，袖纱后 0.2 秒内出现青石与砚案。

- [ ] **Step 2: 写入后期分工**

在正文标记之外写明：1.35—3.35 秒由栀夏后期配“水晶帘动微风起，栀夏。”；4.85—6.55 秒由阿砚后期配“黑云翻墨未遮山，阿砚。”；9.15—10.0 秒叠加“栀夏与阿砚，诗里见。”。明确这些文字不得粘入 Seedance 正文。

- [ ] **Step 3: 验证提示词门禁**

运行以下检查：

```bash
prompt='episodes/yesu-shansi/prompts/zhixia-ayan-introduction-v03.md'
rg -q '原创虚构数字角色' "$prompt"
rg -q '全程不得生成任何可辨识人声' "$prompt"
test "$(rg -c '全程不得生成任何可辨识人声' "$prompt")" -ge 2
rg -q '唯一一条开放式S形水墨尾巴' "$prompt"
rg -q '0.8米' "$prompt"
rg -q '8.8—10.0秒' "$prompt"
rg -q '不得自行生成文字、字幕、诗句、标题、Logo或水印' "$prompt"
! sed -n '/SEEDANCE_PROMPT_START/,/SEEDANCE_PROMPT_END/p' "$prompt" | rg -q '水晶帘动微风起|黑云翻墨未遮山'
git diff --check -- "$prompt"
```

- [ ] **Step 4: 提交提示词文件**

```bash
git add episodes/yesu-shansi/prompts/zhixia-ayan-introduction-v03.md docs/superpowers/plans/2026-08-27-zhixia-ayan-10s-introduction-prompt.md
git commit -m '新增栀夏阿砚十秒庭院出场提示词'
```
