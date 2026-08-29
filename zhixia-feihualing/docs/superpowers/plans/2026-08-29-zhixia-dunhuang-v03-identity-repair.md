# 栀夏敦煌角色母板 v03 身份脸修复 Implementation Plan

> **For agentic workers:** 按定向图片编辑、视觉验收、非破坏归档的顺序执行；不得覆盖 v02。

**Goal:** 生成一张保留敦煌 v02 全部服化道与版式、但恢复日常 v04 标准栀夏脸的 v03 候选角色卡。

**Architecture:** 使用内置图片编辑工具同时读取两个本地输入。v02 是唯一编辑目标和结构真源，v04 只提供脸部身份；输出先进入 `assets/characters/work/`，通过视觉验收后再决定是否正式归档。

**Tech Stack:** 内置 imagegen、PNG、ffmpeg/file 图像校验、人工视觉核对。

## Global Constraints

- 只改变身份脸，不改变敦煌发型、金冠、花钿、服装、六组配饰、飘带、配色与角色卡布局。
- 所有正面、侧面、六表情和五官细节必须属于日常 v04 的同一位栀夏。
- 不覆盖 v02；首轮只保存 v03 候选版。
- 不引入高马尾、白花发冠、浅青常服或粉色腰带。

---

### Task 1: 生成 v03 身份脸修复候选卡

**Files:**
- Reference: `zhixia-feihualing/assets/characters/栀夏角色母板高写实CG-v04-完整档案增彩版-Seedance上传版.jpg`
- Edit target: `zhixia-feihualing/assets/characters/栀夏敦煌十六舞角色母板-v02-服化道升级-Seedance上传版.jpg`
- Create: `zhixia-feihualing/assets/characters/work/栀夏敦煌十六舞角色母板-v03-身份脸修复-候选版.png`

- [ ] **Step 1: 用两个已查看的本地输入执行身份保持编辑**

提示词明确图片 1 只提供身份脸，图片 2 是编辑目标；重复冻结 v02 版式与服化道，只修改全部面部。

- [ ] **Step 2: 保存候选输出到工作目录**

保留工具原始 PNG，不覆盖 v02 或既有归档。

### Task 2: 视觉与文件验收

**Files:**
- Inspect: `zhixia-feihualing/assets/characters/work/栀夏敦煌十六舞角色母板-v03-身份脸修复-候选版.png`

- [ ] **Step 1: 校验文件可解码、尺寸和纵向角色卡比例**

使用 `file` 与 `ffmpeg -v error -i ... -f null -`，确认图像可读取且不是空白或损坏文件。

- [ ] **Step 2: 逐区视觉检查**

检查标准脸、正侧面一致性、六表情一致性、敦煌发髻冠饰、服装、六组配饰、双层飘带、版式和色板纹样；如身份仍漂移，只针对脸部做一次定向迭代。

- [ ] **Step 3: 展示候选版给用户**

报告保留项与仍需关注的细节；候选版在用户确认前不升级为正式 v03。
