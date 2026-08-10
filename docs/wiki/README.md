# 本地 Workspace Wiki

这里保存跨项目、可追溯、可审核的稳定知识。它是快速召回层，不替代子项目 README、外部原始文档或实时系统。

## 页面类型

- `design`：架构、方案和跨项目链路的可追溯重组。
- `knowledge`：稳定结论、边界、不变量、例外和回源条件。

## 状态

- `draft`：可供参考，但必须人工确认或回源。
- `confirmed`：在复审日期前可以直接引用。
- `archived`：仅保留历史背景，必须回源。

即使页面为 `confirmed`，涉及当前服务状态、价格、生产任务、账号权限或外部页面变化时仍要回源。

## Front Matter 契约

每页必须包含：`title`、`type`、`topic`、`aliases`、`tags`、`scope`、`status`、`owner`、`source`、`related_projects`、`review_at`。

Front Matter 只支持字符串标量和单行字符串数组，不支持嵌套 YAML、多行数组、锚点或自定义类型。

```bash
python3 scripts/search_workspace_wiki.py --query "项目空间" --format json
python3 scripts/validate_workspace.py
```

`templates/` 中的文件用于复制，不进入搜索结果。
