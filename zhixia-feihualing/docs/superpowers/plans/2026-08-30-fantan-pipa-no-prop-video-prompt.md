# 《月照反弹琵琶》无道具视频提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 先用 5 秒低成本测试验证栀夏能够在完全无琵琶的情况下完成清楚的肩后反拨身法，再据此制作 15 秒三次同强度高潮的正式 Seedance 提示词。

**Architecture:** 视频输入只保留一张栀夏敦煌角色母板。5 秒提示词只承担角色锁定、零道具和第一高潮验证；通过人工成片验收后，15 秒提示词复用已验证动作语汇并扩展为纵向、横向和纵深三段高潮。所有生成结果由独立 QA 记录追踪，不把失败版本覆盖为正式提示词。

**Tech Stack:** Markdown、Seedance 图生视频、FFmpeg/ffprobe 关键帧检查、Git。

## Global Constraints

- 设计真源：`docs/superpowers/specs/2026-08-30-fantan-pipa-no-prop-15s-design.md`。
- 画幅固定为 9:16；动作测试约 5 秒，正式片 15 秒。
- 视频只上传 `assets/characters/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-Seedance上传版.jpg`。
- 不上传或引用琵琶道具卡、动作照片、场景图、其他人物图或旧版角色卡。
- 画面中零实体琵琶、零琵琶局部、零虚影、零琴形光效、零其他乐器。
- 双手不空抓、不在胸前模拟持琴，只以开放手掌、反折手腕和短促弹拨指法构成肩后反弹意象。
- 15 秒正式片在 0—1.800、4.800—7.000、10.000—13.000 秒分别形成纵向、横向和纵深三次同等强度高潮。
- 原始视频无人声、无朗诵、无字幕、无标题、无印章、无水印；诗朗诵与字幕留到原片通过后制作。
- 不删除或改写现有实体琵琶版提示词；它作为失败实验记录保留。

---

### Task 1: 建立 5 秒无道具动作验证提示词

**Files:**
- Create: `zhixia-feihualing/episodes/fantan-pipa-15s/prompts/seedance-no-prop-test-v01.md`
- Modify: `zhixia-feihualing/episodes/fantan-pipa-15s/README.md`

**Interfaces:**
- Consumes: 栀夏 v03 角色母板与无道具版设计真源。
- Produces: 可直接复制到 Seedance 的 5 秒测试正文，以及明确的单图上传方法。

- [ ] **Step 1: 确认测试提示词尚未误建为正式版本**

Run:

```bash
test ! -e zhixia-feihualing/episodes/fantan-pipa-15s/prompts/seedance-no-prop-test-v01.md
```

Expected: PASS；若文件已经存在，先阅读并确认是否属于用户内容，不得覆盖。

- [ ] **Step 2: 编写 5 秒提示词文件**

文件必须按以下顺序组织，且只包含一个动作高潮：标题、使用方式、由 `SEEDANCE_PROMPT_START` 与 `SEEDANCE_PROMPT_END` 包围的可复制正文、通过条件。正文依次写原创资产与角色锁定、5 秒竖屏边塞场景、第一帧低位反弓、0—1.8 秒纵向骤展、1.8—5 秒两步以内换重、零道具约束、角色与镜头连续性、无人声与无文字。通过条件按动作、无道具、角色、镜头四类逐条列出。

正文避免使用“握琴颈、抱琴、琴弦面、隐形琵琶”等可能诱导模型生成乐器的词；声音只写“短促的琵琶拨弦重音”，不描述可见声波或琴形。

- [ ] **Step 3: 在单集 README 登记测试入口**

在 `episodes/fantan-pipa-15s/README.md` 增加“无道具重制”小节，写明：

```markdown
## 无道具重制

- 设计：`../../docs/superpowers/specs/2026-08-30-fantan-pipa-no-prop-15s-design.md`
- 5 秒动作测试：`prompts/seedance-no-prop-test-v01.md`
- 状态：等待 5 秒动作测试成片。
- 实体琵琶版保留为失败实验记录，不再用于生成。
```

- [ ] **Step 4: 验证测试提示词的关键约束**

Run:

```bash
rg -n "只上传|5 秒|第一帧|反手弹拨|不空抓|不在胸前|不出现实体琵琶|无人声|无字幕" zhixia-feihualing/episodes/fantan-pipa-15s/prompts/seedance-no-prop-test-v01.md
```

Expected: 九类约束均至少命中一次；正文中不存在 `@图片2`、`四弦四轴`、`握琴颈` 或 `琴弦面`。

- [ ] **Step 5: 检查差异并提交**

Run:

```bash
git diff --check -- zhixia-feihualing/episodes/fantan-pipa-15s/prompts/seedance-no-prop-test-v01.md zhixia-feihualing/episodes/fantan-pipa-15s/README.md
git diff -- zhixia-feihualing/episodes/fantan-pipa-15s/prompts/seedance-no-prop-test-v01.md zhixia-feihualing/episodes/fantan-pipa-15s/README.md
```

Expected: 无空白错误，只包含本任务的提示词与 README 入口。

```bash
git add -- zhixia-feihualing/episodes/fantan-pipa-15s/prompts/seedance-no-prop-test-v01.md zhixia-feihualing/episodes/fantan-pipa-15s/README.md
git commit -m "制作无道具反弹琵琶五秒测试提示词"
```

---

### Task 2: 验收 5 秒动作测试成片

**Files:**
- Create: `zhixia-feihualing/episodes/fantan-pipa-15s/qa-no-prop-test-v01.md`
- Modify: `zhixia-feihualing/episodes/fantan-pipa-15s/README.md`

**Interfaces:**
- Consumes: 用户使用 Task 1 提示词生成并上传的 5 秒 MP4。
- Produces: `PASS` 或 `FAIL` 结论；只有 `PASS` 才允许 Task 3 开始。

- [ ] **Step 1: 读取视频基础信息**

Run:

```bash
FANTAN_TEST_VIDEO=/本轮用户上传视频的实际绝对路径
ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate,codec_name -of json "$FANTAN_TEST_VIDEO"
```

Expected: 时长约 5 秒，竖屏视频流可正常解码。

- [ ] **Step 2: 提取动作关键帧联络表**

Run:

```bash
FANTAN_TEST_VIDEO=/本轮用户上传视频的实际绝对路径
ffmpeg -y -i "$FANTAN_TEST_VIDEO" -vf "fps=2,scale=496:-1,tile=5x2:padding=8:margin=8" -frames:v 1 /private/tmp/fantan-pipa-no-prop-test-v01-contact-sheet.jpg
```

Expected: 获得覆盖开场、第一高潮和连接余势的十格联络表。

- [ ] **Step 3: 按四类标准写 QA 记录**

创建 `qa-no-prop-test-v01.md`，把本轮视频的实际绝对路径写入“输入视频”，并逐项填写观察证据：

```markdown
# 无道具反弹琵琶 5 秒动作测试 v01 QA

- 输入视频：本轮实际绝对路径
- 结论：`PASS` 或 `FAIL`

## 无道具
- 是否出现实体、局部、虚影或琴形光效：
- 双手是否出现空抓或胸前持琴：

## 第一高潮
- 第一帧是否已经低位承重：
- 0.2 秒内是否开始变化：
- 是否同时出现反弓、拧腰、肩后高低双臂、反手弹拨和腿部提展：

## 角色连续性
- 脸、妆发、服装、配饰与飘带固定点：

## 镜头与舞蹈
- 是否保持全身主体：
- 是否出现奔跑、整圈旋转、站定或大幅拉远：

## 下一步
- `PASS`：允许制作 15 秒正式提示词。
- `FAIL`：只记录一个首要失败原因和一项最小提示词修改，不扩展到 15 秒。
```

判定规则：任何可见乐器、空抓持琴、第一高潮缺少腿部承重、人物迅速缩成远景，均直接判定 `FAIL`。

- [ ] **Step 4: 更新 README 状态**

若通过，状态改为“5 秒动作测试通过，允许制作 15 秒提示词”；若失败，写明“5 秒动作测试未通过，等待单变量修订”。不得在失败时把 Task 3 标记为开始。

- [ ] **Step 5: 检查差异并提交**

Run:

```bash
git diff --check -- zhixia-feihualing/episodes/fantan-pipa-15s/qa-no-prop-test-v01.md zhixia-feihualing/episodes/fantan-pipa-15s/README.md
```

Expected: QA 记录无占位符，结论与 README 状态一致。

```bash
git add -- zhixia-feihualing/episodes/fantan-pipa-15s/qa-no-prop-test-v01.md zhixia-feihualing/episodes/fantan-pipa-15s/README.md
git commit -m "验收无道具反弹琵琶五秒测试"
```

---

### Task 3: 制作 15 秒无道具正式提示词

**Files:**
- Create: `zhixia-feihualing/episodes/fantan-pipa-15s/prompts/seedance-no-prop-v02.md`
- Modify: `zhixia-feihualing/episodes/fantan-pipa-15s/README.md`

**Interfaces:**
- Consumes: Task 2 的 `PASS` 结论和通过验证的第一高潮动作语汇。
- Produces: 可直接用于完整 15 秒生成的正式 Seedance 提示词。

- [ ] **Step 1: 验证 5 秒测试已经通过**

Run:

```bash
rg -n "结论：.*PASS|5 秒动作测试通过" zhixia-feihualing/episodes/fantan-pipa-15s/qa-no-prop-test-v01.md zhixia-feihualing/episodes/fantan-pipa-15s/README.md
```

Expected: QA 与 README 均明确通过；否则停止本任务。

- [ ] **Step 2: 编写 15 秒正式提示词**

`seedance-no-prop-v02.md` 必须包含：

- 单张栀夏角色母板的上传方法和原创资产说明。
- 一句总纲：完全无乐器，以敦煌舞身韵、肩后高低双臂和反手弹拨表达反弹琵琶意象。
- `0.000—1.800` 纵向低位反弓骤展。
- `1.800—4.800` 两步以内交叉换重连接。
- `4.800—7.000` 横向宽弓反拨。
- `7.000—10.000` 前后错层连接，7 秒后零次完整旋转。
- `10.000—13.000` 纵深沉提斜展。
- `13.000—15.000` 高能量余势，12.5 秒后不继续拉远。
- 角色、飘带、场景、摄影机、环境机制和声音连续性。
- 零实体、零虚影、零琴形光效、零空抓、零胸前持琴、零奔跑、零连续旋转。

提示词不复用实体琵琶版的四弦四轴、琴面方向、握琴颈、手在弦区和穿琴限制；避免在正文中频繁重复“琵琶外形”，降低模型主动补画乐器的概率。

- [ ] **Step 3: 更新 README 正式入口**

在“无道具重制”小节增加：

```markdown
- 15 秒正式提示词：`prompts/seedance-no-prop-v02.md`
- 状态：15 秒无道具版本待生成。
```

- [ ] **Step 4: 运行约束检查**

Run:

```bash
rg -n "0\.000—1\.800|4\.800—7\.000|10\.000—13\.000|纵向|横向|纵深|反手弹拨|不空抓|不在胸前|无人声|无字幕" zhixia-feihualing/episodes/fantan-pipa-15s/prompts/seedance-no-prop-v02.md
rg -n "@图片2|四弦四轴|握琴颈|琴弦面|手在弦区" zhixia-feihualing/episodes/fantan-pipa-15s/prompts/seedance-no-prop-v02.md
```

Expected: 第一条命中全部正式约束；第二条无输出。

- [ ] **Step 5: 检查差异并提交**

Run:

```bash
git diff --check -- zhixia-feihualing/episodes/fantan-pipa-15s/prompts/seedance-no-prop-v02.md zhixia-feihualing/episodes/fantan-pipa-15s/README.md
git diff -- zhixia-feihualing/episodes/fantan-pipa-15s/prompts/seedance-no-prop-v02.md zhixia-feihualing/episodes/fantan-pipa-15s/README.md
```

Expected: 无空白错误，正文没有旧版实体琵琶约束，README 状态与提示词版本一致。

```bash
git add -- zhixia-feihualing/episodes/fantan-pipa-15s/prompts/seedance-no-prop-v02.md zhixia-feihualing/episodes/fantan-pipa-15s/README.md
git commit -m "制作无道具反弹琵琶十五秒提示词"
```

---

### Task 4: 验收 15 秒正式原片

**Files:**
- Create: `zhixia-feihualing/episodes/fantan-pipa-15s/qa-no-prop-v02.md`
- Modify: `zhixia-feihualing/episodes/fantan-pipa-15s/README.md`

**Interfaces:**
- Consumes: 用户使用 Task 3 正式提示词生成并上传的 15 秒 MP4。
- Produces: 原片通过或单变量返修结论；通过后才进入朗诵、字幕和画质升级。

- [ ] **Step 1: 提取 15 秒联络表**

Run:

```bash
FANTAN_FINAL_VIDEO=/本轮用户上传视频的实际绝对路径
ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate,codec_name -of json "$FANTAN_FINAL_VIDEO"
ffmpeg -y -i "$FANTAN_FINAL_VIDEO" -vf "fps=2/3,scale=496:-1,tile=3x4:padding=8:margin=8" -frames:v 1 /private/tmp/fantan-pipa-no-prop-v02-contact-sheet.jpg
```

Expected: 约 15 秒竖屏视频与覆盖三次高潮、两段连接和收尾的联络表。

- [ ] **Step 2: 写正式 QA 记录**

`qa-no-prop-v02.md` 必须逐项记录：零道具、三次高潮的时间与方向、动作强度、腿部承重、反弓与弹拨手势、角色身份、飘带连接、镜头距离、旋转次数、奔跑情况、结尾余势和声音同步。

通过条件采用设计稿十项验收标准；三次高潮任何一次明显偏弱、任何可见乐器或虚影、任何持续奔跑、12.5 秒后人物继续缩小，均不得标记为通过。

- [ ] **Step 3: 更新 README 状态并提交**

通过时写“15 秒无道具原片通过，可进入诗朗诵、字幕和高清出片”；失败时只记录首要失败原因和下一轮单变量修改。

```bash
git diff --check -- zhixia-feihualing/episodes/fantan-pipa-15s/qa-no-prop-v02.md zhixia-feihualing/episodes/fantan-pipa-15s/README.md
git add -- zhixia-feihualing/episodes/fantan-pipa-15s/qa-no-prop-v02.md zhixia-feihualing/episodes/fantan-pipa-15s/README.md
git commit -m "验收无道具反弹琵琶十五秒原片"
```
