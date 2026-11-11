# 妙想股票工作台 Implementation Plan

> 在当前任务内顺序执行，复用现有脚本，不新增算法或运行服务。

**Goal:** 创建可直接触发的统一选股、个股分析与板块研究 Skill。

**Architecture:** 仓库保存编排文档；用户技能目录安装官方依赖并链接编排入口；本地规则与外部报告分别保留来源。

**Tech Stack:** Markdown、YAML、既有 Python CLI、python-dotenv。

## Global Constraints

- 中文、无 emoji；密钥只从 `.env` 读取。
- 不改变本地策略阈值、不启用 LIVE、不自动下单、不安装定时任务。
- 不读取或调用已弃用的东财八维/十一维 SOP。

## 实施步骤

- [x] 创建 `.cursor/skills/miaoxiang-stock-workbench/SKILL.md`、`agents/openai.yaml` 和三个参考文档：路由与证据规则、命令、输出与验收。
- [x] 安装六项已选官方依赖；保存来源版本和哈希，清除预填 Key，补充本机加载方式。业绩点评保留三步入口。
- [x] 将新入口链接到 `~/.codex/skills/miaoxiang-stock-workbench`，不覆盖已有同名目录。
- [x] 运行 Skill 校验、依赖 CLI 帮助、文档链接及密钥扫描；逐项走查输出文档中的验收案例。
- [x] 实测公开热点查询；准确区分已实测接口、仅验证入口的接口和未执行的本地选股。发现上游日期冲突，加入排除与回源核验规则；详见 Skill 的验证记录。
