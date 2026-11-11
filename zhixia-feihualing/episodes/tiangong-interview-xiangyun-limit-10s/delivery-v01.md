# 《天宫采访·祥云限重》字幕版

日期：2026-09-04。用户提供 Seedance 成片并确认可用；本次只增加四句人物对白字幕，不修改原片音频。

## 交付文件

- 字幕成片：`../../exports/tiangong-interview-xiangyun-limit-subtitled-v01.mp4`
- AI 吐槽字幕版：`../../exports/tiangong-interview-xiangyun-limit-subtitled-v02-ai-note.mp4`
- 作者视角吐槽版：`../../exports/tiangong-interview-xiangyun-limit-subtitled-v03-author-note.mp4`
- 作者吐槽与评论引导版：`../../exports/tiangong-interview-xiangyun-limit-subtitled-v04-author-comment-prompt.mp4`
- 封面：`../../exports/tiangong-interview-xiangyun-limit-cover-v01.png`
- 字幕时间轴：`subtitles.json`
- AI 吐槽时间轴：`subtitles-ai-note.json`
- 作者视角吐槽时间轴：`subtitles-author-note.json`
- 作者吐槽与评论引导时间轴：`subtitles-author-comment-prompt.json`
- 原始视频：`/Users/huan.yu/Downloads/5d6834b4-6577-4205-bf7a-f6dcf65116be.mp4`

## 字幕设计

- 沿用天宫采访已确认样式：暖白粗体、深棕描边和轻微阴影。
- 四句对白依次显示在底部安全区；最后一句“祥云限重。”单独呈现。
- 结尾祥云变红与阿砚收回玉如意的无对白反应不添加解说字幕。
- AI 吐槽版在第一句对白期间于画面最上方增加“AI：‘减肥’两个字连成一个了”，其余时间仍保持普通采访字幕。
- 作者视角吐槽版将顶部文字改为“本来让 AI 说‘减肥’，结果两个字直接粘一块儿了”，以视频号作者带观众看翻车的口吻呈现；单行小字置顶，不遮挡人物头饰。
- 作者吐槽与评论引导版保留上述开场吐槽；“祥云限重”说完后，顶部显示“不是，天宫连祥云都限重？这合理吗？”，覆盖祥云变红和结尾反应，引导观众评论。

## 验证

- 输出为 720×1280、24fps、10.080 秒、H.264/AAC。
- 已完整解码视频流和音频流，并检查六个代表帧；字幕未遮挡人物面部、玉如意或祥云的主要变色区域。
- 原片与字幕版 AAC 音轨逐包 SHA-256 均为 `5531dd01611ea592461cad0c8959736895a30616135b4549bc837a1cf90f7415`。
- AIGC 元数据保留。
- 成片 SHA-256：`ee9bdfed16ad9141e981a951ffd15ec99add253976e66c1ef8965a67b69e3185`。
- AI 吐槽字幕版保持 10.080 秒、720×1280、24fps；完整音视频解码通过，AIGC 元数据保留，原片与输出的 AAC 音轨逐包 SHA-256 均为 `5531dd01611ea592461cad0c8959736895a30616135b4549bc837a1cf90f7415`。
- AI 吐槽字幕版 SHA-256：`65dd3397eb34a6d9cf43c98ec58e41dc93edadfded903218a774c3eda305eea7`。
- 作者视角吐槽版保持 10.080 秒、720×1280、24fps；完整音视频解码通过，AIGC 元数据保留，原片与输出的 AAC 音轨逐包 SHA-256 均为 `5531dd01611ea592461cad0c8959736895a30616135b4549bc837a1cf90f7415`。
- 作者视角吐槽版 SHA-256：`97052766d9564ab357e0b9e7ad6387b0db5711692b2e544e632b2c1e27ac2bff`。
- 作者吐槽与评论引导版保持 10.080 秒、720×1280、24fps；完整音视频解码通过，AIGC 元数据保留，原片与输出的 AAC 音轨逐包 SHA-256 均为 `5531dd01611ea592461cad0c8959736895a30616135b4549bc837a1cf90f7415`。
- 作者吐槽与评论引导版 SHA-256：`e788e0830812a4f6d49ae23d0394e485cb43061f9d0241569d8779f375e1d694`。

## 封面

- 取原片 9.400 秒：祥云已经变红，阿砚抬头看向栀夏，玉如意与两位角色均清楚可见。
- 沿用“天宫采访”系列字体和暖白棕边样式；小字“天宫采访”，主标题“仙女也要减肥吗？”，不提前揭示“祥云限重”的答案。
- 输出为 1080×1920 PNG；人物未重绘，原片 AI 标识保留。
- 封面 SHA-256：`a04bd8f0bb8c3cd12b0b371bf938e033458f9c7a4d693a444c1d066c0eaf006e`。
