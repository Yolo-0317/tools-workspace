# Seedance Character Continuity Prompt Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已确认的远景角色连续性、风险节点局部重锚和环境相邻语义排除规则并入现行 Seedance 通用视觉规范。

**Architecture:** 以 `docs/realistic-visual-style.md` 继续作为现行单一事实源，不修改任何单集提示词。规则分别落入人物与角色、摄影与剪辑、Seedance 固定要求、生成前门禁和验收顺序，使提示词编写、提交与生成后抽检形成闭环。

**Tech Stack:** Markdown、`rg`、`git diff --check`。

## Global Constraints

- 本次只更新通用规范，不修改已经完成的《登高》单集提示词或成片。
- 角色身份、物种结构、肢体与附属物数量、相对比例、固定标记和核心材质，优先级始终高于运镜、景别、景观、粒子和其他特效。
- 关键风险节点使用简短正向身份重锚，不机械复制完整角色母版。
- 末尾禁止项只做全局兜底，不承担关键节点的主要约束职责。
- 不生成或修改任何图片、视频、音频资产。

---

### Task 1: 将角色连续性规则并入现行规范

**Files:**
- Modify: `zhixia-feihualing/docs/realistic-visual-style.md`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-08-28-seedance-character-continuity-prompt-rules-design.md`

**Interfaces:**
- Consumes: 已确认设计中的角色优先级、风险节点、局部重锚、角色占比、相邻语义排除和抽检规则。
- Produces: 后续所有场景卡与 Seedance 提示词共同遵守的现行视觉规范。

- [ ] **Step 1: 在人物与角色章节加入不可让渡优先级和风险节点重锚规则**

加入以下要求：角色身份与结构高于景观和特效；角色进入全景、面积明显下降、快速运动、遮挡后重新出现、方向或空间变化以及复杂大景揭示时，时间轴必须就地重复最短必要的正向身份锚点；栀夏与阿砚分别描述，不使用“二人保持一致”等含糊表述。

- [ ] **Step 2: 在摄影与剪辑章节加入角色占比与环境相邻语义规则**

明确时间轴必须写出关键节点的景别、画面区域和最低可辨识状态；景观与角色冲突时先降低环境复杂度或运镜幅度。自然水体、云雾、墨迹和粒子必须排除相邻错误语义，例如无船江面不得形成 V 形尾流、平行白线、规则航迹或多条船迹状高光。

- [ ] **Step 3: 更新 Seedance 固定要求与付费生成前门禁**

加入风险节点识别、局部正向重锚、双角色分别约束、核心限制就地书写和环境相邻语义检查。保持现有参考图、无人声、单一运镜机关与后期字幕规则不变。

- [ ] **Step 4: 更新验收顺序**

要求抽检第一帧、每次景别或方向变化前后、角色遮挡后重新出现时、高潮揭示和最后一帧；检查角色身份、物种、数量、比例、固定标记、远景轮廓、核心材质以及环境是否暗示不存在的船只、道路、额外角色或文字。

- [ ] **Step 5: 验证规则已覆盖且未改动单集提示词**

Run:

```bash
rg -n '不可让渡|局部重锚|相邻视觉语义|V 形尾流|景别或方向变化前后' zhixia-feihualing/docs/realistic-visual-style.md
git diff --check -- zhixia-feihualing/docs/realistic-visual-style.md
git diff --quiet -- zhixia-feihualing/episodes/denggao-10s/prompts/seedance-v01.md
```

Expected: 第一条命令命中新规则；第二条命令无输出且退出码为 0；第三条命令用于确认本次实施没有继续改动《登高》提示词，但如果该文件在实施前已有用户改动，则改用实施前后的文件校验值进行比对并保持一致。

- [ ] **Step 6: 提交现行规范更新**

```bash
git add zhixia-feihualing/docs/realistic-visual-style.md
git commit -m "完善视频提示词角色连续性门禁"
```
