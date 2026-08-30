# 《反弹琵琶》道具卡提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一份可直接用于图片生成工具的《反弹琵琶》独立道具卡中文提示词。

**Architecture:** 使用单一 Markdown 文件保存正式提示词，按“生成任务—唯一道具—版式—三视图—拆解与材质—反弹连接示意—整体效果—严格禁止”组织。提示词只描述道具卡，不生成栀夏、不修改角色母板、不登记尚未生成和确认的图片资产。

**Tech Stack:** Markdown、ripgrep、Git。

## Global Constraints

- 真源为 `docs/superpowers/specs/2026-08-30-fantan-pipa-prop-card-design.md`。
- 全卡只设计同一把四弦曲项琵琶，正面、严格右侧面和背面结构必须对应。
- 固定深胡桃木、暖象牙、孔雀蓝、朱砂红、绿松石和旧金六色体系。
- 连接示意只使用中性灰、无脸、无发型、无服装细节的人体轮廓。
- 不出现栀夏或其他具体人物，不生成舞蹈场景、角色海报或现成舞剧造型。
- 不宣称历史复原，不复制《丝路花雨》或其他现成舞剧的具体造型与编舞。
- 不生成第二把琵琶、额外弦、现代背带、悬浮、发光、穿体、武器化、塑料感、水印和裁切。

---

### Task 1: 写入正式图片生成提示词

**Files:**
- Create: `zhixia-feihualing/assets/props/fantan-pipa-v01/master-prompt.md`

**Interfaces:**
- Consumes: 已确认的道具卡设计规范。
- Produces: 一段可直接复制到图片生成工具的中文提示词。

- [x] **Step 1: 建立提示词文档**

文档只保留标题、使用说明和一个完整提示词代码块。使用说明注明“全新生成，无需上传人物参考图”；正文首段明确生成纵向 2:3 的专业敦煌琵琶道具设定卡，而非人物海报或场景插画。

- [x] **Step 2: 写入道具与三视图约束**

正文固定一把修长梨形四弦曲项琵琶的轮廓、尺寸、六色、真实木材与旧金材质，以及正面、严格右侧面、背面三视图等高、完整入画、可逐项对应。

- [x] **Step 3: 写入拆解和反弹连接示意**

正文列出琴头、四弦、品柱、琴面纹样、捍拨、背板和旧金包边特写；连接区使用无身份灰色人体轮廓，清楚展示琵琶位于后颈下方和双肩后方、一手握琴颈、一手位于弦区、琴身不穿体。

- [x] **Step 4: 写入负面约束**

结尾集中禁止具体人物、多琴、结构错乱、现代元素、悬浮发光、武器化、塑料感、场景背景、文字乱码、水印和裁切，并要求优先保证道具结构而非生成大量小字。

### Task 2: 自审与提交

**Files:**
- Verify: `zhixia-feihualing/assets/props/fantan-pipa-v01/master-prompt.md`
- Modify: `zhixia-feihualing/docs/superpowers/plans/2026-08-30-fantan-pipa-prop-card-prompt.md`

**Interfaces:**
- Consumes: Task 1 的正式提示词。
- Produces: 已核对、已提交的提示词存档。

- [x] **Step 1: 对照规范逐项校验**

人工核对唯一四弦琵琶、三视图、六色材质、结构拆解、灰色连接示意、人物排除、历史表述边界和全部禁止项均已覆盖。纯文案不建立逐字匹配自动化测试，避免正常润色触发无意义失败。

- [x] **Step 2: 检查文件质量**

运行 `git diff --check`，再检查提示词不存在占位标记、内部工作说明、未解释的资产路径或图片编号。

- [x] **Step 3: 提交提示词**

只暂存本计划与 `assets/props/fantan-pipa-v01/master-prompt.md`，提交信息使用：

```bash
git commit -m '制作反弹琵琶道具卡提示词'
```
