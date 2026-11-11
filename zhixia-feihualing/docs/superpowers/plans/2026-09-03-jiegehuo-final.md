# 《借个火》字幕与封面制作计划

**Goal:** 交付保留原声的对白字幕版视频，以及视频原帧排版封面。

**Architecture:** 本地识别辅助定位三句对白，按实际发声拆分包袱；Swift/AppKit 渲染字幕透明层与封面文字，FFmpeg 合成视频，音轨直接复制。

**Tech Stack:** whisper.cpp、Swift/AppKit、FFmpeg、Python标准库验证。

## 约束

- 来源：Downloads/578f3c66-f1c6-4735-92ae-06acba6dfecc.mp4；不改画面剧情、音轨与现代衣物。
- 字幕不提前泄露“烘衣服”，对白结束后清掉字幕。
- 封面原帧排版，不重绘；标题“仙女／借个火”，系列“天宫日常”，保留AI标识。
- 不发起付费生成或对外上传媒体；不覆盖既有成片。

## 执行与验证

- [x] 本地识别音频时间戳，生成 `episodes/tiangong-daily-jiegehuo-10s/subtitles.json`。
- [x] 先运行 `tests/test_jiegehuo_delivery.py`，确认交付文件缺失时失败。
- [x] 新建 `scripts/render_jiegehuo_artwork.swift`：输出720×1280字幕层和1080×1920原帧封面。
- [x] 新建 `scripts/build_jiegehuo_final.py`：依字幕时间叠加透明层，直接复制原AAC音轨；输出 `exports/tiangong-daily-jiegehuo-subtitled-v01.mp4` 与 `exports/tiangong-daily-jiegehuo-cover-v01.png`。
- [x] 验证视频完整解码、720×1280、时长与源片一致、音频包哈希完全相同；封面1080×1920、RGB不透明。
- [x] 抽帧检查字幕与封面手机缩略图，更新复盘与资产登记，提供交付链接。

补充执行决定：复用工作区已有的本地识别模型；停止冗余下载。封面字体按用户中途要求改为既有行楷样式。

用户已批准设计及制作；本次在当前任务内执行，不另开任务。
