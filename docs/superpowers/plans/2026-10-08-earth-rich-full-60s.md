# 地球历史丰富画面完整版 Implementation Plan

> For agentic workers: 当前会话执行；遵守huashu独立审实际成片要求。

**Goal:** 把已验收15秒方向扩展为完整60秒竖版无声视频。

**Architecture:** 新目录video-v04保留所有旧版。复用已确认环境与角色，新增早期地球、岩浆海岸、撞击余波与空间物件。旧批准完整dialogue恢复为60秒时间，内容事件与时标同源；新增丰富场景按它驱动。

**Tech Stack:** ImageGen、Canvas、Playwright、FFmpeg、Node测试。

## Global Constraints

1080×1920/30fps/60秒无音轨。三位讲解角色只嘴型，阿砚小黑提问/栀夏解读；不加非等比例提示。保留智人、聚落、城市和最后80岁不到2毫秒的原文结尾，音频最后。用户已确认丰富画面设计及智人现代样片并要求继续完整制作。

### Task 1 美术
- [x] 生成早期地球、岩浆海岸、撞击余波背景和空间透明物件；检查画面、源框、透明性；保存完整提示词、工具路径与SHA。
### Task 2 时间与全片场景
Files: engine/dialogue.json、timeline.cjs、timeline.test.cjs、scene.js。
Interfaces: T.state(t)返回section/真实秒数/字幕，T.camera(section,t)为镜头，T.civilization(t)仅是文明播放阶段。
- [x] 写测试完整文案连续0—60、事件与字幕同步、科学比例、各主镜头明显运镜、文明不提前出现，先失败再实现。
- [x] 实现开场抓问、地球诞生/海岸下潜、微生物漫长时代、恐龙/撞击/余波、午夜/智人/文明和80年毫秒尺度；字幕独立、角色固定整身仅嘴型。
- [x] 关键帧检查、运行时间测试，修正画面遮挡与素材连接。
### Task 3 交付
- [x] 渲染60秒1800帧无声版；479帧QA、嘴部隔离、ffprobe与全片解码。
- [x] 独立agent实际MP4审完整片，修正阻断项；登记资产、记录限制及skill经验，交付本地可播放成片，下一步才配音。
