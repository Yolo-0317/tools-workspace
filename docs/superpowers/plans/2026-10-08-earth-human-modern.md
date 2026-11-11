# 智人与现代社会样片 Implementation Plan

> For agentic workers: 在当前会话执行；huashu要求制作后由未参与制作agent独立审实际MP4。

**Goal:** 更新15秒竖版无声样片末段，让早期智人、聚落与现代城市可见。

**Architecture:** 旧样片保留，新工作目录video-v03，最终视频输出v03。复用海洋/森林/角色和相机。新增营地人物背景、田地聚落、现代城市与透明交通素材；Canvas统一景深与地平线，用短转场展示文明演变。

**Tech Stack:** ImageGen、Canvas、Node、Playwright、FFmpeg。

## Global Constraints

9:16/1080×1920，15秒，无音轨；台词不变，三讲解角色只嘴型。10—12秒智人营地，12—13.3秒聚落，13.3—15秒现代。艺术展开镜头不充当科学等比例年表；六秒数据单独显示。保存所有生成来源/提示词，保留旧版本，不提交、不发布。

### Task 1: 美术

- [x] 生成并直观看新增三组背景及交通透明素材，检查历史人物可辨、文明元素可辨、无水印、源框与透明留白。
- [x] 原样复制到assets；登记工具来源、完整提示词、尺寸与SHA。

### Task 2: 场景

Files: engine/timeline.cjs、timeline.test.cjs、scene.js。
Interface: T.civilization(t) 返回camp/village/modern，只是播放阶段；T.state保留真实智人时标。

- [x] 测试civilization时段、真实智人54.2907秒数值不变；现代展开不配科学比例尺，先运行失败。
- [x] 实现数据分段及同方向转场，营地显示真实人群、聚落桥梁、现代交通/窗灯与手机；嘴型角色身体固定。
- [x] 运行测试，渲染末段关键帧并检查字幕/比例尺不遮住主事件。

### Task 3: 验证和交付

- [x] 渲染exports/earth-rich-motion-preview-15s-v03.mp4。
- [x] 119帧QA、嘴部隔离、ffprobe、全片解码；独立agent只审实际MP4。
- [x] 修正阻断项，登记新增资产，更新README与skill经验，交付15秒无声样片待用户评价。
