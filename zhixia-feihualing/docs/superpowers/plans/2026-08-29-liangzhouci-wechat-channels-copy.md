# 《凉州词》视频号发布文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为《凉州词》15秒朗诵字幕成片交付一套可直接复制发布的视频号标题、正文、六个话题标签、置顶评论和发布提醒。

**Architecture:** 使用单一Markdown文件保存最终成稿，用独立Zsh门禁检查标题、完整诗文、两个搜索表达、原创虚拟角色声明、恰好六个话题标签、成片路径和禁用词。对话中交付内容与文件完全一致。

**Tech Stack:** Markdown、Zsh、ripgrep

## Global Constraints

- 标题固定为“栀夏这一舞，带着阿砚飞过了玉门关”。
- 第一传播点是栀夏和阿砚一起飞起来，其次才是中国古典舞与边塞诗境。
- 正文自然包含“AI美女舞蹈”和“中国古典舞”，不写成关键词堆叠。
- 完整引用王之涣《凉州词》四句，标点和归属准确。
- 明确栀夏与阿砚为原创虚拟角色，并使用“AI辅助制作”声明。
- 话题标签恰好为`#栀夏飞花令 #王之涣 #凉州词 #AI美女舞蹈 #中国古典舞 #古诗词`。
- 不出现Seedance、提示词、模型参数、镜头代码、真人舞者、专业资历、擦边描述或夸张最高级。
- 发布视频指向`exports/liangzhouci-15s-subtitled-v01.mp4`，提醒选择视频号AI内容声明，不代为上传发布。

---

### Task 1: 编写并质检视频号文案

**Files:**
- Create: `episodes/liangzhouci-15s/wechat-channels-copy.md`
- Create: `tests/test_liangzhouci_wechat_channels_copy.sh`

**Interfaces:**
- Consumes: 已确认的标题、王之涣《凉州词》原文、双角色飞天成片内容和项目视频号文案格式。
- Produces: 一份含标题、发布正文、话题标签、置顶评论和发布提醒的最终Markdown文件，以及一个可重跑的内容门禁。

- [ ] **Step 1: 写入失败门禁**

`tests/test_liangzhouci_wechat_channels_copy.sh` 必须执行以下检查：

```zsh
[[ -s "$copy_file" ]]
rg -qF "栀夏这一舞，带着阿砚飞过了玉门关" "$copy_file"
rg -qF "黄河远上白云间，一片孤城万仞山。" "$copy_file"
rg -qF "羌笛何须怨杨柳，春风不度玉门关。" "$copy_file"
rg -qF "AI美女舞蹈" "$copy_file"
rg -qF "中国古典舞" "$copy_file"
rg -qF "原创虚拟角色｜AI辅助制作" "$copy_file"
rg -qF "exports/liangzhouci-15s-subtitled-v01.mp4" "$copy_file"
```

门禁另行提取“## 话题标签”与下一个二级标题之间的内容，确认`#`话题恰好六个；若文案出现`Seedance|提示词|模型参数|镜头代码|真人舞者|专业舞蹈演员|全网第一|最美`中任何一项则失败。

- [ ] **Step 2: 运行门禁确认红灯**

Run: `zsh tests/test_liangzhouci_wechat_channels_copy.sh`

Expected: FAIL，报告缺少`episodes/liangzhouci-15s/wechat-channels-copy.md`。

- [ ] **Step 3: 写入最终成稿**

`episodes/liangzhouci-15s/wechat-channels-copy.md` 依次包含：

```text
## 标题
## 发布正文
## 话题标签
## 置顶评论
## 发布提醒
```

正文开头写沙风托起栀夏和阿砚，中段以自然句子引入AI美女舞蹈、中国古典舞和边塞诗境，随后完整引诗并说明原创虚拟角色身份，结尾邀请观众留下下一首诗。

- [ ] **Step 4: 运行门禁确认绿灯**

Run: `zsh tests/test_liangzhouci_wechat_channels_copy.sh`

Expected: `PASS: Liangzhouci WeChat Channels copy is ready`

- [ ] **Step 5: 检查格式并提交**

Run:

```bash
git diff --check -- episodes/liangzhouci-15s/wechat-channels-copy.md tests/test_liangzhouci_wechat_channels_copy.sh
git add episodes/liangzhouci-15s/wechat-channels-copy.md tests/test_liangzhouci_wechat_channels_copy.sh docs/superpowers/plans/2026-08-29-liangzhouci-wechat-channels-copy.md
git commit -m "文案：完成凉州词视频号发布文案"
```
