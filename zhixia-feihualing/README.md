# 栀夏飞花令

《栀夏飞花令》是面向抖音新账号的原创国风诗词幻想动画IP。少女栀夏与墨灵阿砚通过飞花令唤醒诗句中的汉字，并进入由诗意展开的东方幻境。

## 当前结论

- 账号名称：栀夏飞花令
- 账号类型：原创国风动画IP，不定位为AI工具教学号
- 主角：18岁的栀夏、原创墨灵阿砚
- 核心玩法：阿砚出题，栀夏接诗，汉字苏醒，诗境展开
- 画面比例：9:16竖屏
- 视觉方向：明亮、清透、低饱和的东方二维动画，融合宣纸、水墨与书法飞白
- 当前制作节点：EP01“一字三诗·花”完整流程已跑通；推荐成片为 `exports/ep01-flower-subtitled-v02-fullscreen.mp4`
- 配音自动化：已支持按剧集清单预览、付费确认、五句分段生成、断点续做、版本保护和字幕时间轴生成

## 当前优先级

1. 以EP01流程为模板，确定后续4个主题字及每集三句诗。
2. 复用固定角色、音色、字幕模板和FFmpeg流程。
3. 每集只重新生成15秒全屏诗境和对应TTS。
4. 准备首发5条内容后再开账号发布。

## 配音自动化快速入口

先在 `episodes/<episode>/voice-lines.json` 填好五句台词，再运行默认预览：

```bash
python3 scripts/generate_episode_audio.py --episode ep04
```

预览不会读取 API Key、不会访问网络，也不会创建音频。确认计划无误后，才使用 `--generate`；程序还会要求手工输入 `GENERATE ep04`，随后才会产生豆包 TTS 调用。单句恢复使用 `--line 03-poem-02`。完整清单格式、版本规则和输出说明见[“一字三诗”短视频生产SOP](docs/one-character-three-poems-sop.md)。

EP01、EP02、EP03 的既有音频、字幕和成片不纳入自动补生成，保持原样。

## 文档导航

- [“一字三诗”单集总览](episodes/README.md)
- [账号规划](docs/account-plan.md)
- [世界观母版](docs/world-bible.md)
- [角色母版](docs/character-bible.md)
- [视觉母版](docs/visual-bible.md)
- [生产流程](docs/production-workflow.md)
- [“一字三诗”短视频生产SOP](docs/one-character-three-poems-sop.md)
- [EP01剧情](episodes/ep01/script.md)
- [EP01分镜状态](episodes/ep01/storyboard.md)
- [资产说明](assets/README.md)
- [首月发布日历](operations/publishing-calendar.md)
- [原始对话提炼](docs/source-notes/chatgpt-conversation-summary-2026-08-22.md)

## 单一事实源规则

- 角色身份以 `docs/character-bible.md` 为准。
- 画风与场景以 `docs/visual-bible.md` 为准。
- 单集剧情与完成状态以对应 `episodes/<episode>/` 为准。
- 生成图片、视频和音频必须登记到 `assets/inventory.csv`。
- 对话中的旧提示词不能直接覆盖母版；确认后的变更先写入文档，再用于生成。
