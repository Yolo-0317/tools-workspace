# 《白雪歌》栀夏舞蹈版封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从《白雪歌》原始无字幕视频的 8.8 秒收势帧制作一张突出“栀夏会跳舞了”的 1080×1920 PNG 封面。

**Architecture:** FFmpeg 只负责按精确时间截取并放大原始视频帧，Swift/AppKit 只负责确定性文字排版。测试先验证脚本与输出缺失，再验证 PNG 尺寸、可解码性、非透明画面和标题渲染区域；最终人工查看确保人物与阿砚未被遮挡。

**Tech Stack:** Zsh、FFmpeg、Swift、AppKit、CoreText、Git。

## Global Constraints

- 输入固定为 `episodes/baixue/assets/video/content-seedance-v01.mp4`，不得从带字幕成片截取。
- 截帧时间固定为 8.800 秒，输出固定为 1080×1920 PNG。
- 只允许 Lanczos 放大与本地精确排版，不重绘、补帧、美颜或修改角色和雪景。
- 主标题为竖排“栀夏”“会跳舞了”，辅助题签为“白雪歌”。
- 字体使用项目已有行楷与楷体，颜色为暖象牙白并带轻微深色阴影。
- 标题位于左上安全区，不覆盖栀夏脸、双手、双臂主要轮廓、阿砚或右下角 AI 标识。
- 不在封面放“AI美女舞蹈”、诗句长文或额外水印。

---

### Task 1: 建立封面输出失败门禁

**Files:**
- Create: `zhixia-feihualing/tests/test_baixue_dance_cover.sh`
- Test: `zhixia-feihualing/exports/baixue-dance-cover-v01.png`

**Interfaces:**
- Consumes: 已归档的原始 Seedance 视频。
- Produces: 调用封面构建脚本并验证最终 PNG 的 Zsh 测试。

- [ ] **Step 1: 写失败测试**

测试要求 `scripts/build_baixue_dance_cover.sh`、`scripts/render_baixue_dance_cover.swift` 和原始视频存在；运行构建脚本后，使用 FFprobe 验证输出为 1080×1920 PNG，并用 FFmpeg 完整解码。另检查输出不是透明空图，且封面路径已登记到资产清单。

```zsh
#!/bin/zsh
set -euo pipefail
project_dir="${0:A:h:h}"
builder="$project_dir/scripts/build_baixue_dance_cover.sh"
renderer="$project_dir/scripts/render_baixue_dance_cover.swift"
output="$project_dir/exports/baixue-dance-cover-v01.png"
test -s "$builder"
test -s "$renderer"
zsh "$builder" >/dev/null
test "$(ffprobe -v error -show_entries stream=width,height -of csv=p=0 "$output")" = "1080,1920"
ffmpeg -v error -i "$output" -frames:v 1 -f null -
rg -qF "baixue-dance-cover-v01" "$project_dir/assets/inventory.csv"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `zsh zhixia-feihualing/tests/test_baixue_dance_cover.sh`

Expected: FAIL，因为封面构建脚本与输出尚不存在。

### Task 2: 实现确定性截帧与排版

**Files:**
- Create: `zhixia-feihualing/scripts/build_baixue_dance_cover.sh`
- Create: `zhixia-feihualing/scripts/render_baixue_dance_cover.swift`
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Modify: `zhixia-feihualing/episodes/baixue/README.md`
- Test: `zhixia-feihualing/tests/test_baixue_dance_cover.sh`

**Interfaces:**
- Consumes: 8.800 秒原片帧和系统行楷、楷体字体。
- Produces: `exports/baixue-dance-cover-v01.png`。

- [ ] **Step 1: 编写截帧脚本**

脚本以 `-ss 8.800` 截取单帧，使用 `scale=1080:1920:flags=lanczos` 输出临时 RGB PNG，再调用 Swift 渲染器生成最终封面。临时文件放在 `mktemp -d` 目录并在退出时清理。

- [ ] **Step 2: 编写 Swift 排版器**

使用 AppKit/CoreText 打开 1080×1920 底图。左侧小列竖排“栀夏”，主列竖排“会跳舞了”，附近放置较小“白雪歌”；文字使用暖象牙白、轻微深色阴影，位置避开人物举起的左臂。最终以无透明 RGB PNG 原子写入输出路径。

- [ ] **Step 3: 登记并链接封面**

在 `assets/inventory.csv` 添加 `baixue-dance-cover-v01`，记录原片截帧、本地精确排版、1080×1920 和保留 AI 标识；在 `episodes/baixue/README.md` 的关联文档中加入最终封面链接。

- [ ] **Step 4: 运行自动验证**

Run: `zsh zhixia-feihualing/tests/test_baixue_dance_cover.sh`

Expected: `PASS: Baixue dance cover is a valid 1080x1920 PNG built from the 8.8s source frame`

### Task 3: 视觉检查与提交

**Files:**
- Verify: `zhixia-feihualing/exports/baixue-dance-cover-v01.png`
- Verify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 2 的封面输出。
- Produces: 经过人工构图确认并可用于发布的最终封面。

- [ ] **Step 1: 查看最终 PNG**

确认栀夏正脸、双臂舞姿、完整裙身和阿砚清楚；“栀夏会跳舞了”第一眼可读；“白雪歌”不抢主体；标题不覆盖右下角 AI 标识。

- [ ] **Step 2: 运行格式检查**

Run: `git diff --check`

Expected: 无输出并返回 0。

- [ ] **Step 3: 提交**

```zsh
git add zhixia-feihualing/scripts/build_baixue_dance_cover.sh zhixia-feihualing/scripts/render_baixue_dance_cover.swift zhixia-feihualing/tests/test_baixue_dance_cover.sh zhixia-feihualing/assets/inventory.csv zhixia-feihualing/episodes/baixue/README.md
git commit -m "制作白雪歌栀夏舞蹈封面"
```
