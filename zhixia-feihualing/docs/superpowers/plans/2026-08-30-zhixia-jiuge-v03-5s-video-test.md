# 栀夏九歌祭舞 v03 五秒视频测试 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用九歌 v03 唯一母板生成一条《东皇太一》5 秒图生视频，并完成可追溯的逐项验收记录。

**Architecture:** 浏览器生成环节只上传一张母板、使用一份冻结提示词并生成一个候选，控制成本和变量。生成结果下载到独立测试目录，再用媒体信息、代表帧和人工视觉检查形成 QA 结论，最后同步资产台账与项目状态。

**Tech Stack:** Seedance 网页端、浏览器控制、FFmpeg/ffprobe、Markdown、CSV。

## Global Constraints

- 唯一上传图为 `assets/characters/栀夏九歌祭舞-v03-整合式高写实视频母板-Seedance上传版.jpg`。
- 只生成 1 条、5 秒、9:16 图生视频，不扩展到 15 秒。
- 使用已确认规格中的完整提示词，不临场增加人物、道具、字幕、人声或复杂特效。
- 生成提交前核对时长、画幅、输入图与数量，避免重复扣费。
- 下载原始视频后才做验收，不用网页缩略图替代原片检查。
- 任一面部身份、服装结构或袖缘数量失败，均不得把九歌状态写为视频已验证。
- 保留工作区其他未提交改动，不覆盖 `assets/inventory.csv` 中已有内容。

---

### Task 1: 执行唯一一次五秒生成

**Files:**
- Read: `zhixia-feihualing/docs/superpowers/specs/2026-08-30-zhixia-jiuge-v03-5s-video-test-design.md`
- Read: `zhixia-feihualing/assets/characters/栀夏九歌祭舞-v03-整合式高写实视频母板-Seedance上传版.jpg`
- Produce externally: Seedance 5 秒生成任务一条

**Interfaces:**
- Consumes: 规格中的“Seedance 投喂提示词”和“生成设置”。
- Produces: 一个可下载的 5 秒 9:16 原始视频候选。

- [ ] **Step 1: 打开现有登录态中的 Seedance 图生视频页面**

使用浏览器现有登录态进入图生视频创作页；若页面未登录、无可用额度或要求额外付费确认，停止提交并报告实际阻塞，不改用其他平台。

- [ ] **Step 2: 上传并核对唯一母板**

上传 `zhixia-feihualing/assets/characters/栀夏九歌祭舞-v03-整合式高写实视频母板-Seedance上传版.jpg`。确认页面只存在这一张输入图，没有历史参考图或尾帧图残留。

- [ ] **Step 3: 填入冻结提示词与设置**

完整复制规格文件“Seedance 投喂提示词”；设置图生视频、5 秒、9:16、单个候选。若平台存在自动配音开关则关闭；其余质量设置保持平台推荐值，不启用模板、运镜预设或风格预设。

- [ ] **Step 4: 提交前复核并只生成一次**

逐项确认输入图文件名、5 秒、9:16、单个候选与提示词开头“上传图片中的栀夏是原创虚构数字角色”。确认无误后提交一次；等待任务完成，不刷新重提、不创建第二个候选。

### Task 2: 下载并验证原始视频

**Files:**
- Create: `zhixia-feihualing/assets/generated-video/jiuge-v03-tests/jiuge-donghuang-taiyi-v03-5s-test-01.mp4`
- Create temporary: `/private/tmp/jiuge-v03-5s-test-01-frames/`

**Interfaces:**
- Consumes: Task 1 完成的唯一视频候选。
- Produces: 固定路径的原始 MP4、媒体信息与代表帧。

- [ ] **Step 1: 下载原始候选并固定命名**

从生成结果页下载原始 MP4，保存为 `assets/generated-video/jiuge-v03-tests/jiuge-donghuang-taiyi-v03-5s-test-01.mp4`；不转码、不裁切、不加字幕。

- [ ] **Step 2: 校验媒体信息**

运行：

```bash
ffprobe -v error -show_entries format=duration -show_entries stream=codec_name,width,height,r_frame_rate -of json zhixia-feihualing/assets/generated-video/jiuge-v03-tests/jiuge-donghuang-taiyi-v03-5s-test-01.mp4
```

预期：视频可解码，纵向分辨率满足 `height > width`，时长接近 5 秒；平台编码与帧率如实记录，不把非 1080×1920 视为身份测试失败。

- [ ] **Step 3: 抽取五张代表帧**

创建临时目录并运行：

```bash
mkdir -p /private/tmp/jiuge-v03-5s-test-01-frames
ffmpeg -y -i zhixia-feihualing/assets/generated-video/jiuge-v03-tests/jiuge-donghuang-taiyi-v03-5s-test-01.mp4 -vf "fps=1" /private/tmp/jiuge-v03-5s-test-01-frames/frame-%02d.png
```

预期：获得约五张可视代表帧，用于比较脸、服装、袖缘和材质随时间的稳定性。

### Task 3: 完成 QA 与资产登记

**Files:**
- Create: `zhixia-feihualing/operations/jiuge-v03-5s-test-01-qa.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Modify only if passed: `zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md`

**Interfaces:**
- Consumes: 原始 MP4、ffprobe 信息、五张代表帧和已确认验收标准。
- Produces: `通过`、`提示词可修复` 或 `母板需返工` 三选一结论及可追溯资产记录。

- [ ] **Step 1: 逐项视觉验收**

按面部身份、服装结构、严格两个袖缘尾端、0.300 秒内动作启动、肢体完整性、自然摄影式写实六项检查。每项只能记录 `通过`、`轻微偏差` 或 `失败`，并写明对应时间点。

- [ ] **Step 2: 写入 QA 结论**

`operations/jiuge-v03-5s-test-01-qa.md` 固定包含：输入母板、冻结提示词来源、生成设置、媒体信息、六项检查表、总判定、是否允许进入下一条测试。前三项任一失败时总判定不得为 `通过`。

- [ ] **Step 3: 追加资产台账**

在 `assets/inventory.csv` 末尾追加一行，固定 `asset_id=jiuge-donghuang-taiyi-v03-5s-test-01`、`type=video`、`character_or_episode=九歌祭舞`、`shot=东皇太一5秒母板测试`、`path_or_url=assets/generated-video/jiuge-v03-tests/jiuge-donghuang-taiyi-v03-5s-test-01.mp4`；`status` 与 `notes` 使用 QA 实际结论，不覆盖原有行。

- [ ] **Step 4: 按实际结果同步路线图**

只有总判定为 `通过` 时，才把路线图改为“九歌 v03 已通过首轮 5 秒基础稳定性测试，但 15 秒与高动态动作尚未验证”。若结论为另外两类，只记录相应问题和下一步，不宣称视频稳定性已验证。

- [ ] **Step 5: 完整复核**

运行：

```bash
ffprobe -v error zhixia-feihualing/assets/generated-video/jiuge-v03-tests/jiuge-donghuang-taiyi-v03-5s-test-01.mp4
git diff --check -- zhixia-feihualing/assets/inventory.csv zhixia-feihualing/operations/jiuge-v03-5s-test-01-qa.md zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md
```

预期：原片可解码，文本与 CSV 无空白错误，QA 结论和路线图状态一致。
