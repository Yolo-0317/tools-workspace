# 小黑初到天宫：字幕版交付

日期：2026-09-24。用户确认使用天宫角色卡，要求按原片音轨定位对白并添加字幕。

- 原片：`../../assets/generated-video/xiaohei-tiangong-arrival-10s-original.mp4`，由用户提供，下载目录原件未修改。
- 字幕时间轴：`subtitles.json`。0.54–4.08 秒为栀夏对白，5.96–9.10 秒为小黑对白；按自然停顿拆为四条字幕。
- 制作：`render.py` 复用上一条小黑视频的 AppKit 字幕样式，保留原 AAC 音轨、AIGC 元数据和画面内 AI 标识。
- 720p 过程版：`../../exports/xiaohei-tiangong-arrival-subtitled-720p-v01.mp4`。
- 1080p 交付版：`../../exports/xiaohei-tiangong-arrival-subtitled-1080p-v01.mp4`；由 720×1280 使用 Lanczos 放大至 1080×1920，原始素材为 496×864，放大不增加真实细节。

核对：1080p 成片完整解码；10.08 秒、24 fps、241 帧。四条字幕在 1.5、3.25、6.5、8.25 秒代表帧中清晰可读，未挡住人物面部和小黑眼睛。原片与成片的 AAC 编码流 SHA-256 均为 `a1c8df77b26231c3b0132912205dc48966d466c450a8069ae86b9e67735e878a`。AIGC 元数据保留。成片待用户验收，未发布。

SHA-256：原片 `79a1faa3a6d2fc458700873e897e3f0180192ce42c3e4387e896da2a362884b9`；720p 版 `a6bf839a81628d750faebb4dfa1d1091f84827ede3a4ff4270624da4e7b4a96b`；1080p 版 `ff8f8185df679f005f79713a8148ac37a780e70b02c2876fb3136ee22fd15083`。

## 封面与视频号文案

- 封面：`../../exports/xiaohei-tiangong-arrival-cover-v01.png`，取原片约 7.25 秒无字幕画面，保留小黑、栀夏、空玉碗和画面内 AI 标识；上方排“走失多年的小黑 · AI影像重逢 / 小黑上天宫 / 蟠桃能续碗不？”。1080×1920，已目视检查标题、人物面部和玉碗。SHA-256 `824187d957d3385f177cd50af3e52f342a6758b59c4ce2b75ac0f5c7898f14ee`。
- 视频号文案：`video-account-copy-v01.md`，交代小黑陪伴十二三年后走失、借旧照片与 AI 在影像中重现，并落到本集“续碗”笑点；正文不暗示小黑现实中已找回。未发布。
