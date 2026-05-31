# Home Hub 工具约定

## 浏览器 / 页面测试

**涉及浏览器页面的场景一律用 OpenCLI**，不用 Playwright 或其他浏览器自动化替代。

```bash
export PATH="$HOME/.nvm/versions/node/v24.14.1/bin:$PATH"
opencli browser open "http://127.0.0.1:5173/"
opencli browser wait time 4
opencli browser state
opencli browser screenshot output/test.png
opencli browser close
```

截图目录建议：`home-hub/output/opencli-test/`

## 聊天后端

与 [wechat-cursor-acp](../../wechat-cursor-acp/) 相同：

- 认证：`agent login`
- 命令：`agent -p --force --output-format stream-json --resume <session_id>`
- 工作区：`HUB_AGENT_CWD` → `stock-ai/investment-agent`

前置：`agent status` 显示已登录。

## 开发服务

```bash
./scripts/dev.sh                    # 后端 :8781（热重载）
cd frontend && npm run dev          # 前端 :5173 → 代理到 :8781
```
