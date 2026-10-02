# 栀夏九歌祭舞十五秒三高潮 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付《九歌》十一篇十五秒三高潮舞蹈设计卡、可直接使用的 Seedance 提示词、研究说明和跨篇去重台账。

**Architecture:** 以原典和外部研究形成统一证据层，再按天神、地祇、人鬼与送神三个批次完成十一篇独立设计卡和提示词。独立 CSV 台账保存三高潮序列与视觉指纹，自动测试负责文件完整性、固定角色约束、禁用词和跨篇去重门禁。

**Tech Stack:** Markdown、CSV、Zsh、Python 标准库、ripgrep、现有 Seedance 提示词与编舞规则。

## Global Constraints

- 每篇固定十五秒，并包含第一高潮、第一连接、第二高潮、第二连接、第三高潮和余势结尾。
- 统一时间窗为 0.300—4.200 秒、5.000—8.800 秒、9.600—13.500 秒；13.500—15.000 秒保持动作余势。
- 第一帧处于可发力状态，0.300 秒内明确踏步、换重或躯干发力。
- 每篇三个高潮形成纵向、横向和纵深差异，不连续三次画圆、旋转或双臂对称展开。
- 每篇至少一次非对称高低袖轮廓；袖缘尾端严格两个，不是专业水袖或额外披帛。
- 栀夏始终是同一位楚地祭舞者，不逐集扮演神祇；使用九歌 v03 正式母板。
- 不复制舞台或社区作品的完整编舞、标志动作、舞美、服装、音乐或镜头。
- 少司命最多使用单枝白芷或兰花，国殇最多使用单剑；其他首轮提示词无手持道具。
- 河伯不用长绸，东君不用弓箭，东皇太一不手持鼓槌，山鬼不骑乘赤豹。
- 只完成文字与台账，不生成视频、不调用付费服务。

---

### Task 1: 建立九歌设计回归门禁

**Files:**
- Create: `zhixia-feihualing/tests/test_jiuge_dance_design_rules.sh`
- Create: `zhixia-feihualing/scripts/validate_jiuge_dance_design.py`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-08-30-zhixia-jiuge-15s-three-peak-dance-design.md`

**Interfaces:**
- Consumes: 设计说明中的十一篇清单、统一时间窗、文件结构和禁用项。
- Produces: 一个退出码为 0/1 的回归测试，供后续所有任务验证。

- [x] **Step 1: 写入初始失败测试**

测试脚本使用下面的固定目标清单：

```zsh
chapters=(
  01-donghuang-taiyi-15s 02-yunzhongjun-15s 03-xiangjun-15s
  04-xiangfuren-15s 05-dasiming-15s 06-shaosiming-15s
  07-dongjun-15s 08-hebo-15s 09-shangui-15s
  10-guoshang-15s 11-lihun-15s
)
```

脚本逐个检查 `assets/prompts/jiuge/<name>.md` 存在，并命中以下固定标题：

```text
## 原典与现代转译
## 十五秒舞蹈设计卡
## Seedance 完整提示词
## 验收要点
```

脚本还检查每篇包含 `0.300—4.200 秒`、`5.000—8.800 秒`、`9.600—13.500 秒`、`13.500—15.000 秒`、`严格两个`、`不复刻角色卡排版` 和 `不得生成可辨识人声`。

- [x] **Step 2: 加入 CSV 结构与去重断言**

在测试脚本中使用 Python 标准库读取 `operations/jiuge-dance-design-history.csv`，要求表头严格等于：

```python
required = [
    "order", "chapter", "ritual_phase", "emotion_arc",
    "opening_silhouette", "spatial_route",
    "peak1_family", "peak1_direction", "peak1_window", "peak1_carrier", "peak1_camera",
    "peak2_family", "peak2_direction", "peak2_window", "peak2_carrier", "peak2_camera",
    "peak3_family", "peak3_direction", "peak3_window", "peak3_carrier", "peak3_camera",
    "sleeve_trajectory", "prop", "ending", "status", "notes",
]
```

断言行数为 11、`order` 为 01 至 11、篇名唯一、相邻两篇三高潮家族序列不同，并要求 `status` 全部为 `designed`。

- [x] **Step 3: 运行测试确认失败**

运行：

```bash
zsh zhixia-feihualing/tests/test_jiuge_dance_design_rules.sh
```

预期：失败，首个缺失目标为研究设计文档、CSV 或 `01-donghuang-taiyi-15s.md`。

- [x] **Step 4: 提交测试门禁**

```bash
git add zhixia-feihualing/tests/test_jiuge_dance_design_rules.sh
git commit -m "建立九歌舞蹈设计回归门禁"
```

### Task 2: 整理研究结论与统一动作语法

**Files:**
- Create: `zhixia-feihualing/docs/jiuge-dance-research-and-design.md`
- Reference: `zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md`
- Reference: `zhixia-feihualing/docs/zhixia-poetry-dance-composer.md`
- Reference: `zhixia-feihualing/docs/zhixia-classical-dance-library.md`
- Reference: `zhixia-feihualing/assets/characters/栀夏九歌祭舞-v03-整合式高写实视频母板-Seedance固定说明.md`

**Interfaces:**
- Consumes: 已确认设计说明、原典与网络研究、现有编舞和角色规则。
- Produces: 十一篇设计和提示词共同引用的研究真源。

- [x] **Step 1: 写入证据分级与来源清单**

按“原典与仪式功能、楚乐舞研究、文物形态、舞台与社区可观察性”四节整理来源。每节明确可采用内容和不得推导的内容；写明大量具体舞人形象属于汉代或楚汉传承，项目不宣称复原战国楚舞。

- [x] **Step 2: 写入十五秒统一动作语法**

记录四段时间窗、三高潮进入—发展—离开结构、呼吸与重心传递、纵向横向纵深差异、非对称袖线、严格两个袖缘尾端、脸部可见性和镜头反馈规则。

- [x] **Step 3: 写入十一篇总表与版权边界**

逐篇记录仪式功能、情绪弧线、三高潮家族、主承接物和道具边界；单列说明外部舞台和社区作品只用于观察，不复刻动作组合。

- [x] **Step 4: 运行文档格式检查并提交**

```bash
git diff --check -- zhixia-feihualing/docs/jiuge-dance-research-and-design.md
rg -n "原典与仪式功能|楚乐舞研究|文物形态|舞台与社区|0.300—4.200 秒|严格两个|不宣称复原" zhixia-feihualing/docs/jiuge-dance-research-and-design.md
git add zhixia-feihualing/docs/jiuge-dance-research-and-design.md
git commit -m "整理九歌舞蹈研究与统一语法"
```

预期：格式检查无输出，七类关键条目均命中。

### Task 3: 完成天神五篇设计卡与提示词

**Files:**
- Create: `zhixia-feihualing/assets/prompts/jiuge/01-donghuang-taiyi-15s.md`
- Create: `zhixia-feihualing/assets/prompts/jiuge/02-yunzhongjun-15s.md`
- Create: `zhixia-feihualing/assets/prompts/jiuge/05-dasiming-15s.md`
- Create: `zhixia-feihualing/assets/prompts/jiuge/06-shaosiming-15s.md`
- Create: `zhixia-feihualing/assets/prompts/jiuge/07-dongjun-15s.md`

**Interfaces:**
- Consumes: Task 2 的证据、时间结构和统一动作语法。
- Produces: 五篇天神篇可直接复制的完整 Seedance 提示词。

- [x] **Step 1: 写东皇太一与云中君**

东皇太一固定为“纵向提沉—改面展臂—行进旋转”，无手持鼓槌；云中君固定为“倾身穿行—腾跃展开—行进旋转”，不生成飞天、翅膀或持续悬浮。两篇分别以开坛秩序和留连远游区分。

- [x] **Step 2: 写大司命与少司命**

大司命固定为“改面展臂—行进旋转—纵向提沉”，动作强调切分、定界和下压；少司命固定为“倾身穿行—单枝香草牵引—腾跃展开”，强调回护和上升。两篇不得共享开场剪影或收束方式。

- [x] **Step 3: 写东君**

固定为“行进旋转—纵向提沉—腾跃展开”，由暗到明形成赤金爆发；不生成弓箭，以斜向开臂、目光和光线因果转译射天狼意象。

- [x] **Step 4: 核对五篇文件结构与正文净化**

逐篇检查四个固定标题和四段时间窗。只在设计卡中保留高潮家族名；`## Seedance 完整提示词` 正文删除内部分类、来源 URL、剧目名、舞者名和验收术语。

- [x] **Step 5: 提交天神五篇**

```bash
git add zhixia-feihualing/assets/prompts/jiuge/01-donghuang-taiyi-15s.md \
  zhixia-feihualing/assets/prompts/jiuge/02-yunzhongjun-15s.md \
  zhixia-feihualing/assets/prompts/jiuge/05-dasiming-15s.md \
  zhixia-feihualing/assets/prompts/jiuge/06-shaosiming-15s.md \
  zhixia-feihualing/assets/prompts/jiuge/07-dongjun-15s.md
git commit -m "设计九歌天神五篇十五秒舞蹈"
```

### Task 4: 完成地祇四篇设计卡与提示词

**Files:**
- Create: `zhixia-feihualing/assets/prompts/jiuge/03-xiangjun-15s.md`
- Create: `zhixia-feihualing/assets/prompts/jiuge/04-xiangfuren-15s.md`
- Create: `zhixia-feihualing/assets/prompts/jiuge/08-hebo-15s.md`
- Create: `zhixia-feihualing/assets/prompts/jiuge/09-shangui-15s.md`

**Interfaces:**
- Consumes: Task 2 的统一语法和 Task 3 已使用的视觉指纹。
- Produces: 四篇地祇篇可直接复制的完整 Seedance 提示词。

- [x] **Step 1: 写湘君与湘夫人**

湘君固定为“改面展臂—倾身穿行—纵向提沉”，突出寻找与离岸；湘夫人固定为“纵向提沉—倾身穿行—改面展臂”，突出遥望、靠近又退开。不得使用相同开场、袖线或镜头反馈。

- [x] **Step 2: 写河伯**

固定为“低位扫展—倾身穿行—腾跃展开”，由低位横向水势转入纵深穿浪，再向上破浪离岸；只使用水纹和浪花，不使用长绸。

- [x] **Step 3: 写山鬼**

固定为“倾身穿行—改面展臂—纵向提沉”，从穿林赴约、含睇宜笑转为等待落空；赤豹只作远景掠影，不骑乘，不使用手持花枝。

- [x] **Step 4: 核对四篇文件结构与正文净化**

逐篇检查四个固定标题、四段时间窗、严格两个袖缘尾端和脸部可见性。确保湘君、湘夫人、河伯三篇水景没有默认共享圆形水特效。

- [x] **Step 5: 提交地祇四篇**

```bash
git add zhixia-feihualing/assets/prompts/jiuge/03-xiangjun-15s.md \
  zhixia-feihualing/assets/prompts/jiuge/04-xiangfuren-15s.md \
  zhixia-feihualing/assets/prompts/jiuge/08-hebo-15s.md \
  zhixia-feihualing/assets/prompts/jiuge/09-shangui-15s.md
git commit -m "设计九歌地祇四篇十五秒舞蹈"
```

### Task 5: 完成人鬼与送神两篇设计卡与提示词

**Files:**
- Create: `zhixia-feihualing/assets/prompts/jiuge/10-guoshang-15s.md`
- Create: `zhixia-feihualing/assets/prompts/jiuge/11-lihun-15s.md`

**Interfaces:**
- Consumes: Task 2 的统一语法和前九篇已使用的视觉指纹。
- Produces: 国殇与礼魂两篇可直接复制的完整 Seedance 提示词。

- [x] **Step 1: 写国殇**

固定为“单剑牵引—腾跃展开—纵向提沉”。栀夏以祭舞悼念阵亡者，不扮演士兵，不表现具体砍杀、刺中、血液、尸体或军阵混战；单剑始终保持唯一持有关系。

- [x] **Step 2: 写礼魂**

固定为“改面展臂—行进旋转—纵向提沉”。动作沿祭坛外圈缓行，最后收掌、提起目送；不得与东皇太一共享开场或收势，不提前静止。

- [x] **Step 3: 核对完整仪式闭环并提交**

确认第一篇从开坛启动，最后一篇以送神余势结束；国殇的悲壮不污染礼魂的平静收束。

```bash
git add zhixia-feihualing/assets/prompts/jiuge/10-guoshang-15s.md \
  zhixia-feihualing/assets/prompts/jiuge/11-lihun-15s.md
git commit -m "设计九歌国殇礼魂十五秒舞蹈"
```

### Task 6: 建立十一篇视觉指纹台账

**Files:**
- Create: `zhixia-feihualing/operations/jiuge-dance-design-history.csv`
- Modify: `zhixia-feihualing/assets/prompts/jiuge/*.md`

**Interfaces:**
- Consumes: Tasks 3—5 的十一篇最终设计卡。
- Produces: 每篇一行、字段完整、可自动比较的去重台账。

- [x] **Step 1: 写入固定 CSV 表头与十一行**

严格使用 Task 1 定义的 26 列表头。每行完整填写三高潮家族、方向、时间窗、承接物、镜头反馈、袖缘轨迹、道具、结尾、`designed` 状态和备注，不留空值。

- [x] **Step 2: 执行跨篇去重审计**

按顺序比较相邻篇章和最近五篇：三高潮序列不得相同；九项视觉指纹相同三项或以上时，优先修改空间路线、袖缘轨迹或镜头反馈，并同步修改对应提示词文件。

- [x] **Step 3: 运行回归测试并提交台账**

```bash
zsh zhixia-feihualing/tests/test_jiuge_dance_design_rules.sh
git add zhixia-feihualing/operations/jiuge-dance-design-history.csv \
  zhixia-feihualing/assets/prompts/jiuge
git commit -m "建立九歌十一篇舞蹈去重台账"
```

预期：测试输出 `PASS: Jiuge 15s three-peak dance designs are complete and distinct`，退出码为 0。

### Task 7: 同步入口状态并完成总验收

**Files:**
- Modify: `zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md`
- Modify: `zhixia-feihualing/README.md`
- Verify: `zhixia-feihualing/docs/jiuge-dance-research-and-design.md`
- Verify: `zhixia-feihualing/assets/prompts/jiuge/*.md`
- Verify: `zhixia-feihualing/operations/jiuge-dance-design-history.csv`

**Interfaces:**
- Consumes: Tasks 1—6 的全部交付物与通过的回归测试。
- Produces: 可发现的项目入口、准确的制作状态和最终验收证据。

- [x] **Step 1: 更新项目入口与状态**

在 README 文档导航加入“九歌祭舞研究与十一篇舞蹈设计”；在文化诗舞路线图中把状态更新为“十一篇十五秒文字设计完成，尚未生成或验证视频”。

- [x] **Step 2: 运行完整验证**

```bash
zsh zhixia-feihualing/tests/test_jiuge_dance_design_rules.sh
git diff --check -- zhixia-feihualing/README.md \
  zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md \
  zhixia-feihualing/docs/jiuge-dance-research-and-design.md \
  zhixia-feihualing/assets/prompts/jiuge \
  zhixia-feihualing/operations/jiuge-dance-design-history.csv \
  zhixia-feihualing/tests/test_jiuge_dance_design_rules.sh
```

预期：回归测试通过，`git diff --check` 无输出。

- [x] **Step 3: 人工抽查高风险五篇**

抽查东皇太一、少司命、河伯、山鬼和国殇，确认分别没有手持鼓槌、香草增生、长绸、骑乘赤豹和具体血腥厮杀；确认五篇均使用九歌 v03 身份与严格两个袖缘尾端。

- [x] **Step 4: 提交入口与状态**

```bash
git add zhixia-feihualing/README.md \
  zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md
git commit -m "完成九歌十一篇舞蹈设计入口"
```
