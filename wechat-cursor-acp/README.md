# wechat-cursor-acp

将微信私聊桥接到 **Cursor CLI**（`agent acp`），与 QClaw / OpenClaw 微信通道分离配置。

| 组件 | 说明 |
|------|------|
| [wechat-acp](https://www.npmjs.com/package/wechat-acp) | 微信 ↔ ACP 协议桥 |
| `agent acp` | Cursor 官方 CLI 的 ACP 子命令 |
| Agent 工作区 | 默认 `../stock-ai/investment-agent`（可在 `.env` 覆盖） |

## 前置条件

1. **Cursor CLI** 已安装并在 PATH 中：

   ```bash
   curl https://cursor.com/install -fsS | bash
   agent login
   agent --version
   ```

2. **Node.js** ≥ 18（用于 `npx wechat-acp`）

3. **停用 QClaw 微信**（避免 iLink 登录冲突）  
   在 QClaw 中关闭 `openclaw-weixin`，或停止对应 Gateway 后再启动本桥。

4. **团队 Plan 额度**  
   默认模型为 **`composer-2.5`**（`.env` 中 `WECHAT_AGENT_MODEL`）。若提示 out of usage，可改为 `auto` 或请管理员提额。

## 快速开始

```bash
cd /Users/yolo/dev/yolo/tools-workspace/wechat-cursor-acp
cp .env.example .env   # 按需改 AGENT_CWD、INSTANCE
./scripts/start.sh
```

默认 **扫码登录成功后自动转入后台守护**；token 保存在 `~/.wechat-acp/instances/<INSTANCE>/`。

## 常用命令

| 命令 | 作用 |
|------|------|
| `./scripts/start.sh` | 扫码登录 → 自动 `--daemon` 常驻 |
| `./scripts/start.sh --foreground` | 全程保持前台（调试） |
| `./scripts/start.sh --login` | 强制重新扫码 |
| `./scripts/stop.sh` | 停止守护进程 |
| `./scripts/status.sh` | 查看守护进程状态 |
| `./scripts/start-typing-watcher.sh` | 单独启动「正在输入」脉冲（`start.sh` 会自动带） |
| `./scripts/install-launchd.sh` | 安装 macOS 登录自启 |

## 登录自启（launchd）

首次扫码登录成功后：

```bash
./scripts/install-launchd.sh
```

- 标签：`com.user.wechat-cursor-acp`
- 登录时启动；每 10 分钟检查，进程退出且已有 token 时会重拉
- 无 token 时跳过（需先手动 `./scripts/start.sh --login`）
- 日志：`logs/launchd-autostart.{out,err}.log`

## 微信「正在输入」

`wechat-acp` 内置 typing，但 Agent 建会话前可能十几秒无刷新。本项目增加 **`typing-watcher`**：收到消息后每 3 秒向微信发送 typing，直到 Agent 回复完成。

- 随 `./scripts/start.sh` 自动启动；日志：`logs/typing-watcher.log`
- 间隔：`WECHAT_TYPING_PULSE_MS`（默认 3000）

## 可选：转发思考摘要

默认**不**把 Agent 内部思考发到微信（避免刷屏）。需要时在 `.env` 开启：

```bash
WECHAT_FORWARD_THOUGHTS=1
```

然后重启桥：

```bash
./scripts/stop.sh
./scripts/start.sh
```

开启后，思考过程会以 `💭 [Thinking]` 开头的消息分段出现在微信里（与「正在输入」可同时使用）。文件 diff 仍默认关闭（`config/wechat-acp.json` 里 `showDiffs: false`）。

## 配置

| 文件 | 说明 |
|------|------|
| `.env` | `AGENT_CWD`、`WECHAT_ACP_INSTANCE`、`WECHAT_AGENT_MODEL`、遥测、`WECHAT_FORWARD_THOUGHTS` |
| `config/wechat-acp.json` | wechat-acp JSON 配置（agent preset、会话超时） |

环境变量 `AGENT_CWD` 指向 Cursor Agent 实际读写代码与规则的目录。投资助手场景保持默认即可。

## 每日选股战报推送

`stock-ai/push_selection_wechat.sh` 默认走本实例的 iLink token（`scripts/tools/wechat_acp_push_text.py`），不占用 Cursor Agent 额度。

- 定时：工作日 17:30 → `stock-ai/scripts/install-daily-selection-launchd.sh`
- 手动：`cd stock-ai && ./push_selection_wechat.sh`

## 与 QClaw 的关系

- **QClaw**：`~/.qclaw`，OpenClaw Gateway + `qclaw/modelroute`，IM 插件 `openclaw-weixin`
- **本仓库**：`tools-workspace/wechat-cursor-acp`，仅负责 **微信 → Cursor CLI**
- 工作区内容可与 `~/.qclaw/workspace` 同步（见 `stock-ai/investment-agent/scripts/sync-from-qclaw.sh`）

两套微信桥**不要同时在线**。

## 目录结构

```
wechat-cursor-acp/
├── .env.example
├── config/wechat-acp.json
├── scripts/
│   ├── lib/common.sh
│   ├── start.sh
│   ├── stop.sh
│   ├── status.sh
│   ├── wechat-acp-autostart.sh
│   └── install-launchd.sh
└── README.md
```
