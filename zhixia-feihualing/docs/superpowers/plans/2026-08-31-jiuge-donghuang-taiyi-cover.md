# 《九歌·东皇太一》正式封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以九歌 v03 母板和已保留的《东皇太一》15 秒视频为参考，生成一张无发光法阵、身份稳定的 9:16 写实祭舞底图，并确定性叠加 `九歌`、`东皇太一`、`栀夏祭舞` 三组竖排中文。

**Architecture:** 图片部分由内置图片生成工具完成，只负责人物、舞姿、祭坛和光线，不生成中文；排版部分由独立 Swift/AppKit 渲染器完成，保证中文准确、位置稳定。最终通过图像尺寸检查、解码检查和人工视觉检查后保存到单集目录与发布目录。

**Tech Stack:** 内置 `image_gen`、FFmpeg、Swift/AppKit/CoreText、zsh、`sips`。

## Global Constraints

- 栀夏必须保持九歌 v03 同一虚拟身份、楚式盘髻、黑漆凤鸟冠梳、玄黑朱红舞衣和自然修长比例。
- 双手始终空着；礼鼓只在远景，不触碰、不拿取、不击鼓。
- 人物三分之四正面，全身完整可见，双臂一高一低，脚下承重和内弧行进方向清楚。
- 袖缘尾端严格两个，宽而有重量，不成为细长独立飘带，不横穿胸脸。
- 石面只允许浅刻楚纹和低反射嵌线，禁止完整圆形发光阵、符文、光环和仙侠法术。
- 电影级自然摄影式写实；禁止塑料皮肤、蜡像感、油润 CG、游戏角色渲染和高饱和霓虹。
- 图片生成阶段不出现任何文字、logo、水印或 AI 标记。
- 最终封面只出现 `九歌`、`东皇太一`、`栀夏祭舞`，不得有错字或其他文字。
- 最终发布副本为 1080×1920 PNG；不得覆盖其他封面。

---

### Task 1: 选择视频动作参考帧

**Files:**
- Read: `zhixia-feihualing/episodes/jiuge-donghuang-taiyi-15s/assets/video/content-raw-v01.mp4`
- Create temporary: `/private/tmp/jiuge-donghuang-cover/frame-09.5.png` through `frame-12.0.png`
- Create temporary: `/private/tmp/jiuge-donghuang-cover/contact-sheet.png`

**Interfaces:**
- Consumes: 已保留的 15.093 秒、496×864 视频。
- Produces: 一张三分之四正面、全身可见、双手空着的选定动作参考帧路径，供 Task 2 使用。

- [ ] **Step 1: 抽取 9—12 秒候选帧**

Run:

```zsh
mkdir -p /private/tmp/jiuge-donghuang-cover
for timestamp in 09.5 10.0 10.5 11.0 11.5 12.0; do
  ffmpeg -hide_banner -loglevel error -y -ss "$timestamp" \
    -i zhixia-feihualing/episodes/jiuge-donghuang-taiyi-15s/assets/video/content-raw-v01.mp4 \
    -frames:v 1 "/private/tmp/jiuge-donghuang-cover/frame-$timestamp.png"
done
```

- [ ] **Step 2: 生成接触表并检查**

Run:

```zsh
ffmpeg -hide_banner -loglevel error -y \
  -pattern_type glob -i '/private/tmp/jiuge-donghuang-cover/frame-*.png' \
  -vf 'scale=360:-1,tile=3x2' -frames:v 1 \
  /private/tmp/jiuge-donghuang-cover/contact-sheet.png
```

使用 `view_image` 检查六帧。选择标准依次为：脸为三分之四正面、全身和鞋履可见、双手空着、双臂一高一低、袖缘未遮脸、人物右侧构图能给左侧留字。若没有一帧全部满足，选择身份与舞姿最稳定的一帧，并在图片生成提示词中重新组织构图。

### Task 2: 用图片生成工具制作无字底图

**Files:**
- Read reference: `zhixia-feihualing/assets/characters/栀夏九歌祭舞-v03-整合式高写实视频母板-Seedance上传版.jpg`
- Read reference: Task 1 选定的 `/private/tmp/jiuge-donghuang-cover/frame-*.png`
- Create: `zhixia-feihualing/episodes/jiuge-donghuang-taiyi-15s/assets/cover/donghuang-taiyi-cover-base-v01.png`

**Interfaces:**
- Consumes: 母板负责身份和服装，视频帧负责舞姿、祭坛与空间尺度。
- Produces: 无文字、无水印、可供确定性排版的 9:16 底图。

- [ ] **Step 1: 检查两张输入图**

使用 `view_image` 分别查看九歌 v03 母板与选定动作帧。母板为身份参考图，动作帧为姿态、构图和环境参考图；两者都不是需要原样复制的排版目标。

- [ ] **Step 2: 调用内置图片生成工具**

使用 `image_gen`，传入两个本地参考路径，提示词固定为：

```text
Use case: photorealistic-natural
Asset type: 9:16 vertical Chinese dance video cover base, no typography
Primary request: Create a cinematic natural-photography cover image for the fictional digital character Zhixia performing the ritual dance of Jiuge: Donghuang Taiyi. Preserve the exact virtual facial identity, age impression, Chu-style narrow high bun, small black-lacquer phoenix hair ornament, black-and-vermilion integrated wide-sleeve dance costume, waist structure, jade pendant, shoes, and natural slender proportions from reference image 1. Use reference image 2 only for the inner-arc traveling turn, ritual altar atmosphere, cool night sky, small real flames, distant ritual drum, and full-body scale.
Composition/framing: 9:16 portrait. Zhixia is the only person, positioned center-right, full body from head to shoes, about 62–70% of image height, three-quarter frontal face visible. One foot clearly bears weight while the other follows the altar's inner arc. One empty arm rises diagonally beside the head and the other empty arm opens sideways or slightly downward, clearly asymmetrical. Reserve a calm, dark, continuous negative-space column on the left for later vertical Chinese typography.
Lighting/mood: cool blue natural night skylight with a small amount of physically plausible warm firelight; solemn, mysterious, restrained Chu ritual atmosphere; face remains readable.
Materials/textures: real skin pores and fine facial hair, natural skin color variation, individually visible hair strands, low-reflection silk and brocade, weathered stone, physically plausible flame and shadow.
Constraints: both hands empty and fully visible; no held object; exactly two wide, weighty vermilion sleeve-edge tails continuously attached to the sleeve hems, naturally drooping, lowest point around mid-calf; distant ritual drum remains untouched; shallow worn Chu patterns or dark metal inlay on stone only.
Avoid: all text, Chinese characters, logos, watermarks, AI marks, borders, character-card layout, extra people, extra limbs, malformed hands, closed eyes, face obstruction, handheld props, drumsticks, touching the drum, complete glowing circular floor pattern, magic circle, floating rune, halo, spell effects, narrow independent ribbons, long water sleeves, fabric crossing the face or chest, plastic skin, wax figure, oily CG, game rendering, high-saturation neon.
```

- [ ] **Step 3: 检查生成底图**

使用 `view_image` 检查：身份、脸部角度、双手、全身、两个袖缘尾端、左侧留白、礼鼓距离、地面无发光阵、无文字水印和写实材质。若只有一个明确问题，使用一次定向编辑，仅修复该问题并保持其他部分不变；若存在多项结构失败，重新生成一次而不是连续局部修补。

- [ ] **Step 4: 保存项目底图**

把通过检查的图片复制到：

```text
zhixia-feihualing/episodes/jiuge-donghuang-taiyi-15s/assets/cover/donghuang-taiyi-cover-base-v01.png
```

若生成尺寸不是 1080×1920，使用 FFmpeg Lanczos 等比覆盖并居中裁切到 1080×1920；不得拉伸人物比例。

### Task 3: 测试先行实现确定性中文排版

**Files:**
- Create: `zhixia-feihualing/tests/test_donghuang_taiyi_cover.sh`
- Create: `zhixia-feihualing/scripts/render_donghuang_taiyi_cover.swift`
- Create: `zhixia-feihualing/scripts/build_donghuang_taiyi_cover.sh`
- Create: `zhixia-feihualing/episodes/jiuge-donghuang-taiyi-15s/assets/cover/donghuang-taiyi-cover-v01.png`
- Create: `zhixia-feihualing/exports/donghuang-taiyi-cover-v01.png`

**Interfaces:**
- Consumes: Task 2 的 1080×1920 无字底图。
- Produces: 同尺寸正式有字封面和发布副本。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_donghuang_taiyi_cover.sh`，内容检查构建脚本和渲染器存在，运行构建后验证两个输出均为可解码的 1080×1920 PNG：

```zsh
#!/bin/zsh
set -euo pipefail
project_dir=${0:A:h:h}
builder="$project_dir/scripts/build_donghuang_taiyi_cover.sh"
renderer="$project_dir/scripts/render_donghuang_taiyi_cover.swift"
base="$project_dir/episodes/jiuge-donghuang-taiyi-15s/assets/cover/donghuang-taiyi-cover-base-v01.png"
episode_output="$project_dir/episodes/jiuge-donghuang-taiyi-15s/assets/cover/donghuang-taiyi-cover-v01.png"
export_output="$project_dir/exports/donghuang-taiyi-cover-v01.png"

[[ -s "$base" ]] || { print -u2 "FAIL: missing Donghuang Taiyi cover base"; exit 1; }
[[ -x "$builder" ]] || { print -u2 "FAIL: missing executable cover builder"; exit 1; }
[[ -s "$renderer" ]] || { print -u2 "FAIL: missing cover renderer"; exit 1; }

"$builder" >/dev/null
for output in "$episode_output" "$export_output"; do
  [[ -s "$output" ]] || { print -u2 "FAIL: missing output $output"; exit 1; }
  properties=$(sips -g pixelWidth -g pixelHeight -g format "$output")
  print -r -- "$properties" | rg -q 'pixelWidth: 1080'
  print -r -- "$properties" | rg -q 'pixelHeight: 1920'
  print -r -- "$properties" | rg -q 'format: png'
  ffmpeg -v error -i "$output" -f null -
done
print "PASS: Donghuang Taiyi cover outputs are ready"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `zsh zhixia-feihualing/tests/test_donghuang_taiyi_cover.sh`

Expected: `FAIL: missing executable cover builder`，因为构建脚本和渲染器尚未创建。

- [ ] **Step 3: 创建 Swift 渲染器**

创建 `scripts/render_donghuang_taiyi_cover.swift`，使用 AppKit/CoreText：画布固定 1080×1920；加载行楷和楷体；先铺满底图，再按从左到右三列绘制：

```swift
drawVertical("九歌", x: 92, top: 235, step: 58, font: seriesFont, color: quietIvory)
drawVertical("东皇太一", x: 208, top: 220, step: 112, font: titleFont, color: titleIvory)
drawVertical("栀夏祭舞", x: 334, top: 690, step: 46, font: creditFont, color: quietIvory)
```

字体固定为 `STXingkaiSC-Bold` 92pt、`STKaitiSC-Regular` 42pt 和 34pt；文字为暖象牙白，使用轻微玄黑阴影，禁止发光和粗描边。渲染器接受 `<base.png> <output.png>` 两个参数并以原子写入输出 PNG。

- [ ] **Step 4: 创建构建脚本**

创建可执行的 `scripts/build_donghuang_taiyi_cover.sh`：验证底图与渲染器；使用临时 Swift 模块缓存运行渲染器；把单集输出原样复制到 `exports/donghuang-taiyi-cover-v01.png`；打印发布路径。

- [ ] **Step 5: 运行测试确认通过**

Run: `zsh zhixia-feihualing/tests/test_donghuang_taiyi_cover.sh`

Expected: `PASS: Donghuang Taiyi cover outputs are ready`。

### Task 4: 视觉验收、归档和提交

**Files:**
- Inspect: `zhixia-feihualing/episodes/jiuge-donghuang-taiyi-15s/assets/cover/donghuang-taiyi-cover-base-v01.png`
- Inspect: `zhixia-feihualing/episodes/jiuge-donghuang-taiyi-15s/assets/cover/donghuang-taiyi-cover-v01.png`
- Commit: renderer, builder, test, and non-ignored project outputs

**Interfaces:**
- Consumes: Task 3 的正式封面。
- Produces: 用户可直接查看和发布的封面，以及可复现的构建流程。

- [ ] **Step 1: 使用 `view_image` 检查正式封面**

逐项确认：人物位于中右、左侧文字区没有袖缘和火光干扰；`九歌`、`东皇太一`、`栀夏祭舞` 无错字；缩略状态仍能辨认主标题；脸、双手、脚、两个袖缘、礼鼓和祭坛无结构问题。若文字与人物重叠，只调整三列 `x` 或 `top` 参数一次并重新运行测试，不重新生成底图。

- [ ] **Step 2: 运行最终验证**

Run:

```zsh
zsh zhixia-feihualing/tests/test_donghuang_taiyi_cover.sh
git diff --check
git status --short
```

Expected: 封面测试通过，`git diff --check` 无输出；状态中不包含无关文件被暂存。

- [ ] **Step 3: 提交可复现流程**

仅暂存本任务新建的渲染器、构建脚本、测试和未被忽略的封面文件，检查 `git diff --cached --name-only` 后提交：

```bash
git commit -m "制作九歌东皇太一正式封面"
```

- [ ] **Step 4: 交付**

在最终回复中直接展示正式封面，并提供无字底图、正式封面、发布副本的绝对路径；同时报告内置图片生成工具、最终提示词、测试结果和提交号。
