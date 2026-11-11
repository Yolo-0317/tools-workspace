# 《黄河》舞蹈版封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从《黄河》无字幕配音版 5.800 秒截帧，制作一张突出栀夏腾跃水弧舞姿、同时保留阿砚与黄河诗景的 1080×1920 PNG 正式封面。

**Architecture:** 构建脚本用 FFmpeg 从既有视频精确取帧并放大为目标尺寸，再调用独立 Swift 渲染器完成行楷与楷体竖排文字合成。验收脚本从用户可见输出验证尺寸、编码、可解码性和资产登记，不测试实现文本。

**Tech Stack:** Zsh、FFmpeg/FFprobe、Swift AppKit/CoreText、Git。

## Global Constraints

- 输入固定为 `exports/huanghe-voiced-v01.mp4` 的 5.800 秒帧；这是视觉检查后用于避免阿砚被遮挡的相邻帧。
- 输出固定为 `exports/huanghe-dance-cover-v01.png`，PNG，1080×1920。
- 文案固定为“栀夏”“黄河一舞”“李白《将进酒》”，采用左侧竖排。
- 不使用图像模型，不重绘、补画、换脸或重塑角色。
- 保留原片 AI 生成标识，不增加额外水印、边框、标签、对白或完整诗句。
- 不修改视频内容，也不把封面姿态写回后续诗境的舞蹈规则。

---

### Task 1: 建立封面输出门禁并完成精确取帧排版

**Files:**
- Create: `zhixia-feihualing/tests/test_huanghe_dance_cover.sh`
- Create: `zhixia-feihualing/scripts/build_huanghe_dance_cover.sh`
- Create: `zhixia-feihualing/scripts/render_huanghe_dance_cover.swift`
- Produce: `zhixia-feihualing/exports/huanghe-dance-cover-v01.png`

**Interfaces:**
- Consumes: `build_huanghe_dance_cover.sh` 无参数运行，读取固定输入视频与 Swift 渲染器。
- Produces: 可完整解码的 1080×1920 RGB PNG；构建脚本成功时在标准输出打印绝对输出路径。

- [ ] **Step 1: 写入失败测试**

创建测试脚本，先要求构建脚本和渲染器可执行/存在，执行构建后使用以下真实输出断言：

```zsh
builder="$project_dir/scripts/build_huanghe_dance_cover.sh"
renderer="$project_dir/scripts/render_huanghe_dance_cover.swift"
output="$project_dir/exports/huanghe-dance-cover-v01.png"

[[ -x "$builder" ]] || { print -u2 "FAIL: missing executable builder"; exit 1; }
[[ -s "$renderer" ]] || { print -u2 "FAIL: missing renderer"; exit 1; }
"$builder"
[[ -s "$output" ]] || { print -u2 "FAIL: missing output cover"; exit 1; }

spec="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,pix_fmt -of default=noprint_wrappers=1 "$output")"
[[ "$spec" == *"codec_name=png"* && "$spec" == *"width=1080"* && "$spec" == *"height=1920"* ]] || exit 1
ffmpeg -v error -i "$output" -f null -
```

- [ ] **Step 2: 运行测试并确认按预期失败**

Run: `zsh zhixia-feihualing/tests/test_huanghe_dance_cover.sh`

Expected: FAIL，提示缺少 `build_huanghe_dance_cover.sh`。

- [ ] **Step 3: 编写最小构建脚本**

构建脚本创建临时目录，以以下命令生成精确底图，再调用 Swift 渲染器：

```zsh
ffmpeg -hide_banner -loglevel error -y \
  -ss 5.800 -i "$source_video" -frames:v 1 \
  -vf "scale=1080:1920:flags=lanczos,format=rgb24" "$base"
swift "$renderer" "$base" "$output"
```

脚本需检查输入和渲染器均为非空文件，并用 `trap` 清理 `mktemp -d` 创建的目录。

- [ ] **Step 4: 编写独立 Swift 排版器**

渲染器加载 1080×1920 底图，注册项目既有的 `STXingkaiSC-Bold` 与 `STKaitiSC-Regular` 字体，绘制：

```swift
drawVertical("栀夏", x: 108, top: 220, step: 62, font: nameFont, color: quietIvory)
drawVertical("黄河一舞", x: 226, top: 208, step: 112, font: titleFont, color: titleIvory)
drawVertical("李白《将进酒》", x: 344, top: 665, step: 42, font: creditFont, color: quietIvory)
```

主标题字号 88，小标题字号 46，题署字号 31；沿用深色柔影并输出无损 PNG。

- [ ] **Step 5: 运行测试并确认通过**

Run: `zsh zhixia-feihualing/tests/test_huanghe_dance_cover.sh`

Expected: PASS，输出是 1080×1920 PNG 且 FFmpeg 可完整解码。

- [ ] **Step 6: 视觉检查**

使用 `view_image` 打开最终 PNG，确认栀夏面部、腾跃肢体和水弧未被文字遮挡；阿砚完整可见；标题位于左侧山体留白区；AI 生成标识仍在右下角。

### Task 2: 登记正式封面并完成验收

**Files:**
- Modify: `zhixia-feihualing/episodes/huanghe/README.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Test: `zhixia-feihualing/tests/test_huanghe_dance_cover.sh`

**Interfaces:**
- Consumes: Task 1 视觉检查通过的 `exports/huanghe-dance-cover-v01.png`。
- Produces: 单集说明和资产清单中的正式封面记录。

- [ ] **Step 1: 扩展失败测试以检查资产登记**

在测试末尾增加真实登记断言：

```zsh
rg -qF "huanghe-dance-cover-v01" "$project_dir/assets/inventory.csv" || {
  print -u2 "FAIL: cover is not inventoried"
  exit 1
}
```

- [ ] **Step 2: 运行测试并确认登记缺失**

Run: `zsh zhixia-feihualing/tests/test_huanghe_dance_cover.sh`

Expected: FAIL，提示封面尚未登记。

- [ ] **Step 3: 更新单集说明与资产清单**

在 README 增加封面路径、5.800 秒取帧、1080×1920 规格、左侧竖排文案和“不使用图像模型重绘”的说明。向 `assets/inventory.csv` 追加 `huanghe-dance-cover-v01`，类型为 `cover`、状态为 `final`、来源为本地 FFmpeg 截帧与 Swift 精确排版。

- [ ] **Step 4: 完成最终验证**

Run: `zsh zhixia-feihualing/tests/test_huanghe_dance_cover.sh && git diff --check`

Expected: 测试输出 PASS，`git diff --check` 无输出且退出码为 0。

- [ ] **Step 5: 提交实现**

```bash
git add zhixia-feihualing/docs/superpowers/plans/2026-08-29-huanghe-dance-cover.md \
  zhixia-feihualing/scripts/build_huanghe_dance_cover.sh \
  zhixia-feihualing/scripts/render_huanghe_dance_cover.swift \
  zhixia-feihualing/tests/test_huanghe_dance_cover.sh \
  zhixia-feihualing/episodes/huanghe/README.md \
  zhixia-feihualing/assets/inventory.csv
git commit -m "制作黄河舞蹈版封面"
```

Expected: 只提交《黄河》封面计划、脚本、测试和登记文件；PNG 作为本地导出资产保留，不纳入提交。
