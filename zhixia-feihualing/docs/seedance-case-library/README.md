# Seedance 公开提示词案例库

本库收录可回源核查的 Seedance 官方与社区公开案例，为《栀夏飞花令》的诗境设计提供研究依据。案例采用中文结构化改写，不把社区经验表述为平台保证。

## 证据等级

- A：官方发布或官方文档，并有公开结果。
- B：社区公开了提示词或工作流，并有对应成片或关键帧。
- C：只有提示词、术语或教程观点，仅供词汇研究。

## 统一字段

每条案例记录来源、访问日期、模型版本、输入方式、主体与场景、动作与因果、摄影机、光线与物理反馈、声音、中文结构化改写、可复用写法、失败风险和栀夏适用性。缺失信息统一写“来源未披露”。

## 分类导航

1. [人物肖像与首次亮相](01-characters-and-portraits.md)
2. [双人及多人互动](02-multi-character-interaction.md)
3. [舞蹈与身体运动](03-dance-and-body-movement.md)
4. [动作与表演](04-action-and-performance.md)
5. [风景与环境](05-landscape-and-environment.md)
6. [运镜与一镜到底](06-camera-and-one-take.md)
7. [特效与物理反馈](07-effects-and-physics.md)
8. [声音、对白与节拍](08-sound-dialogue-and-rhythm.md)
9. [多模态参考](09-multimodal-reference.md)
10. [运镜句式库](camera-phrases.md)
11. [人物与舞蹈句式库](character-dance-phrases.md)

## 收录规则

- 同一案例只在主要专题完整收录，其他专题使用链接引用。
- 优先引用官方原页或作者原帖；转载页只作定位线索。
- 明确区分来源陈述、成片观察和项目适配建议。
- 不下载、转载社区视频，不大段复制原始提示词。
- 句式库只引用 A/B 级案例，并标注来源案例编号。

## 当前统计

最后核验日期：2026-08-28。

- 唯一案例：80 个。
- A 级官方成片案例：10 个。
- B 级社区可复核案例：22 个。
- C 级词汇与方法参考：48 个。
- 人物肖像与首次亮相：8 个。
- 双人及多人互动：6 个。
- 舞蹈与身体运动：10 个，其中 8 个明确涉及脚步、重心、动作顺序或节拍参考。
- 动作与表演：8 个。
- 风景与环境：14 个。
- 运镜与一镜到底：12 个，覆盖推近、后拉、横移、跟随、弧移、升降、穿越、主观镜头、速度变化及多镜头表等路径。
- 特效与物理反馈：8 个。
- 声音、对白与节拍：6 个。
- 多模态参考：8 个。
- 可复用句式：16 条，均反向引用 A/B 级案例。

## 主要来源

- [字节 Seed：Seedance 2.0 正式发布](https://seed.bytedance.com/zh/blog/official-launch-of-seedance-2-0?view_from=content_recommend)：官方 A 级案例与官方能力边界。
- [FreyaVideo Prompt + Video Cases](https://freyavideo.com/video-models/seedance-2-0/prompts)：带匹配视频、提示词和设置的 B 级案例。
- [Scenic 舞蹈分镜工作流](https://www.scenic.sh/en/blog/gpt-image-seedance-dance-video)：舞蹈分镜、固定全身镜头、衣料物理和音频同步案例。
- [SeedanceTips Prompt Library](https://seedancetips.com/prompts/seedance-prompt-library/)：分类完整但缺少逐例成片证据，统一按 C 级使用。
- [ClipDance Camera Movement List](https://clipdance.ai/blog/seedance-2-camera-movement-prompt-list)：运镜词汇池，统一按 C 级使用。
- [SeedanceNow Cinematic Prompts](https://seedancenow.com/seedance-prompts)：风景、人物和材质词汇池，统一按 C 级使用。
- [Reddit：整段舞蹈换皮](https://www.reddit.com/r/Seedance_AI/comments/1uk9jhd/reskin_an_entire_dance_swap_the_dancer_and_the/)、[一镜打斗摄影机路径](https://www.reddit.com/r/Seedance_AI/comments/1tzvjpv/onetake_fight_in_a_single_shot_the_camerapath/)、[七镜头结构表](https://www.reddit.com/r/Seedance_AI/comments/1tprtbi/7_shots_from_one_seedance_20_prompt_shot_list/)：带作者输入、提示词或成片的社区 B 级案例。

## 首轮结论

1. 舞蹈只写舞种和气质不足以保证复杂度；高等级案例会写步法、重心、方向、节拍或直接提供分镜/动作视频。
2. 固定全身镜头更有利于复杂动作可读性；复杂运镜与复杂编舞同时出现时容易争夺模型控制力。
3. 一条主运镜不等于匀速后退。可执行镜头还需要起点、路径、速度变化、前景视差和最终揭示目标。
4. 高质量复合镜头普遍采用“主体动作发生—摄影机作出反应—环境产生结果”的因果写法。
5. 两张角色母版加纯文字适合低成本诗境，但复杂舞蹈与复杂一镜到底存在能力上限；更高控制需要合法动作视频、分镜板或场景参考。
6. 官方明确提示多主体一致性、文字还原和复杂编辑仍有改进空间，案例库不把单次成功写成稳定保证。
