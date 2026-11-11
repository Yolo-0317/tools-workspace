# 拉链60秒角色动作与嘴型实施计划

**Goal:** 按用户认可的60秒文案，交付1080×1920、30fps无声视频；3秒内进入原理，添加连续肢体动作和对白嘴型，最后再配音。

**Architecture:** 沿用C博物馆与B内部风格，时间轴固定60秒。角色生成分层头部口型与身体/肢体素材，Canvas控制肩颈、腿和尾巴的连续姿态；对白估计字时驱动闭口/开口/圆口，配音后再以真实声音校准。机械镜头通过近景与整体剖视交替，避免长时间说明板构图。

**Tech Stack:** huashu-art-motion、ImageGen透明角色分层、Canvas、Playwright、FFmpeg、Node测试。

## 用户已确认的约束

- 开头小黑直接问“拉链一拉，为什么就能合上？”，0–3秒抛题，3秒后进入拉头内部。
- 栀夏解释，阿砚和小黑提问；保留当前完整句子。
- 总长60秒，C→B→C；没有零食袋桥段。
- 青绿暖金、三位Q版身份不变；嘴型是无声预演，当前不声称逐音素同步。
- 不生成TTS、不添加旧音频、不发布视频、不修改原角色母版。

## 文件与验证

- [x] `video-v04/engine/motion.test.cjs`：先测试60秒、字幕完整覆盖、前3秒提问、嘴型仅发言角色改变、非发言角色闭口、连续骨架角度及反向机械运动。
- [x] `video-v04/assets/*-rig.png`与`rig-layout.json`：基于三人母图逐个生成分层图集；观察alpha与部件身份，登记身体比例和锚点。脸、发饰、服装、四足与单尾均保留。
- [x] `video-v04/engine/dialogue.json`、`timeline.cjs`与`character-motion.cjs`：固定各对白时间，标点切字幕；建立抬手、倾身、摆头、眨眼、前爪与尾部连续曲线。
- [x] `scene.js`：配合近景/剖视/扣合/反向镜头，标明箭头为拉头移动方向；贴地接触阴影，避免文字与角色重叠、推近露底。
- [x] 抽帧及嘴型连续片段检查，导出完整60秒MP4、字幕与分镜；运行技能QA、ffprobe与完整解码。
- [x] 按huashu技能要求独立审片，只读最终视频，修复阻断问题后交付。

## 命令

`node --test artifacts/life-principles/ep01-zipper/video-v04/engine/motion.test.cjs`

`UV_CACHE_DIR=/private/tmp/zipper-uv-cache uv run --with playwright python artifacts/life-principles/ep01-zipper/video-v04/engine/render.py --spec artifacts/life-principles/ep01-zipper/video-v04/engine/spec.json --out artifacts/life-principles/ep01-zipper/video-v04/exports/zipper-60s-silent-v01.mp4`
