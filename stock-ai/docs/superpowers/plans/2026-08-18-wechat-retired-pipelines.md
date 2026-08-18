# 公众号旧链路退役 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除不再使用的公众号商品垂直稿、Top5、龙虎榜和增长提醒链路，并让现用通知与热点研究测试稳定通过。

**Architecture:** 以当前 `news + hotspot` 批次为真源，从公开路由向内删除不可达旧模块；增长开关收敛为显式环境变量。现用热点研究保留生产联网能力，但测试通过依赖注入隔离网络。

**Tech Stack:** Python 3.11、pytest、公众号草稿工具、Markdown 技能文档。

## Global Constraints

- 用户可见内容、UI 与汇报禁止 emoji。
- 不改写历史方案文档，只更新当前运行入口。
- 不提交工作区中与本任务无关的草稿、素材或用户改动。
- 生产代码变更必须先有失败测试或现有失败用例。

---

### Task 1: 公开路由退役

**Files:**
- Modify: `scripts/tools/wechat_mp_content.py`
- Modify: `scripts/tools/wechat_mp_draft.py`
- Test: `tests/unit/test_wechat_mp_retired_kinds.py`

**Interfaces:**
- Consumes: `build_article(kind=...)` 与 CLI kind 路由。
- Produces: 当前公开 kind 集合不含 `top5`、`dragons`。

- [ ] 写失败测试，断言公开 kind 集合和 `build_article` 不再接受两个退役 kind。
- [ ] 运行定向测试，确认因旧路由仍存在而失败。
- [ ] 删除公开 kind、构建分支和命令提示中的旧入口。
- [ ] 运行定向测试并提交。

### Task 2: 删除旧文章实现

**Files:**
- Delete: `scripts/tools/wechat_mp_commerce_draft.py`
- Delete: `scripts/tools/wechat_mp_commerce_slots.py`
- Delete: `scripts/tools/wechat_mp_top5_article.py`
- Delete: `scripts/tools/wechat_mp_top5_polish.py`
- Delete: `scripts/tools/wechat_mp_dragons_article.py`
- Delete: `scripts/tools/wechat_mp_dragons_polish.py`
- Delete: `scripts/tools/wechat_mp_evening_align.py`
- Delete: `tests/unit/test_wechat_mp_commerce_draft.py`
- Delete: `tests/unit/test_wechat_mp_commerce_layout.py`
- Delete: `tests/unit/test_wechat_mp_top5_article.py`
- Delete: `tests/unit/test_wechat_mp_top5_polish.py`
- Delete: `tests/unit/test_wechat_mp_dragons_article.py`
- Delete: `tests/unit/test_wechat_mp_evening_align.py`

**Interfaces:**
- Consumes: Task 1 已关闭的公开入口。
- Produces: 仓库中不存在可导入的旧文章生成模块。

- [ ] 用 `rg` 确认模块仅由退役入口、测试或文档引用。
- [ ] 删除实现和专属测试，清理共享枚举、SEO、商品与排版映射中的旧 kind。
- [ ] 运行导入扫描和公众号相关定向测试并提交。

### Task 3: 删除增长提醒与配置依赖

**Files:**
- Delete: `scripts/tools/wechat_mp_growth.py`
- Delete: `scripts/tools/wechat_mp_growth_check.py`
- Delete: `scripts/tools/wechat_mp_growth_remind.py`
- Delete: `scripts/wechat_mp_growth_remind.sh`
- Delete: `tests/unit/test_wechat_mp_growth.py`
- Modify: `scripts/tools/wechat_mp_draft_batch.py`
- Modify: `scripts/tools/wechat_mp_draft_notify.py`
- Modify: `scripts/tools/wechat_mp_stock_ai_cta.py`
- Modify: `scripts/install-wechat-mp-launchd.sh`

**Interfaces:**
- Consumes: `EVENING_PUBLISH_ORDER = ("news", "hotspot")` 与 `WECHAT_MP_STOCK_AI_CTA`。
- Produces: 晚间批次固定，CTA 默认关闭，通知不依赖本地增长 JSON。

- [ ] 写失败测试，断言 CTA 未配置时关闭、晚间 kind 固定且通知不包含增长模块旧文案。
- [ ] 运行测试确认旧配置依赖导致失败。
- [ ] 移除增长导入、包装脚本和安装项，改用固定批次与显式环境变量。
- [ ] 运行定向测试并提交。

### Task 4: 修复保留链路的两个测试

**Files:**
- Modify: `tests/unit/test_wechat_mp_draft_notify.py`
- Modify: `tests/unit/test_wechat_mp_hot_trends_enrich.py`

**Interfaces:**
- Consumes: 当前通知 `news + hotspot`；`attach_hotspot_research(item)`。
- Produces: 无真实网络副作用的稳定单测。

- [ ] 先运行两个失败用例并记录现有失败。
- [ ] 将通知断言更新为当前批次；热点研究测试 monkeypatch 研究结果。
- [ ] 运行两个测试文件并提交。

### Task 5: 文档与全量验证

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-drafts/INDEX.md`
- Modify: `.cursor/skills/wechat-mp-drafts/reference.md`
- Modify: `.cursor/skills/wechat-mp-drafts/operations-sop.md`
- Modify: current README/docs found by `rg`.

**Interfaces:**
- Consumes: Tasks 1–4 的最终入口。
- Produces: 当前文档和代码一致。

- [ ] 清理当前入口文档中的旧命令和定时表述，保留历史设计文档。
- [ ] 运行 `rg` 确认无活动代码导入已删除模块。
- [ ] 运行 `python -m compileall scripts/tools` 的相关模块检查。
- [ ] 完整运行 `pytest tests/unit/test_wechat_mp_*.py -q`。
- [ ] 检查 `git diff --check` 和精确暂存内容，提交最终文档。
