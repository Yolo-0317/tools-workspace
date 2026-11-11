# 公众号用户主动热点交付门禁 Implementation Plan

> **For agentic workers:** 逐项实施并在每项后做独立测试。当前任务不授权子代理；由主代理内联执行。

**Goal:** 把用户主动热点稿的事实、图片、正文确认和草稿续跑接成可核验的交付链。

**Architecture:** 保留现有文章 JSON、`figure_sources.json` 和 workflow 状态机。新增轻量 `editorial_handoff.json` 校验器；只有新建的用户主动 `hotspot` workflow 强制使用，历史记录和其他稿型保持兼容。写作 Skill 定义内容判断，草稿 Skill 定义操作与失败恢复。

**Tech Stack:** Python 3、pytest、现有微信草稿脚本和 Markdown Skill 文档。

## Global Constraints

- 不改定时稿、其他稿型和群发规则；只写草稿箱。
- 抖音只看搜索卡片与封面，不打开或播放视频；最多三张正文图，合格图不超过三张时全入正文且封面复用其中一张。
- 当前工作区已有大量用户改动，只在目标文件中做局部修改，不清理或重置。
- 不提交 `.env`、凭据、图片缓存或无关改动；提交信息若使用 Git，必须中文。

---

### Task 1: 已确认正文直接登记

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_workflow.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_browser_workflow.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_browser_write_cli.py`

**Interfaces:**
- `record_confirmed_body(workflow_id, raw_response, *, confirmation_text, root)` 接受 `RESEARCHED` 或 `PROMPT_CONFIRMED`，只限 `hotspot`。
- `BrowserWritingWorkflow` 新增 `response_sha256: str = ""`，对确认全文保存 SHA-256；老记录缺省为空。
- 普通 `record_response`、`record_pasted_response` 继续只接受 `PROMPT_CONFIRMED`。

- [ ] 写一条失败测试：从 `RESEARCHED` 登记完整正文及确认原话后状态为 `RESPONSE_RECEIVED`，`first_confirmation_at` 仍为空，正文摘要与手算 SHA-256 一致。
- [ ] 运行 `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_browser_workflow.py -q`，确认仅新测试按预期失败。
- [ ] 最小修改 `record_confirmed_body` 状态判断与摘要字段；保持缺正文、缺确认文本和 `literary` 拒绝。
- [ ] 复跑该测试文件与 CLI 对应测试，确认旧手工交接仍不能跳过首次确认。

### Task 2: 交付记录与关键主张校验

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_editorial_handoff.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_workflow.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_write.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_editorial_handoff.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_browser_write_cli.py`

**Interfaces:**
- `create_workflow(..., handoff_required: bool = False)`；CLI `prepare --kind hotspot` 传 `True`，旧调用保留默认值。
- `validate_handoff(path: Path, *, workflow: BrowserWritingWorkflow, article_path: Path, selected_images: VerifiedHotspotImages) -> HandoffSummary`，验证 workflow ID、文章文件 SHA-256、被确认正文 SHA-256、确认方式、关键主张、入选图片与来源清单一致。
- `stage --handoff <path>` 仅新 `hotspot` workflow 必填；`stage_edited_article` 保存 `handoff_path` 与 `article_sha256`；`push` 再次核对哈希，拒绝暂存后悄悄换稿。

- [ ] 写失败测试：缺主张来源或时间、把页面快照标为实时价格、缺正文确认摘要、文章文件被替换时均拒绝；完整记录返回可打印的核对摘要。
- [ ] 运行新测试文件，确认失败点来自缺少校验器而非测试数据错误。
- [ ] 实现 `editorial_handoff.json` 最小 schema：`workflow_id`、`article_sha256`、`confirmed_body_sha256`、`confirmation_mode`、`claims[]`、`images[]`。主张的 `kind` 限 `source_fact|reported_snapshot|party_statement|author_inference`；每条需 `text`、`source_url`、`published_at`、`observed_at`、`scope_or_period`、`body_anchor`。`reported_snapshot` 的正文锚点须指向带“当时／报道时”等时间限定的原句；作者推断不得标为来源原话。
- [ ] 在 `stage` 与 `push` 接入校验器，`show` 展示当前状态与可重试错误分类；质量报告列出未通过检查的名称与说明，不只显示总分。
- [ ] 运行新文件、workflow 与 CLI 测试，确认新旧入口兼容。

### Task 3: 图片语义核对与封面复用

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_image_policy.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_codex_images.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_hotspot_image_policy.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_editorial_handoff.py`

**Interfaces:**
- `validate_verified_hotspot_images(..., require_visual_check: bool = False)`；新工作流传 `True`，旧调用默认行为不变。
- 新工作流入选的 `figure_sources.json` 条目增加 `visual_description`、`visual_checked_at`、`evidence_role`；交付记录 `images[]` 以文件名和 SHA-256 对应入选图。

- [ ] 写失败测试：图片缺视觉核对字段、图片哈希不符、交付记录误把实景照当价格截图时拒绝；两张合格图必须都在正文且封面是其中一张。
- [ ] 运行图片门禁和交付记录测试，确认新增场景失败。
- [ ] 仅对 `require_visual_check=True` 增加字段及角色验证；`evidence_role=price_snapshot` 时只接受视觉说明含地点与价格的人工记录，最终画面检查仍由编辑目检，不伪称机器识图。
- [ ] 复跑相关测试；用本次月租稿两张真实图做本地干跑，不向微信写入。

### Task 4: 出口失败可续跑与 Skill 路由更新

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_workflow.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_write.py`
- Modify: `.cursor/skills/wechat-mp-writing/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-writing/editorial-evidence-gate.md`
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-drafts/operations-sop.md`
- Modify: `.cursor/skills/wechat-mp-everyday-economy/SKILL.md`
- Test: `stock-ai/tests/unit/test_wechat_mp_browser_write_cli.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_browser_workflow.py`

**Interfaces:**
- `record_push_environment_failure(workflow_id, code, *, root)` 保持 `PUSH_CONFIRMED`，记录错误分类，不擦除两次确认或文章路径。
- `push` 仅在出口预检失败时记录 `wechat_egress_unavailable`，本次命令退出；每次调用至多尝试一次，不自动循环。已成功写入时仍使用 `mark_drafted`。

- [ ] 写失败测试：模拟预检失败，断言确认和暂存稿保持、错误码可见；第二次调用不会改变正文或重复进入编辑；其他写稿失败不伪装成出口错误。
- [ ] 运行 CLI/workflow 测试，确认失败点。
- [ ] 实现错误分类与可续跑状态；不要关闭预检、修改白名单或输出凭据。
- [ ] 更新三层 Skill：研究层只产证据，写作层核主张与快照时间，草稿层核图片、确认与出口；去掉相互重复的详细规则并保留准确链接。出口失败只允许在获准网络环境按同一 workflow 重试一次，再失败就报告并停在可恢复状态。
- [ ] 运行 `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_browser_workflow.py tests/unit/test_wechat_mp_browser_write_cli.py tests/unit/test_wechat_mp_hotspot_image_policy.py tests/unit/test_wechat_mp_editorial_handoff.py -q`；运行 `python3 /Users/huan.yu/.codex/skills/.system/skill-creator/scripts/quick_validate.py` 分别校验三个 Skill；核对 Git diff 仅涉及计划内文件。

## 交付检查

- [ ] 用本次酒店月租稿的事实、图片和确认文本构造完整 `editorial_handoff.json` 干跑，不触碰微信草稿。
- [ ] 检查其他稿型和旧工作流测试未退化。
- [ ] 在最终汇报中区分“Skill 文档已更新”“门禁代码已验证”和“真实公众号未重复推稿”，不以测试通过代替线上发布验证。
