# ollama-hermes

在 Cursor 终端里通过 [Ollama Python 库](https://github.com/ollama/ollama-python) 调用本地 **hermes3:8b**，进行多轮对话（含可选 system prompt 角色设定）。

## 前置条件

| 项目 | 要求 |
|------|------|
| Ollama | 已安装并在运行（`ollama serve` 或菜单栏常驻） |
| 模型 | `ollama pull hermes3:8b` |
| Python | 3.10+ |

## 安装

```bash
cd ollama-hermes
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 按需改 OLLAMA_HOST / HERMES_SYSTEM_PROMPT
```

## 用法

**交互聊天**（流式输出，默认）：

```bash
python chat.py
```

**单条消息**：

```bash
python chat.py -m "Hello"
```

**自定义 system prompt**（角色 / 场景）：

```bash
python chat.py --system "You are Luna, a witty companion. Stay in character."
```

**在其它 Python 脚本里调用**：

```python
from hermes_client import HermesClient, HermesConfig

client = HermesClient(HermesConfig(system="Your system prompt here."))
print(client.chat("Hi there"))
```

## 交互命令

| 命令 | 作用 |
|------|------|
| `/reset` | 清空当前会话历史 |
| `/quit` | 退出 |

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama 地址 |
| `OLLAMA_MODEL` | `hermes3:8b` | 模型名 |
| `HERMES_SYSTEM_PROMPT` | 空 | 默认 system prompt |

## 在 Cursor 里用

1. 打开本目录 `ollama-hermes/`
2. 终端：`source .venv/bin/activate && python chat.py`
3. 或用 Cursor 内置终端跑 `python chat.py -m "..."` 做快速测试

数据走本机 Ollama，不经过 Cursor 云端模型。

## 故障排查

```bash
ollama list                  # 确认 hermes3:8b 存在
curl http://127.0.0.1:11434/api/tags
python chat.py -m "ping"     # 应返回模型回复
```

若首次回复很慢，属正常（模型冷加载进内存）。

## 读 txt 片段并续写

```bash
source .venv/bin/activate

python rewrite_novel.py \
  -f ~/Downloads/美女江山一锅煮.txt \
  --encoding gbk \
  --chapter-start 七十 \
  --chapter-end 七十三 \
  -o outputs/meinv_ch70_continue.txt
```

**在哪里改 prompt**：见 [`prompts/README.md`](prompts/README.md)

| 文件 | 作用 |
|------|------|
| `prompts/novel_system.txt` | 文风 / 角色 / 禁止项 |
| `prompts/novel_user.txt` | 消息模板（含 `{fragment}`） |
| `prompts/novel_task_default.txt` | 续写任务（写哪段后续） |

生成结果默认另存 `outputs/continuation_*.txt`。
