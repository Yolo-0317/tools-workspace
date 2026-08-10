# sillytavern-mac

在 **macOS** 上最小部署 [SillyTavern](https://github.com/SillyTavern/SillyTavern)（中文圈俗称「酒馆」）——开源 AI 角色扮演前端。

## 前置条件

| 项目 | 要求 |
|------|------|
| 系统 | macOS 12+ |
| Node.js | **20+**（`node -v`） |
| 工具 | `git` |
| LLM 后端 | 任选其一：本机 **Ollama**、OpenAI 兼容 API、Claude 等 |

> 酒馆本身不生成 AI 内容，须接入模型 API 才能对话。

## 一键安装

```bash
cd sillytavern-mac
bash scripts/install.sh
```

脚本会：

1. 克隆 `SillyTavern/SillyTavern`（`release` 分支）到 `vendor/SillyTavern`
2. 执行 `npm install`
3. 生成 `.env`

## 启动

```bash
bash scripts/start.sh
# 或 launchd 常驻：
bash scripts/install-launchd.sh
```

| 访问 | URL |
|------|-----|
| 本机 | http://127.0.0.1:8792/ |
| Hub 公网 | https://hub.yoloworld.site:8883/silly/ |
| Hub 内网 | https://hub.yoloworld.site:8443/silly/ |

默认仅监听 `127.0.0.1`；公网经 Caddy `handle_path /silly/*` 反代。

Caddy 变更后：`cd sidestore-infra && docker compose restart caddy`

## 界面美化

默认 `Dark Lite` + 赛博朋克背景偏「工具面板」风。一键换 **Hub Polished**（圆角气泡、纯色背景、略大字号）：

```bash
bash scripts/configure-ui-polish.sh
# 硬刷新浏览器 Cmd+Shift+R
```

主题文件：`themes/Hub Polished.json`（可手改 `custom_css` 后重跑脚本）。

## 验证

另开终端：

```bash
bash scripts/verify.sh
```

## 接本机 Ollama

一键配置（自动读取 `ollama list` 第一个模型）：

```bash
bash scripts/configure-ollama.sh
```

或指定模型：

```bash
OLLAMA_MODEL=qwen3.5-9b-uncensored-q4:latest bash scripts/configure-ollama.sh
```

配置完成后 **硬刷新浏览器**（Cmd+Shift+R）。顶部应显示 **Valid** 或 **Status check bypassed**，而非「未连接」。

若仍显示未连接：打开 **API 连接** -> 点击 **Connect**（插头图标）手动触发一次。

| 字段 | 值 |
|------|-----|
| Endpoint | `http://127.0.0.1:11434/v1` |
| API Key | `ollama`（任意非空） |
| Model | `ollama list` 中的模型名 |

手动配置：UI 里 **API 连接** -> **Chat Completion** -> **Custom**，填上表。

## 接 OpenRouter

```bash
OPENROUTER_API_KEY=sk-or-v1-... bash scripts/configure-openrouter.sh
```

可选指定模型（默认 `qwen/qwen3.5-flash-02-23`）：

```bash
OPENROUTER_MODEL=deepseek/deepseek-v3.2 bash scripts/configure-openrouter.sh
```

**Provider returned error / 429**：多为选了 `:free` 免费模型被上游限流，换非 free 模型或等十几秒重试。Google/Gemini 系列在你所在区域可能不可用。

**NSFW 角色扮演 + 世界书**（Mistral/Qwen 等常会拒答）：

```bash
OPENROUTER_PROFILE=nsfw OPENROUTER_API_KEY=sk-or-v1-... bash scripts/configure-openrouter.sh
```

默认模型 `sao10k/l3.1-euryale-70b`（131k 上下文，RP/NSFW 向；`l3.3` 常被上游 429 限流，用 `l3.1` 更稳）。备选：`nousresearch/hermes-4-70b`（更便宜、同样少拒答）。

Key 写入 `vendor/SillyTavern/data/default-user/secrets.json`（已在 `.gitignore` 的 `data/` 范围内，勿提交 git）。

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `ST_PORT` | `8792` | 监听端口（Caddy 反代目标） |
| `ST_LISTEN` | `127.0.0.1` | 绑定地址 |
| `SILLYTAVERN_BRANCH` | `release` | 安装时克隆分支 |

## 数据位置

Standalone 模式下，角色卡、聊天记录等在：

```text
sillytavern-mac/vendor/SillyTavern/data/
```

升级/重装时勿删 `data/`。

## 故障排查

**顶部显示「未连接到 API」**

Ollama 后端正常时，多半是页面未自动触发连接检测。已内置修复：

1. 硬刷新（Cmd+Shift+R）
2. 或重新运行 `bash scripts/configure-ollama.sh`（会开启 `auto_connect` 并应用 patch）
3. 或手动：API 连接 -> 点击 Connect（插头按钮）

```bash
node -v                    # 须 >= 20
curl http://127.0.0.1:11434/api/tags   # Ollama 是否在线
tail -f logs/server.log    # 启动日志
```

端口占用时改 `.env` 里 `ST_PORT`，重启 `start.sh`。

## 参考

- 官方文档：https://docs.sillytavern.app/
- 中文教程：https://guide.sillytavern.one/
