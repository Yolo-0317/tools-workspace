# Prompt 文件说明（改这里）

续写脚本 `rewrite_novel.py` 读三个文本文件组 prompt，**不用改 Python 代码**。

| 文件 | 改什么 |
|------|--------|
| **`novel_system.txt`** | 全局人设与文风：作者身份、禁止事项、语气（武侠/诙谐等） |
| **`novel_user.txt`** | 发给模型的消息骨架；保留 `{fragment}` `{task}` `{word_count}` 占位符 |
| **`novel_task_default.txt`** | **本次要写什么情节**（续写任务说明） |

## 示例：破庙狗肉章后续

编辑 `novel_task_default.txt`，例如：

```text
从鬼瑶儿离去、战天风跳河之后写起。重点写：河上躲避鬼灵、下游遇险、鬼瑶儿是否折返。保持战天风嘴贫、鬼瑶儿外冷。
```

## 自定义任务（不改默认文件）

```bash
python rewrite_novel.py -f ~/Downloads/美女江山一锅煮.txt \
  --chapter-start 七十 --chapter-end 七十三 \
  --task "你的任务写在这里"
```

或指定别的任务文件：

```bash
--task-file my_task.txt
```
