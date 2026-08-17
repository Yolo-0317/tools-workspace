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

### 润色 / 改稿 / eval 质检 / **热点深评**

1. **[wechat-mp-writing/SKILL.md](../wechat-mp-writing/SKILL.md)** — 改稿与推稿门禁  
2. **[hotspot-deep-review.md](../wechat-mp-writing/hotspot-deep-review.md)** — 热点深评：参考仿写、去元叙述、事实标题、排版  
3. **[social-commentary-voice.md](../wechat-mp-writing/social-commentary-voice.md)** — **社会民生热点**：短段、物件立人、通报对照、感情色彩  
4. [eval-gates.md](../wechat-mp-writing/eval-gates.md) · [revision-workflow.md](../wechat-mp-writing/revision-workflow.md) · [anti-ai-voice.md](../wechat-mp-writing/anti-ai-voice.md) · [depth-and-opinion.md](../wechat-mp-writing/depth-and-opinion.md)

### 贴图 / 图片消息 / 小绿书

1. [newspic-sop.md](newspic-sop.md) — 选题、文案、配图顺序与发布链路
2. `uv run python -m scripts.tools.wechat_mp_newspic_draft --help` — 创建或更新 `newspic` 草稿

### 改 market / news / workspace / temp

1. [templates.md](templates.md) — 各槽骨架与标题池  
2. [writing-guide.md](writing-guide.md) — 标题/排版/去 AI / 发布总检  
3. [researcher-voice.md](researcher-voice.md) — 行情四槽  

### 11:00 话题讨论（tv_trial · 2026-08-02 起）

1. **[tv-morning-discussion-sop.md](tv-morning-discussion-sop.md)** — 关注度选题 + 社会评论体（非五节剧评）  
2. **[social-commentary-voice.md](../wechat-mp-writing/social-commentary-voice.md)** — 社会民生：排版、语气、感情（Agent）；读者向摘要见 `stock-ai/docs/share/`  
3. 预览：`uv run python -m scripts.tools.wechat_mp_tv_morning_discussion --limit 8`

### 影视试跑（tv_review_v2 ·《铁拳教育》定稿 · 手动/片单）

1. **[tv-review-template.md](tv-review-template.md)** — **影视稿金标准（优先）**
2. **`stock-ai/docs/WECHAT_MP_TV_REVIEW.md`**
3. `stock-ai/data/wechat_mp_tv_review_golden/teach_you_a_lesson.body_core.md`
4. 改定稿 → `repush`；**禁止**为微调重跑 Codex

### 东财股吧转载（sector → 微信引流）

1. **[guba-repost-sop.md](guba-repost-sop.md)** — 股吧改写骨架、CTA 句式、0609 示例帖

### 关注引流 / 星标 / 关键词「写作」

1. **[follow-growth-copy.md](../wechat-mp-growth-ops/follow-growth-copy.md)** — 话术真源：简介/关注回复/稿末星标、读者可见 vs 内部策略、A/B  
2. **[account-packaging.md](account-packaging.md)** — 公众平台后台粘贴（菜单、自动回复、写作夸克链）  
3. [operations-sop.md](operations-sop.md) §二点五、§二点六 — 配置清单与每周衡量  
4. 读者向笔记：`stock-ai/docs/share/牛马也智能-AI写作与公众号API笔记.md`

### 冲阅读 / 搜一搜 / 复盘数据 / 增长运营

1. **[wechat-mp-growth-ops](../wechat-mp-growth-ops/SKILL.md)** — **增长运营官**：KPI 台阶、流量主口径、写稿推草稿、日复盘（优先）  
2. [cold-start-playbook.md](../wechat-mp-growth-ops/cold-start-playbook.md) — **起号**：入池、搜一搜主粮、发表必勾、限推恢复（用户问起号/新号/运营多久时读）  
3. [traffic-optimization.md](traffic-optimization.md) — `--traffic`、`wechat_mp_eval`  
3. [sousou-analytics-sop.md](sousou-analytics-sop.md) — 看板与改稿闭环  
4. **[content-analytics-sop.md](content-analytics-sop.md)** — **内容分析页**：日期范围、`.highcharts-container`、渠道 API  
5. [stock-opencli](../stock-opencli/SKILL.md) — OpenCLI 抓取命令  
6. `stock-ai/docs/wechat_mp_seo_topics.md` — 热点实体 SEO / `#话题` 词表  

### 改代码 / 合规 / 不回退

1. [rules-implemented.md](rules-implemented.md)  
2. [reference.md](reference.md)  
3. `stock-ai/tests/unit/test_wechat_mp_*.py`

---

## 文档职责（勿重复造轮子）

| 文档 | 只管什么 | 不管什么 |
|------|----------|----------|
| [brand.md](brand.md) | 定位、slogan、与简选边界 |
| [account-packaging.md](account-packaging.md) | **公众平台包装**：介绍、菜单、自动回复、关键词「写作」→ 夸克笔记 | 命令、env |
| [SKILL.md](SKILL.md) | Agent 入口、槽位表、流水线摘要 | 长模板正文 |
| [operations-sop.md](operations-sop.md) | 节奏、人工发布、维护、**关注引流 §二点六** | prompt 细则 |
| [evening-trilogy-templates.md](evening-trilogy-templates.md) | 晚间三篇结构与好句 | market/news |
| [templates.md](templates.md) | 五槽模板（**晚间指向 trilogy**） | 工程 API |
| [writing-guide.md](writing-guide.md) | 行业写法 + 发布前五步 | 批次 cron |
| [researcher-voice.md](researcher-voice.md) | `RESEARCHER_VOICE_RULE` | 封面 env |
| [sector-discovery.md](sector-discovery.md) | 热门行业多源投票 | 龙头逻辑 |
| [reference.md](reference.md) | 模块、env、历史坑 | 运营周历 |
| [rules-implemented.md](rules-implemented.md) | 用户规则 → 代码 | 品牌故事 |
| [traffic-optimization.md](traffic-optimization.md) | 完读/推荐/垂直词 | 草稿 API |
| [content-analytics-sop.md](content-analytics-sop.md) | **内容分析** · 流量来源 · 日期范围 | 搜一搜 plugin |
| [sousou-analytics-sop.md](sousou-analytics-sop.md) | 搜一搜看板 SOP | 写稿 prompt |

### 仓库内关联（非 skill 目录）

| 路径 | 用途 |
|------|------|
| `stock-ai/assets/wechat_mp/COVER_THUMBS.md` | top5/dragons 封面定稿 |
| `stock-ai/docs/DEEPSEEK_USAGE.md` | `LLM_BACKEND` / `SOP_LLM_BACKEND` |
| `stock-ai/data/wechat_mp_skip_scheduled.date` | 按日跳过 18:20 自动写稿 |
| `stock-ai/output/wechat_mp_weekly/` | **运营周报**（搜一搜 7 天 + 下周只调一类） |
| `stock-ai/docs/WECHAT_MP_TV_REVIEW.md` | **影视试跑 tv_review_v2** 定稿模板（《铁拳教育》） |
| `stock-ai/data/wechat_mp_tv_review_template.json` | tv_review 机器可读真源 |

---

## 环境与 LLM（2026-06-04）

```bash
# stock-ai/.env
WECHAT_MP_CODEX_TIMEOUT_SECONDS=420 # 公众号写稿固定 Codex
WECHAT_MP_CODEX_MAX_RETRIES=1
SOP_LLM_BACKEND=deepseek           # 东财 SOP Top5 并发，保持不变
DEEPSEEK_API_KEY=sk-...
```

| 时刻 | 含义 |
|------|------|
| **19:00 launchd** | 交易日三篇；**周日/节假日** `news`（72h 个股优先）；**周六** 跳过 |
| **后台发表** | **每天 1 次通知**（个人号）→ 多篇**同批群发**；头条放完读最强一篇；**禁止**18:30/18:40 错开 |

---

## 修订

| 日期 | 说明 |
|------|------|
| 2026-06-04 | 初版导航；收敛 12 个子文档分工 |
| 2026-06-16 | 增 content-analytics-sop（页面柱图 · daily-series · 6/2–6/15 实测 · 限推解读） |
| 2026-06-08 | 增 tv_review_v1 影视试跑模板导航（WECHAT_MP_TV_REVIEW.md） |
| 2026-06-18 | 增 cold-start-playbook 导航（起号 · 外部教程吸收） |
| 2026-06-18 | templates §news 去重；draft-ops 质检；rules-implemented 映射 |
