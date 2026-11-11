# 《小黑片场·AI 废片实录》关门上板版

日期：2026-09-24。使用用户提供的 10.08 秒 Seedance 成片做后期包装，没有重新生成视频。

## 文件

- 原片：`../../assets/generated-video/xiaohei-selective-hearing-10s-original.mp4`，来自 `/Users/huan.yu/Downloads/f6d32838-b0d2-439f-a24a-083f8410149f.mp4`，保持原样。
- 交付视频：`../../exports/xiaohei-selective-hearing-ai-fail-captioned-1080p-v04.mp4`。
- 对白字幕版：`../../exports/xiaohei-selective-hearing-ai-fail-dialogue-1080p-v06.mp4`，为当前推荐交付版。
- 封面：`../../exports/xiaohei-selective-hearing-ai-fail-cover-v01.png`。
- 视频号文案：`video-account-copy-ai-fail-v01.md`。
- 吐槽时间轴：`subtitles-ai-fail-v01.json`；渲染程序：`render_ai_fail.py`、`render_ai_fail_cover.swift`。
- 对白字幕时间轴：`subtitles-dialogue-v01.json`；渲染程序：`render_dialogue_subtitles.swift`、`add_dialogue_subtitles.py`。

## 包装

沿用上一条小黑 AI 废片的深色顶部文字区和保留原声的做法。四组作者视角吐槽依次点出：拍小黑躲洗澡、关门过熟、听到出去玩立即上板、仙家滑板却被 AI 装了轮子。原片画面置于文字区下方，吐槽不遮挡角色。小黑在滑板上的侧身镜头做了腹下小范围柔边模糊；原片其他画面与对白未重绘或替换。

## 验证

- 完整解码通过；1080×1920，24fps，242 帧，10.083 秒，H.264/AAC。
- 原片与交付片 AAC 编码流 SHA-256 均为 `70e4d05c33982f076c81a6794813d288aed5b210a84a65c902cbf3b180657868`。
- AIGC 元数据保留。目视检查顶部文字、关门、上板和轮子镜头，隐私模糊局限于腹下。
- 交付视频 SHA-256：`c4fe11b524cbb8ca3dc7ce2d76d2df216ae74950b31a9e01736e0d6b4b5775c1`。
- 封面为最终视频 5.5 秒帧与 AppKit 标题排版，1080×1920 PNG；SHA-256：`1b664dcdcf332e0fc5f04974463b4fc5de2f699a1537a2200339afc085adf96e`。
- 待用户验收，未发布。

## 对白字幕补充

用户要求在顶部吐槽之外加入对白字幕。本地语音识别核对出三句原声：栀夏“小黑，洗澡啦。”约 0.14–1.76 秒；栀夏“那出去玩啦。”约 4.00–4.79 秒；小黑“这还差不多。”约 8.00–8.79 秒。字幕分别显示于 0.10–1.90、3.88–4.95、7.90–9.20 秒。使用项目既有白字、棕色描边与阴影样式，放在画面下缘，不挡角色脸、爪和滑板主体。顶部吐槽、局部隐私模糊和原片声音保持不变。

对白字幕版已完整解码；1080×1920，24fps，242 帧，10.083 秒；AAC 编码流 SHA-256 仍为 `70e4d05c33982f076c81a6794813d288aed5b210a84a65c902cbf3b180657868`；AIGC 元数据保留。目视检查三句字幕对应画面及位置。成片 SHA-256：`456e0cc9314cd5a6f2695ab232d449603a1e19f5026e4434f75a5e102e2f4170`。待用户验收，未发布。
