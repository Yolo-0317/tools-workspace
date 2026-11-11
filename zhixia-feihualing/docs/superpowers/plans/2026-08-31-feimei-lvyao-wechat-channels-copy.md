# 《飞袂绿腰》视频号文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已确认的《飞袂绿腰》标题、发布正文、话题标签、首评与发布提醒写入可直接发布且可自动验收的单集文案文件。

**Architecture:** 用一个 zsh 门禁检查完整标题、四句诗、作者篇名、六个标签、首评、视频与封面路径，以及禁用表述。正文作为独立 Markdown 资产保存，README 只记录发布稿入口，不复制整篇文案。

**Tech Stack:** Markdown、zsh、ripgrep、Git

## Global Constraints

- 设计真源为 `docs/superpowers/specs/2026-08-31-feimei-lvyao-wechat-channels-copy-design.md`。
- 标题严格为 `《栀夏·敦煌十六舞》07｜飞袂绿腰`。
- 正文完整保留“南国有佳人，轻盈绿腰舞。华筵九秋暮，飞袂拂云雨。”四句及原标点。
- 话题标签固定为 `#栀夏飞花令 #敦煌舞 #李群玉 #长沙九日登东楼观舞 #中国古典舞 #古诗词`。
- 首评严格为 `敦煌十六舞下一支，你想看哪一种舞？也可以留下相关诗句。`。
- 视频路径固定为 `exports/feimei-lvyao-15s-subtitled-v01.mp4`，封面路径固定为 `exports/feimei-lvyao-dance-cover-v01.png`。
- 不使用 emoji，不声称古舞复原、壁画复刻、文物活化、数字敦煌、非遗传承或官方合作。
- 不修改正式视频、封面或其他单集发布稿。

---

### Task 1: 建立文案准确性门禁

**Files:**
- Create: `tests/test_feimei_lvyao_wechat_channels_copy.sh`

**Interfaces:**
- Consumes: 已确认文案设计。
- Produces: 对 `episodes/feimei-lvyao-15s/wechat-channels-copy.md` 的唯一自动验收命令。

- [ ] **Step 1: 写入失败测试**

```zsh
#!/bin/zsh
set -euo pipefail
project_dir="${0:A:h:h}"
copy="$project_dir/episodes/feimei-lvyao-15s/wechat-channels-copy.md"
[[ -s "$copy" ]] || { print -u2 'FAIL: missing Feimei Lvyao WeChat Channels copy'; exit 1; }
rg -Fxq '《栀夏·敦煌十六舞》07｜飞袂绿腰' "$copy"
for text in '南国有佳人，' '轻盈绿腰舞。' '华筵九秋暮，' '飞袂拂云雨。' \
  '原创虚拟角色｜AI辅助制作' \
  '敦煌十六舞下一支，你想看哪一种舞？也可以留下相关诗句。' \
  'exports/feimei-lvyao-15s-subtitled-v01.mp4' \
  'exports/feimei-lvyao-dance-cover-v01.png'; do
  rg -Fq "$text" "$copy"
done
[[ "$(rg -o '#[^ #]+' "$copy" | sort -u | wc -l | tr -d ' ')" == '6' ]]
if rg -q '古舞复原|壁画复刻|文物活化|数字敦煌|非遗传承|官方合作' "$copy"; then
  print -u2 'FAIL: unsupported historical or institutional claim'
  exit 1
fi
print 'PASS: Feimei Lvyao WeChat Channels copy is ready'
```

- [ ] **Step 2: 运行测试确认先失败**

Run: `chmod +x tests/test_feimei_lvyao_wechat_channels_copy.sh && ./tests/test_feimei_lvyao_wechat_channels_copy.sh`

Expected: FAIL，报告缺少《飞袂绿腰》视频号文案文件。

- [ ] **Step 3: 提交门禁**

```bash
git add tests/test_feimei_lvyao_wechat_channels_copy.sh
git commit -m "建立飞袂绿腰视频号文案门禁"
```

### Task 2: 写入正式发布稿并归档

**Files:**
- Create: `episodes/feimei-lvyao-15s/wechat-channels-copy.md`
- Modify: `episodes/feimei-lvyao-15s/README.md`

**Interfaces:**
- Consumes: 设计真源中的正式正文。
- Produces: 可直接复制的五区块发布稿及 README 入口。

- [ ] **Step 1: 写入正式发布稿**

文件必须按以下顺序写入标题、正文、话题标签、首评和发布提醒：

```markdown
# 《飞袂绿腰》视频号发布文案

## 标题

《栀夏·敦煌十六舞》07｜飞袂绿腰

## 发布正文

秋叶被舞步卷起，蓝橙飞袂从地面划向高处。栀夏一次侧折、一次回腰，再以深弓把最后一道袖线送入暮色。

这是《栀夏·敦煌十六舞》第七支《飞袂绿腰》。栀夏以原创敦煌绿腰舞意象，回应唐·李群玉《长沙九日登东楼观舞》开篇四句：

南国有佳人，
轻盈绿腰舞。
华筵九秋暮，
飞袂拂云雨。

绿腰不只在腰间，也在每一次重心回落与飞袂上扬之间。

三次飞袂里，你最喜欢开场侧折、游龙回腰，还是结尾凌云？

原创虚拟角色｜AI辅助制作

## 话题标签

#栀夏飞花令 #敦煌舞 #李群玉 #长沙九日登东楼观舞 #中国古典舞 #古诗词

## 首评（置顶评论）

敦煌十六舞下一支，你想看哪一种舞？也可以留下相关诗句。

## 发布提醒

- 视频使用 `exports/feimei-lvyao-15s-subtitled-v01.mp4`。
- 封面使用 `exports/feimei-lvyao-dance-cover-v01.png`。
- 发布时选择视频号要求的 AI 内容声明。
```

- [ ] **Step 2: 更新 README 入口**

在 `episodes/feimei-lvyao-15s/README.md` 末尾增加：

```markdown
## 视频号发布

- 发布文案与首评：`wechat-channels-copy.md`。
- 标题：`《栀夏·敦煌十六舞》07｜飞袂绿腰`。
- 视频与封面分别使用正式字幕版和正式舞蹈封面，发布时选择平台要求的 AI 内容声明。
```

- [ ] **Step 3: 运行完整验证**

Run:

```bash
./tests/test_feimei_lvyao_wechat_channels_copy.sh
git diff --check -- episodes/feimei-lvyao-15s/wechat-channels-copy.md episodes/feimei-lvyao-15s/README.md tests/test_feimei_lvyao_wechat_channels_copy.sh
```

Expected: `PASS: Feimei Lvyao WeChat Channels copy is ready`，且无空白错误。

- [ ] **Step 4: 提交发布稿**

```bash
git add episodes/feimei-lvyao-15s/wechat-channels-copy.md episodes/feimei-lvyao-15s/README.md
git commit -m "制作飞袂绿腰视频号文案"
```
