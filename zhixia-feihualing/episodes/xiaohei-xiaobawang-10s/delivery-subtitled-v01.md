# 小黑《小霸王一开》字幕成片交付

日期：2026-10-06。用户提供原片并要求只配字幕，沿用小黑已有的 AppKit 白字深描边样式。

- 原片：`../../assets/generated-video/xiaohei-xiaobawang-10s-original.mp4`，下载目录原件未修改；SHA-256 `7c182d8ec129b1b0efba0ead1b6b67c9dbaeff81decac944c0982559110d7bc8`。
- 成片：`../../exports/xiaohei-xiaobawang-subtitled-1080p-v01.mp4`；SHA-256 `678ed23c1eda84b35e84b6b892904c2d4e1c7edcd9f1da91b37562833ccb7203`。
- 字幕轴：`subtitles.json`，五句分别覆盖 0.48–1.58、2.28–3.66、4.56–5.58、6.90–8.24、9.10–9.72 秒。
- 渲染：`render_subtitled.py` 与 `render_subtitle_cards.swift`；字幕居中放在画面下方，避开电视主要画面和小黑面部。

原片与成片均为 10.08 秒、24 fps、241 帧。成片为 1080×1920，原片为 496×864，放大不增加真实细节。整片解码无错误；原 AAC 编码流 SHA-256 均为 `624553578c90810737332cfba3f2cb6ab37166b609d7ece464e7861144de1b61`；原 AIGC 元数据和画面内 AI 标识保留。已目视检查五条字幕的代表帧及片尾无字幕画面。

字幕文字来自已确认的剧本，时间轴依据音频频谱中的五段发声区间定位。本机缺少可用的中文离线语音识别资源，未完成逐字核听；交付供用户试听验收。未发布。
