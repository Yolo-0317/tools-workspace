# 牛马也智能 · 文档导航

> Agent **先读本页**选路径，再打开对应子文档；避免通读全部 12 个文件。

## 一句话

| 用户说 | 账号 | Skill |
|--------|------|-------|
| **公众号**、牛马也智能 | `WECHAT_MP_*` | **本目录** |
| 简选、旧商品垂直稿 | — | **已退役，无生成入口** |

工作目录：`stock-ai/` · CLI：`uv run python -m scripts.tools.wechat_mp_draft`

---

## 按任务选读顺序

### 推草稿 / 定时批次（工程）

1. [SKILL.md](SKILL.md) — 命令与流水线摘要  
2. [operations-sop.md](operations-sop.md) — 19:00 写稿、发表、跳过、每周维护  
3. [reference.md](reference.md) — 环境变量、模块表、踩坑  
4. `stock-ai/docs/WECHAT_MP_SCHEDULING.md` — launchd / `skip` 文件  

### 改财经手动稿（market / sector / news）

1. [templates.md](templates.md) — 稿型骨架
2. [researcher-voice.md](researcher-voice.md) — 口吻与论证  
3. [sector-discovery.md](sector-discovery.md) — `sector` 选题
4. [rules-implemented.md](rules-implemented.md) — 改代码前查映射  

### 润色 / 改稿 / eval 质检 / **热点深评**

1. **[wechat-mp-writing/SKILL.md](../wechat-mp-writing/SKILL.md)** — 改稿与推稿门禁  
2. **[hotspot-deep-review.md](../wechat-mp-writing/hotspot-deep-review.md)** — 热点深评：参考仿写、去元叙述、事实标题、排版  
3. **[social-commentary-voice.md](../wechat-mp-writing/social-commentary-voice.md)** — **社会民生热点**：短段、物件立人、通报对照、感情色彩  
4. [eval-gates.md](../wechat-mp-writing/eval-gates.md) · [revision-workflow.md](../wechat-mp-writing/revision-workflow.md) · [anti-ai-voice.md](../wechat-mp-writing/anti-ai-voice.md) · [depth-and-opinion.md](../wechat-mp-writing/depth-and-opinion.md)

用户主动要求新写热点深评时，必须走 [deepseek-writer-sop.md](../wechat-mp-writing/deepseek-writer-sop.md) 的手工交接双确认流程：Agent 只提供完整提示词，用户自行向 DeepSeek 取标题和初稿并贴回，Agent 再核实编辑。Agent 不直接调用或控制 DeepSeek。配图必须先查抖音搜索结果卡片，只取封面且不打开视频；正文允许 0—3 张真实图，零图因缺封面而停止，禁止任何自动生成图片。定时热点仍使用 Codex。

### 文学与典籍（literary · 手动独立槽位）

1. 读取 [deepseek-writer-sop.md](../wechat-mp-writing/deepseek-writer-sop.md)。
2. Agent 研究并展示完整提示词，用户第一次确认后自行向 DeepSeek 取稿并贴回；Agent 不直接调用 DeepSeek。
3. Agent 核验原文、节目、篇数、字数、时代和人物关系，完成高亮及公开来源配图。
4. 用户第二次确认后写入 `literary`，不得复用或覆盖 `tv_review`。

### 热点商业（手动独立流程）

1. 从每日热点自动选题：`uv run python -m scripts.tools.wechat_mp_draft --kind hot_business --dry-run`
2. 手动指定热点：`uv run python -m scripts.tools.wechat_mp_draft --kind hot_business --topic "具体热点" --dry-run`
3. 该流程复用热点深评的研究、配图、合规和长图文渲染，但只写入 `hot_business` 槽位，不进入任何定时批次。

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
3. `stock-ai/assets/wechat_mp/templates/teach_you_a_lesson.body_core.md`
4. 改定稿 → `repush`；微调仍由 Codex 完成，禁止切换其他模型

### 单剧强情节推广稿（short_drama_feature · 手动独立槽位）

1. 生成请求：`uv run python -m scripts.tools.wechat_mp_draft --kind short_drama_feature --dry-run`，写出 `output/short_drama_feature_request.json`。
2. 当前 Codex 从收益前三候选中选一部，浏览公开资料并写 `output/short_drama_feature_codex.json`；每条剧情事实必须绑定平台资料和至少一个独立公开来源。
3. 校验预览：`uv run python -m scripts.tools.wechat_mp_draft --kind short_drama_feature --codex-draft output/short_drama_feature_codex.json --dry-run`。
4. 确认后去掉 `--dry-run`，只更新独立槽位，不自动发表。不得调用 Cursor/DeepSeek 自动写稿，也不得根据短剧池单段简介扩写情节。

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
| [templates.md](templates.md) | 当前手动财经稿模板 | 工程 API |
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
| `stock-ai/docs/DEEPSEEK_USAGE.md` | 公众号 Codex 与东财 DeepSeek 的边界 |
| `stock-ai/data/wechat_mp_skip_scheduled.date` | 按日跳过 18:20 自动写稿 |
| `stock-ai/output/wechat_mp_weekly/` | **运营周报**（搜一搜 7 天 + 下周只调一类） |
| `stock-ai/docs/WECHAT_MP_TV_REVIEW.md` | **影视试跑 tv_review_v2** 定稿模板（《铁拳教育》） |
| `stock-ai/assets/wechat_mp/templates/tv_review_v2.json` | tv_review 机器可读真源 |

---

## 环境与 LLM（2026-06-04）

```bash
# stock-ai/.env
WECHAT_MP_CODEX_TIMEOUT_SECONDS=420 # 定时公众号写稿只用 Codex，失败不回退
WECHAT_MP_CODEX_MAX_RETRIES=1
SOP_LLM_BACKEND=deepseek          # 仅非公众号的东财 SOP
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
