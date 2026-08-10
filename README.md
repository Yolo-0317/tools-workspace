# tools-workspace

个人工具 monorepo，集中维护投资自动化、家庭基础设施、少儿教育与语音、小智设备以及本地模型实验。

本页是工作空间入口。安装、运行和排障细节留在各子项目 README；机器可读的项目事实位于 [`project-registry/projects.json`](project-registry/projects.json)。

## 五分钟开始

1. 在下表选择目标子项目，不确定时先查询项目注册表。
2. 运行只读 preflight，获取最小入口文档、Memory、Skill 和验证建议。
3. 只读取命中的一个专项 Memory 和一个 Skill 或路由页。
4. 涉及价格、生产状态、外部页面或高风险操作时回源验证。
5. 修改后运行子项目最相关验证，再运行仓库治理检查。

```bash
python3 scripts/workspace_registry.py --list --format text
python3 scripts/workspace_registry.py --project stock-ai --format json
python3 scripts/workspace_preflight.py --project stock-ai --risk normal --format text
python3 scripts/validate_workspace.py
```

治理脚本只读本地元数据，不会启动服务、执行注册的验证命令或操作生产系统。

## 子项目地图

生命周期：`core` 为核心业务或底座，`active` 为活跃产品，`incubating` 为孵化项目，`tooling` 为独立工具，`legacy` 为已被替代的历史项目，`offline` 为明确下线项目。

### 投资与交互入口

| 项目 | 生命周期 | 职责 | 入口 |
| --- | --- | --- | --- |
| `stock-ai` | core | A 股数据、选股、监控、投资 Agent 与公众号内容工程 | [README](stock-ai/README.md) |
| `stock-mysql` | core | 行情、持仓、监控、选股和快讯数据 | [README](stock-mysql/README.md) |
| `a-share-short-term-trading` | incubating | 收盘诊断、证据快照和盘中交易门禁 | [README](a-share-short-term-trading/README.md) |
| `home-hub` | core | 投资和个人运维看板 | [README](home-hub/README.md) |
| `wechat-cursor-acp` | core | 微信私聊与 Cursor CLI 的 ACP 桥接 | [README](wechat-cursor-acp/README.md) |
| `emquant-sim` | offline | 东财掘金仿真量化历史实现 | [README](emquant-sim/README.md) |

### 家庭基础设施

| 项目 | 生命周期 | 职责 | 入口 |
| --- | --- | --- | --- |
| `sidestore-infra` | core | Caddy、HTTPS、DDNS 与 SideStore | [README](sidestore-infra/README.md) |
| `substore-clash` | core | Sub-Store 订阅合并和 Clash 配置生成 | [README](substore-clash/README.md) |

### 教育、阅读与音频

| 项目 | 生命周期 | 职责 | 入口 |
| --- | --- | --- | --- |
| `english-buddy` | active | 少儿英语实时带读与牛津阅读树 | [README](english-buddy/README.md) |
| `harryputter` | active | EPUB 与有声书句级对齐播放器 | [README](harryputter/README.md) |
| `hp-readalong` | legacy | 第一章音频对齐概念验证，已由 HarryPutter 接替 | [README](hp-readalong/README.md) |
| `cosyvoice-mac` | tooling | 儿童故事离线批量配音 | [README](cosyvoice-mac/README.md) |

### 小智设备

| 项目 | 生命周期 | 职责 | 入口 |
| --- | --- | --- | --- |
| `xiaozhi-atoms3r` | active | AtomS3R 与 Echo Base 固件开发 | [README](xiaozhi-atoms3r/README.md) |
| `xiaozhi-mac-server` | active | 小智协议网关、Mac 模拟器和夸克播放 | [README](xiaozhi-mac-server/README.md) |

### 本地模型与聊天实验

| 项目 | 生命周期 | 职责 | 入口 |
| --- | --- | --- | --- |
| `ollama-hermes` | tooling | Ollama Hermes 命令行聊天与文本续写 | [README](ollama-hermes/README.md) |
| `openrouter-chat` | tooling | OpenRouter 极简流式聊天页 | [README](openrouter-chat/README.md) |
| `sillytavern-mac` | tooling | SillyTavern 角色聊天前端 | [README](sillytavern-mac/README.md) |

## 核心关系

```text
stock-mysql
  -> stock-ai -> home-hub
             -> wechat-cursor-acp

sidestore-infra
  -> substore-clash
  -> home-hub / english-buddy / harryputter / sillytavern-mac 的统一 HTTPS 入口

xiaozhi-atoms3r <-> xiaozhi-mac-server

hp-readalong -> harryputter
emquant-sim -> stock-ai（只读执行卡，项目已下线）
```

服务端口、启动机制和健康检查见 [`docs/SERVICES.md`](docs/SERVICES.md)。该文档描述仓库配置，不代表服务当前正在运行。

## 知识与上下文路由

```text
项目注册表 / preflight
  -> 子项目入口文档
  -> 一个命中的专项 Memory
  -> 一个匹配的 Skill 或路由页
  -> 仅在新鲜度或风险要求时回源
```

- 项目注册表：结构化项目状态、入口、依赖和验证建议。
- 本地 Wiki：跨项目的稳定知识与设计解释，见 [`docs/wiki/`](docs/wiki/README.md)。
- Memory：历史经验和陷阱，索引在 [`.cursor/rules/project-memory.mdc`](.cursor/rules/project-memory.mdc)。
- Skills：可复用操作流程，位于 [`.cursor/skills/`](.cursor/skills)。
- Superpowers：设计、计划、TDD 和验证工作流，见 [`.cursor/rules/superpowers.mdc`](.cursor/rules/superpowers.mdc)。

## 仓库级目录

| 路径 | 作用 |
| --- | --- |
| `project-registry/` | 机器可读项目注册表及维护规则 |
| `docs/wiki/` | 本地可检索知识层 |
| `docs/superpowers/` | 已确认设计和实施计划 |
| `scripts/` | 工作空间治理与 Docker 自启脚本 |
| `launchd/` | macOS 宿主机任务定义 |
| `.cursor/rules/` | 工作空间规则和按需 Memory |
| `.cursor/skills/` | 任务型操作流程 |

## 安全边界

- 不提交 `.env`、证书、私钥、订阅链接、持仓或个人记忆。
- README、Wiki 和注册表不代表当前生产状态；需要最新信息时必须回源。
- `legacy` 和 `offline` 项目不应进入新的自动化或日常调度。
- 工作区可能存在用户未提交修改；治理改动必须与业务改动分开提交。
- 仓库外的家庭媒体栈不属于本仓库子项目，只在服务依赖中引用。

## 治理验证

```bash
python3 -m unittest discover -s tests/workspace_governance -v
python3 scripts/validate_workspace.py --format text
git diff --check
```

具体业务验证以项目注册表和子项目 README 为准；治理脚本不会代替执行这些命令。
