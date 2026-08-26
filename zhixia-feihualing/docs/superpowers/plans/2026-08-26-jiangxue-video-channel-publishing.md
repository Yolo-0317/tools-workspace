# 《江雪》视频号发布文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成并归档一套可直接用于《江雪》视频号发布的标题、正文、话题和置顶评论。

**Architecture:** 以成片对白“他怎么不收竿？”作为悬念入口，用寒江独钓意象承接情绪，再以开放问题引导评论。最终文案保存到《江雪》单集目录，成片事实仍以现有配音清单和质检记录为准。

**Tech Stack:** Markdown、项目既有发布文案格式、Git

## Global Constraints

- 文案必须与成片对白“他怎么不收竿？”及诗句“孤舟蓑笠翁，独钓寒江雪”一致。
- 不把“等一场雪”或其他解释写成柳宗元原作的唯一答案。
- 不突出鱼竿、鱼线与鱼漂的空间连接。
- 不使用网络热梗或表情符号。
- 话题不超过六个。
- 保留“原创国风动画｜AI辅助制作”。

---

### Task 1: 归档《江雪》视频号发布文案

**Files:**
- Create: `zhixia-feihualing/episodes/jiangxue/publishing-copy.md`
- Reference: `zhixia-feihualing/episodes/jiangxue/voice-lines.json`
- Reference: `zhixia-feihualing/episodes/jiangxue/qa-notes.md`
- Reference: `zhixia-feihualing/operations/video-copy.md`

**Interfaces:**
- Consumes: 成片对白、诗句、系列命名和视频号发布文案格式。
- Produces: 可直接复制的视频号标题、发布正文、六个话题和置顶评论。

- [ ] **Step 1: 创建发布文案文件**

写入以下完整内容：

```markdown
# 《江雪》视频号发布文案

## 推荐标题

他怎么还不收竿？｜《江雪》

## 发布正文

千山无鸟，万径无人。

天地都白了，江上只剩一叶孤舟。

阿砚忍不住问：“他怎么还不收竿？”

他等的是鱼，还是一份无人打扰的清静？

“孤舟蓑笠翁，独钓寒江雪。”

你觉得，他为什么还不走？

《栀夏与阿砚·江雪》
原创国风动画｜AI辅助制作

## 话题

#栀夏飞花令 #江雪 #柳宗元 #古诗词 #国风动画 #原创动画

## 置顶评论

你觉得老翁为什么不走？

A｜在等鱼
B｜不愿归去
C｜享受一个人的清静
D｜你有自己的答案

这道题没有标准答案。选一个，也可以写下你的理解。
```

- [ ] **Step 2: 核对成片事实**

运行：

```bash
rg -n '他怎么不收竿|孤舟蓑笠翁，独钓寒江雪' \
  zhixia-feihualing/episodes/jiangxue/voice-lines.json \
  zhixia-feihualing/episodes/jiangxue/publishing-copy.md
```

预期：配音清单与发布文案均命中对白及诗句；发布标题中的“还”仅作为悬念表达，不改变成片对白引文。

- [ ] **Step 3: 核对文案边界与格式**

运行：

```bash
rg -n '原创国风动画｜AI辅助制作|^#栀夏飞花令 ' \
  zhixia-feihualing/episodes/jiangxue/publishing-copy.md
git diff --check -- zhixia-feihualing/episodes/jiangxue/publishing-copy.md
```

预期：内容说明和话题行各命中一次；文案没有空白错误；话题行恰好包含六个话题。

- [ ] **Step 4: 人工复核互动表达**

确认发布正文只提出开放问题，没有把“无人打扰的清静”写成标准诗意；置顶评论明确写有“没有标准答案”；正文没有提到鱼线或鱼漂；全文不含表情符号。

- [ ] **Step 5: 提交发布文案**

```bash
git add zhixia-feihualing/episodes/jiangxue/publishing-copy.md
git commit -m '文案：归档江雪视频号发布内容'
```

