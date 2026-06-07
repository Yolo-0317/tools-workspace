# Readalong 产品策略与公网试听前置条件

> **状态**：策略已确定；**公网试听尚未正式对外推广** — 须先完成 [§4 网络安全清单](#4-公网试听前须完成的网络安全清单)。

## 1. 定位（2026-06-07 定稿）

**不是卖听书，是技术分享。**

| 维度 | 决策 |
|------|------|
| 引流目的 | 分享「EPUB + MP3 → 句级同步带读 PWA」方案 |
| 代码 | **可开源**（pipeline + 播放器 + 文档） |
| 交付物 | **试读链接** + **Git 仓库地址** → 读者自己 clone、自备素材、本地/自建部署 |
| 不做 | 关注换全本账号、一对一部署辅导、在公网托管完整版权有声书 |

### 用户路径

```text
小红书 / 公众号（技术向）
    ↓
关注 → 自动回复：试读 URL + GitHub 地址 + BYO 素材说明
    ↓
试读：外网仅第 1 章（Live Demo，证明对齐效果）
    ↓
全本：自己拉库 → import EPUB/MP3 → pipeline → 本地听
```

### 公众号回复模板（草稿）

```text
【Readalong 句级带读 · 开源 Demo】

试读（第 1 章）：https://hub.yoloworld.site:8883/readalong/web/
（Safari/Chrome → 添加到主屏幕）

开源仓库：<GitHub URL>/readalong
仓库不含 MP3/EPUB，须自备正版素材。

快速开始见 README：import → pipeline.sh 1 → 本地 :8791/web/

Issues 欢迎讨论；不做一对一部署辅导。
```

---

## 2. 与当前实现对齐

| 能力 | 用途 |
|------|------|
| `READALONG_MAX_PUBLIC_CHAPTER=1` | 公网试读 |
| `admin` 登录（`.env`，勿提交） | **仅本人**外网听全本，不发给读者 |
| 321 Mbps 上行 | 试读 ch1 足够；全本流量由读者自建承担 |
| Caddy 静态分离 `web/` | 减 Python 负载 |

---

## 3. 开源边界（版权）

**可公开：**

- `web/`、`scripts/`、`docs/`、`data/book01_chapters.json`（结构配置）

**不得进公开仓库 / 不得公网分发：**

- `samples/` 内 HP MP3、EPUB
- `.env`、`data/.auth_secret`
- 含全书句子的 manifest（若对外仅 Demo ch1，服务器上仍勿开放全章 URL）

README 须写明 **Bring Your Own Book**。

---

## 4. 公网试听前须完成的网络安全清单

> **原则**：8883 映射的是整台 Caddy Hub（SideStore / Home Hub / English Buddy / Readalong 等），**开试读 = 扩大整站攻击面**，不能只做 readalong 半套。

### 4.1 必做（推广前）

- [ ] **admin 强密码** — `readalong/.env` 中 `READALONG_ADMIN_PASSWORD` 非弱口令；`.env` 已在 `.gitignore`
- [ ] **确认 `:8791` 仅监听 `127.0.0.1`** — 外网不可直连 Python 静态服务
- [ ] **Caddy 登录/管理面** — Home Hub、English Buddy 等其它 Hub 路径须各自鉴权或不可匿名滥用
- [ ] **English Buddy 并发上限** — 保持 `MAX_READ_ALONG_SESSIONS` / `WHISPER_WORKERS` 默认低位，防 WS 打满 CPU
- [ ] **试读仅 ch1** — 确认外网 IP 下 `ch02.json` / `chapter02.mp3` / EPUB / `*_words.json` 均 403
- [ ] **日志与告警** — 至少定期看 `readalong/logs/`、Caddy/docker 日志；异常流量能发现
- [ ] **一键下线** — 熟悉「Caddy 注释 readalong 块 + `docker compose restart caddy`」或停 launchd readalong

### 4.2 强烈建议

- [ ] **登录限速** — `/api/auth/login` 按 IP 限流（防 admin 暴力破解）
- [ ] **Caddy 层 rate limit** — 对 `/readalong/*` 限制单 IP 请求率（防刷带宽、扫目录）
- [ ] **字典 API 限流或内网-only** — `/api/dict` 会打外网有道，可被滥用
- [ ] **路由器** — 仅映射必要端口（8883→8443）；管理口不对 WAN 开放
- [ ] **Mac 防火墙** — 除 Docker 映射口外，不额外暴露服务
- [ ] **备份与恢复** — 被扫/被打时知道如何快速断公网（关端口映射或停 Caddy）

### 4.3 可选（流量变大再做）

- [ ] 试读 Demo 迁到 **Cloudflare Pages / 独立 VPS**，Hub 只留 Git 链接（攻击面与家庭 IP 解耦）
- [ ] **Fail2ban** / 云 WAF 对 8883 前置
- [ ] 独立子域 + 最小 Caddy `handle`，不与其他服务共端口

### 4.4 已知风险（接受或缓解）

| 风险 | 说明 | 缓解 |
|------|------|------|
| 8883 共享 Hub | 攻击者扫的是整站，不只 readalong | 限流 + 各服务鉴权 + 监控 |
| 试读 URL 公开 | 不关注也能听 ch1 | 设计如此；ch1 带宽可控 |
| 猜 URL 下 EPUB | 已封禁 demo 路径 | 保持 `_DEMO_SENSITIVE_RE` 规则 |
| admin 单账号 | 泄露则全章 | 强密码 + 限速 + 勿分享 |

---

## 5. 推广节奏

1. **现在**：代码与文档就绪；策略记录本文；**暂不主动推公网试读**
2. **完成 §4.1 + 至少 2 项 §4.2** 后：公众号/小红书发技术文 + 试读链接 + Git
3. **观察流量**：若 ch1 试听并发或扫描异常 → 限流或 Demo 迁出家庭网络

---

## 6. 相关文档

- 部署与试读门禁：`../README.md`
- Pipeline 踩坑：`PIPELINE-NOTES.md`
- 导入 Skill：`.cursor/skills/readalong-import/`
- Hub 基础设施：`../../sidestore-infra/README.md`
