# 《九歌·云中君》诗舞剧视频号文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将《云中君》旧版动作说明型发布文案更新为可直接发布的“体面告别”情绪转发型正文与首评。

**Architecture:** 只修改单集 `wechat-channels-copy.md`，继续使用标题、正文、标签、首评、发布提醒五区块结构。正文承担情感代入，首评承担原典读音与经历型互动，发布提醒指向诗舞剧 v04 成片和 v02 封面。

**Tech Stack:** Markdown、ripgrep、Git

## Global Constraints

- 标题固定为 `《栀夏·九歌祭舞》02｜云中君`。
- 正文不复述三段舞蹈动作，不使用“送一程”或“最后一程”。
- 栀夏是楚地祭舞者，不是云中君本尊。
- 首评必须包含屈原《九歌·云中君》、“猋”读 `biāo` 和一个经历型互动问题。
- 保留 `原创虚拟角色｜AI辅助制作`，发布时选择平台要求的 AI 内容声明。

---

### Task 1: 更新并验证发布文案

**Files:**
- Modify: `episodes/jiuge-yunzhongjun-15s/wechat-channels-copy.md`
- Test: 文本门禁命令

**Interfaces:**
- Consumes: 已确认的诗舞剧情绪方向、现代映射朗诵、v04 字幕成片和 v02 封面。
- Produces: 可直接复制到微信视频号的正文、标签和首评。

- [x] **Step 1: 运行旧稿门禁并确认失败**

  Run:

  ```bash
  rg -q '不是所有相逢，都要用留下来证明' episodes/jiuge-yunzhongjun-15s/wechat-channels-copy.md
  ```

  Expected: exit 1，因为旧稿尚未包含新的情绪钩子。

- [x] **Step 2: 写入最终发布物**

  将文件正文更新为：

  ```markdown
  # 《九歌·云中君》视频号发布文案

  ## 标题

  《栀夏·九歌祭舞》02｜云中君

  ## 发布正文

  不是所有相逢，都要用留下来证明。

  栀夏追出一步，又停在原地。不是不再舍不得，而是终于明白：真正珍惜过一个人，也包括允许他走向自己的远方。

  “灵皇皇兮既降，猋远举兮云中。”

  愿你记得相逢，也不为离开失去体面。

  原创虚拟角色｜AI辅助制作

  ## 话题标签

  #栀夏飞花令 #楚辞 #九歌 #云中君 #诗舞剧 #国风

  ## 首评（置顶评论）

  “猋”读 biāo，意为迅疾。诗句出自屈原《九歌·云中君》。这一支写的不是忘记，而是明明舍不得，仍愿意松开手。你有没有认真目送过一个后来没有继续同行的人？

  ## 发布提醒

  - 视频使用 `exports/jiuge-yunzhongjun-poetry-drama-subtitled-v04.mp4`。
  - 封面使用 `exports/yunzhongjun-poetry-drama-cover-v02.png`。
  - 发布时选择视频号要求的 AI 内容声明。
  ```

- [x] **Step 3: 运行文本门禁**

  Run:

  ```bash
  rg -n '《栀夏·九歌祭舞》02｜云中君|不是所有相逢，都要用留下来证明|猋.*biāo|屈原《九歌·云中君》|后来没有继续同行的人|原创虚拟角色｜AI辅助制作|poetry-drama-subtitled-v04|poetry-drama-cover-v02' episodes/jiuge-yunzhongjun-15s/wechat-channels-copy.md
  ! rg -n '送一程|最后一程|你更喜欢开头穿云|你会选云神降临' episodes/jiuge-yunzhongjun-15s/wechat-channels-copy.md
  ```

  Expected: 八个新内容锚点全部命中，四个淘汰表达均不命中。

- [x] **Step 4: 检查格式并提交**

  Run:

  ```bash
  git diff --check -- episodes/jiuge-yunzhongjun-15s/wechat-channels-copy.md
  git add episodes/jiuge-yunzhongjun-15s/wechat-channels-copy.md
  git commit -m "更新云中君诗舞剧视频号文案"
  ```

  Expected: diff 无空白错误，只提交该单集发布文案。
