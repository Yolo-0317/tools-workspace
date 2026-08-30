# 《月照反弹琵琶》15 秒 Seedance 提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成《栀夏·敦煌十六舞》第二支《月照反弹琵琶》的单集说明、可直接提交 Seedance 的 15 秒完整提示词和跨集三高潮去重记录。

**Architecture:** 单集目录保存内容真源与生成提示词，提示词使用图片 1 栀夏 v03 和图片 2 反弹琵琶上传版，按 0—15 秒六段动作顺序展开。舞蹈去重台账新增一行，记录纵向、横向、纵深三次高潮及秋夜长风与冷月反光机制；纯文案使用人工规范校验，不建立逐字匹配自动化测试。

**Tech Stack:** Markdown、CSV、ripgrep、Git。

## Global Constraints

- 设计真源为 `docs/superpowers/specs/2026-08-30-fantan-pipa-15s-dance-design.md`。
- 15 秒、9:16、一镜到底，三次同等强度高潮分别位于 0.000—1.800、4.800—7.000、10.000—13.000 秒。
- 图片 1 只锁定栀夏敦煌 v03 身份与服化道，图片 2 只锁定唯一四弦四轴琵琶。
- 琵琶全程横置肩后，一手握琴颈、一手位于弦区，不增生、换向、离手、悬浮、发光或穿体。
- 三次方向固定为纵向蹬地提展、横向宽弓急停、纵深沉提远展；7 秒后无完整旋转。
- 唯一环境机制为秋夜长风与冷月反光，不生成金色细沙或额外特效系统。
- 摄影机只有侧前方低位缓慢后退主路径，12.500 秒后不继续拉远。
- 生成阶段无人声、无诗句、无字幕、无标题和无水印；四句诗后期另行制作。

---

### Task 1: 建立单集真源与 Seedance 提示词

**Files:**
- Create: `zhixia-feihualing/episodes/fantan-pipa-15s/README.md`
- Create: `zhixia-feihualing/episodes/fantan-pipa-15s/prompts/seedance-v01.md`

**Interfaces:**
- Consumes: 已确认设计规范、栀夏敦煌 v03 上传版、反弹琵琶上传版。
- Produces: 单集定位与一段可直接复制提交 Seedance 的正式提示词正文。

- [x] **Step 1: 写单集 README**

记录系列编号 02、工作标题《月照反弹琵琶》、王昌龄《从军行七首·其二》四句、两张上传图路径、三高潮摘要、生成边界和当前状态“提示词已完成，等待生成原片”。

- [x] **Step 2: 写参考图映射与总目标**

提示词首段声明图片 1 为原创虚拟角色栀夏、图片 2 为原创设计的虚构乐器道具，不对应现实人物或现成影视舞剧资产；分别限定身份服化道与琵琶结构职责，并禁止复刻卡面排版。

- [x] **Step 3: 写 0—10 秒动作**

按 0.000—1.800、1.800—4.800、4.800—7.000、7.000—10.000 秒依次写纵向高潮、侧向连接、横向高潮和前后连接；明确腿部承重、躯干方向、双手接触、琵琶方向、飘带轨迹和对应镜头反馈。

- [x] **Step 4: 写 10—15 秒动作**

按 10.000—13.000 和 13.000—15.000 秒写纵深沉提远展与高能量余势；第三高潮人物全身不低于画面 60%，12.500 秒后不继续拉远，最后一帧在运动中结束。

- [x] **Step 5: 写全局连续性、场景、运镜与声音**

集中锁定同一张脸、固定服装、四弦四轴、肩后持琴、飘带固定点、秋夜城关、长风与冷月反光、单一路径运镜、无人声配乐及禁止项；末尾注明四句诗朗诵和字幕后期加入。

### Task 2: 登记三高潮去重信息

**Files:**
- Modify: `zhixia-feihualing/operations/dance-design-history.csv`

**Interfaces:**
- Consumes: Task 1 已固化的三高潮顺序与环境机制。
- Produces: `fantan-pipa-15s` 去重记录。

- [x] **Step 1: 追加单集记录**

新增 `fantan-pipa-15s` 行：诗文为王昌龄《从军行七首·其二》；高潮顺序为纵向反弹提展、横向宽弓急停、纵深沉提远展；旋转上限为一次不超过 90 度改面且 7 秒后零完整旋转；承接物为肩后四弦琵琶与蓝橙双层飘带；视觉机制为秋夜长风和冷月反光；镜头反应依次为降低微推、有限横移、短撤轻抬。

### Task 3: 校验与提交

**Files:**
- Verify: `zhixia-feihualing/episodes/fantan-pipa-15s/README.md`
- Verify: `zhixia-feihualing/episodes/fantan-pipa-15s/prompts/seedance-v01.md`
- Verify: `zhixia-feihualing/operations/dance-design-history.csv`
- Modify: `zhixia-feihualing/docs/superpowers/plans/2026-08-30-fantan-pipa-15s-seedance-prompt.md`

**Interfaces:**
- Consumes: Task 1 和 Task 2 的全部产物。
- Produces: 已校验并提交的第二支舞 Seedance 提示词存档。

- [x] **Step 1: 逐项核对设计覆盖**

人工核对两张图映射、六段时间窗、三方向高潮、四弦四轴、双手接触、飘带固定、12.500 秒镜头边界、唯一环境机制、无人声边界和后期诗文说明均已出现，且不存在内部动作编号或模糊的“继续起舞”“类似动作”。

- [x] **Step 2: 检查文件质量与暂存范围**

运行 `git diff --check`，检查无占位标记；只暂存本计划、单集 README、Seedance 提示词和舞蹈历史中的新增一行，保留其他未提交改动。

- [x] **Step 3: 提交提示词**

```bash
git commit -m '制作敦煌反弹琵琶视频提示词'
```
