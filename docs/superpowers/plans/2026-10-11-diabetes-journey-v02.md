# 糖尿病穿越动画制作计划

**Goal:** 按已确认扁平插画方案交付16:9无声动画，栀夏贯穿21个解释单元。

**Architecture:** 独立透明人物帧与程序化场景分开。绝对时间控制场景、相机、解释状态和字幕；复用已验证本地渲染器输出H.264，后续按真实配音调整时间轴。

**Tech Stack:** HTML、Canvas、Python、Playwright、FFmpeg、内置imagegen。

## 约束

1920×1080、30fps；单一当代扁平插画；字幕底部无标点无背景；不生成音频；不删除旧视频；不提交Git；保留424字正文与CTA位置。素材生成参考栀夏身份；不使用参考板中的肾脏糖粒过滤误示意。

## 执行

- [ ] 角色：生成8格透明帧，检查行走与站立、指示。按透明包围盒与脚底锚点对齐，保存assets/hero.json及帧PNG。
- [ ] 时序：engine/timeline.json逐项保存21个单元、全文片段、时长及字幕。先用qa/check_timeline.py检查正文覆盖、连续时间和字幕无标点，确认缺失时失败后再补齐。
- [ ] 场景：engine/art.js负责器官、食物、人物、环境；scenes.js负责血管、眼、肾、神经、消化、胰腺/细胞/肝、风险、饮食运动测量与检查的解释动作；main.js负责连续运镜、英雄与字幕。
- [ ] 渲染：先输出21个中间静帧和转场静帧，目视检查，再render.py --spec engine/spec.json --out exports/diabetes-journey-silent-v02.mp4 --crf 18。
- [ ] 验证：完整解码、ffprobe流属性；同秒重复截图哈希；每幕两帧差；21幕接触表核对内容、人物位置、字幕超框与医学示意，记录实际执行范围。

## 验证接口

页面导出window.prepare(t)、renderFrame(t)、__canvas、__total、__ready，复用渲染器无需外部研究目录。时序文件包含shots（start/end/text/id）和captions（start/end/text），scene state由t绝对求值。qa/check_timeline.py将各shot去标点文本拼接与script-current-v02.txt正文一致性比较。
