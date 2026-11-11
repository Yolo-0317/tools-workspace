# 拉链完整无声视频实施计划

**Goal:** 按当前完整文案制作1080×1920、30fps的无声MP4，画面完成后再配音。

**Architecture:** 复用用户已确认的青绿暖金博物馆、内部背景和三角色动作图集。新工程保存台词与时间轴，Canvas根据绝对时间绘制机械演示、角色与字幕；每句保留自然阅读时间，生成字幕文件以便后续配音对齐。

**Tech Stack:** Canvas、huashu-art-motion工具库、Playwright Chromium、FFmpeg、Node测试。

## 约束

- 栀夏解读，阿砚与小黑提问；台词使用完整句子，不削减当前正文。
- C→B→C结构，结尾回到展台操作拉链，没有零食袋桥段。
- 本轮不调用TTS、不添加既有音频；生成文件与8秒预览隔离。
- 机械演示用普通金属拉链为例；保留链牙凸起/凹位、错开、Y形导向和反向分离。

## 执行

- [x] `video-v03/engine/timeline.test.cjs`：先验证完整台词、角色分工、字幕连续边界、首尾场景和镜头连续性；首次运行预期缺少模块失败。
- [x] `video-v03/engine/dialogue.json`与`timeline.cjs`：保存已确认台词，按标点切字幕、字符数估时，留出转场和观察窗口；输出`spec.json`、`dialogue.srt`和`storyboard.md`。
- [x] `video-v03/engine/scene.js`：复用角色图集的脚底锚点，重新布局字幕安全区；建立通道剖视、链牙凸凹扣合、反向分离与展台回归镜头。
- [ ] 抽帧与镜头状态测试；检查字幕、角色重叠、机械方向和过渡；修正后导出完整MP4。
- [x] 运行技能QA与ffprobe检查；由独立审片者只看最终成片，按时间码修正阻断问题；交付无声视频及后续音频对齐文件。

## 验证命令

`node --test artifacts/life-principles/ep01-zipper/video-v03/engine/timeline.test.cjs`

`UV_CACHE_DIR=/private/tmp/zipper-uv-cache uv run --with playwright python artifacts/life-principles/ep01-zipper/video-v03/engine/render.py --spec artifacts/life-principles/ep01-zipper/video-v03/engine/spec.json --out artifacts/life-principles/ep01-zipper/video-v03/exports/zipper-full-silent-v01.mp4`

`ffprobe -v error -show_streams -show_format artifacts/life-principles/ep01-zipper/video-v03/exports/zipper-full-silent-v01.mp4`

交付：video-v03/exports/zipper-full-silent-v03.mp4，215秒、6450帧、无音轨。字幕完整性、方向、确定性、框景与完整解码验证已完成；独立审片无本轮交付阻断问题。未生成音频、未进行发布操作。
