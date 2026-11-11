# 《一舞一愿·九月好运》天宫双姝视频号文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为九月好运天宫双人热舞生成一套可直接复制发布的视频号标题、正文、六个标签、首评和发布提醒。

**Architecture:** 全部发布内容写入单集目录中的一个 Markdown 文件，按标题、正文、标签、首评、发布提醒五区块组织。文案属于创意内容，不增加逐字自动化测试；使用结构、精确祝福、标签数量、禁用词和媒体路径检查完成验收。

**Tech Stack:** Markdown、ripgrep、Git。

## Global Constraints

- 标题固定为 `《一舞一愿》｜当天宫双姝跳起现代热舞`。
- 正文首句直接体现“天宫仙女 × 现代热舞”的文化反差。
- 正文包含精确祝福 `愿所有美好，久久相伴。`。
- 正文同时包含自然的转送对象和自我收藏入口，但不得命令观众转发或收藏。
- 不限定恰恰、拉丁、街舞等具体舞种。
- 标签恰为六个：`#栀夏飞花令 #一舞一愿 #天宫双姝 #现代热舞 #国风舞蹈 #古诗词`。
- 首评提供国风卡点、轻快拉丁、东方爵士三个下一场舞会选项。
- 禁止猎奇段子、玄学承诺、AI 炫技以及点赞、关注、转发、@朋友或固定口令要求。
- 不修改视频、朗诵、字幕、音乐或封面，不执行实际发布。

---

### Task 1: 写入并验证发布文案

**Files:**
- Create: `episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/wechat-channels-copy-jiuyue-haoyun.md`

**Interfaces:**
- Consumes: 已确认的文案设计、字幕成片、天宫双姝封面。
- Produces: 可直接复制到视频号的完整发布素材。

- [ ] **Step 1: 写入五区块文案**

```markdown
# 《一舞一愿·九月好运》天宫双姝视频号发布文案

## 标题

《一舞一愿》｜当天宫双姝跳起现代热舞

## 发布正文

当天宫仙女，踩上现代热舞的节拍。

云海与飞檐还在，仙衣却跟着鼓点扬起。栀夏与阿砚一静一灵，让古典意境有了明快的心跳。

这一舞，送给想祝福的人，也留给九月的自己。
愿所有美好，久久相伴。

原创虚拟角色｜AI辅助制作

## 话题标签

#栀夏飞花令 #一舞一愿 #天宫双姝 #现代热舞 #国风舞蹈 #古诗词

## 首评（置顶评论）

如果天宫还有下一场舞会，你更想看栀夏和阿砚跳国风卡点、轻快拉丁，还是东方爵士？

## 发布提醒

- 视频使用已经确认的重新合并朗诵版 `exports/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-subtitled-v03-remerged-preview.mp4`。
- 封面使用 `exports/tiangong-hot-dance-jiuyue-haoyun-cover-v01.png`。
- 发布时按视频号要求选择 AI 内容声明。
```

- [ ] **Step 2: 检查结构与精确内容**

```bash
copy=episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/wechat-channels-copy-jiuyue-haoyun.md
for heading in '## 标题' '## 发布正文' '## 话题标签' '## 首评（置顶评论）' '## 发布提醒'; do
  rg -q -F "$heading" "$copy"
done
rg -q -F '《一舞一愿》｜当天宫双姝跳起现代热舞' "$copy"
rg -q -F '愿所有美好，久久相伴。' "$copy"
rg -q -F '国风卡点、轻快拉丁，还是东方爵士' "$copy"
test "$(rg -o '#[^ #[:space:]]+' "$copy" | sort -u | wc -l | tr -d ' ')" = 6
```

Expected: 所有检查 exit 0。

- [ ] **Step 3: 检查禁用表达与媒体路径**

```bash
copy=episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/wechat-channels-copy-jiuyue-haoyun.md
! rg -n '点赞|快转发|关注|@[[:alnum:]_]|接住好运|刷到就是好运|必定如愿|仙女蹦迪|天宫开舞厅|没想到|竟然|震撼' "$copy"
test -s exports/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-subtitled-v03-remerged-preview.mp4
test -s exports/tiangong-hot-dance-jiuyue-haoyun-cover-v01.png
```

Expected: 禁用表达无输出，两项媒体文件存在。

- [ ] **Step 4: 提交文案文件**

```bash
git add \
  zhixia-feihualing/docs/superpowers/plans/2026-09-02-jiuyue-haoyun-wechat-channels-copy.md \
  zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/wechat-channels-copy-jiuyue-haoyun.md
git diff --cached --check
git commit -m '编写九月好运天宫双姝视频号文案'
```
