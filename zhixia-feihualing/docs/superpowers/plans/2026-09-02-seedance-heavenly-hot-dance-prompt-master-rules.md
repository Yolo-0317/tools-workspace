# 《天宫热舞》Seedance 提示词母规则 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已确认的《天宫热舞》设计固化为可复用母规则、四份单一舞种模块、精简提示词模板和分级验收资料，并登记本次双人成片的真实复盘结论。

**Architecture:** 新建 `docs/heavenly-hot-dance/` 作为项目级规则目录，母规则只定义全系列共同约束，四份舞种模块分别提供独立动作词汇，模板负责组装素材与时间线，验收清单负责生成后的三级决策。现有双人 episode 只新增本次视频复盘记录，不覆盖已经使用过的 v01 提示词、音乐结构或原验收清单。

**Tech Stack:** Markdown、Seedance 2.0 多模态引用规范、`rg`、Git。

## Global Constraints

- 规则适用于《天宫热舞》单人和双人视频，不替代《一舞一愿》朗诵诗词主线。
- 每期只启用卡点摇、轻街舞、现代舞或拉丁中的一个主舞种；拉丁必须进一步选择恰恰、桑巴或牛仔之一。
- 10 秒至少两组连续舞步，每组至少 1.5 秒，并包含脚步换重和两个以上身体重拍。
- 第一帧进入舞蹈，走路累计不超过 0.8 秒，互动累计不超过 2 秒，单次静止或纯摆姿不超过 0.25 秒。
- 5–8 秒为最高能量段，8–10 秒保持同等动作密度，运动持续至最后约 0.2 秒。
- 使用平台实际插入的 `@素材标签`；角色图片、动作视频和音频分别承担明确职责，不手工伪造引用标签。
- 有合法动作视频时优先用其参考动作密度和节奏；所有动作视频必须为自有或已获授权素材。
- 阿砚墨尾保持自然粗细、开放 S 形与低幅度滞后摆动，不变成粗大问号、圆环或独立书法笔画。
- 正式可复制正文采用“素材职责、角色关系、单一舞种、五段时间线、场景镜头、精简约束”六段结构。
- 时间线使用 `0–2 秒、2–4 秒、4–6 秒、6–8 秒、8–10 秒`，不使用虚假毫秒精度。
- 本计划只创建和验证文本资产；不调用 Seedance，不生成视频，不执行外部付费操作。

---

### Task 1: 创建全系列母规则

**Files:**
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-09-02-seedance-heavenly-hot-dance-prompt-master-rules-design.md`
- Reference: `zhixia-feihualing/docs/seedance-case-library/03-dance-and-body-movement.md`
- Reference: `zhixia-feihualing/docs/seedance-case-library/09-multimodal-reference.md`
- Create: `zhixia-feihualing/docs/heavenly-hot-dance/master-rules.md`

**Interfaces:**
- Consumes: 已确认设计、案例库中的舞蹈与多模态证据。
- Produces: 后续四份舞种模块、提示词模板和验收清单共同引用的唯一全系列规则。

- [ ] **Step 1: 建立规则身份和适用边界**

文件开头明确：

```text
# 《天宫热舞》Seedance 提示词母规则

适用于栀夏、阿砚及后续天宫角色的10秒单人或双人热舞。角色身份来自角色固定说明，本文只控制舞蹈密度、素材分工、时间线、镜头和生成边界。本规则不替代《一舞一愿》朗诵诗词视频规范。
```

- [ ] **Step 2: 写入动作密度硬指标**

逐项写入第一帧开跳、至少两组连续舞步、每组至少 1.5 秒、每 2 秒至少一个身体重拍、走路累计不超过 0.8 秒、互动不超过 2 秒、静止不超过 0.25 秒、5–8 秒最高能量、8–10 秒不降速和最后约 0.2 秒仍在运动。

- [ ] **Step 3: 写入素材职责与官方能力边界**

明确：

```text
- @图片：只参考人物身份、体态和服装。
- @视频：只参考舞步、动作密度、身体节奏和双人关系，不参考原人物、服装和场景。
- @音频：只参考拍速、重拍、能量变化和结束点，不参考人声。
```

同时写明素材标签以实际页面插入结果为准；视频素材必须自有或获授权；多模态引用提高控制力但不保证逐帧复刻；官方来源与项目实测结论分段呈现。

- [ ] **Step 4: 写入反走秀、服装物理和墨尾规则**

固定加入设计稿中的反走秀正文，并明确大幅举臂最多一次、飘带只做动作后的延迟反馈、阿砚墨尾只做低幅度滞后摆动。

- [ ] **Step 5: 写入提示词结构和精简排除项**

列出六段顺序，并只保留以下六类排除：不走秀巡游、不提前停舞、不换脸融合、不增加肢体猫耳墨尾、不穿模浮脚、不使用危险低俗或性暗示动作。

- [ ] **Step 6: 验证并提交母规则**

Run:

```bash
rg -n "至少两组|1\.5 秒|每 2 秒|0\.8 秒|不超过 2 秒|0\.25 秒|5–8 秒|8–10 秒|最后约 0\.2 秒|@图片|@视频|@音频|自有或已获授权|反走秀|低幅度滞后" zhixia-feihualing/docs/heavenly-hot-dance/master-rules.md
git diff --no-index --check /dev/null zhixia-feihualing/docs/heavenly-hot-dance/master-rules.md
test $? -le 1
```

Expected: 所有母规则至少命中一次，空白检查没有诊断输出。

显式只暂存该文件并提交：

```text
文档：固化天宫热舞提示词母规则
```

### Task 2: 创建四份单一舞种模块

**Files:**
- Reference: `zhixia-feihualing/docs/heavenly-hot-dance/master-rules.md`
- Create: `zhixia-feihualing/docs/heavenly-hot-dance/modules/beat-dance.md`
- Create: `zhixia-feihualing/docs/heavenly-hot-dance/modules/light-hiphop.md`
- Create: `zhixia-feihualing/docs/heavenly-hot-dance/modules/modern-dance.md`
- Create: `zhixia-feihualing/docs/heavenly-hot-dance/modules/latin-dance.md`

**Interfaces:**
- Consumes: 母规则的动作密度、风险边界和五段时间线。
- Produces: 每期只能选择其中一份的动作模块；模板通过模块名称与可复制动作段使用它们。

- [ ] **Step 1: 创建卡点摇模块**

文件必须给出两套不同组合：

```text
组合A：侧向弹步四拍 → 连续肩部顿点两拍 → 胸腔收放两拍 → 反方向侧步与前臂切线四拍。
组合B：交叉换重四拍 → 髋部左右切换两拍 → 手腕甩点两拍 → 短促回弹并改变朝向四拍。
```

声明走秀、反复抬臂、原地扭胯和慢速仙女转圈不计入舞步。

- [ ] **Step 2: 创建轻街舞模块**

文件必须给出两套组合：弹性律动＋左右踏点＋上身隔离＋手臂锁点；反方向踏点＋短距离侧滑＋胸肩顿点＋快速回弹。排除地板动作、大跳、快速深蹲、力量翻转和连续高速旋转。

- [ ] **Step 3: 创建现代舞模块**

文件必须给出两套组合：斜线跨步＋身体收缩＋快速释放＋手臂切线；重心倾斜＋脚下换重＋快速回弹＋反方向延展。每次延展后立即回收或落重拍，排除长时间仰头、原地挥袖和连续慢转。

- [ ] **Step 4: 创建拉丁模块**

分别给出恰恰、桑巴和牛仔三个子模块，每期只能选一个：

```text
恰恰：检查步、横向追步、纽约步或锁步中选择两组。
桑巴：弹跳动作、桑巴走步和博塔弗戈中选择两组。
牛仔：原地基本步、换位步和踢步中选择两组。
```

三者都必须写明脚步换重、膝盖伸屈和足底着力，髋部由腿部动作带动。

- [ ] **Step 5: 给每个模块加入使用接口**

每个文件统一包含：`适用气质`、`可复制动作段`、`双人改写`、`禁止退化`、`验收动作`五个标题。双人改写只能调整方向、半拍和高低层次，不降低母规则动作密度。

- [ ] **Step 6: 验证并提交四份模块**

Run:

```bash
for file in beat-dance light-hiphop modern-dance latin-dance; do rg -n "适用气质|可复制动作段|双人改写|禁止退化|验收动作" "zhixia-feihualing/docs/heavenly-hot-dance/modules/$file.md"; done
rg -n "侧向弹步|肩部顿点|胸腔收放|手腕甩点" zhixia-feihualing/docs/heavenly-hot-dance/modules/beat-dance.md
rg -n "弹性律动|左右踏点|上身隔离|手臂锁点|短距离侧滑" zhixia-feihualing/docs/heavenly-hot-dance/modules/light-hiphop.md
rg -n "身体收缩|快速释放|重心倾斜|快速回弹" zhixia-feihualing/docs/heavenly-hot-dance/modules/modern-dance.md
rg -n "恰恰|桑巴|牛仔|膝盖伸屈|足底着力" zhixia-feihualing/docs/heavenly-hot-dance/modules/latin-dance.md
```

Expected: 四份文件结构一致，各自关键动作完整命中。

对四份文件运行 `git diff --no-index --check /dev/null <file>`，确认无空白诊断后一起提交：

```text
文档：增加天宫热舞四类舞种模块
```

### Task 3: 创建精简提示词模板

**Files:**
- Reference: `zhixia-feihualing/docs/heavenly-hot-dance/master-rules.md`
- Reference: `zhixia-feihualing/docs/heavenly-hot-dance/modules/beat-dance.md`
- Reference: `zhixia-feihualing/docs/heavenly-hot-dance/modules/light-hiphop.md`
- Reference: `zhixia-feihualing/docs/heavenly-hot-dance/modules/modern-dance.md`
- Reference: `zhixia-feihualing/docs/heavenly-hot-dance/modules/latin-dance.md`
- Create: `zhixia-feihualing/docs/heavenly-hot-dance/prompt-template.md`

**Interfaces:**
- Consumes: 母规则与当期唯一舞种模块。
- Produces: 可按单人、双人、动作视频和音频四种输入组合填充的六段 Seedance 正文模板。

- [ ] **Step 1: 写入素材组合表**

列出四种组合：单角色图＋文字、双角色图＋文字、角色图＋合法动作视频、角色图＋合法动作视频＋10秒纯音乐。每种组合明确所需素材和适用场景。

- [ ] **Step 2: 写入六段模板**

模板按以下顺序提供可替换槽位：

```text
1. 素材职责：{角色标签}、{动作视频标签或无}、{音频标签或无}。
2. 角色关系：{单人主舞或双人主次}。
3. 单一舞种：只粘贴一份模块中的可复制动作段。
4. 五段时间线：0–2、2–4、4–6、6–8、8–10秒。
5. 场景镜头：前景英雄式天宫、完整全身、稳定单镜头。
6. 精简约束：六类关键排除。
```

槽位必须配有一个完整的双人卡点摇示例，但示例不得重复旧版 9 千字提示词。

- [ ] **Step 3: 写入有无动作视频的差异**

有 `@视频` 时，文字只负责角色替换、天宫场景、素材职责和动作边界，不逐拍重写参考视频中的每个动作；无 `@视频` 时，必须完整粘贴一个舞种模块的连续动作段。

- [ ] **Step 4: 写入有无音频的差异**

有 `@音频` 时直接要求动作重拍对应音频，不再文字指定 124 BPM；无音频时才写拍速、0 秒落拍、5–8 秒最高能量和最后一拍结束。

- [ ] **Step 5: 验证并提交模板**

Run:

```bash
rg -n "素材职责|角色关系|单一舞种|0–2 秒|2–4 秒|4–6 秒|6–8 秒|8–10 秒|场景镜头|精简约束|有动作视频|无动作视频|有音频|无音频|双人卡点摇示例" zhixia-feihualing/docs/heavenly-hot-dance/prompt-template.md
```

Expected: 六段结构、四种输入差异和完整示例均存在。

运行空白检查后只提交模板：

```text
文档：增加天宫热舞精简提示词模板
```

### Task 4: 创建全系列验收表并登记本次视频

**Files:**
- Reference: `zhixia-feihualing/docs/heavenly-hot-dance/master-rules.md`
- Reference: `zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/qa-checklist.md`
- Create: `zhixia-feihualing/docs/heavenly-hot-dance/qa-checklist.md`
- Create: `zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/review-9f8429ad.md`

**Interfaces:**
- Consumes: 母规则的硬指标和原 episode 验收结构。
- Produces: 所有后续热舞共用的三级验收表，以及本次候选的可追溯复盘记录。

- [ ] **Step 1: 创建三级验收表**

`qa-checklist.md` 明确三种结论：

- 热舞合格：至少两组连续舞步、每组至少 1.5 秒、5–10 秒不降速、最后约 0.2 秒仍运动。
- 视觉可用但热舞不足：角色场景稳定，但主要是走位、举臂、慢转或摆姿。
- 直接淘汰：换脸、融合、额外肢体、穿模、耳尾错误、长期浮脚、前 2 秒无动作或 8 秒前停舞。

- [ ] **Step 2: 加入舞种专项验收**

为卡点摇、轻街舞、现代舞和拉丁各加入至少三项可见动作检查；拉丁按恰恰、桑巴、牛仔分别判断，不能用泛化摆胯判为合格。

- [ ] **Step 3: 登记本次视频**

`review-9f8429ad.md` 固定记录：

```text
文件：9f8429ad-6817-4244-bb6f-c3827c476779.mp4
时长：10.08秒
结论：视觉可用但热舞不足
用途：天宫双姝亮相、系列预告、封面或过场素材
处理：保留，不返工，不作为热舞动作标准
```

优点写入天宫、人物大小、身份区分、首秒动作和一次互动换位；问题写入走秀化、5 秒后未形成强卡点、8 秒后降速、约 9.40 秒音频进入静音以及墨尾粗大问号化。

- [ ] **Step 4: 验证并提交验收资料**

Run:

```bash
rg -n "热舞合格|视觉可用但热舞不足|直接淘汰|至少两组|1\.5 秒|5–10 秒|最后约 0\.2 秒|卡点摇|轻街舞|现代舞|恰恰|桑巴|牛仔" zhixia-feihualing/docs/heavenly-hot-dance/qa-checklist.md
rg -n "9f8429ad|10\.08秒|视觉可用但热舞不足|保留，不返工|走秀|5 秒后|8 秒后|9\.40 秒|问号" zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/review-9f8429ad.md
```

Expected: 分级、舞种验收和本次真实复盘均完整命中。

运行两个文件的空白检查后一起提交：

```text
文档：登记天宫双人亮相片并更新热舞验收
```

### Task 5: 全套一致性与非回归验证

**Files:**
- Inspect: `zhixia-feihualing/docs/heavenly-hot-dance/master-rules.md`
- Inspect: `zhixia-feihualing/docs/heavenly-hot-dance/modules/*.md`
- Inspect: `zhixia-feihualing/docs/heavenly-hot-dance/prompt-template.md`
- Inspect: `zhixia-feihualing/docs/heavenly-hot-dance/qa-checklist.md`
- Inspect: `zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/review-9f8429ad.md`

**Interfaces:**
- Consumes: Tasks 1–4 的全部文本产物。
- Produces: 术语、时间线、舞种名称、素材标签规则和分级结果一致的可复用规则包。

- [ ] **Step 1: 检查名称与时间线一致**

Run:

```bash
rg -n "卡点摇|轻街舞|现代舞|拉丁" zhixia-feihualing/docs/heavenly-hot-dance
rg -n "0–2 秒|2–4 秒|4–6 秒|6–8 秒|8–10 秒" zhixia-feihualing/docs/heavenly-hot-dance/{master-rules.md,prompt-template.md}
```

Expected: 四类舞种名称统一，母规则与模板使用同一五段时间线。

- [ ] **Step 2: 检查关键数值一致**

Run:

```bash
rg -n "1\.5 秒|0\.8 秒|不超过 2 秒|0\.25 秒|最后约 0\.2 秒" zhixia-feihualing/docs/heavenly-hot-dance/{master-rules.md,qa-checklist.md,prompt-template.md}
```

Expected: 母规则是数值真源，模板和验收表没有冲突值。

- [ ] **Step 3: 检查素材引用与版权边界**

Run:

```bash
rg -n "实际.*@素材标签|@图片|@视频|@音频|自有或.*授权|不保证逐帧" zhixia-feihualing/docs/heavenly-hot-dance/{master-rules.md,prompt-template.md}
```

Expected: 实际标签、素材职责、授权要求和能力边界均存在。

- [ ] **Step 4: 检查旧产物未被覆盖**

Run:

```bash
git diff --exit-code -- zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/prompt.md zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/music-structure.md zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/qa-checklist.md
```

Expected: 旧提示词、音乐结构和原验收表无差异。

- [ ] **Step 5: 检查提交范围**

Run:

```bash
git status --short -- zhixia-feihualing/docs/heavenly-hot-dance zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/review-9f8429ad.md
git log -5 --oneline -- zhixia-feihualing/docs/heavenly-hot-dance zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/review-9f8429ad.md
```

Expected: 所有计划产物均已提交，未把工作区其他现有改动带入提交；不推送、不调用 Seedance。
