# 《飞袂绿腰》舞蹈封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从《飞袂绿腰》无字幕朗诵版 13.000 秒精确取帧，制作一张带固定三列竖排中文的 1080×1920 正式舞蹈封面。

**Architecture:** FFmpeg 只负责从已确认的无字幕朗诵版提取原始视频帧；独立 Swift/AppKit 渲染器只负责字体注册和确定性文字叠加。zsh 验收门禁固定输入哈希、取帧时间、文字内容、输出规格与可解码性，README 和素材清单记录最终资产。

**Tech Stack:** zsh、FFmpeg/ffprobe、Swift/AppKit/CoreText、sips、Git

## Global Constraints

- 设计真源为 `docs/superpowers/specs/2026-08-31-feimei-lvyao-dance-cover-design.md`。
- 唯一底图输入为 `exports/feimei-lvyao-15s-voiced-v01.mp4`，SHA-256 固定为 `9935399575bdc9ed648a12ecaf62c42b9f01ea9160e2cf5484918ac5febee071`。
- 取帧时间固定为 13.000 秒，禁止换帧、重绘、补画、美化或修改人物和场景。
- 封面文字只允许“栀夏”“飞袂绿腰”“唐·李群玉《长沙九日登东楼观舞》”。
- 输出固定为 `exports/feimei-lvyao-dance-cover-v01.png`，1080×1920 PNG。
- 保留右下角原片已有“AI生成”标识，不新增英文、完整诗句、印章、边框或平台图标。
- 不提交或覆盖工作区中与本封面无关的修改。

---

## File Structure

- `tests/test_feimei_lvyao_dance_cover.sh`：固定输入、时间、中文文字和输出规格的验收门禁。
- `scripts/build_feimei_lvyao_dance_cover.sh`：从 13.000 秒取帧并调用渲染器。
- `scripts/render_feimei_lvyao_dance_cover.swift`：只负责确定性三列竖排排版。
- `exports/feimei-lvyao-dance-cover-v01.png`：最终封面，不纳入 Git。
- `episodes/feimei-lvyao-15s/README.md`：记录封面来源、时间和制作方式。
- `assets/inventory.csv`：登记最终封面资产；若文件含用户未提交修改，只保留本地登记，不混入本次提交。

### Task 1: 建立封面验收门禁

**Files:**
- Create: `tests/test_feimei_lvyao_dance_cover.sh`

**Interfaces:**
- Consumes: `exports/feimei-lvyao-15s-voiced-v01.mp4`。
- Produces: 对构建入口、渲染器和正式 PNG 的单一验收命令。

- [ ] **Step 1: 写入失败测试**

```zsh
#!/bin/zsh
set -euo pipefail
project_dir="${0:A:h:h}"
source_video="$project_dir/exports/feimei-lvyao-15s-voiced-v01.mp4"
build_script="$project_dir/scripts/build_feimei_lvyao_dance_cover.sh"
renderer="$project_dir/scripts/render_feimei_lvyao_dance_cover.swift"
output="$project_dir/exports/feimei-lvyao-dance-cover-v01.png"

[[ "$(shasum -a 256 "$source_video" | awk '{print $1}')" == "9935399575bdc9ed648a12ecaf62c42b9f01ea9160e2cf5484918ac5febee071" ]]
[[ -x "$build_script" ]]
[[ -s "$renderer" ]]
rg -q -- '-ss 13.000' "$build_script"
rg -q 'drawVertical\("栀夏"' "$renderer"
rg -q 'drawVertical\("飞袂绿腰"' "$renderer"
rg -q 'drawVertical\("唐·李群玉《长沙九日登东楼观舞》"' "$renderer"
"$build_script" >/dev/null
properties="$(sips -g pixelWidth -g pixelHeight -g format "$output")"
print -r -- "$properties" | rg -q 'pixelWidth: 1080'
print -r -- "$properties" | rg -q 'pixelHeight: 1920'
print -r -- "$properties" | rg -q 'format: png'
ffmpeg -v error -i "$output" -f null -
print 'PASS: Feimei Lvyao dance cover is ready'
```

- [ ] **Step 2: 运行测试确认先失败**

Run: `chmod +x tests/test_feimei_lvyao_dance_cover.sh && ./tests/test_feimei_lvyao_dance_cover.sh`

Expected: FAIL，首先报告缺少可执行构建脚本或渲染器，不得因 zsh 语法错误失败。

- [ ] **Step 3: 提交门禁**

```bash
git add tests/test_feimei_lvyao_dance_cover.sh
git commit -m "建立飞袂绿腰封面门禁"
```

### Task 2: 实现确定性封面构建

**Files:**
- Create: `scripts/build_feimei_lvyao_dance_cover.sh`
- Create: `scripts/render_feimei_lvyao_dance_cover.swift`
- Produce: `exports/feimei-lvyao-dance-cover-v01.png`

**Interfaces:**
- Consumes: 13.000 秒源帧和系统行楷、楷体字体。
- Produces: `render_feimei_lvyao_dance_cover.swift <base.png> <output.png>` 与正式 PNG。

- [ ] **Step 1: 编写最小构建入口**

```zsh
#!/bin/zsh
set -euo pipefail
project_dir="${0:A:h:h}"
source_video="$project_dir/exports/feimei-lvyao-15s-voiced-v01.mp4"
renderer="$project_dir/scripts/render_feimei_lvyao_dance_cover.swift"
output="$project_dir/exports/feimei-lvyao-dance-cover-v01.png"
build_dir="$(mktemp -d /tmp/zhixia-feimei-cover.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT
base="$build_dir/base.png"
ffmpeg -hide_banner -loglevel error -y -ss 13.000 -i "$source_video" -frames:v 1 -vf 'format=rgb24' "$base"
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$base" "$output"
print -r -- "$output"
```

- [ ] **Step 2: 编写独立 Swift 渲染器**

渲染器创建 1080×1920 RGBA 位图，原尺寸绘制底图，并注册：

```swift
let xingkaiURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc")
let kaitiURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc")
```

文字绘制固定为：

```swift
drawVertical("栀夏", x: 92, top: 214, step: 62, font: nameFont, color: quietIvory)
drawVertical("飞袂绿腰", x: 208, top: 198, step: 112, font: titleFont, color: titleIvory)
drawVertical("唐·李群玉《长沙九日登东楼观舞》", x: 328, top: 560, step: 38, font: creditFont, color: quietIvory)
```

字体固定为 `STXingkaiSC-Bold` 88 pt、`STKaitiSC-Regular` 46 pt 和 28 pt；主字颜色 `(0.97, 0.92, 0.82)`，辅助字颜色 `(0.91, 0.86, 0.76, 0.96)`，阴影黑度 `0.76`、模糊 `6`、位移 `(2,-2)`。

- [ ] **Step 3: 运行测试并确认转绿**

Run: `chmod +x scripts/build_feimei_lvyao_dance_cover.sh && ./tests/test_feimei_lvyao_dance_cover.sh`

Expected: `PASS: Feimei Lvyao dance cover is ready`。

- [ ] **Step 4: 视觉检查**

使用本地图片查看器检查正式 PNG：面部、头冠、躯干中心和右下角标识不被文字遮挡；主标题在缩略图中可读；文字没有错字、溢出或列间重叠。若题署接近脸部，只调整题署列的 `x` 或 `top`，不得更换 13.000 秒源帧。

- [ ] **Step 5: 提交实现**

```bash
git add scripts/build_feimei_lvyao_dance_cover.sh scripts/render_feimei_lvyao_dance_cover.swift
git commit -m "制作飞袂绿腰舞蹈封面"
```

### Task 3: 归档与最终验证

**Files:**
- Modify: `episodes/feimei-lvyao-15s/README.md`
- Modify: `assets/inventory.csv`

**Interfaces:**
- Consumes: 已通过视觉检查的正式封面。
- Produces: 可追溯的单集说明和资产清单记录。

- [ ] **Step 1: 更新单集说明**

在 README 增加“正式舞蹈封面”小节，准确写明：

```markdown
- 文件：`../../exports/feimei-lvyao-dance-cover-v01.png`。
- 规格：1080×1920 PNG。
- 底图：无字幕朗诵版 13.000 秒第三高潮定格。
- 排版：左侧“栀夏”“飞袂绿腰”“唐·李群玉《长沙九日登东楼观舞》”三列竖排文字。
- 制作：本地 FFmpeg 取帧与 Swift/AppKit 排版；未调用图片生成模型，保留原片 AI 生成标识。
```

- [ ] **Step 2: 登记资产清单**

追加且只追加一行：

```csv
feimei-lvyao-dance-cover-v01,cover,飞袂绿腰,dance-cover,exports/feimei-lvyao-dance-cover-v01.png,final,local FFmpeg frame extraction plus Swift typography,derived from approved project video,1080×1920；取自无字幕高清朗诵版13.000秒；左侧竖排栀夏与飞袂绿腰；附唐·李群玉长沙九日登东楼观舞题署；保留AI生成标识；无图像模型重绘
```

- [ ] **Step 3: 运行新鲜完整验证**

Run:

```bash
./tests/test_feimei_lvyao_dance_cover.sh
git diff --check -- episodes/feimei-lvyao-15s/README.md assets/inventory.csv scripts/build_feimei_lvyao_dance_cover.sh scripts/render_feimei_lvyao_dance_cover.swift tests/test_feimei_lvyao_dance_cover.sh
test "$(rg -c '^feimei-lvyao-dance-cover-v01,' assets/inventory.csv)" = "1"
```

Expected: 门禁 PASS、无空白错误、资产记录恰好一条。

- [ ] **Step 4: 提交归档说明**

只提交本次 README 改动；若 `assets/inventory.csv` 同时含其他用户未提交修改，不提交该文件并在交付说明中注明本地登记已经完成。

```bash
git add episodes/feimei-lvyao-15s/README.md
git commit -m "归档飞袂绿腰舞蹈封面"
```
