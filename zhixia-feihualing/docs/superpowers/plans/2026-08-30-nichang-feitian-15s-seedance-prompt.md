# 《霓裳飞天》15 秒 Seedance 提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立《栀夏·敦煌十六舞》第四支《霓裳飞天》的单集说明、可直接提交 Seedance 2.0 的 15 秒正式提示词、自动门禁和跨集舞蹈去重记录。

**Architecture:** 单集 README 保存诗文、上传图和验收重点；单一 Markdown 提示词保存上传说明与完整模型正文；shell 门禁检查三高潮、人物占比、空手、飘带连接、莲瓣方向和禁用项。舞蹈台账追加一条 25 列记录，使后续敦煌舞能读取本集视觉指纹并避开重复。

**Tech Stack:** Markdown、zsh、ripgrep、awk、CSV

## Global Constraints

- 系列编号固定为《栀夏·敦煌十六舞》04，工作标题固定为《霓裳飞天》。
- 唯一上传图为 `assets/characters/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-Seedance上传版.jpg`。
- 视频固定为 15 秒、9:16、一镜到底、电影级高写实东方 CG，只有栀夏，无阿砚和其他人物。
- 四句固定为“素手把芙蓉，虚步蹑太清。霓裳曳广带，飘拂升天行。”；朗诵与字幕留给后期。
- 栀夏双手始终空着，莲花只属于浅水莲池、石雕莲台和水面莲瓣环境。
- 三次高潮固定为纵向离地提展、横向 S 形腾移、斜前俯冲再提展；时间窗为 0.000—1.800、4.800—7.000、10.000—13.200 秒。
- 莲瓣三次只按纵向、左右横向、由远向近斜向纵深运动；不增加第二种主要特效。
- 第三高潮人物高度至少约 60%，13—15 秒不得低于约 55%；第三高潮镜头保持或微推，禁止后撤。
- 飘带固定在左右上臂后外侧，不被抓住、不缠腰、不复制、不穿体。
- 原片无人声、无诗句、无字幕、无标题、无水印。

---

### Task 1: 建立失败门禁

**Files:**
- Create: `zhixia-feihualing/tests/test_nichang_feitian_15s_prompt.sh`

**Interfaces:**
- Consumes: 已确认的正式设计与目标文件路径。
- Produces: 在单集说明、正式提示词或台账记录缺失时失败的可执行门禁。

- [ ] **Step 1: 写入测试脚本**

门禁固定检查 `episodes/nichang-feitian-15s/README.md`、`episodes/nichang-feitian-15s/prompts/seedance-v01.md` 和 `operations/dance-design-history.csv`。提示词必须包含：

```zsh
for needle in \
  '只有一个栀夏' \
  '双手全程空着' \
  '0.000—1.800秒' \
  '4.800—7.000秒' \
  '10.000—13.200秒' \
  '第三高潮人物高度至少约60%' \
  '13—15秒人物高度不得低于约55%' \
  '第三高潮.*保持或微推' \
  '左右上臂后外侧' \
  '不生成对白、旁白、诗歌朗诵'; do
  rg -q "$needle" "$prompt"
done
```

测试还检查正文没有内部路径、版本号、设计分类名和历史复原声明；台账中 `nichang-feitian-15s` 恰好一行、全表每行 25 列、状态为 `designed`。

- [ ] **Step 2: 运行测试确认失败**

Run: `zsh tests/test_nichang_feitian_15s_prompt.sh`

Expected: FAIL，首先报告缺少《霓裳飞天》README 或正式提示词，而不是 shell 语法错误。

- [ ] **Step 3: 提交门禁**

```zsh
git add tests/test_nichang_feitian_15s_prompt.sh
git commit -m "建立霓裳飞天提示词门禁"
```

### Task 2: 写入单集说明和 Seedance 正式提示词

**Files:**
- Create: `zhixia-feihualing/episodes/nichang-feitian-15s/README.md`
- Create: `zhixia-feihualing/episodes/nichang-feitian-15s/prompts/seedance-v01.md`

**Interfaces:**
- Consumes: 正式设计中的角色、场景、动作、摄影机、声音和禁用项。
- Produces: 项目可追溯的单集说明和用户可直接复制提交的完整 Seedance 提示词。

- [ ] **Step 1: 写入 README**

README 包含系列编号 04、标题《霓裳飞天》、15 秒规格、李白四句、唯一上传图、莲花环境边界、三高潮表、人物占比、镜头硬限制和原片验收重点。状态固定为“正式提示词已完成，等待生成原片”。

- [ ] **Step 2: 写入上传说明与完整正文**

提示词文件先写项目内上传说明，再以一个代码块提供可直接提交正文。正文按以下六段自然组织：

1. 0.000—1.800 秒纵向离地提展。
2. 1.800—4.800 秒点落换重。
3. 4.800—7.000 秒横向 S 形腾移。
4. 7.000—10.000 秒落脚反向蓄势。
5. 10.000—13.200 秒斜前俯冲再提展。
6. 13.200—15.000 秒高能量余势切断。

正文第一段声明 15 秒、9:16、一镜到底、原创虚构角色、只有一个栀夏、手中无道具。结尾统一写角色稳定、飘带结构、莲瓣唯一特效、摄影机占比和声音文字禁用项。

- [ ] **Step 3: 运行测试确认失败点前移到台账**

Run: `zsh tests/test_nichang_feitian_15s_prompt.sh`

Expected: README 和提示词检查通过，只因缺少 `nichang-feitian-15s` 台账行而失败。

### Task 3: 登记去重台账并完成验收

**Files:**
- Modify: `zhixia-feihualing/operations/dance-design-history.csv`

**Interfaces:**
- Consumes: Task 2 的最终动作、莲瓣和摄影机设计。
- Produces: 一条完整 25 列、状态为 `designed` 的第四支视觉指纹记录。

- [ ] **Step 1: 追加唯一台账行**

台账核心字段固定为：

```text
episode=nichang-feitian-15s
poem=李白《古风·其十九》
peak_sequence=纵向离地提展；横向S形腾移；斜前俯冲再提展
peak_directions=纵向；左右横向；斜向由远及近
peak_windows=0.000—1.800秒；4.800—7.000秒；10.000—13.200秒
carrier_trajectories=双带上下错层双弧；横向宽扇；前后错层纵深长线
camera_peak_reactions=短促推近并抬升；有限横移；保持或微推
status=designed
```

其余字段准确登记第一帧离地、点落交叉步、莲台与莲瓣、人物占比、无手持物和不复用前三支发力链。

- [ ] **Step 2: 运行完整门禁**

Run: `zsh tests/test_nichang_feitian_15s_prompt.sh`

Expected: PASS，输出 `PASS: Nichang Feitian 15s prompt and history are complete`。

- [ ] **Step 3: 执行最终验证**

Run:

```zsh
zsh tests/test_nichang_feitian_15s_prompt.sh
git diff --check
awk -F, 'NF != 25 {print NR ":" NF; bad=1} END {exit bad}' operations/dance-design-history.csv
```

Expected: 测试 PASS、diff 无空白错误、台账全部 25 列。

- [ ] **Step 4: 提交单集与台账**

```zsh
git add episodes/nichang-feitian-15s/README.md episodes/nichang-feitian-15s/prompts/seedance-v01.md operations/dance-design-history.csv docs/superpowers/plans/2026-08-30-nichang-feitian-15s-seedance-prompt.md
git commit -m "制作敦煌霓裳飞天视频提示词"
```

若舞蹈台账同时包含其他用户未提交改动，只暂存本次新增的 `nichang-feitian-15s` 行并单独提交。
