# tools-workspace

个人工具 monorepo：`stock-ai`、`sidestore-infra`、`substore-clash`、`english-buddy`、`xiaozhi-*`、`harryputter` 等。

## 必须遵守

- 用户可见内容、UI 与汇报禁止 emoji。
- 先用 `project-registry/projects.json` 或 `scripts/workspace_preflight.py` 定位项目，再读项目入口文档。
- 再读 `.cursor/rules/project-memory.mdc` 的短索引；用 `rg` 在命中的 **一个**专项 Memory 中定位相关条目。不要整份加载任何 `memory-*.mdc`。
- 跨项目稳定知识先查 `docs/wiki/`；`draft`、过期或涉及当前外部状态时必须回源。
- 新功能先做简短设计和计划；修改后运行最相关的验证。
- 不提交 `.env`、证书、订阅链接、持仓或个人记忆。
- 复杂流程可用 Superpowers；其规则在 `.cursor/rules/superpowers.mdc`。

## 中文表达中的语气与承接

- 中文交流、创作与表达修改统一执行[中文写作基座](docs/writing/中文写作基座.md)。新写、重写或系统润色先读基座，再按路由读取专题和相关用户正例；局部修改只查受影响上下文。
- 内容表达要直接、态度鲜明，写清具体判断和读者在意的问题；标题不擅自降成温和科普，正文不靠空话制造冲突。选材、标题和逐段回读执行基座的[直接表达与鲜明态度](docs/writing/中文写作基座.md#直接表达与鲜明态度)。
- 不以套话平衡已有判断，不主动预判读者质疑或追加免责声明。文体、叙述线索、判断形成和必要解释统一按基座处理；不再要求所有文章选择阵营、证明唯一结论或套固定作者人格。事实与专业边界仍按对应专题核对。
- 基座是通用规则唯一真源，已整合自然语气、默认叙述身份、材料取舍、隐含回答节奏、分段loop及Humanizer-zh编辑边界。后续只在基座改共通要求，各Skill与账号SOP保留引用和自身差异，不再逐处同步。
- 财经、健康、广告、虚构、口播与技术文档的证据、角色、格式和交付限制继续由专题负责；不要把一种题材的口吻、审稿人数、画面或发布规则扩到所有写作。

## 项目路由

股票 Skill 当前仅启用妙想系列。选股、个股分析与板块研究统一进入 `.cursor/skills/miaoxiang-stock-workbench/SKILL.md`。非妙想股票 Skill 已暂时下线；不得按历史 Memory、旧文档或归档副本重新调用。下线范围与恢复清单见 `docs/skill-archive/2026-09-16-stock-skills/README.md`。旧程序和已有调度未停用，但不再作为股票 Skill 的默认执行后端；代码维护任务仍按项目入口处理。

不确定子项目时先运行：

```bash
python3 scripts/workspace_preflight.py --project <project-id> --risk normal
```

| 任务 | 先读 |
|---|---|
| A 股、MySQL、选股、公众号工程 | `stock-ai/docs/PROJECT_LAYOUT.md` |
| 股票选股、个股分析、板块研究 | `.cursor/skills/miaoxiang-stock-workbench/SKILL.md` |
| 公众号后台抓取 | `.cursor/skills/wechat-mp-drafts/content-analytics-sop.md` |
| 酒类视频、火柴人酒类动画、酒类配音 | `docs/alcohol-video-sop.md`；默认使用已确认的北京口音男声，提示词与声音资产按该 SOP 加载 |
| SideStore、Caddy、DDNS | `sidestore-infra/README.md` |
| Sub-Store、Clash | `substore-clash/README.md` |
| 英语带读、ORT | `english-buddy/docs/ORT_READ_ALONG.md` |
| 小智固件或 Mac 网关 | `xiaozhi-atoms3r/README.md` 或 `xiaozhi-mac-server/README.md` |
| 哈利波特导入/对齐 | `.cursor/skills/harryputter-import/SKILL.md` |
| 夸克网盘 | `.cursor/skills/quarkclouddrive/ROUTING.md` |

用户说“公众号”默认指「牛马也智能」。先读 `.cursor/skills/wechat-mp-drafts/SKILL.md` 的决策树；写作/质检只再读命中的一个专题文档。简选带货仅在用户明确要求时处理。

用妙想数据写 A 股盘后公众号文章、逐句去 AI 味并生成手机排版时，进入 `.cursor/skills/miaoxiang-market-review-article/SKILL.md`；选股、诊股和板块研究仍走妙想股票工作台。

Docker 开机自启说明见 `scripts/install-docker-launchd.sh` 与各子项目 README。

2026-09-17 历史用户更新（已被2026-09-20仅Skill数据源要求覆盖）：妙想工作台的历史日线默认改用原Tushare及其stock_daily库，允许日线读取和必要同步；妙想保留预筛与研究能力。此例外不恢复任何已下线的股票Skill或旧选股执行后端。

2026-09-20 用户更新：卸载此前十个妙想技能；股票工作台仅整合 mx-data、mx-search、mx-xuangu、mx-zixuan、mx-moni、mx-poster 六个技能。V3规则保持；当时的Tushare日线安排已被下述最新要求覆盖；旧专项分析改为查数与搜索证据综合，不调用归档技能。自选、模拟账户与真实持仓必须区分，研究不自动触发交易或社区发布。

2026-09-20 最新用户要求：股票研究数据仅通过 mx-data、mx-search、mx-xuangu、mx-zixuan、mx-moni、mx-poster 六个妙想 Skill 获取，覆盖并撤销此前 Tushare/stock_daily 读取与同步例外。不直接调用东财旧接口、网页抓取、浏览器行情采集、其他行情源或通用网页搜索补数。V3公式保留；仅在当前六技能来源的日线完整性、复权、单位及适配经过验证后计算，缺项标记未完成，不回退旧来源。
