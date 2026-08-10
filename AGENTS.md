# tools-workspace

个人工具 monorepo：`stock-ai`、`sidestore-infra`、`substore-clash`、`english-buddy`、`xiaozhi-*`、`harryputter` 等。

## 必须遵守

- 用户可见内容、UI 与汇报禁止 emoji。
- 先读 `.cursor/rules/project-memory.mdc` 前 60 行主题索引；用 `rg` 定位相关条目，再按需读 **一个**子项目记忆。不要整份加载任何 `memory-*.mdc`。
- 新功能先做简短设计和计划；修改后运行最相关的验证。
- 不提交 `.env`、证书、订阅链接、持仓或个人记忆。
- 复杂流程可用 Superpowers；其规则在 `.cursor/rules/superpowers.mdc`。

## 项目路由

| 任务 | 先读 |
|---|---|
| A 股、MySQL、选股、公众号工程 | `stock-ai/docs/PROJECT_LAYOUT.md` |
| OpenCLI、东财、公众号后台抓取 | `.cursor/skills/stock-opencli/ROUTING.md` |
| 东财个股深度 SOP | `stock-ai/investment-agent/docs/skills/eastmoney-browser-sop/ROUTING.md` |
| SideStore、Caddy、DDNS | `sidestore-infra/README.md` |
| Sub-Store、Clash | `substore-clash/README.md` |
| 英语带读、ORT | `english-buddy/docs/ORT_READ_ALONG.md` |
| 小智固件或 Mac 网关 | `xiaozhi-atoms3r/README.md` 或 `xiaozhi-mac-server/README.md` |
| 哈利波特导入/对齐 | `.cursor/skills/harryputter-import/SKILL.md` |
| 夸克网盘 | `.cursor/skills/quarkclouddrive/ROUTING.md` |

用户说“公众号”默认指「牛马也智能」。先读 `.cursor/skills/wechat-mp-drafts/SKILL.md` 的决策树；写作/质检只再读命中的一个专题文档。简选带货仅在用户明确要求时处理。

Docker 开机自启说明见 `scripts/install-docker-launchd.sh` 与各子项目 README。
