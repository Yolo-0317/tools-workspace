# 《月照反弹琵琶》15 秒敦煌舞

## 定位

- 系列：《栀夏·敦煌十六舞》第二支。
- 工作标题：《月照反弹琵琶》。
- 舞蹈：反弹琵琶原创敦煌舞意象。
- 诗文：唐·王昌龄《从军行七首·其二》。
- 画幅与时长：9:16 竖屏，15 秒，一镜到底。
- 情绪：边塞壮阔、清冷有力。
- 当前状态：无道具舞蹈原片已由用户确认可用；四句栀夏朗诵、逐句竖排字幕与 1080×1920 高清成片已完成，等待用户最终试听确认。

## 诗文

> 琵琶起舞换新声，
>
> 总是关山旧别情。
>
> 撩乱边愁听不尽，
>
> 高高秋月照长城。

原始视频不生成人声、诗句或字幕；四句朗诵和字幕在舞蹈原片通过后另行制作。

## 无道具重制

- 设计：`../../docs/superpowers/specs/2026-08-30-fantan-pipa-no-prop-15s-design.md`。
- 5 秒动作测试：`prompts/seedance-no-prop-test-v01.md`。
- 15 秒正式提示词：`prompts/seedance-no-prop-v02.md`。
- 状态：按用户决定跳过 5 秒测试；15 秒无道具原片已确认可用。
- 正式生成只上传栀夏敦煌 v03 单张大脸锁定版，不上传琵琶道具卡或其他参考图。
- 全片不出现实体乐器或虚影，以反弓身法、肩后高低双臂、反手弹拨、飘带和琵琶声表现反弹意象。
- 实体琵琶版保留为失败实验记录，不再用于生成。

## 旧版实体道具实验输入

1. 图片 1：`assets/characters/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-Seedance上传版.jpg`。
2. 图片 2：`assets/props/fantan-pipa-v01/敦煌反弹琵琶道具卡-v01-Seedance上传版.jpg`。

旧版曾同时上传这两张图：图片 1 负责栀夏身份与固定服化道；图片 2 负责四弦四轴曲项琵琶。实测模型仍把道具移到胸前，因此此输入组合不再使用。

## 三次同强度高潮

1. 0.000—1.800 秒：低位反弓转纵向蹬地提展与肩后反拨。
2. 4.800—7.000 秒：横跨宽弓急停与横向肩后反拨。
3. 10.000—13.000 秒：向镜头急沉后沿长城纵深沉提远展。

三次高潮分别使用纵向、横向和纵深剪影；全片只有一次不超过 90 度的改面，7 秒后零完整旋转。13—15 秒保持高能量余势并在运动中结束。

## 视觉与声音

- 场景：秋夜边塞城关、冷灰石砖、低矮垛口、深蓝夜空、后上方秋月和少量远处烽火。
- 唯一环境机制：秋夜长风与冷月反光。
- 禁止重复上一支的金色细沙。
- 摄影机只有侧前方低位缓慢后退主路径，12.500 秒后不继续拉远。
- 原始声音只有冷峻琵琶、低沉羯鼓、长风、脚步、衣料和拨弦声，无可辨识人声。

## 朗诵字幕成片

- 源视频：`assets/video/content-seedance-no-prop-v02.mp4`，与用户下载原片 SHA-256 一致。
- 四句声音：栀夏固定音色 `ICL_uranus_zh_female_tianmeihuopo_tob`，分别朗诵“琵琶起舞换新声”“总是关山旧别情”“撩乱边愁听不尽”“高高秋月照长城”。
- 混音：原片背景音乐与动作声全程保持 `volume=1.0`，不使用侧链、闪避或人声时间窗音量包络；只在最终总线进行透明峰值保护。
- 字幕：暖象牙白竖排逐句出现，第一句附“唐·王昌龄《从军行七首·其二》”题署，位于右侧安全区并保留右下角 AI 标识。
- 无字幕试听版：`../../exports/fantan-pipa-15s-voiced-v01.mp4`。
- 最终字幕版：`../../exports/fantan-pipa-15s-subtitled-v01.mp4`。
- 输出规格：1080×1920、24fps、15.104 秒、48kHz 双声道 AAC；最终综合响度约 −15.09 LUFS，真峰值约 −1.01 dBTP。
- QA：`qa-recitation-subtitles-v01.md`。

## 真源

- 当前设计规范：`docs/superpowers/specs/2026-08-30-fantan-pipa-no-prop-15s-design.md`。
- 当前 5 秒测试提示词：`episodes/fantan-pipa-15s/prompts/seedance-no-prop-test-v01.md`。
- 当前 15 秒正式提示词：`episodes/fantan-pipa-15s/prompts/seedance-no-prop-v02.md`。
- 朗诵字幕成片设计：`docs/superpowers/specs/2026-08-30-fantan-pipa-recitation-subtitles-design.md`。
- 朗诵字幕实施计划：`docs/superpowers/plans/2026-08-30-fantan-pipa-recitation-subtitles.md`。
- 旧版实体道具设计：`docs/superpowers/specs/2026-08-30-fantan-pipa-15s-dance-design.md`。
- 旧版实体道具提示词：`episodes/fantan-pipa-15s/prompts/seedance-v01.md`。
