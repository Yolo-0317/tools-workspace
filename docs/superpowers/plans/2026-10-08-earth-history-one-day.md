# 地球历史一天钟 Implementation Plan

> For agentic workers: 按任务在当前会话逐项实施；成片必须按 huashu-art-motion 独立审片要求交给未参与制作的 agent 检查。

**Goal:** 输出获准文案对应的 1080×1920、30fps、60 秒无声视频，含三角色嘴型、完整字幕和历史钟缩放。

**Architecture:** 独立目录 `artifacts/world-in-miniature/ep01-earth-day/video-v01/`。`timeline.cjs` 处理近似年代换算和字幕时间轴，`world.js` 绘制程序化场景，`scene.js` 合成时钟、镜头、固定全身角色与字幕；复用现有角色渲染器。

**Tech Stack:** Canvas、Playwright、Node 原生测试、FFmpeg，huashu render.py/qa.py。角色素材复用获准 RGBA 嘴型图，不调用音频服务。

## Global Constraints

- 设计稿于 2026-10-08 获用户确认，完整台词不删改。
- 地球基准 45.4 亿年，生命证据不当作精确起源，六秒特指智人，灭绝特指非鸟类恐龙。
- 所有角色身体、头部、肢体保持固定，只有当前说话者的嘴型变化。
- 延续青绿暖金立体展厅；人物素材不覆盖，拉链项目停止。
- 本轮仅交付无声视频，付费配音最后处理。无 Git 提交或自动发布。

### Task 1: 时间与对白

Files: `engine/dialogue.json`, `engine/dialogue.js`, `engine/timeline.cjs`, `engine/timeline.test.cjs`。
Interfaces: `T.ageToSeconds(years)`, `T.state(t)`, `T.cue(t)`, `T.step(t,a,b)`；`T.state(t).seconds` 表示历史钟面时间而非片中时间。

- [x] 先写独立数值预期：300000 年距午夜约 5.7 秒，66000000 年约 23:39；完整对白字幕连续覆盖 0—60，随机跳读历史钟不能倒转。
- [x] 运行 `node --test engine/timeline.test.cjs`，确认缺失行为失败；实现换算、字幕按标点分段和分镜状态，再运行至通过。

### Task 2: 画面与角色

Files: `engine/world.js`, `engine/scene.js`, `engine/clip.html`, `engine/character-motion.cjs`, `engine/character-rig.js`, `engine/spec.json`。
Interfaces: `createWorldPainter(ctx)` 返回 `paint(kind,t,x,y,r)`；`window.renderFrame(t)`、`window.prepare(t)` 与 huashu 渲染协议兼容。

- [x] 将既有角色嘴型素材与渲染器复制到新目录，保留来源及许可证。静止身体行为由既有已验证的嘴型模块保持。
- [x] 绘制深青展厅、暖金钟环、岩浆地球、微生物海景、时代森林、灭绝粒子、智人符号及两级放大窗。每个场景至少包含整体运动和两种环境循环。
- [x] 准备 PNG 关键帧 0、7、17、28、33、38、44、49、56、59 秒；直接检查构图、时期差异、字幕与角色清晰度。
- [x] 关键帧修正后渲染完整无声 MP4，不将静帧连播当成成片。

### Task 3: 验证与交付

Files: `qa/`, `exports/`, `README.md`。

- [x] 跑 Node 时间测试及 huashu `qa.py --project engine --spec engine/spec.json --fps 8 --out qa/skill`，检查确定性、帧差与文字框景；文字误报逐帧核查。
- [x] `ffprobe` 核对 1080×1920、30fps、1800 帧、60 秒及无音轨；FFmpeg 完整解码。
- [x] 独立 agent 仅审最终候选成片，检查时间比例、字幕、构图、角色嘴型、画面连贯性；修复阻塞问题再复验。
- [x] 登记资产来源、成片与 QA 结果，设计状态更新为无声视频已交付；在 skill 写入可泛用的正面经验。

计划自检：范围覆盖已确认文案、钟面比例、嘴型限制与视频先行流程；实现接口统一，无新增付费服务或旧项目改动。

完成记录：无声版v04已渲染；4项Node测试、479帧动画QA、嘴型像素隔离、ffprobe与完整解码通过；独立审片确认时序修正并无剩余阻断项。音频未生成，按约定放在后续最后一步。
