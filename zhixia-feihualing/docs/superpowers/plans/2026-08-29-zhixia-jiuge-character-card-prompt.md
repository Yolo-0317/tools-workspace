# 栀夏九歌祭舞角色卡提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute this plan inline in the current task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出一份以栀夏日常 v04 角色母板为图片1、可直接用于图片生成的《九歌祭舞》完整角色卡提示词。

**Architecture:** 提示词按身份锁定、档案卡版式、妆发、服装、纹样材质、六表情和禁止项分段。图片1只提供栀夏身份与版式，新九歌造型独立于日常 v04 和敦煌 v02。

**Tech Stack:** 中文自然语言图片生成提示词、Markdown 文档、人工规则核对。

## Global Constraints

- 不调用图片生成，只交付提示词。
- 图片1固定为栀夏日常 v04 角色母板上传版。
- 保留同一张脸、18岁年龄感、自然修长约7头身比例、三视图和六表情信息结构。
- 九歌造型采用玄黑、朱红、暖象牙白、暗金和少量浅青玉色。
- 不继承日常青绿常服，也不混入敦煌 v02 的妆发、莲焰冠、蓝橙飘带和露腰舞服。

---

### Task 1: 生成并核验完整角色卡提示词

**Files:**
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-08-29-zhixia-jiuge-ritual-dancer-character-card-design.md`
- Create: `zhixia-feihualing/assets/characters/work/栀夏九歌祭舞统一角色卡-v01-生成提示词.md`

**Interfaces:**
- Consumes: 用户上传的栀夏日常 v04 角色母板，作为图片1。
- Produces: 一段可直接复制到图片生成工具的中文提示词，不触发实际生成。

- [x] **Step 1: 建立提示词骨架**

按“用途与输入 → 身份锁定 → 版式 → 妆发 → 服装 → 纹样材质 → 六表情 → 禁止项”的顺序组织，避免互相矛盾的重复要求。

- [x] **Step 2: 写入全部固定设计**

逐项覆盖设计规范中的单体盘髻、黑漆凤鸟冠梳、一体式宽袖、两个袖缘尾端、高腰多层长裙、朱红斜裁裙片、固定配饰和五色色板。

- [x] **Step 3: 写入身份与系列隔离门禁**

明确图片1只锁定身份与档案卡结构，禁止复刻日常服装，禁止混入敦煌 v02 和普通仙侠元素。

- [x] **Step 4: 核验提示词**

运行：

```bash
rg -n "图片1|同一张脸|严格右侧面|黑漆凤鸟冠梳|两个末端|六种表情|敦煌|严格禁止" 'zhixia-feihualing/assets/characters/work/栀夏九歌祭舞统一角色卡-v01-生成提示词.md'
```

预期：八类门禁均至少命中一次；`git diff --check` 无格式错误。
