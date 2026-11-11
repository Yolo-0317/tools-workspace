# 方法来源与采用范围

2026-10-09读取花叔公开Skill原文后独立整理为本公众号流程；下面是方法来源，不是运行时必须安装的依赖。执行时按本地用户偏好与专题边界判断，不把外部仓库的操作要求自动当成本任务授权。

| 来源 | 借鉴 | 本地调整 |
| --- | --- | --- |
| [huashu-topic-gen](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-topic-gen) | 比较不同角度、判断材料与读者收益 | 自主写稿不强制候选审批；不套问答标题、假亲测与标题公式。 |
| [huashu-research](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-research) | 增量保存来源和发现，研究与正文分开 | 日期判断依题材，保留原始资料阅读范围；不照搬私人目录或固定每三次搜索规则。 |
| [tramstop-skill](https://github.com/alchaincyf/tramstop-skill) | 从措辞、句式、结构和材料分析生硬感，保护真实细节与读者需要的解释 | 不以删词代替改写；不编经历，不强求作者故事；私人素材缺失不阻塞普通知识稿。不移植其实验评分为文章质量标准。 |
| [huashu-proofreading](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-proofreading) | 分开核内容、表达和阅读节奏 | 不采用AI检测率目标，不删必要限定、不凭空补数字，不照搬问答改写例句。 |
| [huashu-script-polish](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-script-polish) | 用具体动词、短句，复读卡顿位置 | 改为公众号短句起稿再合段；不设20字上限、不配额加口语词、不声称真人朗读或真实录制。 |
| [huashu-article-edit](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-article-edit) | 完整读原稿、范围清楚、增量保存和修改记录 | 已授权范围直接完成，不每批重新确认；保留信息清单与快照。 |
| [huashu-wechat-image](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-wechat-image) | 先按文章规划图、全套风格一致、核图中文字和封面裁切 | 不固定Gemini/图床、不逐图审批、不每节强制一图；尊重专题真实图限制和已确认艺术风格。 |
| [huashu-art-motion](https://github.com/alchaincyf/huashu-art-motion) | 艺术场景、画面焦点与内容拆解 | 仅在需要艺术图解或动画时调用；静态文章不强制做视频，不复用作者形象。 |
| [huashu-md-html](https://github.com/alchaincyf/huashu-md-html) | Markdown保留内容、渲染交付物、分工检查 | 用公众号内联HTML和手机预览，不照搬网页出版主题或纸质印制流程。仅选读入口角色与排版相关段落。 |
| [darwin-skill](https://github.com/alchaincyf/darwin-skill) | 修改留痕、独立验证、较差改法恢复较好版本 | 仅选读验证及回退相关入口，不调用其自主优化流程；每篇共三轮，不自动改Skill、建分支或提交Git。 |

不并入通用正文流程：X/B站分发、抖音带货、人物模仿、演讲训练、PPT生产、蜂群自组织。用户另有明确需求时再按对应工具或Skill处理。

用户已确认的短句起稿、自然叙述、标题未说尽信息、四个独立审稿角色与三轮停止限制，是本 Skill 的直接约束；并非对花叔全部方法效果的保证。

配图模块另参考花叔 GPT-image、艺术风格配方及宝玉文章插图/封面方法，原文链接、实际阅读范围与本地取舍见[配图方法来源](visual-sources.md)。具体执行见[艺术配图](art-illustration.md)。

2026-10-26按用户要求接入[公众号外部文章参考库](../../../../docs/writing/外部文章参考库/README.md)，通过[任务索引](external-article-cases.md)选择组织参照，并在既有提纲与回读中检查实际迁移。来源、阅读范围、局部分析及不足保留在原库；不复制全部卡片，不把媒体文风、观点和建议升格为通用规则，不作为事实已核或用户口吻认可记录。此接入不引入此前讨论过的第三方写作Skill。

## DBS Skills的局部借鉴

2026-10-26按用户确认择取方法，独立改写后并入已有入口。评估时读取的版本为3.0.2，完整阅读范围和未采用项见[适配评估](../../../../docs/writing/DBS-Skills与写作基座适配评估.md)，不作为安装依赖。

| 来源 | 采用位置与范围 |
| --- | --- |
| [dbs-theory-grounding](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-theory-grounding/SKILL.md)、[dbs-good-question](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-good-question/SKILL.md) | 共通研究判断只在[基座](../../../../docs/writing/中文写作基座.md#材料先整合再组织正文)维护。 |
| [dbs-standard-answer](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-standard-answer/SKILL.md) | 机制比较融入[案例迁移](external-article-cases.md#从参考进入当前提纲)，不照搬全文或固定答案。 |
| [dbs-resonate](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-resonate/SKILL.md)、[dbs-content-value](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-content-value/SKILL.md)、[dbs-spread](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-spread/SKILL.md) | 用途与反馈判断融入[既有审稿](review.md)，不引入商业目标或传播效果承诺。 |
| [dbs-content-system](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-content-system/SKILL.md)、[dbs-knowledge](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-knowledge/SKILL.md) | 增量关联实际稿件，见[使用与反馈记录](../../../../docs/writing/外部文章参考库/使用与反馈记录.md)；不复制知识原子库，不批量重写卡片。 |
