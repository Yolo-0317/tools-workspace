# 公众号社区写作规则择优整合实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已审计的社区写作与事实核验原则裁剪进现有公众号热点深评 Skill，并增强高置信度的自我审稿腔自动门禁。

**Architecture:** 新增一份只承载事实与编辑判断的参考文档，由 `hotspot-deep-review.md` 路由加载；`deepseek-writer-sop.md` 与 `anti-ai-voice.md` 仅保留必要摘要。自动代码只阻断明确的写作过程泄漏和自我审稿说明，来源独立性、信息增量与争议方身份继续人工判断。

**Tech Stack:** Markdown Skill 文档、Python 3、pytest。

## Global Constraints

- 不安装或执行任何社区 Skill、脚本或外部模型子进程。
- 不改变北上广深地域门禁、教育费用优先级、DeepSeek 手工交接和两次确认。
- 正文目标 900—1100 字，去空白后少于 850 字拒绝。
- 正文图片上限 3 张；找到不超过 3 张合格真实图时全部进入正文，其中一张同时作为封面。
- 自动阻断只覆盖高置信度问题；依赖上下文的判断保留为人工检查。
- 工作区已有用户改动，不提交或覆盖无关内容；实施完成后只报告本次差异。

---

### Task 1: 新增事实与编辑判断参考规范

**Files:**
- Create: `.cursor/skills/wechat-mp-writing/editorial-evidence-gate.md`
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md`
- Modify: `.cursor/skills/wechat-mp-writing/SKILL.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-09-14-wechat-community-writing-rules-integration-design.md`。
- Produces: 热点初稿核实与编辑时使用的独立参考规范，以及可发现的路由入口。

- [ ] **Step 1: 创建聚焦的参考文档**

写入五类内容：主张分类、来源优先级、来源独立性、写作与事实分离、逐段信息增量。明确“官方原文可单独证明政策条文，但争议方通报只能证明其公开说法”。

- [ ] **Step 2: 在热点执行真源中增加加载条件**

在“用户主动成稿入口”中要求：Agent 收到 DeepSeek 初稿后，完整读取 `editorial-evidence-gate.md`，先建内部核验清单，再改公开正文；内部标签和审校过程不得进入正文。

- [ ] **Step 3: 在 Skill 路由表中增加入口**

将“热点深评 / 推稿前事实核验”路由到 `hotspot-deep-review.md`，并由该文档按需加载新参考文档，避免每次写作加载全部资料。

- [ ] **Step 4: 验证文档可发现且没有复制社区固定模板**

Run: `rg -n "editorial-evidence-gate|事实|当事方说法|来源独立|信息增量" .cursor/skills/wechat-mp-writing/SKILL.md .cursor/skills/wechat-mp-writing/hotspot-deep-review.md .cursor/skills/wechat-mp-writing/editorial-evidence-gate.md`

Expected: 路由和规范均有命中；不存在强制口语短语、文化比喻或三来源逐条硬要求。

### Task 2: 收紧 DeepSeek 事实包与公开文案边界

**Files:**
- Modify: `.cursor/skills/wechat-mp-writing/deepseek-writer-sop.md`
- Modify: `.cursor/skills/wechat-mp-writing/anti-ai-voice.md`

**Interfaces:**
- Consumes: Task 1 的 `editorial-evidence-gate.md`。
- Produces: DeepSeek 提示词的事实来源边界，以及公开正文去自我审稿腔的编辑规则。

- [ ] **Step 1: 约束事实包内容**

明确风格参考只能影响表达，不能作为事实证据；事实包按“已核实事实、当事方说法、待核信息”分开，待核信息不得写成确定事实。

- [ ] **Step 2: 增加编辑后的逐段检查**

要求每段至少增加事实、解释、边界或判断；删除只换词重复上一段的内容。要求核心判断回应最强合理异议，但不机械设置固定段落或金句数量。

- [ ] **Step 3: 补充自我审稿腔示例与改写方向**

禁止“为了避免读者误解”“本文并不是要说”“这篇文章不能被理解为”等面向文章自身的解释。改为直接陈述事实差异、适用范围和家庭后果。

- [ ] **Step 4: 检查既有流程未被改写**

Run: `rg -n "用户自行|不得.*DeepSeek|两次确认|900—1100|四城|正文.*3 张|封面" .cursor/skills/wechat-mp-writing/deepseek-writer-sop.md .cursor/skills/wechat-mp-writing/hotspot-deep-review.md .cursor/skills/wechat-mp-drafts/SKILL.md`

Expected: DeepSeek 手工交接、双确认、字数、地域和图片规则仍然存在。

### Task 3: 用测试驱动扩展高置信度自动门禁

**Files:**
- Modify: `stock-ai/tests/unit/test_wechat_mp_hotspot_quality_gate.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_quality_gate.py`
- Modify: `.cursor/skills/wechat-mp-drafts/rules-implemented.md`

**Interfaces:**
- Consumes: `scan_hotspot_public_copy(title: str, digest: str, body: str, research_urls: Sequence[str]) -> tuple[HotspotGateFinding, ...]`。
- Produces: 扩展后的 `self_review_voice` 高置信度匹配，不改变函数签名或调用方。

- [ ] **Step 1: 先写失败测试**

增加以下正例，均应返回 `self_review_voice`：

```python
@pytest.mark.parametrize(
    "body",
    (
        "为了避免读者误解，这篇文章并不是要否定学校已经做的工作。",
        "本文想讨论的不是学校好坏，而是家长应该怎样理解这项政策。",
        "这篇稿子不能被理解为对所有民办学校的批评。",
    ),
)
def test_rejects_article_level_self_explanation(body: str) -> None:
    findings = scan_hotspot_public_copy(
        title="教育政策怎样落到家庭？",
        digest="讨论家庭承担的现实成本。",
        body=body,
        research_urls=("https://www.moe.gov.cn/policy",),
    )
    assert "self_review_voice" in {item.code for item in findings}
```

同时增加以下反例，均不得返回 `self_review_voice`：

```python
@pytest.mark.parametrize(
    "body",
    (
        "这项减免不包括伙食费，家庭仍需按实际就餐天数结算。",
        "校方通报只能说明学校已经作出这一回应，最终结论仍待主管部门核查。",
        "政府购买学位不等于学费全免，超过购买标准的差额仍由家庭承担。",
    ),
)
def test_allows_direct_fact_boundaries(body: str) -> None:
    findings = scan_hotspot_public_copy(
        title="教育政策怎样落到家庭？",
        digest="讨论家庭承担的现实成本。",
        body=body,
        research_urls=("https://www.moe.gov.cn/policy",),
    )
    assert "self_review_voice" not in {item.code for item in findings}
```

- [ ] **Step 2: 运行测试确认新正例失败**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_hotspot_quality_gate.py -q`

Expected: 新增文章层级自我解释用例失败，既有测试继续通过。

- [ ] **Step 3: 添加最小匹配规则**

在 `_SELF_REVIEW_VOICE_PATTERNS` 中增加只针对文章自身的模式：

```python
re.compile(r"(?:为了避免|以免)(?:读者)?误解[^。！？\n]{0,100}"),
re.compile(
    r"(?:本文|本篇|这篇文章|这篇稿子|本稿)[^。！？\n]{0,20}"
    r"(?:不是要|并不是要|不能被理解为|不应被理解为|想讨论的不是)"
),
```

- [ ] **Step 4: 运行单元测试确认通过**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_hotspot_quality_gate.py -q`

Expected: 全部通过。

- [ ] **Step 5: 更新规则与代码映射**

在 `rules-implemented.md` 的热点公开文案门禁条目中注明：自动门禁覆盖文章层级自我解释；来源独立性、事实分类和信息增量仍为人工核验项。

### Task 4: 对齐既有封面与正文共用规则

**Files:**
- Modify: `stock-ai/tests/unit/test_wechat_mp_hotspot_image_policy.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_image_policy.py`
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md`

**Interfaces:**
- Consumes: `validate_verified_hotspot_images(out_dir: Path, expected_topic: str, max_body: int = 3) -> VerifiedHotspotImages`。
- Produces: 合格真实图总数不超过正文上限时，封面图同时进入正文；总数超过上限时仍最多返回三张正文图。

- [ ] **Step 1: 先修改行为测试并确认失败**

将 1、2、3 张合格图的期望正文列表分别设为 1、2、3 张，且都包含封面；4 张及以上仍只返回 3 张正文图。同步覆盖仅有官方封面、`reuse_in_body` 缺失或格式错误的场景。

- [ ] **Step 2: 运行图片策略测试确认失败原因**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_hotspot_image_policy.py -q`

Expected: 仅“不超过三张时封面未进入正文”的新期望失败。

- [ ] **Step 3: 写入最小选择逻辑**

当 `len(figures) <= max_body` 且 `max_body > 0` 时，正文候选直接使用全部合格图；图片超过上限时，继续按显式 `reuse_in_body` 决定封面是否占用正文名额。

- [ ] **Step 4: 更新图片规则文档并回归测试**

明确：合格图总数为 1—3 张时全部进入正文，其中一张兼作封面；超过 3 张时正文仍最多 3 张。运行图片策略测试，预期全部通过。

### Task 5: 综合验证与差异复核

**Files:**
- Verify: `.cursor/skills/wechat-mp-writing/`
- Verify: `stock-ai/scripts/tools/wechat_mp_hotspot_quality_gate.py`
- Verify: `stock-ai/tests/unit/test_wechat_mp_hotspot_quality_gate.py`
- Verify: `stock-ai/tests/unit/test_wechat_mp_browser_write_cli.py`
- Verify: `stock-ai/tests/unit/test_wechat_mp_browser_push.py`

**Interfaces:**
- Consumes: Tasks 1—3 的全部产物。
- Produces: 可复核的验证结果和仅限本次改动的差异摘要。

- [ ] **Step 1: 运行 Skill 结构校验**

Run: `python3 /Users/huan.yu/.codex/skills/.system/skill-creator/scripts/quick_validate.py .cursor/skills/wechat-mp-writing`

Expected: `Skill is valid!`

- [ ] **Step 2: 运行热点门禁及暂存/推送相关测试**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_hotspot_quality_gate.py tests/unit/test_wechat_mp_browser_write_cli.py tests/unit/test_wechat_mp_browser_push.py -q`

Expected: 全部通过。

- [ ] **Step 3: 运行格式与规则一致性检查**

Run: `git diff --check -- .cursor/skills/wechat-mp-writing stock-ai/scripts/tools/wechat_mp_hotspot_quality_gate.py stock-ai/tests/unit/test_wechat_mp_hotspot_quality_gate.py .cursor/skills/wechat-mp-drafts/rules-implemented.md`

Expected: 无空白错误。

- [ ] **Step 4: 复核本次范围**

Run: `git diff -- .cursor/skills/wechat-mp-writing/SKILL.md .cursor/skills/wechat-mp-writing/editorial-evidence-gate.md .cursor/skills/wechat-mp-writing/hotspot-deep-review.md .cursor/skills/wechat-mp-writing/deepseek-writer-sop.md .cursor/skills/wechat-mp-writing/anti-ai-voice.md stock-ai/scripts/tools/wechat_mp_hotspot_quality_gate.py stock-ai/tests/unit/test_wechat_mp_hotspot_quality_gate.py .cursor/skills/wechat-mp-drafts/rules-implemented.md`

Expected: 只出现本设计范围内的增量和原先已有的用户改动；不得出现社区 Skill 安装、草稿覆盖、发布调用或图片生成逻辑变化。

- [ ] **Step 5: 保留工作区现有改动，不创建实施提交**

本次涉及的目标文件在开始前已有未提交修改。为避免把用户改动一并纳入提交，实施完成后不自动提交；向用户报告修改文件、验证结果和现有脏工作区状态。
