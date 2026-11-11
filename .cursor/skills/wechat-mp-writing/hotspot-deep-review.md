# 热点深评（hotspot）专题

用于社会、文娱、职场、公共事件及本页限定的教育热点。先读[中文写作基座](../../../docs/writing/中文写作基座.md)，再执行[公众号通用 Skill](../wechat-mp-article/SKILL.md)；本页只维护专题差异。账号观察角度按仓库入口加载，不复制其角色卡。

## 稿型定位

| 项目 | 当前要求 |
| --- | --- |
| 内容 | 以同题公开事实为依据的非虚构随笔；主笔任务与审稿按基座，不将“展开处境、阐明意义”预设为全文结构 |
| 篇幅 | 用户未另定时以900—1100字为篇幅参考；约数服从材料，不能用解释补足字数。明确硬性字数按要求执行；旧工程门槛另行核对，缺口如实记录 |
| 正文格式、语气、审稿、标题和默认配图 | 直接调用通用 Skill 对应入口，本页不另设模板 |
| 新闻写法 | [news-report-craft.md](news-report-craft.md)：选择新闻点、导语和背景位置 |
| 评论材料 | [news-commentary-structure.md](news-commentary-structure.md)：评论池与入稿取舍 |
| 关键主张及费用政策 | [editorial-evidence-gate.md](editorial-evidence-gate.md)：来源核验与交付字段 |
| 用户指定 DeepSeek | [deepseek-writer-sop.md](deepseek-writer-sop.md)，不默认走该交接 |

仅选题时提供候选，不启动全文、配图或推送。本文不修改生产代码、评分程序和定时状态。

### 用户近期选题偏好：四城教育政策与升学规则

人工教育候选限北京、上海、广州、深圳及各自辖区，不扩为广东全省；在展示候选前过滤。全国政策须有四城之一的实施通知、执行案例、收费标准、办理安排或家庭账单变化作主体；仅说可能影响当地家庭不够。无法确认发生地的材料不入选。

地域通过后，依次优先家庭费用及退费、入学择校与升学、托管接送、校园服务及其他有明确家庭影响的教育新闻。优先主管部门正式文件和当地实施报道；普通校园纠纷、师生私德、鸡汤或仅由专家个人意见支撑的题目，不因热度入选，除非确有制度问题。

每个候选记城市、发布主体、发布和事件日期、原始材料、适用人群、家庭成本、实际关注证据、讨论角度和事实风险。按热度、家庭相关性、政策确定性及评论空间筛选，不用焦虑标题代替依据；旧通知不当新规。

#### 教育费用政策优先

用户提供过退费稿表现较好的运营观察，但尚无同口径后台验证，不据此承诺流量。选题优先找实缴、减免、退费等具体规则及变化，不重复没有增量的旧题；时间与接送题仍保留。

费用、范围、园校性质、时间口径、测算假设和例外，统一由[费用核验](editorial-evidence-gate.md#教育费用稿重点核对)维护。本条只影响人工排序，不改自动评分。

#### 北上广深择校专题

涉及义务教育或高中选校、学区、幼升小、小升初、积分入学、公民同招、学校比较时，加读[school-choice-policy.md](school-choice-policy.md)。高考志愿仍按考试与志愿专题；普通教育新闻不额外加载择校规则。

### 用户选题偏好：专家建议与普通人现实的落差

候选可留意与就业、退休、生育、消费、住房、养老、教育有关的专家建议，不限定配额。先核原始时间、身份、完整原话与语境；区分个人建议、机构研究和已发布政策。找不到可靠原话不推荐，旧话不冒充新建议。

角度落在可行前提、配套和普通人的时间、金钱、尊严、选择成本上。可肯定或批评具体建议，不为吐槽预设专家全错，也不用人身标签。候选说明主张、关注证据、影响人群、现实落差及成稿条件。

## 用户主动成稿入口

按通用 Skill 完成取证、结构、分段回读和审稿。本题另外读取[证据门禁](editorial-evidence-gate.md)，按需要查新闻或评论方法，不把全部参考当必读。

编辑稿先记录 `title`、`digest`、`body`、`topic`、`article_mode`、`research_urls`；随笔用 `narrative_focus` 记录叙述线索，论证稿确有主张时记录 `original_thesis`。这属于编辑交接，不宣称旧工程已支持这些差异。旧推稿入口仍可能要求三个来源域及不少于20字的判断字段，按证据门禁记录兼容状态，不为满足字段创造论点或添无关材料。内容审定与工程可推送分别记录。

新用户主动工作流同时准备 `editorial_handoff.json`，关键主张与编辑判断字段见证据门禁；不以内部标签代替公开正文。指定DeepSeek才用其交接，不操作其浏览器、账户或会话。写稿与后续推送范围由用户授权决定，不从旧说明推导额外确认阶段。

## 联网取材（社会热点核心）

先收集同题公开报道、原始文件、回应及实际评论，再按基座整合。自动兼容链路使用 `fetch_discussion_research`；人工研究直接记录实际来源与阅读范围，不为满足函数名重复取材。风格参考不是证据，转载不算独立印证，具体见证据门禁。

## 配图（当前默认与真实视频分支）

默认来源选择只见[通用 Skill](../wechat-mp-article/SKILL.md#5-标题配图与手机排版)：艺术封面与正文真实场景图。用户要求原报道画面或内容确需资料图时，按[真实视频截帧](../wechat-mp-article/references/real-video-stills.md)执行。停止抖音搜索，不生成虚假的 `douyin-search.json`；评论与生成图不作新闻事实证据。

工程记录继续保存 `figure_sources.json`，真实视频分支保留原报道、视频、年代、截取位置和实际看图结果。新配图协议若与旧工程“必须真实封面”等校验冲突，如实报告未满足，不伪造来源或绕过门禁。

## 改稿检查清单

表达和审稿操作只执行通用 Skill，不在专题重列语法、承接和轮次。专题追加检查仅为：

- 标题、导语、关键数字以及正文实际提出的判断，可回到原始材料；当事方声明未被写成中立调查结论。
- 地区、学段、园校性质、费用类别、年份和统计口径一致；测算有明确假设。
- 存在论证时核论据和实际异议；所有稿型都不为制造冲突删掉已有配套或不利事实。
- 公开稿与 `editorial_handoff.json` 对应；文字通过不等于工程通过。

### 新闻组织与叙事检查

只在需要选择或调整新闻结构时查[新闻方法](news-report-craft.md)。

### 中文语法与上下文承接（必查）

统一调用[基座](../../../docs/writing/中文写作基座.md#句法分析与表达检查)和[公众号审稿](../wechat-mp-article/references/review.md)，不另设专题动作表。

### 转述价值检查（人工编辑项）

热点稿的信息与判断应有明确对象和依据，具体评论组织见[评论取材](news-commentary-structure.md)。传播表现留待同口径观察，不将钩子数量或金句配额当人工门禁。

### 事实与编辑判断检查（人工项）

只执行[证据门禁](editorial-evidence-gate.md)，不重复建立另一份事实表。

## 标题路牌与结尾

标题策划和兑现见[公众号钩子适配](../wechat-mp-article/references/content-hooks.md)。标题按本篇实际内容与用户要求选取；已证实的风险、费用或冲突可以入题，不强制所有热点稿制造风险、疑问或读者痛点。标题中的具体承诺仍须兑现，不用夸大后果或公文摘要替代内容。用户已定标题按其要求保留。

文末按[公共交付规则](../wechat-mp-article/references/delivery.md#文末自然结束)自然结束，不再加问号钩子或评论邀请。

## 排版（移动端）

人工排版只执行[delivery.md](../wechat-mp-article/references/delivery.md)，按实际意思形成手机可读的自然段，不另设每段句数、行数或判断配额。下文旧重排程序的130字行为只作兼容记录，不反过来规定主笔段落。

## 公开文案门禁（现有工程行为）

`wechat_mp_hotspot_quality_gate.py` 在stage与push执行检查，push检查发生在上传图片和微信接口之前。现有两层行为：

1. 阻断项：过程指令泄漏、固定营销词、无权威来源的绝对政策范围、标题数字未兑现、完全重复段落、残留Markdown标题或清单。
2. 评分项：核心判断、三个来源域、首段实体、前1/3普通人影响、反方或边界、具体结尾问句（评论钩子）、移动端段落，共7项至少5项。

上述评分项仅描述旧工程行为，不是主笔或人工审稿要求，不传入起稿委托。按当前规则不加评论钩子，也不为评分项预设中心判断、反方或段落任务。分数不能代替人工事实或文体验收，不改代码绕过失败；未满足记录原因。

```bash
cd stock-ai
.venv/bin/python -m scripts.tools.wechat_mp_eval --user-hotspot-article <成稿JSON>
```

该命令只读预检，不推送。用户明确要求推草稿后，按 `wechat-mp-drafts` 的当前暂存与回读入口处理，不能改用下列自动批次命令绕过用户主动稿交接。

## 旧自动链路与兼容信息

本节描述历史代码，不是当前人工工作流，也不代表定时正在运行。旧热点定时已暂停；本次文档整理不改变实际调度。旧槽位为 `hotspot_early`、`hotspot_morning`、`hotspot_afternoon`、`hotspot_evening`，原批次时间为09/11/15/18。

历史链路：双榜选题 → `fetch_discussion_research` → 旧LLM生成/仿写 → `reflow_hotspot_layout` → 配图门禁 → 草稿。未传 `--codex-draft` 的兼容LLM为Composer，不经DeepSeek API；旧重排仍可能按≤130字拆合段，旧图片校验可能要求真实封面。它们不覆盖本页人工要求。

### 推稿命令（旧自动批次）

```bash
cd stock-ai
export WECHAT_MP_HOTSPOT_TREND_ENRICH=0
uv run python -m scripts.tools.wechat_mp_draft_batch --batch hotspot_afternoon --no-notify
uv run python -m scripts.tools.wechat_mp_push_quality_gate --kind hotspot
uv run python -m scripts.tools.wechat_mp_eval --kind hotspot --traffic
```

仅维护或获授权执行旧自动任务时使用；用户主动稿不走这组命令。

## 环境变量

| 变量 | 历史默认 | 兼容含义 |
| --- | --- | --- |
| `WECHAT_MP_HOTSPOT_SOURCE` | `trends` | 微博+百度选题 |
| `WECHAT_MP_DISCUSSION_RESEARCH` | `1` | 同题报道取材 |
| `WECHAT_MP_HOTSPOT_TREND_ENRICH` | `0` | 社会稿保持0，避免混入旧东财盘面数据 |
| `WECHAT_MP_HOTSPOT_IMITATE_REWRITE` | `0` | 旧二次仿写开关 |
| `WECHAT_MP_HOTSPOT_SOCIAL_FIGURES` | `1` | 旧社会稿配图 |
| `WECHAT_MP_HOTSPOT_REQUIRE_FIGURES` | `1` | 旧真实图校验，不覆盖新默认来源 |
| `WECHAT_MP_DISCUSSION_BODY_FIGURES` | `3` | 旧正文图片上限 |
| `WECHAT_MP_DISCUSSION_FIGURES_FORCE` | `0` | 强制重抓旧素材 |
| `WECHAT_MP_HOTSPOT_TOPIC` | 未设 | 手动定题 |
| `WECHAT_MP_LLM_MODEL` | `composer-2.5` | 旧兼容LLM |
| `WECHAT_MP_CURSOR_MAX_RETRIES` | `1` | 旧LLM重试 |
| `WECHAT_MP_CURSOR_TIMEOUT_SECONDS` | `420` | 旧LLM超时 |
| `WECHAT_MP_HOTSPOT_MIN_BODY_SLACK` | `80` | 旧2000字门禁容差，不用于人工稿 |
| `WECHAT_MP_QUALITY_GATE_STRICT` | `1` | 现有门禁开关，不为人工稿绕过而改 |

## 故障排查

| 现象 | 处理 |
| --- | --- |
| 旧链路未达2000字 | 区分自动/人工入口，不将该旧阈值套到人工稿 |
| 新配图与真实封面校验冲突 | 保留真实记录，如实标记工程未满足，不伪造来源 |
| 文末误入财经复盘口吻 | 查 `_NO_RECOMMEND_HOOK_KINDS` 与实际稿型，不改写正文迎合误注入 |
| 低分或短稿 | 区分人工文章问题与旧fallback，不用分数替代文章判断 |

## 附录：财经热搜分支（少见）

历史 `fetch_hotspot_research` 盘面分支只供代码溯源，不是股票研究数据授权。涉及股票时先走当前妙想六Skill路由，不调用旧来源补数。

## 交叉引用

自动代码映射见 `wechat-mp-drafts/rules-implemented.md`；旧评分见[eval-gates.md](eval-gates.md)。写作方法的历史来源记录仍保留在[新闻技巧](news-report-craft.md#来源与采用范围)、[评论方法](news-commentary-structure.md#来源与适配)；未在本次整理中重新访问外部材料。
