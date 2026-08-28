# 《白雪歌送武判官归京》Seedance 精简提示词重写实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将《白雪歌送武判官归京》10秒 Seedance 提示词重写为更短、更清楚的生产版，同时完整保留已确认的角色、镜头、时间轴、自由舞蹈和声音约束。

**Architecture:** 以现有 `seedance-v01.md` 为唯一成片提示词入口，不新增提示词版本文件。测试脚本先锁定原创角色首句、双母版输入、栀夏先动、阿砚40厘米、自由舞蹈短语和纯文字场景，再用分层结构重写正文：原创身份与参考图映射、全局镜头总控、连续时间轴、身份优先级、禁止项、声音。

**Tech Stack:** Markdown、Zsh、ripgrep、现有项目规则检查脚本。

## Global Constraints

- 只上传@图片1栀夏角色母版和@图片2阿砚角色母版，不上传状态图、首帧图或其他场景参考图。
- 正文第一句固定为“@图片1与@图片2均为本项目原创虚拟角色，均为虚构数字角色，不对应任何现实人物、艺人、真实动物或既有影视动漫角色。”
- 0.5秒内由栀夏完成全片第一个可感知动作；不得以纯风景、雪晶微距、阿砚单独画面或角色缺席的空镜开场。
- 阿砚足底至耳尖约40厘米、肩高约24至28厘米、躯干长度约40至45厘米且不含尾巴，并保持双耳四足单尾结构。
- 舞蹈约束完整且仅为“中国古典舞身韵、轻盈克制、连续自然、不遮脸”，具体动作、连接与收势由 Seedance 自由发挥。
- 不改变既有音频节点：0.500、1.850、3.600、6.200和9.032秒。
- 对白、诗句、朗诵、旁白、耳语、吟唱和字幕不交给视频模型生成。
- 不改动其他剧集，也不处理工作区内与本任务无关的已有修改。

---

### Task 1: 重写并验收白雪 Seedance 生产提示词

**Files:**
- Modify: `zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh`
- Modify: `zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md`
- Verify: `zhixia-feihualing/episodes/baixue/voice-lines.json`
- Verify: `zhixia-feihualing/episodes/baixue/subtitles-baixue.json`

**Interfaces:**
- Consumes: 设计稿 `zhixia-feihualing/docs/superpowers/specs/2026-08-28-baixue-seedance-concise-prompt-rewrite-design.md` 与现有音频时间轴。
- Produces: `SEEDANCE_PROMPT_START` 与 `SEEDANCE_PROMPT_END` 标记之间可直接复制到 Seedance 的最终中文提示词。

- [ ] **Step 1: 扩充失败规则检查**

在 `test_zhixia_first_opening_rules.sh` 中继续使用首行精确匹配，并增加以下生产版结构检查：

```zsh
for phrase in \
  "两张参考图只用于锁定原创角色身份、结构与造型" \
  "场景、首帧构图和全部运动只由文字提示词生成" \
  "具体动作、连接与收势由 Seedance 自由发挥" \
  "声音只生成无人声背景音乐和自然环境声"; do
  print -r -- "$prompt_block" | rg -qF "$phrase"
done
```

同时继续拒绝状态图输入、8至10厘米体型和雪晶微距开场。

- [ ] **Step 2: 运行检查并确认当前冗长版本未满足新结构**

Run:

```bash
zsh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
```

Expected: FAIL，缺少至少一个新加入的精简生产版固定句或结构句。

- [ ] **Step 3: 重写 Seedance 提示词正文**

保留首句逐字固定；第二段一次性完成参考图映射与输入边界。随后依次写：

```text
原创身份与双母版映射
10秒一镜到底及雪林总控
0.000—0.500 栀夏先动
0.500—1.724 阿砚无声口型
1.724—1.850 视线交接
1.850—3.482 栀夏无声口型
3.482—3.600 入舞呼吸
3.600—6.048 自由舞蹈第一段
6.048—6.200 唯一方向变化
6.200—9.032 自由舞蹈第二段与雪林揭示
9.032—10.000 稳定结尾
身份优先级
画面禁止项
声音限制
```

每个时间段只保留该段可观察、可执行的主体动作、摄影机运动和最短局部身份重锚；删除前后段重复的固定脸、服装全称、阿砚全套结构和同义禁止项。不得改变任何时间点。

- [ ] **Step 4: 运行专项检查并确认通过**

Run:

```bash
zsh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
zsh zhixia-feihualing/tests/test_classical_dance_library_rules.sh
zsh zhixia-feihualing/tests/test_realistic_visual_style_rules.sh
zsh zhixia-feihualing/tests/test_baixue_10s_assets.sh
```

Expected: 四项检查均输出 `PASS`，退出码均为0。

- [ ] **Step 5: 检查提示词边界与文本一致性**

Run:

```bash
sed -n '/<!-- SEEDANCE_PROMPT_START -->/,/<!-- SEEDANCE_PROMPT_END -->/p' zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md
git diff --check -- zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
```

Expected: 正文完整位于两个标记之间；没有尾随空格、冲突标记、状态图输入、错误体型、具体舞步或可辨识人声指令。

- [ ] **Step 6: 提交本任务文件**

```bash
git add zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
git commit -m "文档：重写白雪Seedance精简提示词"
```
