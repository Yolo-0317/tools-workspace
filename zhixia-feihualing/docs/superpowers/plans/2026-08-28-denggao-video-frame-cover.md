# Denggao Video Frame Cover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从《登高》无字幕原片截取角色与江景兼顾的一帧，精确叠加两列诗句和作者篇名，输出 1080×1920 PNG 封面。

**Architecture:** FFmpeg 从 `content-seedance-v01.mp4` 截取并放大基础帧；专用 Swift/AppKit 渲染器在同一画布上绘制竖排封面文字。Shell 构建脚本串联两步，验收测试检查尺寸、PNG 格式、基础帧与最终封面均存在，并保证成品可被系统图像工具读取。

**Tech Stack:** Zsh、FFmpeg、Swift/AppKit、CoreText、PNG、Shell 测试。

## Global Constraints

- 不调用图像生成模型，不重绘栀夏、阿砚或环境。
- 从无字幕 Seedance 原片取帧，不把“看江上。”烧录字幕带入封面。
- 在约 2.6 秒范围内选择阿砚仍清楚可见的最佳帧；抽帧比较后固定使用 2.300 秒。
- 输出固定为 1080×1920 PNG。
- 文字固定为 `无边落木萧萧下`、`不尽长江滚滚来`、`杜甫《登高》`。
- 字幕位于左侧安全区，不遮挡栀夏面部、发冠、阿砚和右下角“AI生成”标识。
- 不增加 Logo、营销文案、英文、贴纸、边框或背景底板。

---

### Task 1: 用测试定义封面输出契约

**Files:**
- Create: `zhixia-feihualing/tests/test_denggao_10s_cover.sh`

**Interfaces:**
- Consumes: `exports/denggao-10s-cover-base-v01.png` 与 `exports/denggao-10s-cover-v01.png`。
- Produces: 对基础帧和最终封面的尺寸、格式与可读性的自动验收。

- [ ] **Step 1: 写失败测试**

测试断言基础帧和最终封面均存在，二者均为 1080×1920 PNG，并能被 `sips` 与 FFmpeg 正常读取；最终封面文件哈希必须与基础帧不同，证明字幕层已经合成。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
zsh zhixia-feihualing/tests/test_denggao_10s_cover.sh
```

Expected: 因 `exports/denggao-10s-cover-base-v01.png` 尚未生成而非零退出。

### Task 2: 实现确定性截帧与排版

**Files:**
- Create: `zhixia-feihualing/scripts/render_denggao_10s_cover.swift`
- Create: `zhixia-feihualing/scripts/build_denggao_10s_cover.sh`
- Generate: `zhixia-feihualing/exports/denggao-10s-cover-base-v01.png`
- Generate: `zhixia-feihualing/exports/denggao-10s-cover-v01.png`

**Interfaces:**
- Consumes: `episodes/denggao-10s/assets/video/content-seedance-v01.mp4`。
- Produces: 1080×1920 基础帧和带标准字幕的最终封面。

- [ ] **Step 1: 实现专用封面排版器**

使用 1080×1920 AppKit 位图画布绘制基础帧；主文案采用象牙白行楷、克制深色阴影，第一句位于右列、第二句位于左列；第二句中的 `江` 使用朱红。`杜甫《登高》` 使用较小楷体竖排题签。所有文字保持左侧安全区。

- [ ] **Step 2: 实现构建脚本**

FFmpeg 在 2.300 秒截取一帧并使用 Lanczos 放大为 1080×1920，再调用 Swift 排版器输出最终封面。

- [ ] **Step 3: 构建封面**

Run:

```bash
zsh zhixia-feihualing/scripts/build_denggao_10s_cover.sh
```

Expected: 生成基础帧与最终封面 PNG。

- [ ] **Step 4: 运行自动验收**

Run:

```bash
zsh zhixia-feihualing/tests/test_denggao_10s_cover.sh
```

Expected: 输出 `denggao 10s cover: PASS`。

### Task 3: 视觉抽检与交付

**Files:**
- Inspect: `zhixia-feihualing/exports/denggao-10s-cover-v01.png`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 2 的封面。
- Produces: 通过人工构图与文字检查的项目封面资产。

- [ ] **Step 1: 全尺寸检查**

确认诗句、作者和篇名逐字准确，字幕不压住栀夏面部、发冠与阿砚，右下角“AI生成”标识保留。

- [ ] **Step 2: 缩略图检查**

生成约 270×480 预览，确认缩小时仍能先读到诗句，再识别栀夏、阿砚与长江。

- [ ] **Step 3: 登记与提交**

在资产清单登记 `denggao-10s-cover-v01`，然后只提交本次封面源文件、脚本、测试和输出：

```bash
git add zhixia-feihualing/scripts/render_denggao_10s_cover.swift \
  zhixia-feihualing/scripts/build_denggao_10s_cover.sh \
  zhixia-feihualing/tests/test_denggao_10s_cover.sh \
  zhixia-feihualing/exports/denggao-10s-cover-base-v01.png \
  zhixia-feihualing/exports/denggao-10s-cover-v01.png
git commit -m "完成登高截帧封面"
```
