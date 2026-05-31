# tools-workspace — Agent 指南

个人工具 **monorepo**（单一 git）：`stock-ai`（A 股 / MCP）+ `sidestore-infra`（SideStore / Docker）+ `substore-clash` 等。

## 已安装能力

### Superpowers

- **插件**：Cursor 市场 `superpowers`（TDD、头脑风暴、计划、调试、代码评审）
- **项目 Hook**：`.cursor/hooks.json` → 每次会话启动注入 `using-superpowers`
- **规则**：`.cursor/rules/superpowers.mdc`

若 Agent 未识别 Superpowers 技能，在聊天执行：

```text
/add-plugin superpowers
```

### Hermes 十步工作法

- **规则**：`.cursor/rules/hermes-protocol.mdc`
- **记忆**：`project-memory.mdc`、`memory-python.mdc`、`memory-infra.mdc`

## 推荐工作流

1. 读 `project-memory.mdc` 与子项目记忆
2. 新功能 → Superpowers `brainstorming` → `writing-plans`
3. 实现 → `test-driven-development` + `verification-before-completion`
4. 结束 → Hermes 询问是否写入记忆

## Docker 开机自启

- **Docker Desktop**：`settings-store.json` → `AutoStart: true`（或 Settings → General → 登录时启动）
- **Compose 栈**：`scripts/install-docker-launchd.sh` 安装 `com.user.docker-stacks`（登录后 `docker-autostart.sh` 幂等 `compose up -d`）
- 各服务 `restart: unless-stopped` / `always` 时，Docker 引擎起来后也会自动恢复容器

## 子项目

| 目录 | 文档 |
|------|------|
| `stock-ai/` | `stock-ai/docs/PROJECT_LAYOUT.md` |
| `wechat-cursor-acp/` | `wechat-cursor-acp/README.md` — 微信桥接 Cursor CLI |
| `sidestore-infra/` | `sidestore-infra/README.md` |
| `substore-clash/` | `substore-clash/README.md` — Sub-Store + Mihomo 订阅生成 |
| `stock-mysql/` | `stock-mysql/README.md` — MySQL 8，stock-ai 业务库 |
| `~/docker/jellyfin-stack` | `.cursor/skills/jellyfin/SKILL.md`（NAS / 迅雷 / 夸克 三库） |

### Jellyfin Skills

Stack 在 `~/docker/jellyfin-stack`（非本 repo 子目录）。Agent 技能：

| Skill | 用途 |
|-------|------|
| `jellyfin` | 总入口，按数据源路由 |
| `jellyfin-nas-smb-staging` | NAS-影音（琅琊榜、人世间、绝命毒师） |
| `jellyfin-xunlei-tv-import` | 迅雷-影音 |
| `jellyfin-quark-tv-import` | 夸克-影音 |

Canonical 路径：`~/docker/jellyfin-stack/.cursor/skills/`；`~/.cursor/skills/jellyfin-nas-smb-staging` 为 NAS skill 的用户级副本。
