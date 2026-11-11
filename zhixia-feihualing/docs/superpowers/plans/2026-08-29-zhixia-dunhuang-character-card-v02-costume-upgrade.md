# 栀夏敦煌角色卡 v02 服化道升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用现版栀夏敦煌角色卡与三张服化道参考图，生成一张孔雀蓝、琥珀橙、象牙白与旧金配色的 v02 完整角色卡候选图。

**Architecture:** 以内置图片生成工具执行一次多参考图生成：现版角色卡锁定身份、版式与三视图，三张用户照片分别提供配色、服装结构和配饰语言。候选图先保存到工作目录并进行视觉验收，用户确认后再制作正式版、高清版与上传版，避免覆盖 v01。

**Tech Stack:** Codex 内置图片生成工具、内置图片查看工具、PNG/JPEG 资产、现有 CSV 资产清单。

## Global Constraints

- 栀夏身份、年龄感、脸型、身材比例与六组表情保持连续。
- 一页纵向角色卡必须包含正面、右侧、背面三视图和六组表情。
- 只生成一套固定服装；主配色为孔雀蓝、琥珀橙、象牙白与旧金，朱砂红只作点睛。
- 飘带为一组双层长飘带，固定在左右上臂后外侧，不缠腰、不横挂背部。
- 固定配饰为莲焰金冠、耳坠、双层璎珞、臂钏、手镯和腰链六组。
- 可选圆形莲纹金色乐舞法器只出现在拆解区，三视图不持握。
- 不复制参考照片人物身份、姿态、背景、水印或具体道具形状。
- v02 不覆盖 v01；用户确认候选图后才更新正式资产与固定说明。

---

### Task 1: 生成并验收 v02 候选角色卡

**Files:**
- Reference: `zhixia-feihualing/assets/characters/归档/栀夏敦煌十六舞角色母板-红青舞服-v01-正式版.png`
- Reference: `/var/folders/k9/byvrwvls2y384yw4hq3gpqkm0000gn/T/codex-clipboard-ee5570e2-7c66-48ac-b172-38f4bcacf5eb.png`
- Reference: `/var/folders/k9/byvrwvls2y384yw4hq3gpqkm0000gn/T/codex-clipboard-c40d9140-95c0-44b4-8bab-d7d7ad28f015.png`
- Reference: `/var/folders/k9/byvrwvls2y384yw4hq3gpqkm0000gn/T/codex-clipboard-d062f3b1-87be-4889-b3a8-8b928f23d3e4.png`
- Create: `zhixia-feihualing/assets/characters/work/栀夏敦煌十六舞角色母板-v02-服化道升级-候选版.png`

**Interfaces:**
- Consumes: v01 角色身份与版式、三张服化道参考图、已确认的 v02 设计规范。
- Produces: 一张待用户确认的 PNG 候选角色卡。

- [ ] **Step 1: 调用内置图片生成工具**

使用四张本地参考图。提示词明确各图角色分工，并完整写出主色、服装结构、六组配饰、双层飘带、六组表情、版式文字、禁止项和“不覆盖 v01”。

- [ ] **Step 2: 将候选图保存到工作目录**

把内置工具生成的选中结果复制到：

```text
zhixia-feihualing/assets/characters/work/栀夏敦煌十六舞角色母板-v02-服化道升级-候选版.png
```

- [ ] **Step 3: 检查文件有效性**

运行：

```bash
file 'zhixia-feihualing/assets/characters/work/栀夏敦煌十六舞角色母板-v02-服化道升级-候选版.png'
ffmpeg -v error -i 'zhixia-feihualing/assets/characters/work/栀夏敦煌十六舞角色母板-v02-服化道升级-候选版.png' -f null -
```

预期：文件被识别为 PNG，解码命令退出码为 0。

- [ ] **Step 4: 进行视觉验收**

使用图片查看工具逐项检查：栀夏身份连续；三视图服装、发型、配饰一致；飘带固定在双臂外侧；蓝橙白金层级清楚；织锦、纱、金属和玉石材质可区分；六个表情明显不同；道具只在拆解区；无水印、额外肢体与明显乱码标题。

- [ ] **Step 5: 向用户展示候选图**

展示候选图并报告候选文件路径与最终生成提示词。候选阶段不修改资产清单、固定说明或正式归档文件。

### Task 2: 用户确认后归档正式资产

**Files:**
- Create: `zhixia-feihualing/assets/characters/归档/栀夏敦煌十六舞角色母板-v02-服化道升级-正式版.png`
- Create: `zhixia-feihualing/assets/characters/归档/栀夏敦煌十六舞角色母板-v02-服化道升级-Seedance高清版.png`
- Create: `zhixia-feihualing/assets/characters/栀夏敦煌十六舞角色母板-v02-服化道升级-Seedance上传版.jpg`
- Modify: `zhixia-feihualing/assets/characters/栀夏敦煌十六舞角色母板-v01-Seedance固定说明.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Modify: `zhixia-feihualing/docs/character-bible.md`

**Interfaces:**
- Consumes: 用户确认的 v02 候选角色卡。
- Produces: 正式 PNG、Seedance 高清 PNG、上传 JPEG 以及同步后的固定说明和资产记录。

- [ ] **Step 1: 创建非覆盖正式副本**

复制用户确认的候选图为 v02 正式版，保留 v01 全部文件。

- [ ] **Step 2: 制作 Seedance 高清版与上传版**

高清版保持原始纵横比；上传版保持原始纵横比、JPEG 高质量并小于平台上传限制，不裁切三视图或文字区。

- [ ] **Step 3: 更新固定说明**

把 v02 的色彩、服装、飘带固定点、六组配饰和可选道具边界写入固定说明，并明确敦煌十六舞后续只使用用户最终确认的版本。

- [ ] **Step 4: 更新资产清单与角色圣经**

为正式版、高清版和上传版新增资产行；在角色圣经中记录 v02 的固定配色与配饰，不修改日常栀夏 v04 规则。

- [ ] **Step 5: 验证归档结果**

运行图片解码、尺寸、JPEG 文件体积、CSV 列数与资产 ID 唯一性检查。预期所有图像可解码、CSV 行保持九列且无重复 ID。

- [ ] **Step 6: 提交正式资产记录**

仅暂存 v02 相关文件、固定说明、资产清单与角色圣经，使用中文提交信息：

```bash
git commit -m '归档栀夏敦煌角色卡服化道升级版'
```
