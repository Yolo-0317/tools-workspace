# Tools Workspace 母舰治理层设计

## 目标

为 `tools-workspace` 建立轻量、可检索、可验证的仓库级治理层，让人和 Agent 能快速回答以下问题：

- 工作空间有哪些子项目，各自处于什么生命周期；
- 一个任务应该进入哪个子项目，先读哪些文档、Memory 或 Skill；
- 子项目之间有哪些数据、服务和部署依赖；
- 哪些知识可以直接引用，哪些已经过期或必须回源验证；
- 一次改动应运行哪些最小验证，是否误带敏感文件或失效路径。

第一阶段只优化仓库治理、上下文路由和文档入口，不重构子项目业务代码，不移动历史目录，不改变已有服务、调度或生产权限。

## 设计原则

1. **本地优先**：普通项目定位和稳定知识查询只读本地文件，目标是秒级完成。
2. **事实分层**：README 是入口，项目注册表是结构化目录，Wiki 是稳定知识召回层，Memory 是经验与陷阱，业务数据和线上系统仍是实时事实源。
3. **按需上下文**：默认规则只保留短索引与路由原则，不全量注入长期记忆、Wiki 或子项目 README。
4. **只读预检**：preflight 只输出建议和检查项，不启动服务、不写生产、不替用户确认高风险操作。
5. **渐进治理**：先标注生命周期和依赖，不急于拆仓、搬目录或提取大型共享包。
6. **零新增运行时依赖**：治理脚本使用 Python 标准库；不引入数据库、向量库、RAG 框架或常驻服务。
7. **保护现有工作**：实施时只提交治理范围文件，不夹带当前 `stock-ai` 和公众号 Skill 的未提交修改。

## 方案比较

### 方案 A：只更新 README

优点是改动最小、交付最快。缺点是信息不可可靠地供脚本读取，状态、路径和依赖很快再次漂移，也无法支持 preflight 或自动校验。

### 方案 B：轻量母舰治理层（采用）

增加结构化项目注册表、本地 Wiki、只读 preflight、静态校验和测试。它能复用当前 `.cursor/rules` 与 `.cursor/skills`，同时保持实现简单、透明、可审查。

### 方案 C：独立知识平台或 RAG 服务

可支持更复杂的语义检索和远程共享，但会引入部署、索引同步、权限和数据新鲜度问题。当前个人 monorepo 的规模不足以证明这些复杂度合理，因此第一阶段不采用。

## 信息架构

```text
tools-workspace/
├── README.md                         # 面向人的总入口与项目地图
├── project-registry/
│   ├── README.md                     # 字段、维护和事实源说明
│   └── projects.json                 # 机器可读项目注册表
├── docs/
│   ├── SERVICES.md                   # 端口、启动方式、反代和健康检查
│   ├── wiki/
│   │   ├── README.md                 # Wiki 状态机与回源规则
│   │   ├── templates/
│   │   │   ├── design.md
│   │   │   └── knowledge.md
│   │   └── workspace/knowledge/
│   │       ├── project-landscape.md  # 项目边界与生命周期解释
│   │       └── service-topology.md   # 稳定服务依赖关系
│   └── superpowers/
│       ├── specs/
│       └── plans/
├── scripts/
│   ├── workspace_registry.py         # 注册表加载、校验和查询
│   ├── search_workspace_wiki.py      # 本地 Wiki 确定性检索
│   ├── workspace_preflight.py        # 只读上下文与验证建议
│   └── validate_workspace.py         # 仓库级静态治理检查
└── tests/workspace_governance/
    ├── test_workspace_registry.py
    ├── test_search_workspace_wiki.py
    ├── test_workspace_preflight.py
    └── test_validate_workspace.py
```

`projects.json` 使用 JSON 而不是 YAML，原因是 Python 标准库可严格解析，避免为了一个小型注册表增加 PyYAML 或维护不完整的 YAML 解析器。README 和 Wiki 负责保持人类可读性。

## 项目注册表

注册表覆盖当前 17 个业务或实验子项目，不把 `.cursor`、`launchd`、`scripts`、`docs` 计为子项目。每项包含：

```json
{
  "id": "stock-ai",
  "path": "stock-ai",
  "domain": "investment",
  "summary": "A 股数据、选股、监控、投资 Agent 与公众号内容工程",
  "lifecycle": "core",
  "entry_docs": ["stock-ai/README.md", "stock-ai/docs/PROJECT_LAYOUT.md"],
  "depends_on": ["stock-mysql", "wechat-cursor-acp"],
  "serves": ["home-hub"],
  "memory_topics": ["stock-ai", "wechat-mp"],
  "skills": ["stock-opencli", "wechat-mp-drafts"],
  "verify": [],
  "runtime": {"kind": "mixed", "ports": []},
  "aliases": ["A 股", "选股", "公众号"]
}
```

允许的生命周期为：

- `core`：核心业务或基础设施；
- `active`：持续维护的产品或研发项目；
- `incubating`：边界尚在验证的新项目；
- `tooling`：独立工具或实验环境；
- `legacy`：已被替代，仅保留历史价值；
- `offline`：已明确下线，不应进入日常调度。

首批生命周期采用以下确定映射：

- `core`：`stock-ai`、`stock-mysql`、`home-hub`、`wechat-cursor-acp`、`sidestore-infra`、`substore-clash`；
- `active`：`english-buddy`、`harryputter`、`xiaozhi-atoms3r`、`xiaozhi-mac-server`；
- `incubating`：`a-share-short-term-trading`；
- `tooling`：`cosyvoice-mac`、`ollama-hermes`、`openrouter-chat`、`sillytavern-mac`；
- `legacy`：`hp-readalong`；
- `offline`：`emquant-sim`。

第一阶段只登记能够从仓库文档确认的事实。无法确认的验证命令或运行端口使用空数组，不猜测、不填占位符。

## README 与服务目录

根 README 收敛为母舰入口，按以下顺序组织：

1. 工作空间定位与安全边界；
2. 五分钟开始：如何选项目、运行 preflight、进入对应文档；
3. 按领域分组的完整项目表；
4. 核心依赖关系；
5. 常用治理命令；
6. 历史项目和仓库外服务说明。

具体安装步骤、凭据说明和细粒度 SOP 保留在子项目 README 或 Skill，不复制到根 README。

`docs/SERVICES.md` 只记录可从仓库确认的稳定服务元数据：服务名、所属项目、监听端口、启动机制、反代入口类型、健康检查路径和直接依赖。它不记录公网订阅地址、token、账号或证书内容，也不声称服务当前正在运行。

## 本地 Wiki

Wiki 采用参考会话已经验证的两类页面：

- `design`：对设计、架构和跨项目链路的可追溯重组；
- `knowledge`：稳定结论、边界、不变量、例外和回源条件。

每个页面必须包含受限 Front Matter：

```yaml
title: 项目空间服务拓扑
type: knowledge
topic: workspace-service-topology
aliases: [服务地图, 端口地图, 反向代理关系]
tags: [workspace, infrastructure]
scope: workspace
status: confirmed
owner: workspace-maintainer
source: [README.md, sidestore-infra/README.md]
related_projects: [sidestore-infra, home-hub]
review_at: 2026-11-10
```

状态只允许 `draft`、`confirmed`、`archived`。只有 `confirmed` 且未超过 `review_at` 的页面可被检索结果标记为可直接引用；`draft`、过期和归档页面仍可返回，但必须明确要求人工确认或回源。

Front Matter 限定为扁平子集：字符串标量和单行方括号字符串数组，不支持嵌套对象、多行数组、锚点或自定义 YAML 类型。检索和校验脚本只实现这一明确语法，不声称支持完整 YAML。

第一阶段只创建两个仓库级知识页，不批量复制各子项目 README。注册表保存项目结构，Wiki 保存跨项目解释，避免形成两份相互竞争的事实源。

## Memory 与上下文预算

`.cursor/rules/project-memory.mdc` 保持全局可见，但收敛为短索引：工作空间速览、主题到目标 Memory/Skill/文档的映射，以及按需读取规则。历史通用条目迁移到非自动加载的 `.cursor/rules/memory-workspace.mdc`；现有 `memory-python.mdc`、`memory-infra.mdc`、`memory-english-buddy.mdc`、`memory-xiaozhi.mdc` 和 `memory-emquant.mdc` 保持按主题读取。

约束如下：

- 默认不自动加载任何完整 Memory 或 Wiki 页面；
- 单次任务最多按需读取一个专项 Memory，除非用户明确扩大范围；
- preflight 返回推荐路径，不读取正文；
- 生产状态、价格、调度结果、凭据和外部页面内容必须回源；
- 迁移前后保留原有记忆内容，不因瘦身丢失历史经验。

实施验收以行为为准：全局索引中不再携带详细历史正文，且所有原主题仍可通过索引定位。

## 只读 preflight

命令形式：

```bash
python3 scripts/workspace_preflight.py \
  --project stock-ai \
  --risk normal \
  --task "调整公众号热点稿输入" \
  --wiki-query "公众号"
```

输出支持文本与 JSON，包含：

- 项目摘要、生命周期和边界；
- 推荐入口文档、Memory 和 Skill；
- 依赖项目；
- 注册的最小验证命令；
- Wiki 命中及是否需要回源；
- 与风险等级对应的检查项。

风险等级为 `low`、`normal`、`high`。`high` 只增加人工确认、独立复核和生产回源提示，不自动执行这些动作。未知项目必须报错，不做模糊猜测。

## 静态校验

`validate_workspace.py` 聚合以下只读检查：

1. 注册表 schema、枚举、唯一 ID、路径和入口文档存在；
2. 注册表依赖引用有效且不能自依赖；
3. 当前 17 个顶层项目全部登记，登记路径确实存在；
4. Wiki 必填字段、状态、日期、唯一 topic、内部链接和项目引用有效；
5. 根 README 覆盖全部注册项目；
6. 被 Git 跟踪的文件不命中 `.env`、私钥、证书、移动配置描述文件等敏感路径规则；
7. 注册的验证命令只作为数据输出，不由校验器自动执行。

硬编码本机路径和 launchd 引用的深度检查放到后续阶段。第一阶段只修正文档中已经确认失效的旧路径，避免用宽泛正则造成大量误报。

## 测试策略

采用标准库 `unittest`，测试不访问网络、不启动服务、不读取未跟踪的敏感文件。

- 注册表测试：有效注册表、重复 ID、未知生命周期、缺失路径、无效依赖；
- Wiki 测试：中文/英文别名检索、状态与复审期、重复 topic、坏链接；
- preflight 测试：已知项目、未知项目、风险门禁、推荐内容去重；
- 聚合校验测试：README 覆盖、敏感跟踪路径、错误聚合和退出码。

测试先构造临时夹具验证失败，再实现最小功能使其通过。完成后运行：

```bash
python3 -m unittest discover -s tests/workspace_governance -v
python3 scripts/validate_workspace.py
git diff --check
```

## 实施拆分

本设计分为三个可独立验收的实施批次：

1. **注册表与入口**：项目注册表、注册表校验、根 README、服务目录；
2. **Wiki 与路由**：Wiki 契约、搜索、preflight、初始知识页；
3. **上下文瘦身**：Memory 内容无损迁移、精简索引、聚合校验与最终文档。

每个批次都应先写失败测试、最小实现、运行相关验证，再形成独立提交。若实施中发现某个子项目需要业务重构，记录为后续设计输入，不扩大本阶段范围。

## 非目标

第一阶段明确不做：

- 重构 `stock-ai`、English Buddy、小智等业务代码；
- 移动或删除 `hp-readalong`、`emquant-sim`；
- 改动 launchd、Docker Compose、Caddy 或线上调度；
- 自动生成或发布飞书文档；
- 建立向量库、Embedding、RAG 或独立 Wiki 服务；
- 自动执行注册表中的验证、启动、部署或生产命令；
- 提交 `.env`、证书、订阅链接、持仓或个人记忆。

## 验收标准

1. 17 个子项目全部在注册表中，生命周期、入口和依赖通过静态校验。
2. 根 README 能作为完整入口，不再遗漏实际子项目。
3. `workspace_preflight.py` 能对已知项目给出确定性的最小上下文建议，并拒绝未知项目。
4. Wiki 可用标题、topic、中文别名和英文标识本地检索；过期或非 confirmed 页面明确要求回源。
5. `project-memory.mdc` 只保留精简路由，原有历史内容可从新索引无损定位。
6. 聚合校验能发现注册表、Wiki、README 和敏感跟踪路径问题。
7. 治理测试、聚合校验和 `git diff --check` 全部通过。
8. 所有提交仅包含本设计范围文件，不夹带现有公众号和 `stock-ai` 工作区修改。
