# 《回雪胡旋》视频号发布文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成并登记一套可直接复制发布的《回雪胡旋》视频号标题、正文、标签、置顶评论和发布提醒。

**Architecture:** 单一 Markdown 文件保存完整发布物，独立 shell 门禁验证固定标题、四句诗、六个标签、AI 声明、置顶评论以及视频和封面路径。实现不新增发布脚本，不访问视频号后台，不执行实际发布。

**Tech Stack:** Markdown、zsh、ripgrep

## Global Constraints

- 标题固定为“敦煌十六舞第三支，栀夏这一转停不下来了”。
- 正文准确引用白居易《胡旋女》四句，不改字、不漏句、不打乱顺序。
- 只使用六个标签：`#栀夏飞花令 #敦煌舞 #胡旋舞 #白居易 #中国古典舞 #古诗词`。
- 正文末尾固定包含“原创虚拟角色｜AI辅助制作”。
- 不声称历史复原、非遗传承、专业舞谱复刻或真人舞者表演。
- 文件不使用 emoji，不包含绝对路径、视频参数、提示词或内部版本讨论。

---

### Task 1: 写入并验证视频号发布文案

**Files:**
- Create: `zhixia-feihualing/tests/test_huxuan_wechat_channels_copy.sh`
- Create: `zhixia-feihualing/episodes/huxuan-15s/wechat-channels-copy.md`

**Interfaces:**
- Consumes: 已确认的发布文案设计、正式字幕视频和正式封面路径。
- Produces: 可直接复制的五区块发布文案和可重复执行的文本门禁。

- [ ] **Step 1: 写入失败门禁**

创建可执行 `tests/test_huxuan_wechat_channels_copy.sh`，在文案文件缺失时失败；文件存在后固定检查：

```zsh
rg -q '^## 标题$' "$copy"
rg -q '^敦煌十六舞第三支，栀夏这一转停不下来了$' "$copy"
rg -q '^弦鼓一声双袖举，$' "$copy"
rg -q '^回雪飘飖转蓬舞。$' "$copy"
rg -q '^左旋右转不知疲，$' "$copy"
rg -q '^千匝万周无已时。$' "$copy"
rg -q '^原创虚拟角色｜AI辅助制作$' "$copy"
rg -q '^#栀夏飞花令 #敦煌舞 #胡旋舞 #白居易 #中国古典舞 #古诗词$' "$copy"
rg -q 'exports/huxuan-15s-subtitled-v01.mp4' "$copy"
rg -q 'exports/huxuan-dance-cover-v01.png' "$copy"
```

门禁还检查“历史复原”“非遗传承”“专业舞谱”“真人舞者”等禁用声明没有作为正向描述出现。

- [ ] **Step 2: 运行测试确认因文案缺失而失败**

Run: `zsh tests/test_huxuan_wechat_channels_copy.sh`

Expected: FAIL，报告缺少 Huxuan 视频号文案。

- [ ] **Step 3: 写入发布文案**

创建 `wechat-channels-copy.md`，包含五个二级区块：标题、发布正文、话题标签、置顶评论、发布提醒。正文以弦鼓和双袖开场，明确第三支和原创胡旋舞意象，完整引用四句诗，结尾只征集第四支；发布提醒使用项目相对路径。

- [ ] **Step 4: 运行测试确认通过**

Run: `zsh tests/test_huxuan_wechat_channels_copy.sh`

Expected: PASS，输出 `PASS: Huxuan WeChat Channels copy is ready`。

- [ ] **Step 5: 复核可复制性并提交**

Run:

```zsh
git diff --check
zsh tests/test_huxuan_wechat_channels_copy.sh
```

Expected: diff 无空白错误，测试 PASS。

Commit:

```zsh
git add tests/test_huxuan_wechat_channels_copy.sh episodes/huxuan-15s/wechat-channels-copy.md docs/superpowers/plans/2026-08-30-huxuan-wechat-channels-copy.md
git commit -m "制作回雪胡旋视频号文案"
```
