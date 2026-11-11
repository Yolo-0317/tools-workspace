# 《晓出净慈寺送林子方》舞蹈封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 13.800 秒无字幕原片帧制作一张带“栀夏 / 荷花一舞 / 杨万里《晓出净慈寺送林子方》”竖排文字的 1080×1920 正式封面。

**Architecture:** FFmpeg 构建脚本负责从无字幕原片精确截帧并使用 Lanczos 放大，独立 Swift/AppKit 渲染器负责注册项目既有中文字体并完成三列竖排文字。Zsh 门禁执行真实构建，验证 PNG 尺寸、可解码性和非透明输出；人工抽查文字没有遮挡角色、朝阳、阿砚和核心红荷。

**Tech Stack:** Zsh、FFmpeg、FFprobe、Swift、AppKit、CoreText、sips

## Global Constraints

- 底图固定为 `episodes/jingci-lotus-15s/assets/video/content-seedance-v01.mp4` 的 13.800 秒帧。
- 只允许截帧、Lanczos 放大和本地文字排版，不调用图像模型或重绘画面。
- 标题固定为系列名“栀夏”、主标题“荷花一舞”和题署“杨万里《晓出净慈寺送林子方》”。
- 文字采用右上晨雾天空三列竖排，主标题行楷粗体，系列名和题署楷体，暖象牙白并带轻微深色柔影。
- 输出固定为 `exports/jingci-lotus-dance-cover-v01.png`，1080×1920 PNG，并保留右下角原片“AI生成”标识。
- 不加入完整诗句、对白字幕、发布标签、色块、边框、贴纸或额外水印。

---

### Task 1: 构建并登记正式封面

**Files:**
- Create: `tests/test_jingci_lotus_cover.sh`
- Create: `scripts/build_jingci_lotus_cover.sh`
- Create: `scripts/render_jingci_lotus_cover.swift`
- Create: `exports/jingci-lotus-dance-cover-v01.png`
- Modify: `episodes/jingci-lotus-15s/README.md`
- Modify: `assets/inventory.csv`

**Interfaces:**
- Consumes: 无字幕 Seedance 原片和 macOS 既有行楷、楷体字体。
- Produces: 可重复执行的封面构建脚本和 1080×1920 正式 PNG。

- [x] **Step 1: 写入失败门禁**

门禁要求 `build_jingci_lotus_cover.sh` 与 `render_jingci_lotus_cover.swift` 存在且可用，执行真实构建后检查输出文件非空、PNG 宽高恰为 1080×1920、具有 RGB 通道且透明度不为全空。

- [x] **Step 2: 运行门禁确认红灯**

Run: `zsh tests/test_jingci_lotus_cover.sh`

Expected: FAIL，报告缺少可执行封面构建脚本。

- [x] **Step 3: 实现 Swift 精确排版**

渲染器使用 `STXingkaiSC-Bold` 绘制“荷花一舞”，使用 `STKaitiSC-Regular` 绘制“栀夏”和题署；在 1080×1920 画布上将题署、主标题和系列名从左到右排列在右上天空留白区，保持题署视觉权重最低，并为三列文字添加统一柔影。

- [x] **Step 4: 实现 13.800 秒截帧构建**

构建脚本从无字幕原片 13.800 秒精确截取一帧，使用 `scale=1080:1920:flags=lanczos,format=rgb24` 生成临时底图，再调用 Swift 渲染器输出正式 PNG；临时目录使用 `mktemp -d` 并在退出时清理。

- [x] **Step 5: 运行门禁确认绿灯**

Run: `zsh tests/test_jingci_lotus_cover.sh`

Expected: `PASS: Jingci lotus dance cover is ready`

- [x] **Step 6: 视觉抽查并微调**

打开正式 PNG，确认标题没有遮挡太阳、栀夏面部与双臂、阿砚、前景红荷和主要水面倒影；若发生遮挡，只调整三列文字坐标、字号或行距，不更换底图时刻和标题内容。

- [x] **Step 7: 更新本集与资产登记**

README 记录正式封面路径、13.800 秒底图、三列文字和无重绘边界；`assets/inventory.csv` 追加 `jingci-lotus-dance-cover-v01`，状态为 `final`，来源为本地 FFmpeg 截帧与 Swift 排版。

- [x] **Step 8: 最终验证并提交**

Run: `zsh tests/test_jingci_lotus_cover.sh && git diff --check`

只提交本集封面计划、测试、构建脚本、渲染器、README 和资产登记，不提交其他未关联修改。
