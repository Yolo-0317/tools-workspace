# 公众号返佣单品稿型 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为「牛马也智能」增加手动 `product_feature` 稿型，从已有返佣接口选品并生成需求切入的单品草稿。

**Architecture:** `wechat_mp_product_feature.py` 负责候选选择、请求及成稿验证；`wechat_mp_draft.py` 路由手动请求与草稿；`wechat_mp_product.py` 只为该稿型生成经核对的 CPS 卡。选品和文章事实以结构化 JSON 交接，普通长文的返佣禁令继续生效。

**Tech Stack:** Python 3、pytest、现有 `wechat_mp_product` Select 接口和微信公众号草稿 API。

## Global Constraints

- `product_feature` 只手动运行、单独槽位，`--kind all` 与定时批次不包含它；只写草稿，不自动发表。
- 每篇只推一件商品、恰好一张普通 CPS 商品卡；其他普通长文继续拒绝普通 CPS 卡。
- 每个关键词最多读取前两页、每页 30 件；销量提示门槛为 1000。
- 商品报价乘佣金比例与预计佣金差额大于 1 元且超过预计值 20% 时排除。
- 写草稿前重新查询；价格变化超过 10% 或预计佣金变化超过 20% 时停止。
- 不编造亲测、采访或效果，显著披露广告关系；标题不超过 32 字、摘要不超过 128 字，用户可见内容无 emoji。
- 不更改用户现有未提交改动；每次提交只包含本计划对应文件。

---

## File map

- `scripts/tools/wechat_mp_product_feature.py`：纯选品、请求结构、Codex 稿件校验、商品卡身份与草稿回读校验。
- `scripts/tools/wechat_mp_product.py`：复用 Select 和 `cps_data_pid`，增加单品稿专用插卡函数，不启用普通长文自动插卡。
- `scripts/tools/wechat_mp_content.py`：注册新稿型并路由文章构建；`DAILY_DRAFT_KINDS` 保持不变。
- `scripts/tools/wechat_mp_draft.py`：单篇请求、`--codex-draft`、只读预览和安全写草稿。
- `scripts/tools/wechat_mp_draft_slots.py`：为新稿型增加先创建新草稿再删除旧稿的安全更新入口。
- `scripts/tools/wechat_mp_short_drama.py`：明确 `product_feature` 的单 CPS 例外，其他长文禁令保持原样。
- `tests/unit/test_wechat_mp_product_feature.py` 与现有 CLI/槽位测试：验证选品、稿件、商品卡和路由。
- `.cursor/skills/wechat-mp-drafts/SKILL.md`、`.cursor/skills/wechat-mp-writing/SKILL.md`：新增手动稿型路由与写作规范。

### Task 1: 候选选品与只读请求

**Files:** Create `scripts/tools/wechat_mp_product_feature.py`; Test `tests/unit/test_wechat_mp_product_feature.py`.

**Interfaces:** Consumes `search_daihuo_products(keyword, page_no, page_size)` 与 `summarize_daihuo_product(raw)`；produces `prepare_product_feature_request(*, keywords: tuple[str, ...], search_fn=search_daihuo_products) -> dict`。

- [ ] 写失败测试：提供两页重复商品、低销量商品和价格/佣金比例矛盾商品；断言只保留去重后满足销量门槛且金额一致的候选，按需求贴合、销量和预计单笔佣金排序。搜索函数以注入的假函数替代网络。
- [ ] 运行 `.venv/bin/python -m pytest tests/unit/test_wechat_mp_product_feature.py -q`，确认失败源于新接口缺失。
- [ ] 实现 `prepare_product_feature_request`：每词两页且 `page_size=30`；逐项记录查询词、页码和当前时间；过滤销量 `<1000`、佣金或价格 `<=0`、金额差 `>max(1, 0.2*commission)`；返回前三候选与排除原因，无合格候选抛 `ValueError`。请求不得保存缓存或发送草稿。
- [ ] 重跑该测试，确认通过；只提交本任务文件。

### Task 2: 结构化成稿与内容门禁

**Files:** Modify `scripts/tools/wechat_mp_product_feature.py`, `scripts/tools/wechat_mp_product.py`, `scripts/tools/wechat_mp_short_drama.py`; Test `tests/unit/test_wechat_mp_product_feature.py`.

**Interfaces:** Produces `load_product_feature_draft(path: Path) -> ProductFeatureDraft`、`build_product_feature_article(draft: ProductFeatureDraft, *, current_product: dict, upload_figures: bool) -> dict`、`verify_product_feature_article(article: dict, product_id: str) -> None`。

- [ ] 写失败测试：结构化稿含产品 ID、需求场景、标题、摘要、正文、来源和事实项；验证来源绑定、广告标识、不适合人群、禁止虚构亲测、标题/摘要长度、唯一 `data-pid`、无短剧组件。分别给出缺来源、两张卡和错误产品 ID 的反例。
- [ ] 运行该测试，确认失败。
- [ ] 实现数据解析与验证，使用 `_article_shell(..., kind="product_feature", attach_promotion=False)` 渲染正文，再由专用插卡函数通过已选商品的 `warehouse_id`、`product_id` 或 `sku_id` 生成一张 CPS 卡。新例外只允许 `product_feature`，并在现有长文安全函数中显式校验恰好一张普通 CPS 卡。
- [ ] 重跑测试并只提交本任务文件。

### Task 3: CLI、独立草稿槽位及回读

**Files:** Modify `scripts/tools/wechat_mp_content.py`, `scripts/tools/wechat_mp_draft.py`, `scripts/tools/wechat_mp_draft_slots.py`; Test `tests/unit/test_wechat_mp_product_feature.py` and relevant `test_wechat_mp_draft*.py`.

**Interfaces:** CLI `--kind product_feature --dry-run` 输出只读选品请求；`--kind product_feature --codex-draft <json> --dry-run` 预检；去掉 `--dry-run` 仅在用户授权写草稿时执行。专用槽位键为 `product_feature`。

- [ ] 写失败测试：`DRAFT_KINDS` 含新稿型、`DAILY_DRAFT_KINDS` 不含；请求阶段不调用 `draft_add`、`draft_delete` 或图片上传；`--publish` 对该稿型拒绝；预检不写槽位；写入先 `draft_add` 再 `draft_delete`，失败保留旧槽位。
- [ ] 运行相关测试，确认失败。
- [ ] 接入主 CLI 的请求与结构化稿路由；写入前重查同一商品并比较价格、佣金，调用草稿 API 后回读并核对 `data-pid`。回读不符时报告草稿不可发表，不自动发布。打印旧槽位标题与新标题。
- [ ] 重跑相关测试并只提交本任务文件。

### Task 4: 写作路由与整体验证

**Files:** Modify `.cursor/skills/wechat-mp-drafts/SKILL.md`, `.cursor/skills/wechat-mp-drafts/INDEX.md`, `.cursor/skills/wechat-mp-writing/SKILL.md`; Create `.cursor/skills/wechat-mp-writing/product-feature.md`.

**Interfaces:** 新稿型操作说明和写作提示词；不改变热点深评、文学稿的 DeepSeek 手工交接。

- [ ] 在专题文档写明「具体需求 → 选购标准与替代方案 → 单品能解决的部分 → 限制与不适合人群 → 一张商品卡」；列出查证、披露、非亲测和标题规则。
- [ ] 更新入口路由和示例命令；明确 `--dry-run` 只读、独立槽位、普通稿禁插返佣和人工发布。
- [ ] 运行 `.venv/bin/python -m pytest tests/unit/test_wechat_mp_product_feature.py tests/unit/test_wechat_mp_product.py -q` 及 CLI 相关测试；用 Select 接口只读搜索一轮，再执行新稿型 `--dry-run` 检查请求和预览。确认无真实草稿写入后提交文档。

## Final check

核对设计文档的选品门槛、单品写法、唯一商品卡、草稿隔离和失败保留旧槽位均有对应实现与测试。记录真实接口查询时间和因平台限制未能验证的环节，不将预计佣金写成实际收入。
