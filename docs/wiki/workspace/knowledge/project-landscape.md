---
title: Tools Workspace 项目地图
type: knowledge
topic: workspace-project-landscape
aliases: [项目空间, 子项目地图, 项目生命周期, workspace projects]
tags: [workspace, projects, lifecycle]
scope: workspace
status: confirmed
owner: workspace-maintainer
source: [README.md, project-registry/projects.json]
related_projects: [stock-ai, sidestore-infra, english-buddy, xiaozhi-mac-server]
review_at: 2026-11-10
---

# Tools Workspace 项目地图

`tools-workspace` 是个人工具 monorepo，当前登记 17 个业务、产品或实验子项目。项目注册表是结构化目录，根 README 是人工入口；本页只解释稳定的领域和生命周期边界。

## 领域

- 投资：`stock-ai` 是业务核心，`stock-mysql` 是数据底座，`home-hub` 与 `wechat-cursor-acp` 是主要交互入口。
- 基础设施：`sidestore-infra` 负责统一 HTTPS 和家庭网络入口，`substore-clash` 负责代理订阅生成。
- 教育与音频：`english-buddy`、`harryputter` 是活跃产品，`cosyvoice-mac` 是素材生产工具。
- 小智：`xiaozhi-atoms3r` 管固件，`xiaozhi-mac-server` 管本地协议网关和模拟验证。
- 模型实验：`ollama-hermes`、`openrouter-chat`、`sillytavern-mac` 保持独立工具边界。

## 生命周期边界

`hp-readalong` 已由 `harryputter` 接替；`emquant-sim` 已明确下线。二者仍保留历史价值，但不应被加入新的日常调度。

新增项目、状态变化或依赖变化时，以 `project-registry/projects.json` 和对应项目 README 为准，并同步复审本页。
