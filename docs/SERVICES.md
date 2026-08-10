# 工作空间服务目录

本页整理仓库文档中声明的稳定服务配置，用于发现端口、启动边界和依赖。它不是实时健康页面；判断服务是否运行必须执行对应项目的健康检查。

| 服务 | 项目 | 配置端口 | 启动机制 | 健康检查或入口 | 直接依赖 |
| --- | --- | --- | --- | --- | --- |
| MySQL | `stock-mysql` | `3306` | Docker Compose | 见项目 README | 无 |
| Home Hub | `home-hub` | `8780` | launchd | 见项目 README | MySQL、stock-ai |
| English Buddy | `english-buddy` | `18787` | launchd | `/api/health` | 本地语音模型、Caddy |
| HarryPutter | `harryputter` | `8791` | launchd | 见项目 README | 本地书籍素材、Caddy |
| OpenRouter Chat | `openrouter-chat` | `8795` | 前台脚本 | 根页面 | OpenRouter |
| SillyTavern | `sillytavern-mac` | `8792` | 脚本或 launchd | `scripts/verify.sh` | 模型后端、Caddy |
| Anisette | `sidestore-infra` | `6969` | Docker Compose | `scripts/healthcheck.sh` | SideStore 配置 |
| Caddy | `sidestore-infra` | `8443`、`8883` | Docker Compose | `scripts/healthcheck.sh` | 证书、DDNS、宿主机服务 |
| Sub-Store | `substore-clash` | `3001` | Docker Compose | 见项目 README | 订阅源 |
| clash-gen | `substore-clash` | `8787` | Docker Compose | `/health` | 订阅源、Caddy |
| stock-ai host jobs | `stock-ai` | `9876` | launchd | 见调度文档 | MySQL、OpenCLI、微信桥 |
| 小智 WebSocket 网关 | `xiaozhi-mac-server` | `8765` | 项目脚本 | 见项目 README | ASR、TTS |
| 小智 HTTP 与 OTA | `xiaozhi-mac-server` | `8766` | 项目脚本 | 见项目 README | 小智网关、夸克适配器 |

## 边界

- 公网域名、订阅 URL、token 和证书内容不在本页维护。
- Docker、launchd 和前台脚本各自仍由所属项目维护。
- 一个端口出现在注册表或本页，只说明仓库配置，不代表当前占用或可访问。
- 仓库外服务只作为依赖出现，不纳入项目注册表。
