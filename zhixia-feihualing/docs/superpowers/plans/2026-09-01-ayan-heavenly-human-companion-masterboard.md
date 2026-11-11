# 阿砚天宫限定人形角色母板 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以已确认的阿砚 v05 天真圆脸主图为唯一图像输入，先生成一张完整角色母板候选图；经用户确认后，再从同一候选图归档正式 PNG、导出 Seedance JPEG 并建立固定说明。

**Architecture:** 采用“单一身份源—单张候选卡—人工确认门—同源导出”的非破坏流程。ImageGen 只读取 v05，不读取栀夏角色卡、阿砚四足卡或任何否决版本；候选卡通过面容、三视图、服装、飘带、尾巴、鞋履和版式验收后，才允许复制为正式版并生成上传版。

**Tech Stack:** OpenAI 内置 ImageGen、`view_image`、PNG、macOS `sips`、`shasum`、Markdown、CSV、Git。

## Global Constraints

- 唯一图像输入固定为 `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v05-天真圆脸.png`，SHA256 固定为 `8f351cf93fa677b9b94bbb90aa8d9f0ef4e2a819652b45ab1fbc43d957a0cde6`。
- 不向 ImageGen 提供栀夏天宫角色卡、栀夏面容图、阿砚四足母板或 v01—v04d 否决候选。
- 阿砚固定为约 18 岁成年女性、162cm、天真圆脸、暖琥珀杏眼、深墨及肩层次短发、严格一对笔锋猫耳、中央朱砂额印与严格一条开放 S 形墨尾。
- 服装固定为象牙白浅心形无肩带舞衣、侧腰淡墨、不对称白墨拉丁舞裙、白墨交界浅暖金云纹、严格两条宽大墨梢云带和白底墨纹包头高跟舞鞋。
- 母板左侧为 `FRONT`、严格 `RIGHT SIDE`、`BACK` 三张完整中性全身视图；右侧只保留一张大型正面 `FACE IDENTITY` 面容基准。
- 不设置表情宫格、口型格、第二张大型脸、动态舞姿、天宫场景或额外人物。
- 候选阶段只创建 `assets/characters/work/阿砚天宫限定人形角色母板-v01-候选版.png`，不提前创建正式版或上传版。
- 正式版与 Seedance 上传版必须来自用户确认后的同一张候选图，不得重新生成或重排。
- 用户可见文案和 Git 提交信息使用中文，不使用 emoji。
- 不覆盖、删除或回退任何既有资产；只显式暂存本计划列出的任务文件。

---

## 文件结构

- `assets/characters/work/阿砚天宫限定人形小女伴主图-v05-天真圆脸.png`：唯一人物与造型输入，只读。
- `assets/characters/work/阿砚天宫限定人形角色母板-v01-候选版.png`：首次完整母板候选，用户确认前保持工作态且不归档。
- `assets/characters/归档/阿砚天宫限定人形角色母板-v01-正式版.png`：确认后由候选 PNG 无损复制的正式档案。
- `assets/characters/阿砚天宫限定人形角色母板-v01-Seedance上传版.jpg`：从正式 PNG 等比压缩导出的单图上传版。
- `assets/characters/阿砚天宫限定人形角色母板-v01-Seedance固定说明.md`：后续视频使用的身份、服化道与禁止项。
- `assets/inventory.csv`：正式交付后登记新增角色资产；候选图未获确认时不登记为正式资产。

### Task 1: 核验唯一输入并建立生成边界

**Files:**
- Read: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v05-天真圆脸.png`
- Read: `zhixia-feihualing/docs/superpowers/specs/2026-09-01-ayan-heavenly-human-companion-masterboard-design.md`

**Interfaces:**
- Consumes: 已确认的 v05 PNG 和设计规范。
- Produces: 经哈希、尺寸和目视核验的唯一参考输入；Task 2 不得加入第二张参考图。

- [ ] **Step 1: 核对 v05 文件身份**

  Run:

  ```bash
  file 'zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v05-天真圆脸.png'
  shasum -a 256 'zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v05-天真圆脸.png'
  ```

  Expected: `PNG image data, 941 x 1672`；SHA256 为 `8f351cf93fa677b9b94bbb90aa8d9f0ef4e2a819652b45ab1fbc43d957a0cde6`。

- [ ] **Step 2: 使用 `view_image` 以原始清晰度检查 v05**

  必须确认：短圆鹅蛋脸、柔软苹果肌、短圆下巴、暖琥珀眼、及肩短发、严格两只笔锋猫耳、朱砂额印、严格一条墨尾、宽飘带、白墨裙和白底墨纹高跟鞋均可辨认。

- [ ] **Step 3: 检查候选目标不存在或不会覆盖既有结果**

  Run:

  ```bash
  test ! -e 'zhixia-feihualing/assets/characters/work/阿砚天宫限定人形角色母板-v01-候选版.png'
  ```

  Expected: exit 0。若文件已存在，先目视核对并使用新的递增候选版本名，不覆盖旧文件。

### Task 2: 使用单一参考图生成完整候选母板

**Files:**
- Reference: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v05-天真圆脸.png`
- Create: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形角色母板-v01-候选版.png`

**Interfaces:**
- Consumes: Task 1 核验后的唯一 v05 PNG。
- Produces: 一张纵向、暖米白档案背景、完整三视图加唯一大型正面脸的候选 PNG。

- [ ] **Step 1: 使用内置 ImageGen 执行单图参考生成**

  `referenced_image_paths` 严格只传入以下一个路径：

  ```text
  /Users/huan.yu/dev/tools-workspace/zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v05-天真圆脸.png
  ```

  使用以下完整提示词：

  ```text
  Create one premium vertical live-action Chinese xianxia costume-development character archive board for the original fictional adult woman A Yan. The supplied image is the only identity and costume reference. Preserve her exact innocent adult round face, warm amber eyes, shoulder-length layered ink-black hair, exactly two brush-tip cat ears, central cinnabar forehead mark, petite 162 cm adult proportions, ivory-and-ink costume, exactly two broad upper-arm ribbons, exactly one connected open S-shaped ink tail, and ivory closed-toe dance heels with ink-colored motifs, edging, straps and heels. Do not borrow any face, hairstyle or clothing from another character.

  Use a warm ivory archival background, restrained pale-gold hairline dividers, subtle pale-ink section blocks and generous negative space. At the top place only: “A YAN”, “阿砚”, “天宫限定”.

  On the left two-thirds, show three complete neutral full-body orthographic development views of the same A Yan, aligned to the same ear-tip line and shoe-sole line: FRONT, strict human RIGHT SIDE at exactly 90 degrees, and BACK. All three views must show the complete ears, head, hands, skirt, both legs and both shoes without cropping. Use a neutral fitting stance with feet parallel and slightly apart, real weight on both feet, arms relaxed beside the body with a small clear gap. No crossed legs, dance pose, hip twist, raised arms, walking or glamour pose.

  On the right third, show exactly one large frontal head-and-shoulders portrait labeled “面部基准” and “FACE IDENTITY”. This is the only large face and the highest-priority identity anchor. Preserve the same adult 18-year-old innocent face from the reference: short rounded oval face, full soft apple cheeks, short rounded chin, slightly wide-set warm amber almond eyes that are a little larger and rounder but still photorealistic, almost horizontal outer corners, short soft flat brows, small natural nose, naturally full lips without a sharp mature cupid’s bow, clear direct gaze, closed mouth and a calm friendly trace of a smile. Natural matte skin with restrained pores and tonal variation. Do not create a long narrow face, sharp chin, mature seductive eyes, fox-like expression, doll child face, porcelain skin, beauty-filter blur or game-art highlights.

  Keep the hairstyle identical across all views: shoulder-length layered ink-black hair, a slight pale-ink gradient at the tips, individual realistic strands and natural flyaways; exactly one pair of upward-outward brush-tip cat ears naturally integrated into the hair; a small pale-gold cloud hairpin, one cinnabar accent and the central cinnabar forehead mark. Do not add visible human ears, a high bun, long straight hair, jade crown or pearl tassels.

  Keep the costume topology identical across all views. Use an opaque ivory shallow sweetheart strapless dance bodice with dignified secure coverage, bright ivory at the center and restrained pale-ink wash at both side waists. Use an asymmetrical Latin dance skirt whose long edge reaches mid-calf and whose short edge still covers the upper thigh, with a diagonal gradient from ivory to smoke ink so approximately one third of the skirt is ink colored. Place one restrained pale-warm-gold swirling cloud motif along the white-and-ink boundary. No deep V, extreme push-up cleavage, exaggerated bust, transparent pelvis, two high slits, visible safety shorts or inconsistent garment construction.

  Attach exactly two broad cloud ribbons, one at the rear outer side of each upper arm. Each ribbon is as wide as a substantial xianxia drape, transitions from translucent rice-paper white to smoke gray and then a dense black brush-tip end, has only one fine pale-gold edge, reaches the lower calf and never touches the floor. Clearly show both attachment roots and the same width and gradient in all three views. The ribbons must not become sleeves, wrist streamers, handheld silk, a third ribbon, extra ends, or merge with the body, skirt, legs or tail.

  Show exactly one continuous ink tail growing naturally from the tailbone. It forms a clear open S curve, with dry dark-ink paper-fiber texture and a brushy tip. In the strict right-side and back views, make the root connection clearly visible. Do not split, duplicate, close into a loop, detach, float, or merge it into the skirt ink or broad ribbons.

  Keep the shoes consistent in every view: ivory matte-satin closed rounded toe, low-cut instep, stable enclosed heel, crossed instep straps and an approximately 5.5 cm flared dance heel. All shoe motifs, topline edging, construction lines, crossed straps and heel are smoke-to-deep ink; absolutely no gold on the shoes. No open toe, flat slipper, cloud shoe, kitten heel, stiletto, platform, mismatched shoes or floating feet.

  Along the bottom, create seven compact technical breakdown modules: COSTUME BREAKDOWN; DRAPES & ARM STRUCTURE; SHOES; ACCESSORIES & HAIR STRUCTURE; INK TAIL STRUCTURE; DETAIL CLOSE-UP; COLOR PALETTE & MATERIAL. Show garment pieces, both ribbon roots and gradients, front and strict-side shoe details, hair and ear construction, the single tail root and open-S profile, one amber eye, natural lips, cinnabar mark, bodice weave, ink gauze, gold boundary motif and shoe ink pattern, plus swatches for ivory, rice-paper white, pale ink, smoke ink, deep ink, small pale warm gold and cinnabar red, with silk satin, georgette, organza, paper fiber and matte antique gold.

  Visible text is limited to the title, view labels, face labels and the seven module labels above. If small text cannot be rendered accurately, omit it rather than inventing pseudo-Chinese, random English, measurements, slogans, watermarks or platform marks.

  Render as high-end photorealistic live-action Chinese xianxia wardrobe development photography, not anime, illustration, oil painting or glossy game concept art. Use soft neutral studio light. Distinguish natural matte skin, individual hair strands, woven satin, dry translucent gauze, fibrous ink tail and matte antique gold. The entire board must remain a clean warm-ivory archive card with no heavenly palace, cloud sea, jade stairs, lanterns, stage, visual effects, depth-of-field scenery or extra person.
  ```

- [ ] **Step 2: 保存 ImageGen 原始结果为候选 PNG**

  保存到：

  ```text
  zhixia-feihualing/assets/characters/work/阿砚天宫限定人形角色母板-v01-候选版.png
  ```

  保留生成工具的原始 PNG，不进行裁切、重绘、局部拉伸或 JPEG 转码。

- [ ] **Step 3: 使用 `view_image` 以原始清晰度检查候选图**

  按以下顺序核验：

  1. 大型正面脸是否与 v05 同一身份，仍是成年天真圆脸，且不像栀夏。
  2. 是否只有一张大型正面脸，无表情宫格、第二大脸或多余人物。
  3. FRONT、严格 RIGHT SIDE、BACK 是否完整同高，右侧面是否真正接近 90 度。
  4. 是否严格两只笔锋猫耳、两条宽飘带和一条连接尾骨的开放 S 形墨尾。
  5. 抹胸、侧腰淡墨、斜向烟墨裙、金色边界云纹和白底墨纹高跟鞋是否在三视图一致。
  6. 下方是否存在七类拆解模块，且没有明显伪中文、水印、随机宣传文字。
  7. 是否为自然电影实拍材质，而非油润游戏 CG、动漫或瓷娃娃皮肤。

- [ ] **Step 4: 核对文件格式与非空状态**

  Run:

  ```bash
  file 'zhixia-feihualing/assets/characters/work/阿砚天宫限定人形角色母板-v01-候选版.png'
  test -s 'zhixia-feihualing/assets/characters/work/阿砚天宫限定人形角色母板-v01-候选版.png'
  ```

  Expected: `PNG image data`；exit 0。

- [ ] **Step 5: 向用户展示候选图并等待视觉确认**

  明确报告面容、三视图、耳朵、飘带、尾巴、鞋履与材质的检查结果。用户确认前停止；不创建正式版、Seedance 上传版、固定说明或资产登记，也不提交候选图。

### Task 3: 处理候选图反馈

**Files:**
- Read: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形角色母板-v01-候选版.png`
- Create when needed: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形角色母板-v02-候选版.png`

**Interfaces:**
- Consumes: 用户对 v01 候选图的具体视觉反馈。
- Produces: 用户明确确认的候选 PNG，或一张保留全部不变量的递增版本候选图。

- [ ] **Step 1: 若用户确认 v01，锁定其绝对路径与 SHA256**

  Run:

  ```bash
  shasum -a 256 'zhixia-feihualing/assets/characters/work/阿砚天宫限定人形角色母板-v01-候选版.png'
  ```

  Expected: 输出一个可记录的 SHA256；Task 4 只允许消费该确认文件。

- [ ] **Step 2: 若用户要求修改，只执行一次单点编辑或一次完整重生**

  一个局部问题使用已确认候选图作为唯一编辑目标，并在提示词中列出所有不变量；若身份脸、三视图或整体版式失败，则继续只以 v05 为参考完整重生并保存为 `v02-候选版.png`。不得覆盖 v01，也不得加入栀夏图片帮助修正。

- [ ] **Step 3: 对新候选重新执行 Task 2 的全部七项视觉核验**

  新候选必须再次展示给用户。任何“可用”“正式版”或“已定稿”结论都以用户明确确认为准。如果最终确认的是 v02，则在开始 Task 4 前将 Task 4 中三处 v01 候选路径逐字改为 v02 实际路径并重新检查计划差异，确保后续命令没有抽象版本占位符。

### Task 4: 用户确认后归档并导出同源 Seedance 版

**Files:**
- Read: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形角色母板-v01-候选版.png`
- Create: `zhixia-feihualing/assets/characters/归档/阿砚天宫限定人形角色母板-v01-正式版.png`
- Create: `zhixia-feihualing/assets/characters/阿砚天宫限定人形角色母板-v01-Seedance上传版.jpg`

**Interfaces:**
- Consumes: Task 3 锁定 SHA256 的用户确认候选 PNG。
- Produces: 与确认候选同像素内容的正式 PNG，以及等比压缩、不裁切的 JPEG 上传版。

- [ ] **Step 1: 无损复制确认候选为正式版**

  使用显式源文件和目标文件，不覆盖其他版本；复制后核对 SHA256 完全相同。

  Run:

  ```bash
  test ! -e 'zhixia-feihualing/assets/characters/归档/阿砚天宫限定人形角色母板-v01-正式版.png'
  cp -p 'zhixia-feihualing/assets/characters/work/阿砚天宫限定人形角色母板-v01-候选版.png' 'zhixia-feihualing/assets/characters/归档/阿砚天宫限定人形角色母板-v01-正式版.png'
  shasum -a 256 'zhixia-feihualing/assets/characters/work/阿砚天宫限定人形角色母板-v01-候选版.png' 'zhixia-feihualing/assets/characters/归档/阿砚天宫限定人形角色母板-v01-正式版.png'
  ```

  Expected: 两行哈希相同。

- [ ] **Step 2: 从正式版等比导出高质量 JPEG**

  使用 `sips` 直接读取正式 PNG；保持原像素尺寸，只做 JPEG 编码，不裁切、不重排、不重新生成。

  Run:

  ```bash
  test ! -e 'zhixia-feihualing/assets/characters/阿砚天宫限定人形角色母板-v01-Seedance上传版.jpg'
  sips -s format jpeg -s formatOptions 90 \
    'zhixia-feihualing/assets/characters/归档/阿砚天宫限定人形角色母板-v01-正式版.png' \
    --out 'zhixia-feihualing/assets/characters/阿砚天宫限定人形角色母板-v01-Seedance上传版.jpg'
  ```

  Expected: 两条命令 exit 0，且目标文件为非空 JPEG。

- [ ] **Step 3: 核对文件格式与纵横比**

  Run:

  ```bash
  sips -g pixelWidth -g pixelHeight -g format \
    'zhixia-feihualing/assets/characters/归档/阿砚天宫限定人形角色母板-v01-正式版.png' \
    'zhixia-feihualing/assets/characters/阿砚天宫限定人形角色母板-v01-Seedance上传版.jpg'
  ```

  Expected: 正式版格式为 PNG，上传版格式为 JPEG；二者纵横比一致且内容无裁切。

- [ ] **Step 4: 使用 `view_image` 检查上传版**

  必须确认压缩后面部基准、三视图、双耳、双飘带、唯一墨尾、鞋履和底部拆解仍清楚，且没有颜色偏移或边缘裁切。

### Task 5: 编写固定说明、登记资产并完成交付核验

**Files:**
- Create: `zhixia-feihualing/assets/characters/阿砚天宫限定人形角色母板-v01-Seedance固定说明.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Read: `zhixia-feihualing/docs/superpowers/specs/2026-09-01-ayan-heavenly-human-companion-masterboard-design.md`

**Interfaces:**
- Consumes: Task 4 的正式 PNG、Seedance JPEG 和已确认设计规范。
- Produces: 可长期复用的上传规则、完整资产登记和一个不混入既有改动的聚焦中文提交。

- [ ] **Step 1: 编写版本状态与使用边界**

  明确写入：本卡只适用于阿砚天宫限定成年女性化形；日常诗境仍使用四足纸墨灵猫；天宫双人视频只上传本卡与栀夏天宫卡，阿砚人形不得与阿砚四足卡同时上传。

- [ ] **Step 2: 编写固定身份与造型约束**

  固定 v05 面容、18 岁成年年龄感、162cm、及肩短发、严格两只笔锋猫耳、朱砂额印、严格一条开放 S 形墨尾、浅心形抹胸、白墨拉丁舞裙、严格两条宽飘带和白底墨纹高跟舞鞋。

- [ ] **Step 3: 编写 Seedance 固定提示词前缀与禁止项**

  固定前缀只锁定人物身份与服化道，不要求视频复刻档案卡排版或文字；禁止串成栀夏脸、幼童化、狐媚化、普通圆猫耳、额外尾巴、额外飘带、服装换色、鞋履现代化、档案卡文字进入视频和四足形态混入同一人物身体。

- [ ] **Step 4: 检查固定说明无占位符并覆盖关键规则**

  Run:

  ```bash
  rg -n 'v05|18 岁|162cm|笔锋猫耳|朱砂额印|开放 S 形墨尾|两条宽|白底墨纹|不得|只适用于' 'zhixia-feihualing/assets/characters/阿砚天宫限定人形角色母板-v01-Seedance固定说明.md'
  rg -n 'TBD|TODO|待定|待确认|稍后补充|类似上文' 'zhixia-feihualing/assets/characters/阿砚天宫限定人形角色母板-v01-Seedance固定说明.md'
  ```

  Expected: 第一条命令的每个关键要求至少命中一次；第二条命令无输出。

- [ ] **Step 5: 按既有 CSV 表头登记正式 PNG、上传 JPG 和固定说明**

  先保存 `assets/inventory.csv` 的任务前差异并读取表头及相邻角色母板记录，逐字段复用现有格式；使用 `apply_patch` 只追加本任务记录，不修改或重排既有行，不登记未确认候选图为正式资产。该文件在本计划开始前已经存在其他未提交修改，因此最终提交时不暂存它，避免把用户既有改动混入本任务提交；交付报告需明确资产登记已写入但仍随既有差异留在工作区。

- [ ] **Step 6: 执行最终文件与差异核验**

  Run:

  ```bash
  file \
    'zhixia-feihualing/assets/characters/归档/阿砚天宫限定人形角色母板-v01-正式版.png' \
    'zhixia-feihualing/assets/characters/阿砚天宫限定人形角色母板-v01-Seedance上传版.jpg'
  git diff --check -- \
    'zhixia-feihualing/assets/characters/阿砚天宫限定人形角色母板-v01-Seedance固定说明.md' \
    'zhixia-feihualing/assets/inventory.csv'
  ```

  Expected: 两张图片类型正确；文本差异无空白错误。

- [ ] **Step 7: 只暂存最终交付文件并创建中文提交**

  ```bash
  git add -- \
    'zhixia-feihualing/assets/characters/归档/阿砚天宫限定人形角色母板-v01-正式版.png' \
    'zhixia-feihualing/assets/characters/阿砚天宫限定人形角色母板-v01-Seedance上传版.jpg' \
    'zhixia-feihualing/assets/characters/阿砚天宫限定人形角色母板-v01-Seedance固定说明.md'
  git diff --cached --check
  git diff --cached --stat
  git commit -m '生成：固化阿砚天宫限定人形角色母板'
  ```

  Expected: 提交只包含上述三个交付文件；`assets/inventory.csv` 保持未暂存并保留全部既有改动；不推送、不创建 PR。
