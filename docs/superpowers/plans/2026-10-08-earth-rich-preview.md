# 地球历史丰富画面样片 Implementation Plan

> For agentic workers: 在当前会话逐项执行；按 huashu-art-motion 要求派未参与制作的 agent 独立审样片。

**Goal:** 制作15秒无声动态样片，检验满屏场景、丰富素材与明显运动；用户确认样片后才扩展完整一分钟。

**Architecture:** 新目录 `artifacts/world-in-miniature/ep01-earth-day/video-v02/`。ImageGen 生成三组背景及分层环境素材，Canvas 合成；前后景采用不同视差系数，角色整身图固定，仅嘴部替换。时间数据与字幕由 `timeline.cjs` 同源提供。

**Tech Stack:** 内置 ImageGen、Canvas、Playwright、FFmpeg、Node测试及huashu QA。

## Global Constraints

- 用户已确认 `2026-10-08-earth-history-rich-visual-revision.md`。
- 保留三角色、完整原文、生命证据口径及最后六秒特指智人。
- 海景不添加鱼、珊瑚、海草等与35亿年前不符的生物；艺术性微生物放大明确为示意。
- 三角色身体、头和尾固定，不新增人物动作；字幕独立安全区。
- 本次仅制作15秒样片，不调用音频服务，不覆盖旧版本，不提交或发布。

### Task 1: 生成并验收美术素材

Files: `video-v02/assets/`、`assets/prompts.json`、`assets/manifest.json`。

- [x] 内置工具生成海景、森林、夜空营地背景，以及真实透明的微生物/岩石、恐龙/植被图集。
- [x] 直接看每张图，验证构图、时代生物、细节、无文字、水印和人体；用只读像素统计检查透明性与源框。
- [x] 原样复制工具输出到项目，保留提示词、工具、来源路径与SHA；素材切片在Canvas内进行，不改写原图。

### Task 2: 时间和动效

Files: `engine/timeline.test.cjs`、`engine/timeline.cjs`、`engine/scene.js`、`engine/clip.html`。
Interfaces: `T.state(t)` 返回镜头场景与相机缩放/位移，`T.cue(t)` 返回完整原文分句，`window.renderFrame(t)`确定性绘帧。

- [x] 先写测试：15秒字幕连续、原文完整；场景内部相机位移明显；时标与字幕节点一致；镜头跳读确定性。
- [x] 运行测试观察缺失功能失败，随后实现数据和动画并重跑。
- [x] 海景推进穿过微生物群；森林横移穿过前景并有整身恐龙帧活动；午夜镜头推进至最后一分钟刻度，54—60秒高亮，营地火焰和星空持续运动。
- [x] 角色只在讲解边缘和必要提问时出现，三者在午夜段同框；不把全部世界装进固定圆框。

### Task 3: 渲染与样片验证

Files: `qa/`、`exports/earth-rich-motion-preview-15s-v01.mp4`、`README.md`。

- [x] 抽取0.5、3、5.5、7.8、11、14秒关键帧，检查素材层、字幕与角色。
- [x] 渲染1080×1920、30fps、450帧、15秒无声视频。
- [x] 完成时间测试、全片QA、嘴型身体隔离验证、ffprobe与FFmpeg完整解码。
- [x] 独立agent仅看实际样片检查动态丰富度、视差、素材拼接、比例与字幕；修正阻断项。
- [x] 登记资产和提示词；交付可播放样片，等待用户对动态方向的评价后扩展整片。

自检：每张素材用于可见动作与层次；科学口径和三人物限制完整；无新增配音、发布或旧版覆盖行为。
