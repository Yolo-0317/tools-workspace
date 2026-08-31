# 《九歌·云中君》正式封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以九歌 v03 母板和已保留的《云中君》十五秒视频为参考，生成一张身份稳定、自然写实的 9:16 云海祭舞底图，并确定性叠加 `九歌`、`云中君`、`栀夏祭舞` 三组竖排中文。

**Architecture:** 图片部分复用《东皇太一》流程，由内置图片生成工具结合角色母板与视频动作帧生成无字底图；排版部分使用独立 Swift/AppKit 渲染器，保证中文准确和系列版式一致。最终通过尺寸、PNG 解码、像素一致性和人工视觉检查后保存到单集目录与发布目录。

**Tech Stack:** 内置 `image_gen`、FFmpeg、Swift/AppKit/CoreText、zsh、`sips`。

## Global Constraints

- 栀夏必须保持九歌 v03 同一虚拟身份、18 岁年龄感、楚式窄高盘髻、黑漆凤鸟冠梳、玄黑朱红舞衣和自然修长比例。
- 双手始终空着；画面中没有额外人物、神祇实体或手持器物。
- 人物三分之四正面，全身完整可见，占画面高度约 64%—70%，位于中部偏右，左侧保留连续文字安全区。
- 袖缘尾端严格两个，宽重、低反射、与袖口连续，不成为细绳、独立披帛或长水袖。
- 云层开口必须自然、不对称、边缘松散、亮度受控；禁止巨大居中裂缝、垂直光柱和传送门轮廓。
- 石面只允许局部断裂磨损楚纹；禁止完整同心圆、中心圆盘、发光阵、符文和仙侠法术。
- 电影级自然摄影式写实；禁止塑料皮肤、蜡像感、油润 CG、游戏角色渲染和高饱和霓虹。
- 图片生成阶段不出现任何文字、logo、水印、平台标记或 AI 标记。
- 最终封面只出现 `九歌`、`云中君`、`栀夏祭舞`，不得有错字或其他文字。
- 正式封面和发布副本均为 1080×1920 PNG，不覆盖其他封面。

---

### Task 1: 抽取并归档动作参考帧

**Files:**
- Read: `episodes/jiuge-yunzhongjun-15s/assets/video/content-raw-v01.mp4`
- Create: `episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-cover-reference-v01.png`

**Interfaces:**
- Consumes: 已保留的 15.093 秒、496×864 原始视频。
- Produces: 一张约第 2 秒的三分之四正面展臂参考帧，供 Task 2 使用。

- [ ] **Step 1: 抽取 2.000 秒参考帧**

Run:

```zsh
mkdir -p episodes/jiuge-yunzhongjun-15s/assets/cover
ffmpeg -hide_banner -loglevel error -y -ss 2.000 \
  -i episodes/jiuge-yunzhongjun-15s/assets/video/content-raw-v01.mp4 \
  -frames:v 1 \
  episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-cover-reference-v01.png
```

- [ ] **Step 2: 检查参考帧**

使用 `view_image` 检查：栀夏三分之四正面、头顶至鞋履完整可见、双手空着、双臂展开、人物位于中部偏右。平台标记、巨大云缝、完整圆台和低分辨率材质只作为 Task 2 的禁止继承项。

---

### Task 2: 用图片生成工具制作无字底图

**Files:**
- Read reference: `assets/characters/栀夏九歌祭舞-v03-整合式高写实视频母板-Seedance上传版.jpg`
- Read reference: `episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-cover-reference-v01.png`
- Create: `episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-cover-base-v01.png`

**Interfaces:**
- Consumes: 母板负责身份和服装，动作帧负责舞姿、全身尺度和云海空间。
- Produces: 无文字、无平台标记、左侧可排字的 9:16 写实底图。

- [ ] **Step 1: 检查两张输入图**

使用 `view_image` 分别查看母板和参考帧。母板是身份与服装参考，参考帧是姿态、构图与环境参考；不复制两张图片中的排版、文字、边框或平台标记。

- [ ] **Step 2: 调用内置图片生成工具**

使用 `image_gen`，把母板列为 Image 1、动作帧列为 Image 2，提示词固定为：

```text
Use case: photorealistic-natural
Asset type: 9:16 vertical Chinese dance video cover base, no typography
Primary request: Create a cinematic natural-photography cover image for the fictional digital character Zhixia performing the ritual dance of Jiuge: Lord in the Clouds. Preserve the exact virtual facial identity, 18-year-old age impression, Chu-style narrow high bun, small black-lacquer phoenix hair ornament, black-and-vermilion integrated wide-sleeve dance costume, waist structure, pale jade pendant, shoes, and natural slender proportions from Image 1. Use Image 2 only for the three-quarter frontal full-body arm extension, the center-right placement, the high-mountain cloud-sea stone platform, cool blue-gray dawn sky, and restrained pale-gold horizon light.
Composition/framing: 9:16 portrait. Zhixia is the only person, positioned center-right, full body from head to shoes, about 64–70% of image height, with a clear three-quarter frontal face. One foot clearly bears weight on real stone while the other carries a small weight-shift after-motion. The nearer empty arm extends toward the side-front and the other empty arm opens toward the side-back, clearly asymmetrical. Reserve a calm, continuous blue-gray negative-space column on the left for later vertical Chinese typography.
Lighting/mood: physically plausible cool dawn skylight, minimal pale-gold light near the distant horizon, solemn, airy, restrained high-altitude atmosphere; face remains naturally readable without a beauty spotlight.
Scene/backdrop: weathered high-mountain stone platform above a realistic cloud sea. The opening in the clouds is off-center, irregular, soft-edged, low-contrast, and clearly a natural gap in layered clouds, never a portal or vertical beam. Stone patterns are partial, broken, worn Chu cloud-thunder motifs, never a complete circle.
Materials/textures: real skin pores, fine facial hair, natural skin-color variation, moist realistic eyes, individually visible hair strands, low-reflection silk and brocade, weathered non-repeating stone, translucent volumetric water-vapor clouds.
Constraints: both hands empty and anatomically correct; exactly two wide, weighty vermilion sleeve-edge tails continuously attached to the sleeve hems, naturally drooping and responding to the arm gesture, lowest point around mid-calf; no object enters either hand; face, hands, shoes, and contact shadow remain visible.
Avoid: all text, Chinese characters, English letters, logos, watermarks, platform marks, AI marks, borders, character-card layout, extra people, deities, duplicates, extra limbs, malformed hands, closed eyes, sweet smile, face obstruction, handheld props, complete concentric floor rings, center disk, glowing magic circle, floating rune, halo, portal, vertical light beam, symmetrical giant cloud裂缝, wings, cloud-riding flight, narrow independent ribbons, long water sleeves, fabric crossing the face or title area, plastic skin, wax figure, oily CG, game rendering, high-saturation neon, fantasy-poster lighting.
```

- [ ] **Step 3: 检查生成底图**

使用 `view_image` 逐项检查：同一张脸、三分之四正面、双手和鞋履完整、两个袖缘尾端、左侧留白、自然云层开口、无完整圆台、无文字标记、皮肤和织物自然写实。若只有一个明确问题，进行一次定向编辑并明确“只改该问题，其他保持不变”；若同时存在两个以上结构问题，重新生成一次。

- [ ] **Step 4: 保存并规范化项目底图**

把通过检查的生成结果复制到：

```text
episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-cover-base-v01.png
```

若生成尺寸不是 1080×1920，使用 FFmpeg Lanczos 等比覆盖并居中裁切：

```zsh
ffmpeg -hide_banner -loglevel error -y -i generated.png \
  -vf "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920" \
  episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-cover-base-v01.png
```

不得拉伸人物比例。

---

### Task 3: 测试先行实现确定性中文排版

**Files:**
- Create: `tests/test_yunzhongjun_cover.sh`
- Create: `scripts/render_yunzhongjun_cover.swift`
- Create: `scripts/build_yunzhongjun_cover.sh`
- Create: `episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-cover-v01.png`
- Create: `exports/yunzhongjun-cover-v01.png`

**Interfaces:**
- Consumes: Task 2 的 1080×1920 无字底图。
- Produces: 同尺寸正式有字封面和字节一致的发布副本。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_yunzhongjun_cover.sh`：检查底图、可执行构建脚本和渲染器存在；运行构建；验证单集输出与发布输出都是可解码的 1080×1920 PNG，并使用 `cmp -s` 验证两份输出字节一致。成功消息固定为：

```text
PASS: Yunzhongjun cover outputs are ready
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `zsh tests/test_yunzhongjun_cover.sh`

Expected: `FAIL: missing executable Yunzhongjun cover builder`，因为构建脚本和渲染器尚未创建。

- [ ] **Step 3: 创建 Swift 渲染器**

以 `scripts/render_donghuang_taiyi_cover.swift` 为结构参考创建 `scripts/render_yunzhongjun_cover.swift`：画布固定 1080×1920；加载 `STXingkaiSC-Bold` 和 `STKaitiSC-Regular`；先铺满底图，再绘制：

```swift
drawVertical("九歌", x: 92, top: 235, step: 58, font: seriesFont, color: quietIvory)
drawVertical("云中君", x: 208, top: 220, step: 112, font: titleFont, color: titleIvory)
drawVertical("栀夏祭舞", x: 334, top: 620, step: 46, font: creditFont, color: quietIvory)
```

标题字体固定 92pt，系列小字 42pt，辅文 34pt；文字为暖象牙白，使用轻微玄黑阴影，不发光、不粗描边。渲染器接受 `<base.png> <output.png>` 两个参数并原子写入 PNG。

- [ ] **Step 4: 创建构建脚本**

创建可执行的 `scripts/build_yunzhongjun_cover.sh`：验证底图与渲染器；使用 `mktemp -d /tmp/zhixia-yunzhongjun-cover.XXXXXX` 创建 Swift 模块缓存；运行渲染器；把单集输出复制到 `exports/yunzhongjun-cover-v01.png`；打印发布路径。

- [ ] **Step 5: 运行测试确认通过**

Run: `zsh tests/test_yunzhongjun_cover.sh`

Expected: `PASS: Yunzhongjun cover outputs are ready`。

- [ ] **Step 6: 提交可复现排版流程**

```bash
git add scripts/render_yunzhongjun_cover.swift scripts/build_yunzhongjun_cover.sh tests/test_yunzhongjun_cover.sh
git diff --cached --name-only
git commit -m "建立云中君封面制作流程"
```

提交前确认暂存区只有上述三个文件。

---

### Task 4: 视觉验收、归档与交付

**Files:**
- Inspect: `episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-cover-base-v01.png`
- Inspect: `episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-cover-v01.png`
- Inspect: `exports/yunzhongjun-cover-v01.png`
- Modify: `assets/inventory.csv`

**Interfaces:**
- Consumes: Task 3 的正式封面。
- Produces: 用户可直接查看和发布的正式封面、资产登记和完整验证证据。

- [ ] **Step 1: 使用 `view_image` 检查无字底图和正式封面**

确认：人物中部偏右；左侧标题区没有袖缘、云缝或高光干扰；`九歌`、`云中君`、`栀夏祭舞` 无错字；缩略状态仍能辨认主标题；脸、双手、脚、两个袖缘、自然云层开口和断裂石纹均符合设计。若文字与人物重叠，只调整三列 `x` 或 `top` 一次并重新运行测试，不重新生成底图。

- [ ] **Step 2: 登记资产**

在 `assets/inventory.csv` 按现有列顺序增加《云中君》动作参考帧、无字底图和正式封面记录；来源分别写“原片抽帧”“内置图片生成工具”“本地 Swift/AppKit 排版”，不得修改或重排既有记录。

- [ ] **Step 3: 运行最终验证**

Run:

```zsh
zsh tests/test_yunzhongjun_cover.sh
sips -g pixelWidth -g pixelHeight -g format exports/yunzhongjun-cover-v01.png
ffmpeg -v error -i exports/yunzhongjun-cover-v01.png -f null -
cmp -s episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-cover-v01.png exports/yunzhongjun-cover-v01.png
git diff --check
git status --short
```

Expected: 测试通过；发布副本为 1080×1920 PNG；完整解码无错误；单集输出与发布副本字节一致；`git diff --check` 无输出；用户原有无关修改保持未暂存。

- [ ] **Step 4: 提交资产登记**

只暂存本任务实际可追踪的资产登记和未被忽略的封面输出：

```bash
git add assets/inventory.csv
git diff --cached --name-only
git commit -m "归档云中君正式封面"
```

如果封面图片受项目忽略规则保护，只保留工作区文件，不强制加入 Git。

- [ ] **Step 5: 交付**

最终回复直接展示 `exports/yunzhongjun-cover-v01.png`，提供动作参考帧、无字底图、正式封面和发布副本的绝对路径，并报告内置图片生成工具、最终提示词、测试结果和提交号。
