# DBS Skills与写作基座适配评估

2026-10-26。结论是择取方法、按职责放置，暂不整套引入。较有增量的是研究阶段的命题审查、竞争解释，以及案例比较和使用反馈；语义保护、逐段承接、避免套话等内容与现有基座高度重合。

## 来源和评估范围

来源为[dontbesilent2025/dbskill](https://github.com/dontbesilent2025/dbskill)，本轮读取的[VERSION](https://github.com/dontbesilent2025/dbskill/blob/main/VERSION)为3.0.2。[中文README](https://github.com/dontbesilent2025/dbskill/blob/main/README.md)列34个公开入口；另查看了可读取的`dbs-agent-migration`与`dbs-update`，共36个入口。

逐项查看了入口的任务定义、输入输出边界和主要规则。对论证、写作、受众分析、结构化资料等相关部分补读了具体流程；另读`plain-writing`的标准依据与检查边界。未逐份遍历所有附属参考、脚本、模板和知识原子，也未安装、执行这些外部Skill或测试其效果。下表是本项目的适配判断，不是对作者全部方法的评价。

对照对象为[中文写作基座](中文写作基座.md)、[公众号公共Skill](../../.cursor/skills/wechat-mp-article/SKILL.md)及其[案例使用索引](../../.cursor/skills/wechat-mp-article/references/external-article-cases.md)。评估阶段未改执行规则；用户确认后的落地位置见文末。

## 逐项适配

“基座候选”只表示有可提炼的共通动作；“专题候选”表示应留在公众号或资料库；“已有覆盖”表示不再增加同义规则；“不纳入”表示不适合作为中文写作共通流程。

| Skill | 核读后与本项目有关的部分 | 适配判断 |
| --- | --- | --- |
| [dbs](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs/SKILL.md) | 根据任务选择最少够用的能力，也会做版本检查和编号调度 | 已有路由；不引入更新检查或动态编号到写作基座。 |
| [dbs-diagnosis](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-diagnosis/SKILL.md) | 先判断商业问题是否成立，另有较强商业公理 | 不纳入商业公理；问题前提检查由下列论证方法处理。 |
| [dbs-benchmark](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-benchmark/SKILL.md) | 比较完整获客与交付链，强调高度一致地模仿 | 不纳入完整复刻要求；写作参照保留对象差异与原创表达。 |
| [dbs-jtbd](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-jtbd/SKILL.md) | 从具体情境和选择阻力理解需求，区分事实与任务假设 | 专题候选；可分析读者处境，不默认给所有文章套购买任务。 |
| [dbs-goal](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-goal/SKILL.md) | 检查词语是否改变范围、规格和验收，而非只看删后通顺 | 已有语义保护；适合补诊断案例，不增目标卡流程。 |
| [dbs-good-question](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-good-question/SKILL.md) | 候选解释对应可观察信号，并比较竞争解释 | 基座候选；只在关键因果判断处使用，不搬入评分门槛。 |
| [dbs-deconstruct](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-deconstruct/SKILL.md) | 在具体场合辨别概念用法，用展开后的意思检验混用 | 已有语境检查可补例；不固定采用某一哲学或经济学立场。 |
| [dbs-theory-grounding](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-theory-grounding/SKILL.md) | 先审判断，再找理论；区分保留、收窄、重构和放弃 | 基座候选；保留机制匹配，不照搬默认离线及理论评分。 |
| [dbs-standard-answer](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-standard-answer/SKILL.md) | 按角色、约束和决策机制比较成功、失败及反例 | 专题候选；适合案例研究，不要求每篇都有历史类比。 |
| [dbs-content](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-content/SKILL.md) | 已定选题的创作方案诊断，明确不代写 | 不整体纳入；先有产品等商业前提不适用于全部公众号写作。 |
| [dbs-title-cover-intro](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-title-cover-intro/SKILL.md) | 区分标题、封面文字和视频开头，按制作状态调整范围 | 标题与视频专题参考；不新增多平台交付、经历追问或选题审批。 |
| [dbs-resonate](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-resonate/SKILL.md) | 用具体原句定位问题，并列删除、压缩、强化和保留 | 专题候选；用于行文编辑，不强迫每篇套传播理论或只有一个命题。 |
| [dbs-script-flow](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-script-flow/SKILL.md) | 检查段落交界、重复和口播困难，改稿保留原文对照 | 承接检查已有覆盖；口播部分留专题，不加句长门槛或固定过渡句。 |
| [dbs-content-value](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-content-value/SKILL.md) | 区分观看回报、读者相关性和商业价值，不预测具体播放量 | 专题候选；理解、判断本身可以是用途，不要求煽情或转化。 |
| [dbs-spread](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-spread/SKILL.md) | 文本事实、心理推断与待验证反应分开，接受与分享分开 | 专题候选；不把模拟读者反应写成真实效果。 |
| [dbs-ai-check](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-ai-check/SKILL.md) | 提醒检查虚构读者声音、均匀套句和过度收束 | 问题定位已有覆盖；不纳AI指纹定性、字数阈值和逐条等答。 |
| [dbs-content-risk-check](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-content-risk-check/SKILL.md) | 区分平台可能识别的信号与内容实质问题，给最小改法 | 仅发布质检专题参考；机器审核推断不能作为事实或法律判断。 |
| [dbs-plain-writing](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-plain-writing/SKILL.md) | 主体、指代、术语、条件和承诺强度核对，局部改动保护 | 基座基本覆盖；不把说明文开头、结构或行末标点推广到评论。 |
| [dbs-wechat-html](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-wechat-html/SKILL.md) | 排版与改文分开，关注微信粘贴后的样式兼容 | 排版专题参考；不改变现有手机交付或新增风格选择流程。 |
| [dbs-video-extract](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-video-extract/SKILL.md) | 依赖外部服务取得平台数据与转写 | 不纳入基座，不安装服务或读取凭证。 |
| [dbs-video-navigation](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-video-navigation/SKILL.md) | 按真实字幕时间制作独立导航条，区分成片与结构草案 | 视频制作能力，与本次写作基座无直接增量。 |
| [dbs-action](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-action/SKILL.md) | 以特定心理学框架诊断执行阻滞 | 不纳入；不能据此解释作者、家长或受访者的真实心理。 |
| [dbs-learning](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-learning/SKILL.md) | 按真实反馈调整学习文章的深度与顺序 | 连续教学专题参考，不作为普通评论写作流程。 |
| [dbs-decision](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-decision/SKILL.md) | 将事实、规律、阶段状态和待解问题分层保存 | 资料管理参考；不为写稿新建个人决策系统。 |
| [dbs-save](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-save/SKILL.md) | 保存已确认结论、被否决方向和待验证假设 | 工作记录已有相似能力，不引入另一套存档目录。 |
| [dbs-restore](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-restore/SKILL.md) | 按明确存档恢复状态 | 不纳入；写作仍按现有稿件和用户当前指令续接。 |
| [dbs-report](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-report/SKILL.md) | 合并已有存档并保留可追溯性 | 汇总任务参考，不新增写稿必交报告。 |
| [dbs-chatroom](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-chatroom/SKILL.md) | 让不同理论分工、展示分歧，并标明人物发言为模拟 | 不替换现有四角色审稿；模拟专家不是采访或证据。 |
| [dbs-chatroom-austrian](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-chatroom-austrian/SKILL.md) | 固定经济学视角和人物讨论 | 不纳入通用文体，不复制固定模型与角色扮演。 |
| [dbs-knowledge](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-knowledge/SKILL.md) | 导航指向原始文件，区分权威版本与汇总，检查失效引用 | 参考库维护候选；已有目录可增量核查，不另建导航真源。 |
| [dbs-content-system](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-content-system/SKILL.md) | 将可复用内容与来源、关系、去重和处理状态关联 | 参考库维护候选；不按文件数量触发重建或复制外部全文。 |
| [dbs-human-dispatch](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-human-dispatch/SKILL.md) | 以证据验收实际交付，区分派出、接单与完成 | 不纳入写作基座，不引入人员派单与通知。 |
| [dbs-skill-maker](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-skill-maker/SKILL.md) | 入口轻、参考分层，按可观察失败改规则 | 与现有Skill维护原则一致；应以真实改稿验证候选方法。 |
| [dbs-install-skill](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-install-skill/SKILL.md) | 跨宿主建立链接并处理重复入口 | 安装能力，不属于中文表达，本次不调用。 |

补充查看的两个入口不并入上述34项：

| 额外入口 | 与本项目的关系 |
| --- | --- |
| [dbs-agent-migration](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-agent-migration/SKILL.md) | 强调规则真源与宿主入口分开；现有仓库Skill与全局链接已有这种关系，不迁移。 |
| [dbs-update](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-update/SKILL.md) | 官方工具箱更新维护；不是文风方法，不执行。 |

## 值得借鉴的方法及落点

### 先检查判断能否成立，再寻找理论

`dbs-theory-grounding`值得保留的是这个先后关系。对本项目而言，增量在研究和立论阶段：事实可用但解释过强时缩小解释，判断无依据时撤下，不把寻找名人理论当成替原判断背书。

建议落到基座“材料先整合，再组织正文”的研究边界。现有规则已保护事实与判断强弱，只需补清处理顺序；仅润色任务仍不授权改观点。理论不提供新增解释时可以不用，不能要求每篇评论都配理论。

### 关键因果判断要能与另一种解释区分

`dbs-good-question`将解释与可观察信号关联，适合补强基座中“相关不等于因果”的执行方法。核心判断依赖某个原因时，内部检查有没有另一种同样符合现有材料的解释，以及还缺什么资料才能区分。

例如，把家长不报名某项服务归因为“教育焦虑”前，价格、接送时间或服务内容也可能解释选择。这是待核的研究分支，不是可以直接入稿的三个真实原因。只在会改变主要结论的位置使用，不要求每段列反方或编反例，也不把内部问答变成正文结构。

### 比较案例时写出相同机制和足以使比较失效的差异

`dbs-standard-answer`提供的比较角度可用于公众号案例索引：主体面对什么约束、采用什么办法、承担什么代价、结果能否比较。已有索引按任务选例，但“同样讲教育”仍可能掩盖对象差异，适合补一个实际对照示例。

写法参照与事实论据要分开：借鉴一篇文章的推进方式，不等于它证明新稿的机制成立。失败案例和反例在检验关键推断时有用，不必每篇凑齐；多个相似故事本身不能确立因果或成熟共识。这一项放公共Skill参考页，基座不收整套历史研究流程。

### 先确定文章的主要用途，再决定怎样修改

`dbs-resonate`把修改指向具体文字，`dbs-content-value`关注读者从内容中获得什么。可用于公众号行文审稿：这篇主要帮助理解来龙去脉、辨清争议、比较选择，还是完成用户另行指定的传播任务？删改要能说明怎样服务这一用途。

这不要求每篇只准有一个判断，更不要求每篇都促成行动。对纯评论，增加理解和判断依据就可能完成任务。原文已有主线与用途记录，不必新设共鸣评分或单独审稿角色；“删除、压缩、强化、保留”可作实际修改的分类。

### 将文本依据、读者反应假设与真实反馈分开

`dbs-spread`在这点上较有参考价值。公众号稿里某段明确写了家庭支出，是文本事实；某类家长可能关心它，是推测；读者实际怎样理解，则需要真实反馈支持。这三种依据不能互相替代。

建议放在公众号审稿和运营复盘的边界，不增加“读者会共鸣”的通过结论。现有普通读者角色已标明模拟性质，后续只需把假设怎样被真实阅读、评论或数据修正记清，不给模拟反应冠以验证结果。认同、收藏和分享也不视为同一件事。

### 案例库记录使用与反馈，不只积累篇目

`dbs-content-system`的来源、关系与处理状态值得借鉴，`dbs-knowledge`强调导航之后仍要读取原始资料。落到现有库，最小改进是给实际采用过的卡片记关联稿件、借鉴动作、出现的问题与用户具体反馈，而非另建一套内容工程。

这些是本项目的轻量适配建议：读过、拆解过、在稿中用过、经反馈修正过，不是同一状态。使用次数不等于验证有效；某篇写法被采用，也不等于用户认可原文观点。样本反馈稳定后再判断是否补索引或改规则，不默认拆成大量原子文件。

## 已覆盖的内容不再重复加规则

- `plain-writing`中的语义保护，与基座现有主体、指代、条件、否定、承诺强度和局部修改边界基本一致。它的[标准依据说明](https://github.com/dontbesilent2025/dbskill/blob/main/skills/dbs-plain-writing/references/standard-and-scope.md)明确区分英语技术标准与中文编辑适配；没有理由再为中文评论设置字数上限。
- `deconstruct`和`goal`中的语义作用检查，可补入现有语境诊断案例。例如术语删后仍通顺，不代表概念范围、办理条件或承诺未变。标准已有，不再另立一份术语流程。
- `script-flow`的逐段交界与冗余检查已有对应审稿记录；缺的若是事实或因果依据，添一句过渡不能修复。口播长度、拍摄方式及标记式改稿保留为视频或特定交付问题。
- `ai-check`中对虚构读者、反复翻转、段段收束等问题的提醒，基座已有相应诊断。可以比较具体案例，不再增加一套“AI味”判定标准。

## 不采用的要求

| 外部方法中的要求或倾向 | 本项目的取舍 |
| --- | --- |
| 用过分光滑、均匀或毫不犹豫判断AI痕迹，按次数或字数处理 | 只能定位待查处。自然与准确不靠制造卡顿、犹豫、跑题或删掉一半连接词来证明。 |
| 检出问题后逐条追问、逐条等待，再决定是否改写 | 已有明确改稿授权和偏好时直接完成；不会整套移植这种交互方式。 |
| 说明文第一段直接定义对象，沿固定信息顺序展开 | 适用于部分说明任务，不替代评论、观察或叙事的组织。 |
| 以商业产品、成交或利润为内容判断的共同前提 | 公众号的公共评论和知识解释有自身用途，不能默认转为销售文案。 |
| 对标尽可能一致地复刻 | 现有方法比较组织动作及适用条件，不复制表达、人物经历和商业立场。 |
| 给每篇套主理论、候选评分、历史矩阵或固定数量 | 研究量按当前判断需要决定；没有解释增量就不用。 |
| 以模型记忆默认完成专业理论、人物言论或案例核实 | 可以作线索，不能替代本项目当前来源要求；确切出处、争议及高风险主张按现行取证规则处理。 |
| 用目录、节点和全量加工门槛重新搭建资料工程 | 本库已有有效入口，先补使用反馈，不为规模另建真源。 |

## 建议实施范围

若后续采用，基座只补“判断先于理论”和“核心因果的替代解释检查”两项简短操作。公众号公共Skill参考页补案例比较与受众用途示例，沿用既有审稿。案例库再为实际用到的卡片增量记录稿件关联和反馈，不批量重写全部卡片。

第一次验证应使用真实改稿：观察新增方法是否改变了判断范围、补出了缺失依据，或撤掉了不适配的类比。若只是多了表格、术语和检查文字，没有改善当前稿件，就不增加全局规则。

评估阶段交付到方法取舍，未安装DBS Skills，未执行其更新、迁移或派单。外部内容只作有出处的方法参照，原文规则未被当作本项目指令执行。

## 用户确认后的落地位置

2026-10-26按用户确认的上述范围实施：两项共通方法写入[基座的材料处理](中文写作基座.md#材料先整合再组织正文)；案例机制比较接入[原选例与提纲记录](../../.cursor/skills/wechat-mp-article/references/external-article-cases.md#从参考进入当前提纲)；按用途删改与阅读反馈的区分并入[既有审稿](../../.cursor/skills/wechat-mp-article/references/review.md)；实际应用的积累入口设在[案例使用与反馈记录](外部文章参考库/使用与反馈记录.md)。各处只维护所属方法，本评估保留取舍依据，不作为第二份执行规则。
