# 《飞袂绿腰》已接受原片轻后期修整 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留用户确认的《飞袂绿腰》15 秒原片，生成一份带无文字开场方向光痕、三次同强度视听脉冲、不伪造动作且不压低原声的高清轻修母版，并归档本次成功项与已接受偏差。

**Architecture:** 原始 Seedance 文件先按哈希原样归档；独立 FFmpeg 脚本负责等时长放大、轻微影调整理、开场方向光痕、三次等强曝光辉光脉冲，以及本地程序化画鼓/破风/金石重音混合，不做动作补帧或生成式修复；Shell 验收脚本验证编码、尺寸、时长、音轨、三个脉冲时间点与首尾画面；本集 `qa-notes.md` 和项目记忆记录“保留、轻修、偏差不继承为新默认”。

**Tech Stack:** zsh、FFmpeg/ffprobe、jq、shasum、项目 Markdown/CSV 资产登记。

## Global Constraints

- 保持原始 15.093 秒时长、9:16 竖屏、单一连续空间和原始动作顺序。
- 不使用生成式局部重绘，不补造剪式跳跃、落地或深弓动作。
- 不反放、不复制动作段，不加入闪白、速度残影、镜头震动或仙侠粒子。
- 不修改脸、发髻、手指、手掌、服装或飘带结构。
- 背景音乐保持原音量，不做响度归一化、自动闪避或整体压低。
- 末段不再进行数字推近；完整保留输入画面可见范围，避免新增脚部裁切。
- 不插入独立片头，不添加文字或黑场；特效直接覆盖在原舞蹈连续画面上。
- 三次视觉与声音脉冲中心固定为 0.420、5.450、11.550 秒，主观强度相同。
- 仅 0.120—1.050 秒加入一条左下至上方的旧金方向光痕；不做飘带追踪、人物抠像或复杂遮挡。
- 本片固定为“保留、轻修、偏差不继承为新默认”。
- 只提交本计划涉及的 `zhixia-feihualing` 文件，不带入工作区其他既有修改。

---

### Task 1: 原片归档与输入验收

**Files:**
- Create: `zhixia-feihualing/episodes/feimei-lvyao-15s/assets/video/content-seedance-v01.mp4`
- Create: `zhixia-feihualing/tests/test_feimei_lvyao_source.sh`

**Interfaces:**
- Consumes: `/Users/huan.yu/Downloads/a9b01453-b5da-4eaf-b048-e0e10903914a.mp4`
- Produces: 项目内只读事实源 `episodes/feimei-lvyao-15s/assets/video/content-seedance-v01.mp4`，供 Task 2 构建脚本读取。

- [ ] **Step 1: 写入失败的原片验收测试**

创建 `tests/test_feimei_lvyao_source.sh`，检查归档文件存在，并使用 `ffprobe` 与 `jq` 断言：H.264、496×864、24 fps、时长 15.05—15.15 秒、AAC、44.1 kHz、双声道。

- [ ] **Step 2: 运行测试并确认先失败**

Run: `zsh zhixia-feihualing/tests/test_feimei_lvyao_source.sh`

Expected: FAIL，提示 `content-seedance-v01.mp4` 不存在。

- [ ] **Step 3: 原样归档并核对哈希**

创建目标目录，将下载文件复制为 `content-seedance-v01.mp4`；分别运行：

```bash
shasum -a 256 /Users/huan.yu/Downloads/a9b01453-b5da-4eaf-b048-e0e10903914a.mp4
shasum -a 256 zhixia-feihualing/episodes/feimei-lvyao-15s/assets/video/content-seedance-v01.mp4
```

Expected: 两个 SHA-256 完全相同。

- [ ] **Step 4: 运行原片验收测试**

Run: `zsh zhixia-feihualing/tests/test_feimei_lvyao_source.sh`

Expected: PASS，输出原片规格验收通过。

- [ ] **Step 5: 提交测试文件**

原始视频按项目忽略规则留在本地，不加入 Git；仅提交测试脚本。

```bash
git add zhixia-feihualing/tests/test_feimei_lvyao_source.sh
git commit -m "验收飞袂绿腰原片规格"
```

### Task 2: 无文字特效轻修母版构建与规格测试

**Files:**
- Create: `zhixia-feihualing/scripts/build_feimei_lvyao_repaired.sh`
- Create: `zhixia-feihualing/tests/test_feimei_lvyao_repaired.sh`
- Create: `zhixia-feihualing/exports/feimei-lvyao-15s-repaired-v01.mp4`

**Interfaces:**
- Consumes: Task 1 的 `content-seedance-v01.mp4`。
- Produces: 1080×1920、24 fps、H.264/AAC 的 `exports/feimei-lvyao-15s-repaired-v01.mp4`，包含开场方向光痕与三次等强视听脉冲，供后续朗诵和字幕流程直接使用。

- [ ] **Step 1: 写入失败的轻修成片测试**

创建 `tests/test_feimei_lvyao_repaired.sh`，先检查构建脚本可执行并运行它，再断言：

```text
video codec = h264
width × height = 1080 × 1920
frame rate = 24/1
duration = 15.05—15.15 seconds
audio codec = aac
sample rate = 44100 Hz
channels = 2
```

测试另外检查构建脚本包含 `0.420`、`5.450`、`11.550` 三个脉冲中心以及 `0.120`、`1.050` 光痕边界；使用 `ffmpeg -ss 0 -frames:v 1` 与 `ffmpeg -ss 14.5 -frames:v 1` 输出首尾验收帧到临时目录，并断言两个 PNG 非空。

- [ ] **Step 2: 运行测试并确认先失败**

Run: `zsh zhixia-feihualing/tests/test_feimei_lvyao_repaired.sh`

Expected: FAIL，提示缺少可执行构建脚本。

- [ ] **Step 3: 实现最小轻修构建脚本**

创建 `scripts/build_feimei_lvyao_repaired.sh`，基础画面使用以下滤镜链：

```text
scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,
pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x172525,
eq=contrast=1.025:saturation=1.025:brightness=0.002,
unsharp=5:5:0.35:3:3:0.0,
fps=24,
format=yuv420p
```

基础画面分为原始层和高光扩散层。高光层使用 `eq=brightness=0.10:saturation=1.08,gblur=sigma=12`；两层通过 `blend` 在 0.420、5.450、11.550 秒形成三个半宽 0.180 秒、权重峰值 0.22 的等强三角脉冲。开场另创建透明旧金细条层，经过模糊与斜向运动，在 0.120—1.050 秒从左下向上方掠过，最高不透明度不超过 0.45。

程序化音效在构建时由 FFmpeg `lavfi` 生成：低频衰减正弦组成画鼓主体，带通噪声组成短促破风，三个衰减高频正弦组成克制金石尾音；三者预混后分别延迟到 0.420、5.450、11.550 秒，三组使用完全相同的增益。原片音轨直接以 0 dB 进入 `[bed]`，不得出现作用于 `[bed]` 的 `volume`、`loudnorm` 或 `sidechaincompress`；只在 `[bed][sfx]` 最终总线使用 `amix=normalize=0` 和 `alimiter` 防止削波。

输出参数固定为 `libx264 -preset slow -crf 17 -pix_fmt yuv420p -movflags +faststart` 与 `aac -b:a 192k -ar 44100 -ac 2`；使用 `-t 15.093` 保持原时长。脚本只接受固定项目输入与输出路径，缺少输入时明确退出。

- [ ] **Step 4: 运行轻修测试并检查首尾帧**

Run: `chmod +x zhixia-feihualing/scripts/build_feimei_lvyao_repaired.sh zhixia-feihualing/tests/test_feimei_lvyao_repaired.sh && zsh zhixia-feihualing/tests/test_feimei_lvyao_repaired.sh`

Expected: PASS；首帧仍为完整低位侧折，开场没有文字或黑场，14.5 秒帧不新增裁切或人物跳变。

- [ ] **Step 5: 生成三高潮接触表人工验收**

从轻修母版提取 0.0、0.42、0.8、1.05、1.8、4.8、5.45、7.0、10.0、11.55、12.4、13.2、14.5 秒画面，生成接触表。确认光痕不遮脸、不变成新增飘带，三次脉冲亮度克制且主观同强，轻修没有新增脸、手、服装和飘带错误；第二、第三段只作为现有动作的节奏强调，不宣称补齐原设计动作。

- [ ] **Step 6: 提交构建与测试脚本**

输出 MP4 按项目规则保留本地，不加入 Git。

```bash
git add zhixia-feihualing/scripts/build_feimei_lvyao_repaired.sh zhixia-feihualing/tests/test_feimei_lvyao_repaired.sh
git commit -m "制作飞袂绿腰轻修母版"
```

### Task 3: 本集复盘、资产登记与长期约束

**Files:**
- Create: `zhixia-feihualing/episodes/feimei-lvyao-15s/qa-notes.md`
- Modify: `zhixia-feihualing/episodes/feimei-lvyao-15s/README.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Modify: `.cursor/rules/memory-workspace.mdc`

**Interfaces:**
- Consumes: Task 1 的原片哈希、Task 2 的输出规格和逐帧验收结果。
- Produces: 本集单一事实源、资产索引和后续舞蹈生成可检索的硬规则。

- [ ] **Step 1: 写入本集 QA 复盘**

创建 `qa-notes.md`，明确列出四组内容：结论、原片信息、成功项、已接受偏差与后续硬规则。必须包含：飘带手持感、第二高潮双 S 不清楚、第三高潮缺少完整腾跃落地动作链、重复单臂上举轮廓、三种环境反馈未区分，以及“本片不返工、不把偏差写回新默认”。

- [ ] **Step 2: 更新本集状态与资产台账**

把 `README.md` 状态更新为原片已接受并完成轻修母版；向 `assets/inventory.csv` 追加两行：

```text
feimei-lvyao-15s-seedance-v01,video,飞袂绿腰,seedance-source,episodes/feimei-lvyao-15s/assets/video/content-seedance-v01.mp4,approved,user-provided Seedance output,owner-provided AI-assisted asset,15.093秒；496×864；24fps；SHA-256 264ad57a744c0ef748d776ed9ab35d14dad8687ed14316f106f9b9504320c105；用户确认保留
feimei-lvyao-15s-repaired-v01,video,飞袂绿腰,repaired-master,exports/feimei-lvyao-15s-repaired-v01.mp4,available,local FFmpeg light repair,derived from approved project video,15.093秒；1080×1920；24fps；无文字开场方向光痕；三次等强视听脉冲；原声0dB无闪避；无生成式补帧
```

- [ ] **Step 3: 更新长期项目记忆**

在 `.cursor/rules/memory-workspace.mdc` 追加 `2026-08-31-feimei-lvyao-video-review` 小节，只写经本次原片与轻修母版验证的成功项、偏差和后续硬规则，并指向 `episodes/feimei-lvyao-15s/qa-notes.md` 作为真源。

- [ ] **Step 4: 运行文档和资产一致性检查**

Run:

```bash
rg -n "保留、轻修、偏差不继承为新默认|飘带|第三高潮|原声0dB" \
  zhixia-feihualing/episodes/feimei-lvyao-15s/qa-notes.md \
  zhixia-feihualing/episodes/feimei-lvyao-15s/README.md \
  zhixia-feihualing/assets/inventory.csv \
  .cursor/rules/memory-workspace.mdc
git diff --check -- \
  zhixia-feihualing/episodes/feimei-lvyao-15s/qa-notes.md \
  zhixia-feihualing/episodes/feimei-lvyao-15s/README.md \
  zhixia-feihualing/assets/inventory.csv \
  .cursor/rules/memory-workspace.mdc
```

Expected: 所有关键规则均可检索，`git diff --check` 无输出。

- [ ] **Step 5: 提交本集复盘与登记**

```bash
git add zhixia-feihualing/episodes/feimei-lvyao-15s/qa-notes.md \
  zhixia-feihualing/episodes/feimei-lvyao-15s/README.md \
  zhixia-feihualing/assets/inventory.csv \
  .cursor/rules/memory-workspace.mdc
git commit -m "归档飞袂绿腰原片复盘"
```

### Task 4: 最终综合验收

**Files:**
- Verify: `zhixia-feihualing/episodes/feimei-lvyao-15s/assets/video/content-seedance-v01.mp4`
- Verify: `zhixia-feihualing/exports/feimei-lvyao-15s-repaired-v01.mp4`
- Verify: `zhixia-feihualing/episodes/feimei-lvyao-15s/qa-notes.md`

**Interfaces:**
- Consumes: Tasks 1—3 的全部产物。
- Produces: 可交付的轻修母版及下一阶段朗诵、字幕制作入口。

- [ ] **Step 1: 运行两项自动验收**

Run:

```bash
zsh zhixia-feihualing/tests/test_feimei_lvyao_source.sh
zsh zhixia-feihualing/tests/test_feimei_lvyao_repaired.sh
```

Expected: 两项均 PASS。

- [ ] **Step 2: 对比原片与轻修母版音频响度**

分别运行 `ffmpeg -filter:a volumedetect -f null -`。轻修版包含额外音效，因此总线峰值允许升高；另外对构建脚本做静态检查，确认 `[bed]` 路径不存在 `volume`、`loudnorm` 或 `sidechaincompress`。

Expected: 轻修版没有比原片更低的 `mean_volume`，且脚本中的原声主床保持 0 dB；最终峰值不超过 −1.0 dBFS。

- [ ] **Step 3: 核对工作区范围**

Run: `git status --short`

Expected: 本任务相关文档与脚本均已提交；工作区原有其他修改仍被保留且未进入本任务提交。

- [ ] **Step 4: 交付路径**

向用户提供 `exports/feimei-lvyao-15s-repaired-v01.mp4` 的可点击路径，并说明该文件是后续四句诗朗诵和竖排字幕的唯一视频输入。
