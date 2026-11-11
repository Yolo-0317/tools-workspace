---
name: miaoxiang-stock-workbench
description: 基于本工作区 V1.3 买点优先选股、新版个股诊断与东方财富妙想数据的 A 股研究工作台。用于每日选股、候选复核、个股综合分析、持仓分析和板块机会研究。统筹本地交易资格与妙想热点、资金、消息、业绩和机构观点。单纯查股价、单条新闻或宏观指标时直接使用对应妙想基础技能，不启动完整选股流程。
---

# 妙想股票工作台

## 入口与加载顺序

1. 用 `project-registry/projects.json` 或工作区 preflight 定位 `stock-ai` 和 `a-share-short-term-trading`。本机根目录是 `/Users/huan.yu/dev/tools-workspace`；不要使用旧文档里的 `/Users/yolo/...`。
2. 阅读 `stock-ai/docs/PROJECT_LAYOUT.md`、`a-share-short-term-trading/README.md` 的当前选股/诊断章节。读项目 Memory 短索引后，只搜索本次需要的专项条目。旧选股 Skill 的 `combined` 默认入口已落后于 V1.3，不能覆盖当前入口。
3. 按 [工作流](references/workflows.md) 选择每日选股、个股分析、板块研究之一。依赖命令见 [命令表](references/commands.md)。只读将要调用的子 Skill，不一次加载所有子 Skill。
4. 涉及具体仓位、加减仓或持仓时，再读投资 Agent 的 `AGENTS.md`、当前 `投顾主策略.md`、执行卡及授权范围内的账户事实。普通公共行情研究不加载个人持仓。最终按 [输出与验收](references/output-and-checks.md) 交付。

## 核心约定

- 本地引擎决定形态、正式资格、排序、条件计划、股数、规则版本与运行模式。默认沿用原命令，不能为了得到买入结论添加 `--release-mode LIVE`、`--portfolio-approved` 或人工股数。
- 妙想是数据与外部研究来源。报告中的“看好”、主力流入、目标价不能授予交易资格；主力资金统计也不等于真实主力账户持仓。
- 官方专项报告保留原文并链接。工作台另列本地判断和证据核对，不改写上游报告冒充原文，不把多份模型报告的一致意见当成独立证据。
- 不把未验证的妙想文本写入本地点时风险表、概率校准、持仓、监控规则或决策账本。现有选股/诊断脚本正常产生的计划和采集记录依其原流程保存。
- 新发现重大利空时，即使本地尚未收录，也不继续建议执行；标记“新增风险待复核，暂缓执行”，保留原始资格结果供追溯。反向的外部利好不能解除本地否决。
- “每日”是用户按需调用的日度流程；只有用户另行要求才设计调度。创建本 Skill 不授权发消息、创建订单或自动刷新持仓。
- AI 不调用、推荐、读取已弃用的东财八维/十一维 SOP 正文。

## 十项妙想依赖

目录：`/Users/huan.yu/.codex/skills/<名称>/SKILL.md`。运行前检查实际存在；缺失时明确降级，不假装执行。

| 名称 | 用途 |
|---|---|
| mx-finance-data | 行情、财务及估值数据 |
| mx-finance-search | 有明确对象的公告、新闻、研报原文检索 |
| mx-stocks-screener | 条件筛选、补充观察名单 |
| mx-macro-data | 明确指标的宏观背景，非每日必跑 |
| stock-market-hotspot-discovery | 市场热点发现 |
| industry-sector-analysis | 指定板块的驱动与风险 |
| stock-capital-analysis | 单只 A 股资金面专项 |
| stock-news-analysis | 单只 A 股消息面专项 |
| stock-earnings-review | 已发布报告期的业绩点评 |
| stock-institutional-opinion | 单只 A 股机构观点专项 |

专项子 Skill 有严格意图边界。不能把用户只问技术形态的任务强制改成资金分析；每日流程默认用基础查数和资讯搜集证据，专项解读按明确需求调用。业绩点评必须完成实体识别、报告期确认和点评三个步骤。

新增六项依赖的官方来源、版本和文件哈希见 [来源清单](references/upstream-manifest.json)。安装及真实接口验证范围见 [验证记录](references/verification.md)。

## 可以直接这样提问

- “用妙想工作台做今天的选股，说明入选和拒绝原因。”
- “综合分析东方财富，重点看买点、资金和公告风险。”
- “分析半导体板块的驱动，再看看本地有没有符合条件的股票。”
- “看东方财富最新一期财报和机构观点，不给交易建议。”
