# 《一舞一愿·九月好运》天宫双姝封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从九月好运无字幕有声成片的末段精确选帧，制作一张突出“天宫双姝”文化反差与“九月好运”祝福感的 1080×1920 视频号封面。

**Architecture:** 先从 8.80—10.00 秒等距抽帧形成候选联系表，选定双人姿态、面容与天宫纵深最佳的一帧。随后由独立 Swift/AppKit 渲染器在原始帧上确定性绘制三层文字，Shell 构建脚本负责取帧与调用渲染器，验收脚本检查图像规格、取帧保真、文字区域和手机缩略图可读性。

**Tech Stack:** zsh、Swift、AppKit、CoreText、FFmpeg、ffprobe、ImageMagick（如已安装）、SHA-256。

## Global Constraints

- 画面只来自 `exports/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voiced-v01.mp4`，不使用字幕版取帧。
- 不调用图片生成模型，不重绘人物、猫耳、尾巴、服装、飘带、鞋履或天宫。
- 正式输出固定为 1080×1920、非透明 PNG。
- 文字只允许 `天宫双姝`、`九月好运`、`一舞一愿`。
- 主标题和副标题不得遮挡面部、猫耳、尾巴、手部、腿部、髋部、鞋履与天宫中央透视线。
- 原片 AI 生成标识必须保留。
- 输出另存为 `exports/tiangong-hot-dance-jiuyue-haoyun-cover-v01.png`，不覆盖其他封面。
- 只提交本次封面相关文件，不暂存工作区其他修改。

---

### Task 1: 建立候选取帧与失败门禁

**Files:**
- Create: `tests/test_tiangong_hot_dance_jiuyue_haoyun_cover.sh`
- Create: `/tmp/zhixia-jiuyue-cover-candidates/contact-sheet.png`

**Interfaces:**
- Consumes: 无字幕有声成片。
- Produces: 8.80、9.00、9.20、9.40、9.60、9.80、10.00 秒七帧联系表与封面构建失败门禁。

- [ ] **Step 1: 写入失败测试**

测试必须验证：构建脚本和渲染器存在；构建完成后输出为单流 PNG、1080×1920、非透明、可完整解码；封面下半部与选定原帧 SSIM 不低于 0.98；输出文件与原始帧不同；缩至 270×480 后仍可解码。

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd /Users/huan.yu/dev/tools-workspace/zhixia-feihualing
zsh tests/test_tiangong_hot_dance_jiuyue_haoyun_cover.sh
```

Expected: `FAIL: missing executable 九月好运封面 builder`。

- [ ] **Step 3: 生成七帧候选联系表**

```bash
mkdir -p /tmp/zhixia-jiuyue-cover-candidates
for second in 8.80 9.00 9.20 9.40 9.60 9.80 10.00; do
  ffmpeg -y -v error -ss "$second" \
    -i exports/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voiced-v01.mp4 \
    -frames:v 1 -vf scale=270:480 "/tmp/zhixia-jiuyue-cover-candidates/${second}.png"
done
ffmpeg -y -v error \
  -pattern_type glob -i '/tmp/zhixia-jiuyue-cover-candidates/*.png' \
  -vf tile=7x1 -frames:v 1 /tmp/zhixia-jiuyue-cover-candidates/contact-sheet.png
```

Expected: 一张 1890×480 联系表，七帧均可辨识双人姿态。

- [ ] **Step 4: 依据画面而非时间偏好选帧**

按以下顺序评分：两人面容清楚；阿砚猫耳与尾巴完整；双人腿部与鞋履完整；人物不糊；天宫纵深强；上方或侧上方存在标题留白。把最终秒数作为构建脚本常量 `cover_time`。

### Task 2: 确定性绘制封面文字

**Files:**
- Create: `scripts/render_tiangong_hot_dance_jiuyue_haoyun_cover.swift`
- Create: `scripts/build_tiangong_hot_dance_jiuyue_haoyun_cover.sh`
- Modify: `tests/test_tiangong_hot_dance_jiuyue_haoyun_cover.sh`

**Interfaces:**
- Consumes: Task 1 选定的 1080×1920 原始帧。
- Produces: `exports/tiangong-hot-dance-jiuyue-haoyun-cover-v01.png`。

- [ ] **Step 1: 实现最小构建脚本**

脚本校验输入后，以选定 `cover_time` 精确截取 1080×1920 RGB PNG 到临时目录，再调用 Swift 渲染器。临时目录使用 `mktemp -d`，退出时自动清理。

- [ ] **Step 2: 实现三层文字渲染**

Swift 渲染器读取原帧并按 1080×1920 原尺寸绘制：

- `天宫双姝`：暖象牙白行楷粗体，主标题，字距舒展，放在人物上半身之外的天宫留白区。
- `九月好运`：淡金行楷，字号为主标题约 50%，紧邻主标题。
- `一舞一愿`：小号淡金字，位于左下角安全区。
- 三层文字只加深色柔和阴影，不加底框、描边、贴纸与强光晕。

渲染器必须在载入失败、尺寸错误或字体不可用时以非零状态退出，不允许生成空白图。

- [ ] **Step 3: 运行测试确认转绿**

```bash
cd /Users/huan.yu/dev/tools-workspace/zhixia-feihualing
zsh tests/test_tiangong_hot_dance_jiuyue_haoyun_cover.sh
```

Expected: `PASS: 九月好运天宫双姝封面已就绪`。

- [ ] **Step 4: 生成手机缩略图**

```bash
ffmpeg -y -v error \
  -i exports/tiangong-hot-dance-jiuyue-haoyun-cover-v01.png \
  -vf scale=270:480 -frames:v 1 /tmp/zhixia-jiuyue-cover-mobile-preview.png
```

Expected: 主标题第一眼可辨，副标题第二眼可读，人物面部和身份特征仍清楚。

### Task 3: 视觉终检与资产登记

**Files:**
- Modify: `assets/inventory.csv`

**Interfaces:**
- Consumes: Task 2 正式封面与手机缩略图。
- Produces: 可发布封面及可追溯资产记录。

- [ ] **Step 1: 检查全尺寸封面**

确认两人无新增变形，三层文字无错字，文字不遮挡面部、猫耳、尾巴、手、腿、髋和鞋履，原片 AI 标识仍在。

- [ ] **Step 2: 检查手机缩略图**

在 270×480 图上确认 `天宫双姝` 和 `九月好运` 可读，标题没有与人物头饰或天宫高光混在一起。

- [ ] **Step 3: 登记资产**

向 `assets/inventory.csv` 追加 `tiangong-hot-dance-jiuyue-haoyun-cover-v01`，记录选帧秒数、1080×1920、FFmpeg 精确取帧、AppKit 本地排版、未重绘人物、AI 标识保留和 SHA-256。该清单已有其他改动时只追加，不整体暂存。

- [ ] **Step 4: 运行最终验收**

```bash
cd /Users/huan.yu/dev/tools-workspace/zhixia-feihualing
zsh tests/test_tiangong_hot_dance_jiuyue_haoyun_cover.sh
git diff --check -- \
  zhixia-feihualing/scripts/build_tiangong_hot_dance_jiuyue_haoyun_cover.sh \
  zhixia-feihualing/scripts/render_tiangong_hot_dance_jiuyue_haoyun_cover.swift \
  zhixia-feihualing/tests/test_tiangong_hot_dance_jiuyue_haoyun_cover.sh
```

Expected: 测试 exit 0，格式检查无输出。

- [ ] **Step 5: 提交本次封面文件**

```bash
git add \
  zhixia-feihualing/docs/superpowers/plans/2026-09-02-jiuyue-haoyun-tiangong-shuangshu-cover.md \
  zhixia-feihualing/scripts/build_tiangong_hot_dance_jiuyue_haoyun_cover.sh \
  zhixia-feihualing/scripts/render_tiangong_hot_dance_jiuyue_haoyun_cover.swift \
  zhixia-feihualing/tests/test_tiangong_hot_dance_jiuyue_haoyun_cover.sh
git diff --cached --check
git commit -m '制作九月好运天宫双姝封面'
```
