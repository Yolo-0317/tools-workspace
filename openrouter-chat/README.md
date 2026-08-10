# OpenRouter Plain Chat

本机最小纯聊天页：流式调用 OpenRouter NSFW 向模型。无角色卡、无会话落盘。

## 启动

```bash
cd openrouter-chat
bash start.sh
```

打开 http://127.0.0.1:8795/

> 勿用旧端口 `8793`：该口曾跑过 Open WebUI，浏览器 Service Worker 会劫持页面并显示 `500: Internal Error`。

可选：

```bash
OPENROUTER_API_KEY=sk-or-v1-... bash start.sh
CHAT_PORT=8795 bash start.sh
```

未设置 `OPENROUTER_API_KEY` 时，自动读取 SillyTavern `secrets.json` 里已激活的 OpenRouter Key。

## 默认模型

`sao10k/l3.1-euryale-70b`（页面可换 Hermes / Euryale 等）

## 说明

- 仅绑定 `127.0.0.1`
- 刷新或点「清空」会丢掉对话
- 需要能访问 `https://openrouter.ai`
