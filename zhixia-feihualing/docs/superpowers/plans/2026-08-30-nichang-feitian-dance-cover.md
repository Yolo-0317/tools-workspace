# 《霓裳飞天》舞蹈封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从《霓裳飞天》无字幕高清朗诵版 1.450 秒精确取帧，制作一张延续敦煌系列视觉规范的 1080×1920 正式封面。

**Architecture:** FFmpeg 负责从既有成片精确取出无损 RGB 底图，专用 Swift/AppKit 渲染器负责注册行楷与楷体字体并绘制三列竖排文字。zsh 构建脚本提供唯一可重跑入口，独立门禁验证取帧时间、标题内容、PNG尺寸与可解码性。

**Tech Stack:** zsh、FFmpeg、Swift/AppKit、CoreText、sips、Git。

## Global Constraints

- 底图固定为 `exports/nichang-feitian-15s-voiced-v01.mp4` 的 1.450 秒帧。
- 输出固定为 `exports/nichang-feitian-dance-cover-v01.png`，1080×1920 PNG。
- 三列竖排文字固定为“栀夏”“霓裳飞天”“唐·李白《古风·其十九》”。
- 文字采用暖象牙白、克制旧金和深色柔影；标题允许覆盖少量左侧飘带。
- 不调用图像模型，不重绘人物，不裁掉面部、头冠、躯干或抬起的腿。
- 保留原片右下角标识，不增加英文、印章、边框或平台图标。

---

### Task 1: 建立封面失败门禁

**Files:**
- Create: `zhixia-feihualing/tests/test_nichang_feitian_dance_cover.sh`
- Test: `zhixia-feihualing/tests/test_nichang_feitian_dance_cover.sh`

**Interfaces:**
- Consumes: 封面构建脚本、Swift 渲染器、无字幕朗诵版。
- Produces: 对取帧时间、三列文字、文件尺寸、格式和解码能力的自动检查。

- [ ] **Step 1: 创建门禁**

门禁先检查源视频存在，再要求两个实施文件存在；静态检查固定为：

```zsh
rg -q -- '-ss 1.450' "$build_script"
rg -q 'drawVertical\("栀夏"' "$renderer"
rg -q 'drawVertical\("霓裳飞天"' "$renderer"
rg -q 'drawVertical\("唐·李白《古风·其十九》"' "$renderer"
```

执行构建后使用 `sips` 检查 `pixelWidth: 1080`、`pixelHeight: 1920`、`format: png`，并使用 `ffmpeg -v error -i "$output" -f null -` 验证图片可解码。

- [ ] **Step 2: 运行门禁并确认失败**

Run: `zsh zhixia-feihualing/tests/test_nichang_feitian_dance_cover.sh`

Expected: FAIL，报告缺少构建脚本或渲染器。

### Task 2: 实现取帧与竖排排版

**Files:**
- Create: `zhixia-feihualing/scripts/build_nichang_feitian_dance_cover.sh`
- Create: `zhixia-feihualing/scripts/render_nichang_feitian_dance_cover.swift`
- Create: `zhixia-feihualing/exports/nichang-feitian-dance-cover-v01.png`

**Interfaces:**
- Consumes: Task 1 的门禁与固定源视频。
- Produces: 可重复生成的正式封面。

- [ ] **Step 1: 创建构建脚本**

构建脚本使用临时目录，并执行：

```zsh
ffmpeg -hide_banner -loglevel error -y \
  -ss 1.450 -i "$source_video" -frames:v 1 \
  -vf "format=rgb24" "$base"
swift "$renderer" "$base" "$output"
```

- [ ] **Step 2: 创建 Swift 渲染器**

画布为 1080×1920，底图完整铺满。注册系统 `Xingkai.ttc` 与 `Kaiti.ttc`；字体和位置固定为：

```swift
drawVertical("栀夏", x: 96, top: 222, step: 62, font: nameFont, color: quietIvory)
drawVertical("霓裳飞天", x: 218, top: 206, step: 112, font: titleFont, color: titleIvory)
drawVertical("唐·李白《古风·其十九》", x: 342, top: 610, step: 40, font: creditFont, color: quietIvory)
```

标题行楷字号 88，角色名楷体字号 46，题署楷体字号 29；三列使用深色柔影提升暗背景可读性。

- [ ] **Step 3: 运行门禁并生成封面**

Run: `zsh zhixia-feihualing/tests/test_nichang_feitian_dance_cover.sh`

Expected: `PASS: Nichang Feitian dance cover is ready`。

- [ ] **Step 4: 视觉验收**

检查人物全身与抬腿完整、面部和头冠清楚、主标题缩略状态可读、题署不进入底部荷花和右下角标识区域。若发生遮挡，只调整文字列的 x、top 或字号，不更换已确认底图。

### Task 3: 归档与最终验证

**Files:**
- Modify: `zhixia-feihualing/episodes/nichang-feitian-15s/README.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 2 正式封面和检查结果。
- Produces: 封面路径、制作方式与资产登记。

- [ ] **Step 1: 更新 README 与资产清单**

README 记录取帧时间、尺寸、三列文字和不重绘原则。资产清单追加唯一 `nichang-feitian-dance-cover-v01` 九列记录，并保持现有无关未提交改动原样。

- [ ] **Step 2: 最终验证**

```zsh
zsh zhixia-feihualing/tests/test_nichang_feitian_dance_cover.sh
git diff --check
awk -F, 'NF != 9 {print NR ":" NF; bad=1} END {exit bad}' zhixia-feihualing/assets/inventory.csv
```

Expected: 封面门禁 PASS，格式检查无输出，资产清单每行九列。

- [ ] **Step 3: 提交**

```zsh
git add zhixia-feihualing/tests/test_nichang_feitian_dance_cover.sh zhixia-feihualing/scripts/build_nichang_feitian_dance_cover.sh zhixia-feihualing/scripts/render_nichang_feitian_dance_cover.swift zhixia-feihualing/episodes/nichang-feitian-15s/README.md
git commit -m "制作霓裳飞天舞蹈封面"
```

资产清单只分块暂存 `nichang-feitian-dance-cover-v01` 对应记录。
