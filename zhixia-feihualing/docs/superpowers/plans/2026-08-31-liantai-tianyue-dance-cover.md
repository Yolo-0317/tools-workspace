# 《莲台天乐》舞蹈封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从《莲台天乐》无字幕高清朗诵版 14.000 秒精确截帧，制作一张包含“栀夏”“莲台天乐”和诗题署的 1080×1920 正式竖版封面。

**Architecture:** zsh 构建脚本只负责验证输入、精确取帧并调用渲染器；Swift/AppKit 渲染器只负责在原始视频帧上绘制固定三列竖排文字。独立 shell 门禁先验证缺少构建入口时失败，再构建 PNG 并检查时间、文字、尺寸、格式和媒体可解码性；最终只登记已验收封面，不修改视频。

**Tech Stack:** zsh、FFmpeg、Swift、AppKit、CoreText、sips、Git

## Global Constraints

- 设计真源为 `docs/superpowers/specs/2026-08-31-liantai-tianyue-dance-cover-design.md`。
- 唯一底图来源为 `exports/liantai-tianyue-15s-voiced-v01.mp4` 的 14.000 秒原帧。
- 输出固定为 `exports/liantai-tianyue-dance-cover-v01.png`，1080×1920 PNG。
- 三列文字固定为“栀夏”“莲台天乐”“唐·李白《庐山东林寺夜怀》”。
- 主标题使用行楷，角色名与题署使用楷体；颜色为暖象牙白与柔和旧金，并使用克制暗色柔影。
- 文字位于左侧安全区，不遮挡栀夏五官、头冠主体、躯干中心和右下角已有标识。
- 不调用图片生成模型，不重绘、补画、裁切、拉伸或修复人物、飘带和石窟场景。
- 不修改朗诵字幕成片，不制作横版、动态封面或发布文案。

---

## 文件结构

- `tests/test_liantai_tianyue_dance_cover.sh`：封面取帧、文字、规格和可解码性门禁。
- `scripts/build_liantai_tianyue_dance_cover.sh`：14.000 秒取帧和渲染入口。
- `scripts/render_liantai_tianyue_dance_cover.swift`：三列竖排中文的确定性 AppKit 渲染器。
- `exports/liantai-tianyue-dance-cover-v01.png`：本地正式封面资产。
- `episodes/liantai-tianyue-15s/README.md`：取帧、排版和制作边界记录。
- `assets/inventory.csv`：正式封面资产登记。

### Task 1: 建立封面失败门禁

**Files:**
- Create: `zhixia-feihualing/tests/test_liantai_tianyue_dance_cover.sh`

**Interfaces:**
- Consumes: 无字幕高清朗诵版及设计中的固定取帧时间、文字和输出路径。
- Produces: 构建入口缺失时明确失败、实现后可重复生成并验收正式 PNG 的单一测试命令。

- [ ] **Step 1: 写入失败门禁**

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
build_script="$project_dir/scripts/build_liantai_tianyue_dance_cover.sh"
renderer="$project_dir/scripts/render_liantai_tianyue_dance_cover.swift"
source_video="$project_dir/exports/liantai-tianyue-15s-voiced-v01.mp4"
output="$project_dir/exports/liantai-tianyue-dance-cover-v01.png"

[[ -s "$source_video" ]] || { print -u2 "FAIL: missing Liantai Tianyue voiced source"; exit 1; }
[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable Liantai Tianyue cover builder"; exit 1; }
[[ -s "$renderer" ]] || { print -u2 "FAIL: missing Liantai Tianyue cover renderer"; exit 1; }

rg -q -- '-ss 14.000' "$build_script" || { print -u2 "FAIL: cover must use frame 14.000"; exit 1; }
rg -q 'drawVertical\("栀夏"' "$renderer" || { print -u2 "FAIL: missing Zhixia label"; exit 1; }
rg -q 'drawVertical\("莲台天乐"' "$renderer" || { print -u2 "FAIL: missing Liantai Tianyue title"; exit 1; }
rg -q 'drawVertical\("唐·李白《庐山东林寺夜怀》"' "$renderer" || { print -u2 "FAIL: missing poem attribution"; exit 1; }

"$build_script" >/dev/null
[[ -s "$output" ]] || { print -u2 "FAIL: Liantai Tianyue cover was not created"; exit 1; }

properties="$(sips -g pixelWidth -g pixelHeight -g format "$output")"
print -r -- "$properties" | rg -q 'pixelWidth: 1080'
print -r -- "$properties" | rg -q 'pixelHeight: 1920'
print -r -- "$properties" | rg -q 'format: png'
ffmpeg -v error -i "$output" -f null -

print "PASS: Liantai Tianyue dance cover is ready"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd zhixia-feihualing && zsh tests/test_liantai_tianyue_dance_cover.sh`

Expected: FAIL，报告缺少可执行构建脚本，而不是 zsh 语法错误。

### Task 2: 实现精确取帧与文字渲染

**Files:**
- Create: `zhixia-feihualing/scripts/build_liantai_tianyue_dance_cover.sh`
- Create: `zhixia-feihualing/scripts/render_liantai_tianyue_dance_cover.swift`

**Interfaces:**
- Consumes: `exports/liantai-tianyue-15s-voiced-v01.mp4`。
- Produces: `exports/liantai-tianyue-dance-cover-v01.png`。

- [ ] **Step 1: 创建构建脚本**

构建脚本必须使用临时目录，通过以下命令精确取帧：

```zsh
ffmpeg -hide_banner -loglevel error -y \
  -ss 14.000 -i "$source_video" -frames:v 1 \
  -vf "format=rgb24" "$base"
```

随后为 Swift 设置独立模块缓存并调用：

```zsh
swift "$renderer" "$base" "$output"
```

- [ ] **Step 2: 创建渲染器**

渲染器固定 1080×1920 画布，注册系统行楷与楷体字体，并复用项目既有 `drawVertical(_:x:top:step:font:color:)` 接口。绘制参数固定为：

```swift
drawVertical("栀夏", x: 92, top: 214, step: 62, font: nameFont, color: quietIvory)
drawVertical("莲台天乐", x: 208, top: 198, step: 112, font: titleFont, color: titleIvory)
drawVertical("唐·李白《庐山东林寺夜怀》", x: 328, top: 560, step: 38, font: creditFont, color: quietIvory)
```

字体固定为 `STXingkaiSC-Bold` 88 pt、`STKaitiSC-Regular` 46 pt 与 28 pt；背景原帧按原尺寸绘制，不附加边框、渐变或装饰。

- [ ] **Step 3: 赋予执行权限并运行门禁**

Run:

```zsh
chmod +x zhixia-feihualing/scripts/build_liantai_tianyue_dance_cover.sh
cd zhixia-feihualing
zsh tests/test_liantai_tianyue_dance_cover.sh
```

Expected: `PASS: Liantai Tianyue dance cover is ready`。

- [ ] **Step 4: 查看原尺寸封面**

使用图像查看工具打开 `exports/liantai-tianyue-dance-cover-v01.png`，检查人物脸部、头冠、左手、躯干中心、文字列距、题署底部和右下角标识。若文字遮挡五官或题署溢出，只调整 `x`、`top` 与 `step`，不改变底图。

### Task 3: 登记封面并完成交付

**Files:**
- Modify: `zhixia-feihualing/episodes/liantai-tianyue-15s/README.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 2 通过视觉验收的正式封面。
- Produces: 单集完成记录和素材清单中的可追溯封面条目。

- [ ] **Step 1: 更新单集说明**

在 README 增加正式封面路径、14.000 秒取帧、三列竖排文字、1080×1920 PNG、保留原片标识和不使用图片模型重绘的说明。

- [ ] **Step 2: 登记正式封面**

向 `assets/inventory.csv` 增加唯一条目：

```csv
liantai-tianyue-dance-cover-v01,cover,莲台天乐,dance-cover,exports/liantai-tianyue-dance-cover-v01.png,final,local FFmpeg frame extraction plus Swift typography,derived from approved project video,1080×1920；取自无字幕高清朗诵版14.000秒；左侧竖排栀夏与莲台天乐；附唐·李白庐山东林寺夜怀题署；保留AI生成标识；无图像模型重绘
```

- [ ] **Step 3: 最终验证**

Run:

```zsh
cd zhixia-feihualing
zsh tests/test_liantai_tianyue_dance_cover.sh
git diff --check -- scripts/build_liantai_tianyue_dance_cover.sh \
  scripts/render_liantai_tianyue_dance_cover.swift \
  tests/test_liantai_tianyue_dance_cover.sh \
  episodes/liantai-tianyue-15s/README.md assets/inventory.csv
awk -F, 'NF != 9 {print NR ":" NF ":" $0}' assets/inventory.csv
```

Expected: 封面门禁通过、无空白错误、CSV 每行均为 9 列。

- [ ] **Step 4: 提交封面实现**

```bash
git add zhixia-feihualing/scripts/build_liantai_tianyue_dance_cover.sh \
  zhixia-feihualing/scripts/render_liantai_tianyue_dance_cover.swift \
  zhixia-feihualing/tests/test_liantai_tianyue_dance_cover.sh \
  zhixia-feihualing/episodes/liantai-tianyue-15s/README.md \
  zhixia-feihualing/assets/inventory.csv
git commit -m "制作莲台天乐舞蹈封面"
```

PNG 作为本地导出资产保留；提交前只暂存本任务文件与素材清单中的本次条目，保留工作区其他修改。
