# 《雪袖白纻》舞蹈封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从《雪袖白纻》无字幕高清朗诵版 0.800 秒精确取帧，制作一张延续敦煌系列视觉规范的 1080×1920 正式封面。

**Architecture:** FFmpeg 负责从既有成片精确取出无损 RGB 底图，专用 Swift/AppKit 渲染器负责注册行楷与楷体字体并绘制三列竖排文字。zsh 构建脚本提供唯一可重跑入口，独立门禁验证取帧时间、标题内容、PNG 尺寸与可解码性。

**Tech Stack:** zsh、FFmpeg、Swift/AppKit、CoreText、sips、Git

## Global Constraints

- 底图固定为 `exports/xuexiu-baizhu-15s-voiced-v01.mp4` 的 0.800 秒帧。
- 输出固定为 `exports/xuexiu-baizhu-dance-cover-v01.png`，1080×1920 PNG。
- 三列竖排文字固定为“栀夏”“雪袖白纻”“唐·李白《白纻辞三首·其三》”。
- 文字采用暖象牙白、克制旧金和深色柔影；主标题允许覆盖少量左侧手臂或舞绸。
- 不调用图像模型，不重绘人物，不改变源帧构图、光影、人物比例或舞绸连接。
- 保留原片右下角已有标识，不增加英文、印章、边框或平台图标。

---

### Task 1: 建立封面失败门禁

**Files:**
- Create: `zhixia-feihualing/tests/test_xuexiu_baizhu_dance_cover.sh`

**Interfaces:**
- Consumes: 封面构建脚本、Swift 渲染器、无字幕朗诵版。
- Produces: 对取帧时间、三列文字、输出尺寸、格式和解码能力的自动检查。

- [ ] **Step 1: 创建门禁**

创建以下完整 zsh 门禁：

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
build_script="$project_dir/scripts/build_xuexiu_baizhu_dance_cover.sh"
renderer="$project_dir/scripts/render_xuexiu_baizhu_dance_cover.swift"
source_video="$project_dir/exports/xuexiu-baizhu-15s-voiced-v01.mp4"
output="$project_dir/exports/xuexiu-baizhu-dance-cover-v01.png"

[[ -s "$source_video" ]] || { print -u2 "FAIL: missing Xuexiu Baizhu voiced source"; exit 1; }
[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable Xuexiu Baizhu cover builder"; exit 1; }
[[ -s "$renderer" ]] || { print -u2 "FAIL: missing Xuexiu Baizhu cover renderer"; exit 1; }

rg -q -- '-ss 0.800' "$build_script" || { print -u2 "FAIL: cover must use frame 0.800"; exit 1; }
rg -q 'drawVertical\("栀夏"' "$renderer" || { print -u2 "FAIL: missing Zhixia label"; exit 1; }
rg -q 'drawVertical\("雪袖白纻"' "$renderer" || { print -u2 "FAIL: missing Xuexiu Baizhu title"; exit 1; }
rg -q 'drawVertical\("唐·李白《白纻辞三首·其三》"' "$renderer" || { print -u2 "FAIL: missing poem attribution"; exit 1; }

"$build_script" >/dev/null
[[ -s "$output" ]] || { print -u2 "FAIL: Xuexiu Baizhu cover was not created"; exit 1; }

properties="$(sips -g pixelWidth -g pixelHeight -g format "$output")"
print -r -- "$properties" | rg -q 'pixelWidth: 1080'
print -r -- "$properties" | rg -q 'pixelHeight: 1920'
print -r -- "$properties" | rg -q 'format: png'
ffmpeg -v error -i "$output" -f null -

print "PASS: Xuexiu Baizhu dance cover is ready"
```

- [ ] **Step 2: 运行门禁并确认失败**

Run: `zsh tests/test_xuexiu_baizhu_dance_cover.sh`

Expected: FAIL，报告缺少构建脚本，而不是 zsh 语法错误或源视频缺失。

- [ ] **Step 3: 提交失败门禁**

```zsh
git add tests/test_xuexiu_baizhu_dance_cover.sh
git commit -m "建立雪袖白纻封面门禁"
```

### Task 2: 实现取帧与竖排排版

**Files:**
- Create: `zhixia-feihualing/scripts/build_xuexiu_baizhu_dance_cover.sh`
- Create: `zhixia-feihualing/scripts/render_xuexiu_baizhu_dance_cover.swift`
- Create: `zhixia-feihualing/exports/xuexiu-baizhu-dance-cover-v01.png`

**Interfaces:**
- Consumes: Task 1 的门禁和固定源视频。
- Produces: 可重复生成的正式封面。

- [ ] **Step 1: 创建构建脚本**

构建脚本使用临时目录并固定执行：

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/exports/xuexiu-baizhu-15s-voiced-v01.mp4"
renderer="$project_dir/scripts/render_xuexiu_baizhu_dance_cover.swift"
output="$project_dir/exports/xuexiu-baizhu-dance-cover-v01.png"
build_dir="$(mktemp -d /tmp/zhixia-xuexiu-cover.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT
base="$build_dir/base.png"

ffmpeg -hide_banner -loglevel error -y \
  -ss 0.800 -i "$source_video" -frames:v 1 \
  -vf "format=rgb24" "$base"
swift "$renderer" "$base" "$output"
```

- [ ] **Step 2: 创建 Swift 渲染器**

画布为 1080×1920，底图完整铺满。注册系统 `Xingkai.ttc` 与 `Kaiti.ttc`；字体和位置固定为：

```swift
drawVertical("栀夏", x: 92, top: 214, step: 62, font: nameFont, color: quietIvory)
drawVertical("雪袖白纻", x: 208, top: 198, step: 112, font: titleFont, color: titleIvory)
drawVertical("唐·李白《白纻辞三首·其三》", x: 328, top: 600, step: 38, font: creditFont, color: quietIvory)
```

标题行楷字号 88，角色名楷体字号 46，题署楷体字号 28。三列使用深色柔影；暖象牙白主标题和略暗旧金辅助字延续敦煌系列封面。渲染器只绘制文字，不修改底图像素内容。

- [ ] **Step 3: 运行门禁并生成封面**

Run: `zsh tests/test_xuexiu_baizhu_dance_cover.sh`

Expected: PASS，输出 `PASS: Xuexiu Baizhu dance cover is ready`。

- [ ] **Step 4: 视觉验收**

打开正式 PNG，确认人物全身、承重脚、抬起腿、面部和头冠清楚；主标题缩略状态可读；文字可覆盖少量左侧手臂或舞绸，但不进入面部和躯干中心；右下角原片标识保持原样。若发生遮挡，只调整文字列的 `x`、`top`、`step` 或字号，不更换已确认底图。

- [ ] **Step 5: 提交封面实现**

```zsh
git add scripts/build_xuexiu_baizhu_dance_cover.sh scripts/render_xuexiu_baizhu_dance_cover.swift tests/test_xuexiu_baizhu_dance_cover.sh
git commit -m "制作雪袖白纻舞蹈封面"
```

### Task 3: 归档与最终验证

**Files:**
- Modify: `zhixia-feihualing/episodes/xuexiu-baizhu-15s/README.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 2 正式封面和检查结果。
- Produces: 封面路径、制作方式与唯一资产登记。

- [ ] **Step 1: 更新 README**

在 README 新增“正式封面”小节，固定记录：

```markdown
## 正式封面

- 封面为 `../../exports/xuexiu-baizhu-dance-cover-v01.png`，1080×1920 PNG。
- 底图取自无字幕高清朗诵版 0.800 秒的第一高潮动作帧。
- 左侧竖排“栀夏”“雪袖白纻”与“唐·李白《白纻辞三首·其三》”，文字只覆盖少量左侧手臂、舞绸或暗部背景。
- 使用本地 FFmpeg 精确取帧与 Swift/AppKit 文字排版，不调用图像模型，不重绘人物或场景。
```

- [ ] **Step 2: 追加资产记录**

向 `assets/inventory.csv` 追加以下九列记录：

```csv
xuexiu-baizhu-dance-cover-v01,cover,雪袖白纻,dance-cover,exports/xuexiu-baizhu-dance-cover-v01.png,final,local FFmpeg frame extraction plus Swift typography,derived from approved project video,1080×1920；取自无字幕高清朗诵版0.800秒；左侧竖排栀夏与雪袖白纻；附唐·李白《白纻辞三首·其三》题署；保留AI生成标识；无图像模型重绘
```

- [ ] **Step 3: 最终验证**

```zsh
zsh tests/test_xuexiu_baizhu_dance_cover.sh
git diff --check -- episodes/xuexiu-baizhu-15s/README.md scripts/build_xuexiu_baizhu_dance_cover.sh scripts/render_xuexiu_baizhu_dance_cover.swift tests/test_xuexiu_baizhu_dance_cover.sh assets/inventory.csv
awk -F, 'NF != 9 {print NR ":" NF; bad=1} END {exit bad}' assets/inventory.csv
```

Expected: 封面门禁 PASS，格式检查无输出，资产清单每行九列。

- [ ] **Step 4: 提交归档记录**

```zsh
git add episodes/xuexiu-baizhu-15s/README.md
git add -p assets/inventory.csv
git commit -m "登记雪袖白纻舞蹈封面"
```

资产清单只暂存 `xuexiu-baizhu-dance-cover-v01` 对应记录，保留九歌与其他用户改动原样。
