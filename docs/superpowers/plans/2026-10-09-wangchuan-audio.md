# 送王船配音 Implementation Plan

**Goal:** 交付有三角色配音、同步嘴型与完整字幕的2:3王船视频。

**Architecture:** video-v02复用无声v03资产与Canvas引擎；现有豆包TTS逐句缓存，音频时序映射视觉时间，FFmpeg输出独立最终文件。

**Tech Stack:** 豆包TTS、Python、Canvas、Playwright、FFmpeg、Node。

- [x] 缓存十句原声及逐字时序，核对全文与三音色。
- [x] 测试与实现自然节奏适配、精确PCM拼接、字幕时间与单角色嘴部驱动。
- [x] 按实际配音调整画面关键词和字幕，完整渲染、合成。
- [x] 全片解码、响度与音轨核对、两位独立审片；登记最终视频并交付。
