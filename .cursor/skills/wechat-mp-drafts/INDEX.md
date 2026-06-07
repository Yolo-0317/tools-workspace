# 牛马也智能 · 文档导航

> Agent **先读本页**选路径，再打开对应子文档；避免通读全部 12 个文件。

## 一句话

| 用户说 | 账号 | Skill |
|--------|------|-------|
| **公众号**、牛马也智能、晚间三篇 | `WECHAT_MP_*` | **本目录** |
| 简选、带货、小电 | commerce | [wechat-mp-commerce-drafts](../wechat-mp-commerce-drafts/SKILL.md)（**已搁置**） |

工作目录：`stock-ai/` · CLI：`uv run python -m scripts.tools.wechat_mp_draft`

---

## 按任务选读顺序

### 推草稿 / 定时批次（工程）

1. [SKILL.md](SKILL.md) — 命令与流水线摘要  
2. [operations-sop.md](operations-sop.md) — 19:00 写稿、发表、跳过、每周维护  
3. [reference.md](reference.md) — 环境变量、模块表、踩坑  
4. `stock-ai/docs/WECHAT_MP_SCHEDULING.md` — launchd / `skip` 文件  

### 改晚间三篇文案（sector + top5 + dragons）

1. **[evening-trilogy-templates.md](evening-trilogy-templates.md)** — **金标准（唯一优先）**  
2. [researcher-voice.md](researcher-voice.md) — 口吻与论证  
3. [sector-discovery.md](sector-discovery.md) — 仅 `sector` 选题  
4. [rules-implemented.md](rules-implemented.md) — 改代码前查映射  

### 改 market / news / workspace / temp

1. [templates.md](templates.md) — 各槽骨架与标题池  
2. [writing-guide.md](writing-guide.md) — 标题/排版/去 AI / 发布总检  
3. [researcher-voice.md](researcher-voice.md) — 行情四槽  

### 冲阅读 / 搜一搜 / 复盘数据

1. [traffic-optimization.md](traffic-optimization.md) — `--traffic`、`wechat_mp_eval`  
2. [sousou-analytics-sop.md](sousou-analytics-sop.md) — 看板与改稿闭环  
3. [stock-opencli](../stock-opencli/SKILL.md) — 内容分析 OpenCLI 抓取  
4. `stock-ai/docs/wechat_mp_seo_topics.md` — 推荐 `#` 词表  

### 改代码 / 合规 / 不回退

1. [rules-implemented.md](rules-implemented.md)  
2. [reference.md](reference.md)  
3. `stock-ai/tests/unit/test_wechat_mp_*.py`

---

## 文档职责（勿重复造轮子）

| 文档 | 只管什么 | 不管什么 |
|------|----------|----------|
| [brand.md](brand.md) | 定位、slogan、与简选边界 |
| [account-packaging.md](account-packaging.md) | **公众平台包装**：介绍、菜单、自动回复（人工粘贴） | 命令、env |
| [SKILL.md](SKILL.md) | Agent 入口、槽位表、流水线摘要 | 长模板正文 |
| [operations-sop.md](operations-sop.md) | 节奏、人工发布、维护 | prompt 细则 |
| [evening-trilogy-templates.md](evening-trilogy-templates.md) | 晚间三篇结构与好句 | market/news |
| [templates.md](templates.md) | 五槽模板（**晚间指向 trilogy**） | 工程 API |
| [writing-guide.md](writing-guide.md) | 行业写法 + 发布前五步 | 批次 cron |
| [researcher-voice.md](researcher-voice.md) | `RESEARCHER_VOICE_RULE` | 封面 env |
| [sector-discovery.md](sector-discovery.md) | 热门行业多源投票 | 龙头逻辑 |
| [reference.md](reference.md) | 模块、env、历史坑 | 运营周历 |
| [rules-implemented.md](rules-implemented.md) | 用户规则 → 代码 | 品牌故事 |
| [traffic-optimization.md](traffic-optimization.md) | 完读/推荐/垂直词 | 草稿 API |
| [sousou-analytics-sop.md](sousou-analytics-sop.md) | 搜一搜看板 SOP | 写稿 prompt |

### 仓库内关联（非 skill 目录）

| 路径 | 用途 |
|------|------|
| `stock-ai/assets/wechat_mp/COVER_THUMBS.md` | top5/dragons 封面定稿 |
| `stock-ai/docs/DEEPSEEK_USAGE.md` | `LLM_BACKEND` / `SOP_LLM_BACKEND` |
| `stock-ai/data/wechat_mp_skip_scheduled.date` | 按日跳过 18:20 自动写稿 |
| `stock-ai/output/wechat_mp_weekly/` | **运营周报**（搜一搜 7 天 + 下周只调一类） |

---

## 环境与 LLM（2026-06-04）

```bash
# stock-ai/.env
LLM_BACKEND=cursor              # 公众号写稿、战报
CURSOR_AGENT_MODEL=auto
SOP_LLM_BACKEND=deepseek          # 东财 SOP Top5 并发（勿改 cursor）
DEEPSEEK_API_KEY=sk-...
```

| 时刻 | 含义 |
|------|------|
| **19:00 launchd** | 交易日三篇；**周日/节假日** `news`（72h 个股优先）；**周六** 跳过 |
| **后台发表** | 服务号**一天一次通知** → 多篇宜同批群发，头条放最强一篇 |

---

## 修订

| 日期 | 说明 |
|------|------|
| 2026-06-04 | 初版导航；收敛 12 个子文档分工 |
