# 《莲台天乐》视频号发布文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成并登记一套采用最新五段式格式、可直接复制发布的《莲台天乐》视频号标题、正文、标签、首评和发布提醒。

**Architecture:** 单一 Markdown 文件保存完整发布物，独立 zsh 门禁验证五个固定区块、统一系列标题、四句诗、六个标签、AI 声明、首评以及视频和封面路径。`docs/production-workflow.md` 保存后续敦煌十六舞的统一标题规则；实现不访问视频号后台，不执行实际发布，也不修改视频、封面或其他单集内容。

**Tech Stack:** Markdown、zsh、ripgrep

## Global Constraints

- 标题固定为“《栀夏·敦煌十六舞》06｜莲台天乐”。
- 后续《栀夏·敦煌十六舞》视频号主标题统一使用“《栀夏·敦煌十六舞》NN｜单集名”，其中 `NN` 为两位阿拉伯数字，分隔符为无空格的全角竖线。
- 文件按“标题、发布正文、话题标签、首评（置顶评论）、发布提醒”五个区块排列。
- 正文准确引用唐·李白《庐山东林寺夜怀》四句，不改字、不漏句、不打乱顺序。
- 只使用六个标签：`#栀夏飞花令 #敦煌舞 #李白 #庐山东林寺夜怀 #中国古典舞 #古诗词`。
- 正文末尾固定包含“原创虚拟角色｜AI辅助制作”。
- 只将作品描述为“原创敦煌供养舞意象”，不声称壁画复原、古舞复原、数字敦煌、文物活化、非遗传承、专业舞谱复刻或官方合作。
- 标题与正文不使用 emoji，不包含绝对路径、视频参数、提示词或内部版本讨论。

---

### Task 1: 写入并验证视频号发布文案

**Files:**
- Create: `zhixia-feihualing/tests/test_liantai_tianyue_wechat_channels_copy.sh`
- Create: `zhixia-feihualing/episodes/liantai-tianyue-15s/wechat-channels-copy.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-31-liantai-tianyue-wechat-channels-copy-design.md`、正式字幕视频路径和正式封面路径。
- Produces: 可直接复制的五区块发布文案和可重复执行的文本门禁。

- [x] **Step 1: 写入失败门禁**

创建可执行文件 `tests/test_liantai_tianyue_wechat_channels_copy.sh`：

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
copy="$project_dir/episodes/liantai-tianyue-15s/wechat-channels-copy.md"

[[ -s "$copy" ]] || { print -u2 "FAIL: missing Liantai Tianyue WeChat Channels copy"; exit 1; }

for heading in '## 标题' '## 发布正文' '## 话题标签' '## 首评（置顶评论）' '## 发布提醒'; do
  rg -Fqx "$heading" "$copy" || { print -u2 "FAIL: missing section: $heading"; exit 1; }
done

for line in \
  '《栀夏·敦煌十六舞》06｜莲台天乐' \
  '霜清东林钟，' \
  '水白虎溪月。' \
  '天香生虚空，' \
  '天乐鸣不歇。' \
  '原创虚拟角色｜AI辅助制作' \
  '#栀夏飞花令 #敦煌舞 #李白 #庐山东林寺夜怀 #中国古典舞 #古诗词' \
  '敦煌十六舞下一支，你想看哪一种舞？也可以留下相关诗句。'; do
  rg -Fqx "$line" "$copy" || { print -u2 "FAIL: missing exact copy line: $line"; exit 1; }
done

rg -Fq '《栀夏·敦煌十六舞》第六支《莲台天乐》' "$copy"
rg -Fq '原创敦煌供养舞意象' "$copy"
rg -Fq 'exports/liantai-tianyue-15s-subtitled-v01.mp4' "$copy"
rg -Fq 'exports/liantai-tianyue-dance-cover-v01.png' "$copy"
rg -Fq '发布时选择视频号要求的 AI 内容声明' "$copy"

for prohibited in '壁画复原' '古舞复原' '数字敦煌' '文物活化' '非遗传承' '专业舞谱复刻' '官方合作' '真人舞者表演'; do
  ! rg -Fq "$prohibited" "$copy" || { print -u2 "FAIL: prohibited unsupported claim: $prohibited"; exit 1; }
done

print "PASS: Liantai Tianyue WeChat Channels copy is ready"
```

- [x] **Step 2: 运行测试确认因文案缺失而失败**

Run: `zsh tests/test_liantai_tianyue_wechat_channels_copy.sh`

Expected: FAIL，输出 `FAIL: missing Liantai Tianyue WeChat Channels copy`。

- [x] **Step 3: 写入发布文案**

创建 `episodes/liantai-tianyue-15s/wechat-channels-copy.md`，严格写入五个二级区块：

```markdown
## 标题

《栀夏·敦煌十六舞》06｜莲台天乐

## 发布正文

月光落进石窟，一声清钟穿过长夜。金饰随舞步轻响，栀夏在最后一次提展中把月色托向高处。

这是《栀夏·敦煌十六舞》第六支《莲台天乐》。栀夏以原创敦煌供养舞意象，回应李白《庐山东林寺夜怀》中的四句：

霜清东林钟，
水白虎溪月。
天香生虚空，
天乐鸣不歇。

钟声有了回响，月色也在舞姿里缓缓展开。

这四句里，你最喜欢哪一句？

原创虚拟角色｜AI辅助制作

## 话题标签

#栀夏飞花令 #敦煌舞 #李白 #庐山东林寺夜怀 #中国古典舞 #古诗词

## 首评（置顶评论）

敦煌十六舞下一支，你想看哪一种舞？也可以留下相关诗句。

## 发布提醒

- 视频使用 `exports/liantai-tianyue-15s-subtitled-v01.mp4`。
- 封面使用 `exports/liantai-tianyue-dance-cover-v01.png`。
- 发布时选择视频号要求的 AI 内容声明。
```

- [x] **Step 4: 运行测试确认通过**

Run: `zsh tests/test_liantai_tianyue_wechat_channels_copy.sh`

Expected: PASS，输出 `PASS: Liantai Tianyue WeChat Channels copy is ready`。

- [x] **Step 5: 复核可复制性并提交**

Run:

```zsh
git diff --check -- tests/test_liantai_tianyue_wechat_channels_copy.sh episodes/liantai-tianyue-15s/wechat-channels-copy.md
zsh tests/test_liantai_tianyue_wechat_channels_copy.sh
```

Expected: diff 无空白错误，测试 PASS；正文中没有内部绝对路径、生成参数或禁用声明。

Commit:

```zsh
git add tests/test_liantai_tianyue_wechat_channels_copy.sh episodes/liantai-tianyue-15s/wechat-channels-copy.md docs/superpowers/plans/2026-08-31-liantai-tianyue-wechat-channels-copy.md
git commit -m "制作莲台天乐视频号文案"
```

---

### Task 2: 统一当前标题并固化后续系列规则

**Files:**
- Modify: `zhixia-feihualing/tests/test_liantai_tianyue_wechat_channels_copy.sh`
- Modify: `zhixia-feihualing/episodes/liantai-tianyue-15s/wechat-channels-copy.md`
- Modify: `zhixia-feihualing/docs/production-workflow.md`

**Interfaces:**
- Consumes: 已确认的系列格式 `《栀夏·敦煌十六舞》NN｜单集名` 与当前单集编号 `06`。
- Produces: 使用统一标题的《莲台天乐》发布文案，以及后续新单集可直接继承的发布流程规则。

- [x] **Step 1: 先修改门禁以表达新标题规则**

把 `tests/test_liantai_tianyue_wechat_channels_copy.sh` 中原标题断言替换为：

```zsh
'《栀夏·敦煌十六舞》06｜莲台天乐'
```

增加生产流程规则断言：

```zsh
workflow="$project_dir/docs/production-workflow.md"
rg -Fq '《栀夏·敦煌十六舞》视频号主标题统一使用 `《栀夏·敦煌十六舞》NN｜单集名`' "$workflow"
```

- [x] **Step 2: 运行门禁确认旧标题导致失败**

Run: `zsh tests/test_liantai_tianyue_wechat_channels_copy.sh`

Expected: FAIL，因为当前发布文案仍是旧的画面钩子标题，尚未包含 `《栀夏·敦煌十六舞》06｜莲台天乐`。

- [x] **Step 3: 修改当前文案并记录长期规则**

将 `episodes/liantai-tianyue-15s/wechat-channels-copy.md` 的标题行替换为：

```text
《栀夏·敦煌十六舞》06｜莲台天乐
```

在 `docs/production-workflow.md` 的“六、发布与复盘”中增加：

```markdown
7. 《栀夏·敦煌十六舞》视频号主标题统一使用 `《栀夏·敦煌十六舞》NN｜单集名`：`NN` 使用两位阿拉伯数字，分隔符固定为全角竖线 `｜` 且左右不留空格；动作钩子与诗意句放在正文开头，不替代主标题。本规则从第六支及后续新发布文案开始执行，不追溯批量重写已发布旧稿。
```

- [x] **Step 4: 运行门禁确认新标题与长期规则均通过**

Run: `zsh tests/test_liantai_tianyue_wechat_channels_copy.sh`

Expected: PASS，输出 `PASS: Liantai Tianyue WeChat Channels copy is ready`。

- [x] **Step 5: 复核范围并提交**

Run:

```zsh
git diff --check -- tests/test_liantai_tianyue_wechat_channels_copy.sh episodes/liantai-tianyue-15s/wechat-channels-copy.md docs/production-workflow.md docs/superpowers/plans/2026-08-31-liantai-tianyue-wechat-channels-copy.md
zsh tests/test_liantai_tianyue_wechat_channels_copy.sh
```

Expected: diff 无空白错误，门禁通过，正文、首评、标签和素材路径保持不变。

Commit:

```zsh
git add tests/test_liantai_tianyue_wechat_channels_copy.sh episodes/liantai-tianyue-15s/wechat-channels-copy.md docs/production-workflow.md docs/superpowers/plans/2026-08-31-liantai-tianyue-wechat-channels-copy.md
git commit -m "应用敦煌十六舞统一标题格式"
```
