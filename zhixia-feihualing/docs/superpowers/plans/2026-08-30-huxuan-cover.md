# 《回雪胡旋》舞蹈版封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从《回雪胡旋》无字幕高清朗诵版 1.250 秒截取动作帧，制作并登记一张 1080×1920 竖版舞蹈封面。

**Architecture:** 一个 shell 构建脚本负责精确取帧并调用专用 Swift/AppKit 排版器，排版器只叠加三列竖排中文，不修改底图像素内容。独立门禁先验证缺失实现时失败，再检查构建脚本取帧时间、文字常量、输出 PNG 规格和最终文件可解码性。

**Tech Stack:** zsh、FFmpeg、Swift、AppKit、CoreText、ImageMagick `identify` 或 `sips`

## Global Constraints

- 唯一输入为 `exports/huxuan-15s-voiced-v01.mp4`，固定在 1.250 秒取帧。
- 输出固定为 `exports/huxuan-dance-cover-v01.png`，1080×1920 PNG。
- 文字固定为“栀夏”“回雪胡旋”“唐·白居易《胡旋女》”。
- 使用本地行楷和楷体排版，不调用图像模型，不重绘人物、服装、飘带、场景或光线。
- 标题允许覆盖部分飘带和裙摆，但不得遮挡栀夏五官、头冠主体或上举手掌。
- 保留右下角 AI 生成标识，不增加边框、粒子、光效、印章或其他装饰。

---

### Task 1: 构建、验收并登记正式封面

**Files:**
- Create: `zhixia-feihualing/tests/test_huxuan_dance_cover.sh`
- Create: `zhixia-feihualing/scripts/build_huxuan_dance_cover.sh`
- Create: `zhixia-feihualing/scripts/render_huxuan_dance_cover.swift`
- Create: `zhixia-feihualing/exports/huxuan-dance-cover-v01.png`
- Modify: `zhixia-feihualing/episodes/huxuan-15s/README.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: 已完成的 `exports/huxuan-15s-voiced-v01.mp4` 和系统行楷、楷体字体。
- Produces: 可重复执行的本地封面构建入口、1080×1920 正式 PNG 和项目登记。

- [ ] **Step 1: 写入失败门禁**

创建可执行 `tests/test_huxuan_dance_cover.sh`，固定检查：

```zsh
[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable Huxuan cover builder"; exit 1; }
[[ -s "$renderer" ]] || { print -u2 "FAIL: missing Huxuan cover renderer"; exit 1; }
rg -q -- '-ss 1.250' "$build_script"
rg -q 'drawVertical\("栀夏"' "$renderer"
rg -q 'drawVertical\("回雪胡旋"' "$renderer"
rg -q 'drawVertical\("唐·白居易《胡旋女》"' "$renderer"
```

测试执行构建后用 `sips -g pixelWidth -g pixelHeight -g format` 检查输出为 1080×1920 PNG，并用 `sips -g hasAlpha` 或 FFprobe 确认可正常解码。

- [ ] **Step 2: 运行测试确认因构建脚本缺失而失败**

Run: `zsh tests/test_huxuan_dance_cover.sh`

Expected: FAIL，报告缺少可执行封面构建脚本，而不是 shell 语法错误。

- [ ] **Step 3: 实现专用 Swift 排版器**

复用现有封面字体注册方式：主标题使用 `STXingkaiSC-Bold` 88pt，角色名使用 `STKaitiSC-Regular` 46pt，题署使用 `STKaitiSC-Regular` 31pt。画布固定 1080×1920，底图原尺寸绘制；三列位置固定为：

```swift
drawVertical("栀夏", x: 96, top: 222, step: 62, font: nameFont, color: quietIvory)
drawVertical("回雪胡旋", x: 218, top: 206, step: 112, font: titleFont, color: titleIvory)
drawVertical("唐·白居易《胡旋女》", x: 342, top: 665, step: 42, font: creditFont, color: quietIvory)
```

使用暖象牙白与深色柔影；只绘制文字，不增加底板、边框或装饰。

- [ ] **Step 4: 实现构建脚本**

`build_huxuan_dance_cover.sh` 使用 `set -euo pipefail`，校验输入和排版器存在；以临时目录保存底图，执行：

```zsh
ffmpeg -hide_banner -loglevel error -y \
  -ss 1.250 -i "$source_video" -frames:v 1 \
  -vf "format=rgb24" "$base"
swift "$renderer" "$base" "$output"
```

临时目录使用 `mktemp -d /tmp/zhixia-huxuan-cover.XXXXXX` 并在退出时清理，不覆盖源视频。

- [ ] **Step 5: 运行测试确认封面生成成功**

Run: `zsh tests/test_huxuan_dance_cover.sh`

Expected: PASS，输出 `PASS: Huxuan dance cover is ready`，正式 PNG 为 1080×1920。

- [ ] **Step 6: 做视觉验收**

查看正式封面原图和缩小至 270×480 的预览图，确认：正脸、头冠和上举手掌清楚；主标题缩略图可读；文字只覆盖部分飘带或裙摆；右下角 AI 标识仍在；没有拉伸、乱码、截断或意外装饰。

- [ ] **Step 7: 更新 README 与资产清单**

README 新增正式封面路径、1.250 秒取帧、三列文字和不重绘说明。`assets/inventory.csv` 新增唯一资产行：

```csv
huxuan-dance-cover-v01,cover,回雪胡旋,dance-cover,exports/huxuan-dance-cover-v01.png,final,local FFmpeg frame extraction plus Swift typography,derived from approved project video,1080×1920；取自无字幕高清朗诵版1.250秒；竖排栀夏与回雪胡旋；附唐·白居易胡旋女题署；保留AI生成标识；无图像模型重绘
```

- [ ] **Step 8: 运行最终验证并提交**

Run:

```zsh
zsh tests/test_huxuan_dance_cover.sh
git diff --check
awk -F, 'NF != 9 {print NR ":" NF; bad=1} END {exit bad}' assets/inventory.csv
```

Expected: 测试 PASS，diff 无空白错误，资产清单每行九列。

Commit:

```zsh
git add tests/test_huxuan_dance_cover.sh scripts/build_huxuan_dance_cover.sh scripts/render_huxuan_dance_cover.swift episodes/huxuan-15s/README.md docs/superpowers/plans/2026-08-30-huxuan-cover.md
git commit -m "制作回雪胡旋舞蹈封面"
```

资产清单已有其他未提交改动时，只暂存本次新增的 `huxuan-dance-cover-v01` 行并单独提交。
