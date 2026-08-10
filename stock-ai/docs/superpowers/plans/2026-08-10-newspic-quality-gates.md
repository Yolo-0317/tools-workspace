# 公众号贴图质量门禁与回读 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让贴图草稿在上传前符合写作规范，并在写入后自动回读验收。

**Architecture:** 在 `wechat_mp_newspic.py` 集中实现内容、来源与远端回读校验，按普通热点和 `virtual_lifestyle` 两个 profile 选择门禁；CLI 保持素材解析职责并将来源清单传入发布函数。复用现有微信草稿查询接口，不新增依赖。

**Tech Stack:** Python、pytest、微信公众号 draft API

## Global Constraints

- 不改变热点长图文链路。
- 不自动发布或群发。
- 所有生产代码变更先写失败测试。

---

### Task 1: 编辑与来源门禁

**Files:**
- Modify: `tests/unit/test_wechat_mp_newspic.py`
- Modify: `scripts/tools/wechat_mp_newspic.py`

**Interfaces:**
- Consumes: `validate_newspic_input(...)`、`validate_newspic_image_sources(...)`
- Produces: 与热点及栀夏两个 SOP 分别一致的标题、正文、来源和原创标识校验。

- [ ] 写标题、按 profile/图数正文字数、报道页标题及原创标识的失败测试。
- [ ] 运行聚焦测试并确认因缺少新行为而失败。
- [ ] 实现最小校验逻辑。
- [ ] 运行聚焦测试并确认通过。

### Task 2: 写入后回读

**Files:**
- Modify: `tests/unit/test_wechat_mp_newspic.py`
- Modify: `scripts/tools/wechat_mp_newspic.py`

**Interfaces:**
- Consumes: `fetch_draft_news_item(media_id=...)`
- Produces: `verify_newspic_draft(...)`，由 `upsert_newspic_draft(...)` 在远端写入后调用。

- [ ] 写回读成功、回读接口失败及字段不一致的失败测试。
- [ ] 运行聚焦测试并确认因缺少回读而失败。
- [ ] 实现最小回读校验并接入创建、更新路径。
- [ ] 运行聚焦测试并确认通过。

### Task 3: 验证并推送一个草稿

**Files:**
- Modify only ignored runtime article/image/source artifacts as needed.

**Interfaces:**
- Consumes: `python -m scripts.tools.wechat_mp_newspic_draft`
- Produces: 一个经 dry-run 和远端回读确认的 `newspic` 草稿。

- [ ] 运行贴图、Codex 图片和真实报道图测试集。
- [ ] 为“下班两小时”准备合规的栀夏文案和 2～3 张角色一致图片。
- [ ] 执行 dry-run。
- [ ] 正式写入草稿并记录回读结果，不执行发布。
