# 项目注册表

`projects.json` 是 `tools-workspace` 子项目目录的机器可读事实源。它只记录可从仓库确认的稳定元数据，不表示服务当前健康、外部账号有效或生产数据最新。

## 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 与顶层目录一致的稳定项目 ID |
| `path` | 仓库相对路径 |
| `domain` | 业务领域 |
| `summary` | 一句话边界说明 |
| `lifecycle` | `core`、`active`、`incubating`、`tooling`、`legacy` 或 `offline` |
| `entry_docs` | 优先阅读的仓库内文档 |
| `depends_on` | 运行或工作流依赖的其他注册项目 |
| `serves` | 本项目为哪些注册项目提供能力 |
| `memory_topics` | preflight 推荐的 Memory 主题 |
| `skills` | preflight 推荐的本地 Skill 名称 |
| `verify` | 建议人工执行的验证命令，不会被治理脚本自动运行 |
| `runtime` | 服务类型与仓库文档声明的监听端口 |
| `aliases` | 中文名称、缩写和常见任务关键词 |

## 维护规则

1. 新增或删除顶层子项目时同步修改注册表与根 README。
2. 只填写仓库文档可以证实的事实；未知值使用空数组。
3. 不写账号、token、订阅地址、持仓、证书路径或生产结果。
4. `legacy` 表示已有替代项目；`offline` 表示明确停止日常运行。
5. 修改后运行：

```bash
python3 -m unittest tests.workspace_governance.test_workspace_registry -v
python3 scripts/workspace_registry.py --list --format json
```

需要为具体任务选择最小上下文时，使用只读 preflight：

```bash
python3 scripts/workspace_preflight.py \
  --project stock-ai \
  --risk normal \
  --task "任务摘要" \
  --wiki-query "可选知识关键词"
```

preflight 只返回路径、验证建议和风险检查项，不读取推荐文档正文，也不执行任何命令。
