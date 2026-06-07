#!/usr/bin/env python3
"""公众号临时稿变体：飞书官方 lark-cli 接自建应用与 Cursor。"""

from __future__ import annotations

from scripts.tools.wechat_mp_workspace_article import PROJECT_NAME

# 推 temp 槽：--kind temp --variant lark_cli
VARIANT = "lark_cli"


def lark_cli_article_title() -> str:
    return "飞书还在拼 OpenAPI？官方 CLI 一次配好"


def lark_cli_article_digest() -> str:
    return (
        f"「{PROJECT_NAME}」实践：用飞书 lark-cli 把自建应用接到终端和 Cursor，"
        "bot/用户双身份、多维表格与群发告警，附 91403 等排错要点。个人工程笔记。"
    )[:128]


def generate_lark_cli_article_body() -> str:
    return f"""做自动化或在 Cursor 里接工具时，飞书常见两条路：自己拼 OpenAPI，或用官方 lark-cli。后者覆盖消息、文档、多维表格、日历，也支持官方 Skills 扩展。装一次凭证，shell、Cron 和编辑器都能在同一套上操作。

> 为什么值得多一层

· 凭证一次配置：终端里可选机器人或登录用户两种身份  
· 命令分层：快捷命令（+ 前缀）→ 精选 API → 通用 api 兜底  
· 和 Cursor 合拍：npx skills add larksuite/cli 后，可按 Skill 调飞书，不必每次手写 HTTP  

> 开始前要准备什么

在飞书开放平台建企业自建应用，记下 App ID（cli_ 开头）和 App Secret（只显示一次）。

按场景开 Scope 示例：

· 群发消息：im 相关权限  
· 读写多维表格：base:record 等  
· 云文档 / 电子表格：docx、sheets  
· 读本人日历、Wiki：还要 lark-cli auth login  

Scope 开通后，很多场景还要在文档、群或 Base 里把应用加成协作者，否则 forbidden、91403——最容易踩的坑。

本机需要 Node.js；从源码构建才要 Go、Python。

> 安装与把应用接到 CLI

```bash
npx @larksuite/cli@latest install
lark-cli --version
npx skills add larksuite/cli -y -g
```

交互式配置（第一次推荐）：

```bash
lark-cli config init
lark-cli config show
```

还没有应用时，让 CLI 在浏览器里走完创建：

```bash
lark-cli config init --new
```

无人值守时可在终端跑 init --new，本人在浏览器里点完授权页即可。Secret 进系统密钥链，别 echo 到终端历史。

CI / 云主机用 stdin 传 Secret：

```bash
echo "YOUR_APP_SECRET" | lark-cli profile add \\
  --name my-bot \\
  --app-id cli_xxxxxxxxxxxx \\
  --app-secret-stdin
```

多应用 Profile：

```bash
lark-cli config init --new --name bot-reader
lark-cli profile use bot-reader
lark-cli --profile bot-writer im +messages-send ...
```

> bot 和用户两种身份

· bot（--as bot）：App Secret → tenant token，适合告警群发、以应用写表  
· user（--as user）：auth login 后的 token，适合搜群 chat_id、读 Wiki  

```bash
lark-cli auth login --recommend
lark-cli auth status
lark-cli auth check
```

缺权限按域补授权：

```bash
lark-cli auth login --domain calendar,im
lark-cli auth login --no-wait
```

`--no-wait` 会打出验证链接，适合本机开着终端、另一台设备扫码的场景。

> 三层命令怎么发现

```bash
lark-cli --help
lark-cli schema
lark-cli sheets --help
```

日常用快捷命令（如 sheets +read）；精选用 API 命令；兜底：

```bash
lark-cli api GET /open-apis/...
```

写脚本前建议加 --dry-run、--format json。

> 三个真在用的模式

机器人维护多维表格（--as bot）：

```bash
lark-cli base +field-list --as bot \\
  --base-token <BASE_TOKEN> --table-id <TABLE_ID>

lark-cli base +record-upsert --as bot \\
  --base-token <BASE_TOKEN> --table-id <TABLE_ID> \\
  --fields '{{"任务名称":"示例"}}'
```

报 91403：到 Base 里把机器人加成可编辑协作者，并确认开放平台已开 base:record 权限。

用户搜群、机器人发消息：

```bash
lark-cli im +chat-search --query "Oncall" --as user --format json

lark-cli im +messages-send \\
  --chat-id "oc_xxxxxxxx" \\
  --as bot \\
  --markdown "**巡检结果**\\n- 状态：正常"
```

Bot is not in the chat：先把机器人拉进群。

读表格 / 云文档（常用 --as user）：

```bash
lark-cli sheets +read --spreadsheet-token <TOKEN> \\
  --sheet-id <SHEET_ID> --range 'A:Z' --as user

lark-cli docs +fetch --doc <DOC_TOKEN> --as user --format pretty
```

> 和自写 Python 脚本怎么选

· 日常运维和脚本自动化：lark-cli  
· 极窄只读探针：可保留小型 Python（如 token 探测）  
· 收事件推送：仍用 WebSocket 长连接  

> 排错收藏

· command not found：npm install -g @larksuite/cli  
· unauthorized：auth login --recommend  
· permission denied：查 Scope + 资源是否授权给应用  
· Base 91403：Bot 加成 Base 协作者  
· 群消息发不出：Bot 是否在群内  
· 不知道用什么命令：lark-cli schema  
· Secret / Token 勿写进仓库；写删类先 --dry-run  

> 在 Cursor 里怎么配

1. 安装 CLI，并执行 skills add larksuite/cli  
2. 本机 lark-cli config init（或 init --new）完成应用绑定  
3. lark-cli auth login --recommend 完成用户授权  
4. auth status 通过后，在 Skill 里写清哪些命令用 --as bot、哪些用 --as user  

本质就两件事：开放平台建好应用，把 ID / Secret 交给 lark-cli config；按场景选 bot 或 user，并在平台与具体资源上对齐权限。和「{PROJECT_NAME}」里收盘推送、看板、告警放在同一套自动化思路里。"""
