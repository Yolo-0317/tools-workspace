# 非妙想股票 Skill 暂停记录

日期：2026-09-16。依据用户“只保留基于妙想的 skill，其他股票相关 skill 先下线”。

## 当前保留

`miaoxiang-stock-workbench`（纯妙想）以及十项官方妙想子技能：mx-finance-data、mx-finance-search、mx-stocks-screener、mx-macro-data、stock-market-hotspot-discovery、industry-sector-analysis、stock-capital-analysis、stock-news-analysis、stock-earnings-review、stock-institutional-opinion。

## 下线方式

四项非妙想入口已将 `SKILL.md` 改名为 `SKILL.disabled.md`，防止技能发现；原目录保留禁止调用的 ROUTING.md。精确路径见 `disabled-skills.json`。包括 stock-opencli、stock-strategy-selector、eastmoney-browser-sop、a-share-stock-diagnosis（QClaw 分享包）。

股票项目注册表、根 AGENTS 与 Memory 路由已改为妙想。公众号入口保留在公众号内容分析 SOP，不引用已停用的股票 Skill。

原工作台全量副本在 `workbench-before-miaoxiang-only/`，入口也改名，不能自动调用。代码、数据库、MCP 服务、已部署副本及已有调度均未停用。本次不宣称撤回其他机器已经安装的分享包。

## 恢复

只有用户明确要求恢复时，按清单将指定 `SKILL.disabled.md` 改回 `SKILL.md`，并恢复必要的项目注册表与路由。旧东财八维/十一维另有独立的弃用禁令，不能因恢复文件名而解除。恢复旧工作台前对比归档与当前文件，不整体覆盖用户后续修改。
