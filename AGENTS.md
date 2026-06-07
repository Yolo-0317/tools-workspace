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
| `emquant-sim/` | `emquant-sim/OFFLINE.md` — **已下线**（专业投资者门槛）；代码备查 |
| `english-buddy/` | `english-buddy/README.md` — 少儿英文带读（Ollama + edge-tts）；账号见 `docs/AUTH.md` |
| `readalong/` | `readalong/README.md` — 哈利波特有声书句级带读 PWA（`:8791`） |
| `~/docker/jellyfin-stack` | `.cursor/skills/jellyfin/SKILL.md`（NAS / 迅雷 / 夸克 三库） |

### OpenCLI 浏览器（stock-ai）

| Skill | 路径 | 用途 |
|-------|------|------|
| `stock-opencli` | `.cursor/skills/stock-opencli/` | **场景路由真源**：东财 / 公众号内容分析 / JYWG；命令与故障速查 |
| `eastmoney-browser-sop` | `stock-ai/investment-agent/docs/skills/eastmoney-browser-sop/` | 东财 **深度分析** 十一维 SOP（在 OpenCLI 采集之后） |

用户说 **OpenCLI、东财浏览器、公众号后台抓取** → 先读 `stock-opencli`，勿每次重查 `opencli --help`。

### Readalong 章节导入

| Skill | 路径 | 用途 |
|-------|------|------|
| `readalong-import` | `.cursor/skills/readalong-import/` | **按书目+章号导入**：`BOOK=hp01 ./scripts/pipeline.sh N` · verify |

用户说 **导入哈利波特第一部第 N 章、hp01 第 N 章、魔法石第 N 章** → 先读 `readalong-import`。**禁止**仅凭「第 N 章」执行（须确认 book_id）。Whisper 首跑须前台 ~5 min/章。

### 微信公众号草稿 Skill

**约定**：用户说 **「公众号」= 「牛马也智能」**（`wechat-mp-drafts`），不是简选小电。

| Skill | 路径 | 用途 |
|-------|------|------|
| `wechat-mp-drafts` | `.cursor/skills/wechat-mp-drafts/` | **牛马也智能**：先 [INDEX.md](.cursor/skills/wechat-mp-drafts/INDEX.md) → [evening-trilogy-templates.md](.cursor/skills/wechat-mp-drafts/evening-trilogy-templates.md) · [operations-sop.md](.cursor/skills/wechat-mp-drafts/operations-sop.md) · [SKILL.md](.cursor/skills/wechat-mp-drafts/SKILL.md) |
| `wechat-mp-commerce-drafts` | `.cursor/skills/wechat-mp-commerce-drafts/` | **简选小电**（**已搁置**；仅用户明确带货时使用） |

**公众号定时（每日 18:20）**：交易日 `sector`+`dragons`+`top5` · 周日/节假日休市 `news`（72h）· 周六跳过 — 见 `stock-ai/docs/WECHAT_MP_SCHEDULING.md`。

### Jellyfin Skills

Stack 在 `~/docker/jellyfin-stack`（非本 repo 子目录）。Agent 技能：

| Skill | 用途 |
|-------|------|
| `jellyfin` | 总入口，按数据源路由 |
| `jellyfin-nas-smb-staging` | NAS-影音（琅琊榜、人世间、绝命毒师） |
| `jellyfin-xunlei-tv-import` | 迅雷-影音 |
| `jellyfin-quark-tv-import` | 夸克-影音 |

Canonical 路径：`~/docker/jellyfin-stack/.cursor/skills/`；`~/.cursor/skills/jellyfin-nas-smb-staging` 为 NAS skill 的用户级副本。
