---
title: Tools Workspace 服务拓扑
type: knowledge
topic: workspace-service-topology
aliases: [服务地图, 端口地图, 反向代理关系, workspace services]
tags: [workspace, infrastructure, services]
scope: workspace
status: confirmed
owner: workspace-maintainer
source: [docs/SERVICES.md, sidestore-infra/README.md, project-registry/projects.json]
related_projects: [sidestore-infra, substore-clash, home-hub, english-buddy, harryputter, sillytavern-mac]
review_at: 2026-11-10
---

# Tools Workspace 服务拓扑

`sidestore-infra` 是家庭服务的统一 HTTPS、证书和 DDNS 入口，但不拥有被代理服务的业务逻辑。每个服务仍由所属子项目维护启动、健康检查和数据。

```text
客户端
  -> sidestore-infra / Caddy
     -> home-hub
     -> english-buddy
     -> harryputter
     -> sillytavern-mac
     -> substore-clash

stock-mysql
  -> stock-ai
  -> home-hub
  -> a-share-short-term-trading
```

端口和启动机制以 `docs/SERVICES.md` 为目录，以子项目 README 为细节来源。该拓扑不表示服务当前在线；遇到连接失败、证书问题或生产状态查询时必须执行对应健康检查。
