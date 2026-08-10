---
name: wechat-mp-growth-ops
description: >-
  Growth operator for WeChat MP 「牛马也智能」: read-tier KPIs, traffic主 monetization,
  daily/weekly analytics, evening draft production (news+dragons+sector), market triggers,
  title/完读 optimization, cold-start/起号. Use when user asks 公众号运营、涨阅读、流量主收入、
  复盘数据、写稿推草稿、起号、新号、入池、冷启动、推荐为零、运营多久、牛马也智能增长,
  or wants end-to-end ops beyond single-doc edits.
paths:
  - .cursor/skills/wechat-mp-growth-ops/
  - .cursor/skills/wechat-mp-drafts/
  - .cursor/skills/wechat-mp-drafts/content-analytics-sop.md
  - stock-ai/scripts/tools/wechat_mp_*.py
  - stock-ai/data/wechat_mp_draft_slots.json
  - stock-ai/output/wechat_mp_recommend_daily_page*.json
  - stock-ai/docs/WECHAT_MP_SCHEDULING.md
---

# 牛马也智能 · 增长运营官

**角色**：带着现有账号 **持续增长阅读 + 合理变现**，不是单次改稿。工程细节仍读 [wechat-mp-drafts](../wechat-mp-drafts/INDEX.md)；本 skill 管 **目标、节奏、数据、写稿决策**。

## 命名

| 用户说 | 指 |
|--------|-----|
| 公众号、牛马也智能、运营、涨阅读、流量主 | **本 skill** |
| 只改一篇 prompt / 合规 / pytest | [wechat-mp-drafts](../wechat-mp-drafts/SKILL.md) |
| 简选带货 | commerce（搁置） |

## 决策树

```
用户意图？
├─ 昨日/今日数据、流量主、复盘        → analytics-sop.md + content-analytics-sop（渠道/日期）
├─ 内容分析页 / 7日阅读 / 渠道占比    → wechat-mp-drafts/content-analytics-sop.md
├─ 阅读怎么上台阶、KPI、收入预期      → growth-playbook.md + revenue-model.md
├─ 起号、新号、入池、冷启动、运营多久  → cold-start-playbook.md
├─ 今天要不要写稿 / 推草稿 / 加 market  → draft-ops.md
├─ 关注引流 / 星标 / 写作夸克 / 关注回复定稿  → follow-growth-copy.md + account-packaging.md
├─ 润色 / 改稿 / eval / 去 AI 味 / **引流 / 完读 / 语气** → wechat-mp-writing/SKILL.md（引流见 traffic-copy-craft；标题硬禁见 sousou-content-rules）
├─ 改单篇文案结构                     → wechat-mp-drafts/evening-trilogy-templates.md
└─ 搜一搜看板 / 标题词                → wechat-mp-drafts/sousou-analytics-sop.md
```

## 北极星（2026-06 实盘校准）

| 层级 | 阅读（三篇合计/日） | 流量主入账/日（概览「昨日 +X」） | 状态 |
|------|---------------------|----------------------------------|------|
| **底盘** | 60–70 | ¥0.3–0.5 | 格式切换期 |
| **当前** | **75–85** | **¥1.2–1.5** | 6/9–6/10 已验证 |
| **下一阶** | **90–110** | ¥1.5–2.0 | 需头条 + 偶发 market |
| **冲高** | 130+（单日） | ¥2.5+ | 大事件 / market，**非日常** |

**Outlier 排除**：「收盘复盘：油价+半导体…」**321 读** = 用户群发很多群聊，**不得**作标题模板或 KPI 上限。见 `project-memory.mdc` §2026-06-09。

**收入口径**：流量主 **以概览「昨日 +X」为准**；数据统计「每日明细」行收入可滞后，勿与概览混用。

## 每周循环（运营官默认动作）

```text
一  读 growth-playbook「本周只调一类」
二  若用户给 mp token → analytics-sop 抓昨日数据
三  18:20 前 draft-ops 预检（eod / skip / dry-run）
四  人工发表后：记录标题 + 次日对阅读
五  流量主概览入账 vs 阅读 → 更新周表 output/wechat_mp_weekly/
```

## 子文档

| 文档 | 用途 |
|------|------|
| [growth-playbook.md](growth-playbook.md) | 阅读台阶、渠道、大行情识别、变现组合 |
| [cold-start-playbook.md](cold-start-playbook.md) | **起号**：入池机制、搜一搜主粮、发表必勾、限推恢复、教程吸收表 |
| [draft-ops.md](draft-ops.md) | **写稿 + 推草稿**全流程（evening / market / 质检） |
| [analytics-sop.md](analytics-sop.md) | OpenCLI 抓取、联合分析模板、token · 渠道见 [content-analytics-sop](../wechat-mp-drafts/content-analytics-sop.md) |
| [revenue-model.md](revenue-model.md) | 流量主/CPS/引流  realistic 预期 |
| [follow-growth-copy.md](follow-growth-copy.md) | **关注引流**：简介/关注回复/稿末星标句、A/B、禁忌 |
| [../wechat-mp-writing/traffic-copy-craft.md](../wechat-mp-writing/traffic-copy-craft.md) | **写稿引流**：开篇钩子、节奏、语气用词、可转述颗粒、站队问句 |

## 硬约束（与工程 skill 一致）

- 个人号 **每天 1 次通知** → 多篇 **同批群发**；禁止错开发表时间  
- 交易日 evening：**内容** `news→dragons→sector`；**封面槽** 1 牛马 → 2 多屏 → 3 财经（与正文 kind 解耦）  
- 非财经（workspace/英语/temp）**全周 ≤1 篇**  
- 看稿：**mp 草稿箱**；禁止默认写 `output/*preview*.html`  
- `top5` **不在定时**；仅手动 `--kind top5`

## 增长模型（默认开启）

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_growth_check      # 收盘后/发表前
# 18:20 批次 notify 自动附增长清单
```

配置：`data/wechat_mp_growth_focus.json` · 详见 [growth-playbook.md](growth-playbook.md) §零

## 常用命令（摘要）

```bash
cd stock-ai
bash scripts/wechat_mp_draft_scheduled.sh --dry-run
uv run python -m scripts.tools.wechat_mp_draft_batch --batch evening
uv run python -m scripts.tools.wechat_mp_draft --kind market --edition close
uv run python -m scripts.tools.wechat_mp_eval --kind news --traffic
uv run pytest tests/unit/test_wechat_mp_*.py -q
```

抓取与分析见 [analytics-sop.md](analytics-sop.md)。
