# 栀夏敦煌单张大脸锁定角色卡 Implementation Plan

> **For agentic workers:** 使用内置 imagegen 进行一次定向角色卡编辑，逐区视觉验收后保存候选版；候选版在用户确认前不得覆盖或替代 v02 正式资产。

**Goal:** 删除敦煌角色卡右侧六表情宫格，替换为一张日常 v04 标准栀夏身份的大型敦煌正面头肩像。

**Architecture:** 当前敦煌 v03 身份修复候选版作为唯一编辑底图，日常 v04 上传版作为唯一脸部身份参考。生成工具只改变右侧表情区和必要的面部一致性，其他版式、三视图、服化道、拆解、细节、色板与纹样全部冻结；输出先进入工作目录供确认。

**Tech Stack:** 内置 imagegen、PNG、`file`、`ffprobe`、`ffmpeg`、人工视觉验收。

## Global Constraints

- 删除右侧全部六宫格、小格边框和表情名称，只保留一个“面部基准 / FACE IDENTITY”大区块。
- 大正脸自然闭嘴、极轻微亲和、正视镜头，完整显示高髻、金冠、花钿、耳坠和璎珞。
- 日常 v04 只提供脸部身份，不引入高马尾、白花发冠、浅青常服或粉色腰带。
- 正面全身、严格右侧面、眼唇细节与大正脸必须属于同一人。
- 三视图、服装、六组配饰、双层飘带、拆解区、细节区、色板和纹样保持不变。
- 不覆盖敦煌 v02 或现有 v03 候选；新输出使用独立文件名。

---

### Task 1: 生成单张大脸锁定候选卡

**Files:**
- Edit target: `zhixia-feihualing/assets/characters/work/栀夏敦煌十六舞角色母板-v03-身份脸修复-候选版.png`
- Identity reference: `zhixia-feihualing/assets/characters/栀夏角色母板高写实CG-v04-完整档案增彩版-Seedance上传版.jpg`
- Create: `zhixia-feihualing/assets/characters/work/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-候选版.png`

**Interfaces:**
- Consumes: 已确认的右侧大脸版式规范和两个本地图片输入。
- Produces: 可供视觉确认的单张大脸锁定候选 PNG。

- [x] **Step 1: 查看两个本地输入**

确认编辑目标为当前敦煌 v03 候选，身份参考为日常 v04；不得颠倒两图职责。

- [x] **Step 2: 执行定向图片编辑**

提示词明确 Image 1 是编辑目标，Image 2 只提供脸部身份；删除右侧六宫格并替换为单张大正脸，同时重复全部冻结项。

- [x] **Step 3: 保存项目候选文件**

从内置工具默认生成目录复制原始 PNG 到指定工作目录，不覆盖既有文件。

### Task 2: 文件与视觉验收

**Files:**
- Inspect: `zhixia-feihualing/assets/characters/work/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-候选版.png`

**Interfaces:**
- Consumes: Task 1 的候选 PNG。
- Produces: 文件完整性结果和逐区视觉结论。

- [x] **Step 1: 校验文件完整性**

使用 `file`、`ffprobe` 和 `ffmpeg -v error -i ... -f null -` 确认 PNG 可解码、尺寸有效且保持纵向角色卡比例。

- [x] **Step 2: 逐区视觉验收**

检查右侧只有一张大脸、表情闭嘴轻微亲和、冠顶和下巴未裁切；比较日常 v04 身份；核对三视图、六组配饰、双层飘带、拆解、细节、色板和纹样未被重新设计。

- [x] **Step 3: 单变量迭代**

若只有身份脸或右侧构图一项不合格，只针对该项执行一次修正，不同时修改服装、版式或配色。

- [x] **Step 4: 展示候选图**

将候选图作为本轮结果展示；用户确认前不制作正式版、高清版或 Seedance 上传版。

### Task 3: 用户确认后归档正式资产

**Files:**
- Create: `zhixia-feihualing/assets/characters/归档/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-正式版.png`
- Create: `zhixia-feihualing/assets/characters/归档/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-Seedance高清版.png`
- Create: `zhixia-feihualing/assets/characters/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-Seedance上传版.jpg`
- Create: `zhixia-feihualing/assets/characters/栀夏敦煌十六舞角色母板-v03-Seedance固定说明.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Modify: `zhixia-feihualing/docs/character-bible.md`

- [x] **Step 1: 创建非覆盖正式副本**

保留 v02 与全部 v03 候选文件，将用户确认的单张大脸候选图复制为独立 v03 正式版。

- [x] **Step 2: 制作高清版与上传版**

使用 Lanczos 保持纵横比派生 3982×5984 无损 PNG，再制作高质量 4:4:4 JPEG 上传版。

- [x] **Step 3: 更新角色规则与资产记录**

新建 v03 Seedance 固定说明，并把 v03 当前真源、单张大脸身份锚点、上传互斥规则同步到角色圣经和资产清单。

- [x] **Step 4: 验证并提交**

验证三张图可解码、尺寸与 JPEG 体积合规，验证 CSV 九列与资产 ID 唯一，检查仅暂存本次 v03 文件后使用中文提交。
