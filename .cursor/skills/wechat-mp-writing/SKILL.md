---
name: wechat-mp-writing
description: 牛马也智能公众号改稿、去 AI 味、自媒体引流写法、eval 质检与人工审阅。用户说润色、改稿、去 AI 味、引流、完读、语气用词、eval、推稿前质检、审阅 evening 三篇时使用。工程流水线见 wechat-mp-drafts；增长决策见 wechat-mp-growth-ops。
---

# 公众号写稿与质检（wechat-mp-writing）

**账号**：牛马也智能。**分工**：本 skill = 改稿/质检；`wechat-mp-drafts` = 定时/推稿工程；`wechat-mp-growth-ops` = 何时发、发什么。

## 何时用本 skill

| 用户说 | 读 |
|--------|-----|
| 润色 / 改稿 / 去 AI 味 | [anti-ai-voice.md](anti-ai-voice.md) + [revision-workflow.md](revision-workflow.md) |
| **引流 / 完读 / 转发 / 语气用词 / 怎么让人看下去** | **[traffic-copy-craft.md](traffic-copy-craft.md)** |
| **社会热点 / 民生新闻 / 排版语气感情** | **[social-commentary-voice.md](social-commentary-voice.md)** |
| **热点深评 / hotspot 太水 / 仿写参考 / 标题很怪** | **[hotspot-deep-review.md](hotspot-deep-review.md)**（2026-07-30 定稿） |
| 写深一点 / 立意 / 宏观见解 | **[depth-and-opinion.md](depth-and-opinion.md)** |
| 搜一搜 / 标题被截断 / 表意不完整 / **标题很怪** | **[sousou-content-rules.md](sousou-content-rules.md)**（含 §标题硬禁 2026-07-28） |
| eval / 质检 / 能不能推 | [eval-gates.md](eval-gates.md) |
| evening 两篇审阅（news+hotspot） | [revision-workflow.md](revision-workflow.md) §evening |
| 标题/开篇/搜一搜数据复盘 | `wechat-mp-drafts/sousou-analytics-sop.md` · `writing-guide.md` |

**上下文预算**：先按上表选唯一主文档。除非该文档明确要求交叉检查，否则不要同时读取所有写作规范和历史案例。

## 推稿前必跑（路线 A 已接入 batch）

```bash
cd stock-ai

# 整批门禁（evening 默认门槛：总分≥75、AI味≤20）
uv run python -m scripts.tools.wechat_mp_push_quality_gate --batch evening

# 单篇细查
uv run python -m scripts.tools.wechat_mp_eval --kind news --traffic
uv run python -m scripts.tools.wechat_mp_eval --kind sector --traffic
uv run python -m scripts.tools.wechat_mp_eval --kind dragons --traffic
```

`wechat_mp_draft_batch --batch evening` **推稿前自动跑门禁**；未过且 `WECHAT_MP_QUALITY_GATE_STRICT=1`（默认）则 **不 upsert**。

## 环境变量

| 变量 | 默认 | 含义 |
|------|------|------|
| `WECHAT_MP_PUSH_QUALITY_GATE` | evening=1 | 0 关闭门禁 |
| `WECHAT_MP_QUALITY_MIN_SCORE` | 75 | 总分下限 |
| `WECHAT_MP_QUALITY_MAX_AI_FLAVOR` | 20 | AI 味上限 |
| `WECHAT_MP_QUALITY_GATE_STRICT` | 1 | 未过则阻断推稿 |
| `WECHAT_MP_QUALITY_TRAFFIC_BLOCK` | 0 | 1 时 traffic 自动项失败也算硬失败 |

## Agent 工作流（简）

1. `draft_batch --dry-run` 或 `push_quality_gate --batch evening` 看报告
2. 未过 → 先查 [sousou-content-rules.md](sousou-content-rules.md)（标题完整、单主题、开篇一致）→ [traffic-copy-craft.md](traffic-copy-craft.md)（开篇钩子、节奏、可转述颗粒）→ 再按 [revision-workflow.md](revision-workflow.md) 改开篇/合规词（勿大改数据段）
3. 重跑门禁或 `wechat_mp_draft --kind <k>` 单篇 upsert
4. 人工 mp 后台群发前再扫一眼 news 10 条去重、hotspot 与 news 勿重复深写同一题

## 交叉引用

- 模板与结构：`wechat-mp-drafts/evening-trilogy-templates.md`
- 研究员口吻：`wechat-mp-drafts/researcher-voice.md`
- 引流与完读：`traffic-copy-craft.md` · `wechat-mp-drafts/writing-guide.md`
- 规则与代码对照：`wechat-mp-drafts/rules-implemented.md`
- 增长推稿：`wechat-mp-growth-ops/draft-ops.md`
