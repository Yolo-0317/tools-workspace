# 《山行》舞蹈版封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从《山行》15 秒无字幕 Seedance 原片 12.600 秒截帧，制作并登记一张 1080×1920 的“栀夏·山行一舞”发布封面。

**Architecture:** 构建脚本负责校验输入、精确截帧和放大，Swift 渲染器只负责确定性文字排版；单一测试脚本从输出规格、完整解码和资产登记三个方面建立交付门禁。单集 README 与资产清单记录来源和无重绘边界。

**Tech Stack:** Zsh、FFmpeg/FFprobe、Swift AppKit/CoreText、PNG

## Global Constraints

- 底图固定来自 `episodes/shanxing-15s/assets/video/content-seedance-v01.mp4` 的 12.600 秒。
- 输出固定为 `exports/shanxing-dance-cover-v01.png`，1080×1920 PNG。
- 只做原片截帧、Lanczos 放大和本地排版，不重绘角色与诗景。
- 标题为竖排双列“小列栀夏、主列山行一舞”，题署为“杜牧《山行》”。
- 保留右下角原片“AI生成”标识，不加入完整诗句、搜索标签、额外水印、边框或贴纸。

---

### Task 1: 建立封面失败门禁并生成确定性成品

**Files:**
- Create: `tests/test_shanxing_dance_cover.sh`
- Create: `scripts/build_shanxing_dance_cover.sh`
- Create: `scripts/render_shanxing_dance_cover.swift`
- Create: `exports/shanxing-dance-cover-v01.png`

**Interfaces:**
- Consumes: 无字幕原片与系统行楷、楷体字体。
- Produces: 可重复构建的 1080×1920 PNG，以及退出码为零的成品门禁。

- [ ] **Step 1: 写入会失败的输出门禁**

测试先要求构建器可执行、渲染器存在、输出为 1080×1920 PNG、可完整解码，并要求 `assets/inventory.csv` 包含 `shanxing-dance-cover-v01`：

```zsh
[[ -x "$builder" ]] || exit 1
[[ -s "$renderer" ]] || exit 1
"$builder"
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height -of default=noprint_wrappers=1 "$output"
ffmpeg -v error -i "$output" -f null -
rg -qF "shanxing-dance-cover-v01" "$project_dir/assets/inventory.csv"
```

- [ ] **Step 2: 运行门禁并确认红灯**

Run: `zsh tests/test_shanxing_dance_cover.sh`

Expected: FAIL，提示缺少可执行构建器或渲染器。

- [ ] **Step 3: 实现最小构建器与渲染器**

构建器使用以下精确截帧参数：

```zsh
ffmpeg -hide_banner -loglevel error -y \
  -ss 12.600 -i "$source_video" -frames:v 1 \
  -vf "scale=1080:1920:flags=lanczos,format=rgb24" "$base"
```

Swift 渲染器沿用项目封面工具的 `drawVertical` 接口，以暖象牙白和轻微深色柔影绘制三列文字；文字区域限制在左上低冲突区，不覆盖栀夏、阿砚、红枫中心或石阶。

- [ ] **Step 4: 登记资产后运行门禁确认绿灯**

在 `assets/inventory.csv` 增加 `shanxing-dance-cover-v01`，再运行：

Run: `zsh tests/test_shanxing_dance_cover.sh`

Expected: `PASS: Shanxing dance cover is valid, 1080x1920, and inventoried`

- [ ] **Step 5: 提交生成链路**

```bash
git add zhixia-feihualing/tests/test_shanxing_dance_cover.sh \
  zhixia-feihualing/scripts/build_shanxing_dance_cover.sh \
  zhixia-feihualing/scripts/render_shanxing_dance_cover.swift \
  zhixia-feihualing/assets/inventory.csv
git commit -m "制作山行舞蹈版封面"
```

### Task 2: 登记单集交付并完成视觉验收

**Files:**
- Create: `episodes/shanxing-15s/README.md`
- Verify: `exports/shanxing-dance-cover-v01.png`

**Interfaces:**
- Consumes: Task 1 的正式封面。
- Produces: 可追溯的单集说明和经过人工构图复核的发布封面。

- [ ] **Step 1: 写入单集说明**

README 记录诗文、无字幕原片、15 秒朗诵字幕成片、正式封面、12.600 秒取帧、1080×1920 规格，以及“不重绘角色与诗景”的处理边界。

- [ ] **Step 2: 做视觉复核**

检查第一眼读到“山行一舞”，随后识别“栀夏”和题署；栀夏完整舞姿、阿砚、红白霜林、寒山石阶同时可辨，原片“AI生成”标识仍保留。

- [ ] **Step 3: 做最终验证**

Run: `zsh tests/test_shanxing_dance_cover.sh && git diff --check`

Expected: 测试通过且没有空白错误。

- [ ] **Step 4: 提交单集说明**

```bash
git add zhixia-feihualing/episodes/shanxing-15s/README.md
git commit -m "登记山行十五秒诗境成片"
```
