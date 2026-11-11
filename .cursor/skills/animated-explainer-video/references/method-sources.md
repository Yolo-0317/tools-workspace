# 方法来源与取舍

整理日期：2026-10-09。以下是借鉴来源，不是依赖清单或对全部上游观点的认可。按用户需求重写，没有复制完整手册和私人素材。

## 花叔通用库

[alchaincyf/huashu-skills](https://github.com/alchaincyf/huashu-skills)，本次读取 master 提交 `2efea35738efa06abbfa9acaee923fcef0732a14` 的实际 SKILL.md，不用 README 数量证明仓库完整性。

| 来源 | 保留 | 不照搬 |
|---|---|---|
| [douyin-script](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-douyin-script) | 开头文案与视觉共同设计，分镜对应旁白、字幕和转场 | 电商模板、广告转化，下载与 Gemini 分析不是必备流程 |
| [video-outline](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-video-outline) | 比较讲述角度，兑现标题承诺 | 5–8 分钟、长开场及粉丝量封面阈值 |
| [script-polish](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-script-polish) | 内容、口语、镜头标记分层检查 | 固定句长语速、机械口头禅、不可访问私人写作库 |
| [proofreading](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-proofreading) | 事实、表达、节奏审校 | AI 检测分数、删科学限定、编经历 |
| [research](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-research) | 增量保存来源、条件和局限 | 单凭年份或平台排除全部历史材料 |
| [video-check](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-video-check) | 标题封面开头与内容一致 | 营销对比当育儿结论，标题经验当平台限制 |

## 独立仓库

- [huashu-art-motion](https://github.com/alchaincyf/huashu-art-motion)：按用途选择语法、局部变化、镜头关系和时间轴同步，重点参考 y1、y2、y4、y6。研究副本含本项目经验修订，不能把全部本地改动称为上游原文，不把临时路径绑定进本 Skill。
- [huashu-gpt-image](https://github.com/alchaincyf/huashu-gpt-image)：具体主体、媒介、空间关系和设计参考；[视频参考板](https://github.com/alchaincyf/huashu-gpt-image/blob/master/references/video-reference-board.md)提供统一角色、场景、灯光和分镜的思路。模型宣传、强制六视角及效果保证不作通用事实。
- [huashu-slide-codex](https://github.com/alchaincyf/huashu-slide-codex)：单图封面、系列参考和标题画面互补，不引入整套 PPT、自动三方案审批、图床上传和通用尺寸表。

## 代码动画案例库

[yihui-dev/awesome-opus5-5-videos](https://github.com/yihui-dev/awesome-opus5-5-videos)，2026-10-10 读取提交 `756290289742535eb0ac3817548f152e9759cc70` 的 README、LICENSE，扫描全部 513 条记录的元数据，并精读 16 个精选提示词文件。实际阅读范围、完整性与作者链接见 [代码动画案例与适配](code-animation-examples.md)。没有逐条观看视频，也没有获得可直接复用的完整动画引擎。

保留绝对时间驱动、连续对象衔接、过程与结构演示、分层视差和导出前关键帧检查。按本系列重写提示词结构，不整库复制；未公开完整提示词的案例只作为方向。模型名称、工具营销、传播表现、固定时长／帧率、作者私人目录和逐阶段审批不作本 Skill 的依赖或通用要求。上游 MIT 与第三方媒体权利分别处理。

## 本地经验

王船配音版采用可延展视觉时间映射与最终 PCM 包络驱动口型。保留原声、完整台词、最终时序、嘴外不变及技术／主观审查区分等经验，不把该集时长、语速上限和响度设为通用门槛。路径见当前系列参考。

用户的 2:3、三主持人、身体固定、介绍模式和先视觉后音频是系列配置，放独立参考。新系列使用自己的已确认配置。

## 2026-10-10 视频文案复读与适配

重新 fetch 花叔通用库 master，远端提交仍为 `2efea35738efa06abbfa9acaee923fcef0732a14`。全文读取 `huashu-douyin-script`、`huashu-video-outline`、`huashu-script-polish`、`huashu-video-check`、`huashu-proofreading`、`huashu-topic-gen` 六份 SKILL.md，以及 douyin-script 的 `analysis-dimensions.md`、`script-style-samples.md`、`proven-formulas.md`。本轮未获取原作者私人脚本库，也未执行上游下载、Gemini 分析或发布脚本。

补充取舍：把首句与首帧对应、讲述角度、承接关系、口语与演示分开审稿整理进 [视频文案与叙事](video-script-design.md)。不继承营销焦虑、稀缺话术、短句字数上限、固定语速、钩子效果排序、长教程悬念后置、粉丝量阈值和未经核验的增长数字；不把医疗限定改成主观体感来规避审核。上述模板只作表达研究，数据及功效例子不作科普事实。

结合用户提供的两段微信视频，实际查看代表位置画面与可见字幕；未完整转录音轨，未取得工程源码，第三段未成功播放。沉淀资料与解释交替、处境到行动结果、时间线承接、数量图形表达和文案动词对应动画对象的方法，不宣称这些案例证明播放增长或原作者技术栈。

## 2026-10-14 史话口播

读了中新网 2008-11-13 对当年明月的采访、央视《面对面》2009-04-13 文字稿、一篇归纳《明朝那些事儿》修辞的学位论文摘要，以及相声「铺平垫稳、三翻四抖」的创作说明。保留白话降用、跌衬、短句包袱和单口的顶门到结底。不继承补写心理、虚构场面、对口捧哏、自问自答和网络烂梗。2026-10-14 补充：民国八卦须另读评论，评论只提供说法。同日晚些时候，用户把民国八卦改成叙事主线，损友吐槽只在关键处加一两句。样稿里的错误事实不跟着学。规则见 [明月体史话口播](mingyue-shihua-voice.md)。
