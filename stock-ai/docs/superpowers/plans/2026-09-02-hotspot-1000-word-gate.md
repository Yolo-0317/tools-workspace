# Hotspot 1000-Word Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户主动热点深评调整为目标 900—1100 字、正文硬门禁 850 字，同时保持其他稿型和旧自动热点链路不变。

**Architecture:** 用户主动热点的正文门禁分别位于成稿校验和原创性校验，二者共用环境变量 `WECHAT_MP_CODEX_HOTSPOT_MIN_BODY`，因此同步把默认值与安全下限改为 850。提示词与 Skill 文档统一为目标区间 900—1100 字；上限仅作为编辑目标，不设拒绝逻辑。

**Tech Stack:** Python 3.11、pytest、Markdown Skill 文档。

## Global Constraints

- 目标篇幅为 900—1100 字。
- 正文去空白后少于 850 字必须拒绝。
- 超过 1100 字不直接拒绝。
- 只调整用户主动 `hotspot`，不得改变 `hot_business`、影视、银发稿及旧自动热点链路。
- 保留至少三个来源域、原创核心判断、双确认、抖音优先真实图片及禁止生成图门禁。
- 保留工作区已有的未提交修改，不覆盖或顺带提交。

---

### Task 1: 用户主动热点正文与原创性门禁

**Files:**
- Modify: `stock-ai/tests/unit/test_wechat_mp_codex_hotspot.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_originality.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_article.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_originality.py`

**Interfaces:**
- Consumes: `WECHAT_MP_CODEX_HOTSPOT_MIN_BODY` 可选整数环境变量。
- Produces: `codex_hotspot_min_body_gate() -> int` 和 `hotspot_originality_min_chars() -> int` 默认均返回 `850`。

- [ ] **Step 1: 写正文门禁失败测试**

在 `test_wechat_mp_codex_hotspot.py` 添加测试，构造包含数字且不少于五段的自然正文，断言 849 个去空白字符被拒绝、850 个字符不再因字数被拒绝。测试应直接调用 `validate_codex_hotspot_body()`，避免只测常量。

- [ ] **Step 2: 写原创性门禁失败测试**

把默认值断言改为：

```python
def test_hotspot_originality_default_minimum_targets_1000_word_article(monkeypatch) -> None:
    monkeypatch.delenv("WECHAT_MP_CODEX_HOTSPOT_MIN_BODY", raising=False)
    assert hotspot_originality_min_chars() == 850
```

增加环境变量低于安全下限时仍返回 850 的断言。

- [ ] **Step 3: 运行测试并确认 RED**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/unit/test_wechat_mp_codex_hotspot.py \
  tests/unit/test_wechat_mp_originality.py
```

Expected: 默认最小值仍为 1800 或 849/850 边界不符合新要求，测试失败。

- [ ] **Step 4: 最小化修改正文门禁**

在 `wechat_mp_hotspot_article.py` 中改为：

```python
def codex_hotspot_min_body_gate() -> int:
    """用户主动热点默认至少 850 字，单次命令仍可显式提高。"""
    requested = _env_int("WECHAT_MP_CODEX_HOTSPOT_MIN_BODY", 850)
    return max(850, min(HOTSPOT_MIN_BODY_CHARS, requested))
```

不得修改 `hotspot_min_body_gate()` 或 `HOTSPOT_MIN_BODY_CHARS`，避免影响旧自动热点链路。

- [ ] **Step 5: 最小化修改原创性门禁**

在 `wechat_mp_originality.py` 中把默认值与安全下限同步为 850：

```python
def hotspot_originality_min_chars() -> int:
    """用户主动热点原创报告默认至少 850 字，可显式提高。"""
    try:
        requested = int(os.getenv("WECHAT_MP_CODEX_HOTSPOT_MIN_BODY", "850"))
    except ValueError:
        requested = 850
    return max(850, min(1920, requested))
```

- [ ] **Step 6: 运行测试并确认 GREEN**

运行 Step 3 的命令，预期全部通过。

### Task 2: Skill 与提示词口径同步

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md`
- Modify: `.cursor/skills/wechat-mp-writing/deepseek-writer-sop.md`
- Modify: `.cursor/skills/wechat-mp-writing/anti-ai-voice.md`

**Interfaces:**
- Consumes: Task 1 的 850 字硬门禁。
- Produces: 所有用户主动热点写作入口统一提示“目标 900—1100 字、少于 850 字拒绝”。

- [ ] **Step 1: 更新 Skill 真源**

将用户主动热点 JSON 示例、写作说明和 DeepSeek 提示词中的 `1800—2200`、`不少于 1800` 或热点 `≥2000` 改为：

```text
正文目标 900—1100 字；去空白后少于 850 字拒绝。信息复杂时允许超过 1100 字，但应优先精简，不为凑字重复观点。
```

保留旧自动链路的 `2000` 字说明和 `WECHAT_MP_HOTSPOT_MIN_BODY_SLACK` 说明，并明确其不适用于用户主动稿。

- [ ] **Step 2: 检查旧口径残留**

Run:

```bash
rg -n '1800—2200|不少于 1800|≥1800|热点.*≥2000' \
  .cursor/skills/wechat-mp-drafts/SKILL.md \
  .cursor/skills/wechat-mp-writing/hotspot-deep-review.md \
  .cursor/skills/wechat-mp-writing/deepseek-writer-sop.md \
  .cursor/skills/wechat-mp-writing/anti-ai-voice.md
```

Expected: 用户主动热点相关旧口径无残留；若命中旧自动链路说明，文字必须明确限定为旧自动链路。

- [ ] **Step 3: 校验 Skill 结构**

Run:

```bash
python3 /Users/huan.yu/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  .cursor/skills/wechat-mp-drafts
```

Expected: Skill validation passed。

### Task 3: 全量相关验证与差异审查

**Files:**
- Review only: all files modified in Task 1 and Task 2.

**Interfaces:**
- Consumes: Task 1 code and Task 2 documentation.
- Produces: 可安全用于后续热点深评的已验证门禁。

- [ ] **Step 1: 运行热点相关测试**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/unit/test_wechat_mp_codex_hotspot.py \
  tests/unit/test_wechat_mp_originality.py \
  tests/unit/test_wechat_mp_hotspot_image_policy.py
```

Expected: 全部通过。

- [ ] **Step 2: 检查格式与差异**

Run:

```bash
git diff --check -- \
  stock-ai/scripts/tools/wechat_mp_hotspot_article.py \
  stock-ai/scripts/tools/wechat_mp_originality.py \
  stock-ai/tests/unit/test_wechat_mp_codex_hotspot.py \
  stock-ai/tests/unit/test_wechat_mp_originality.py \
  .cursor/skills/wechat-mp-drafts/SKILL.md \
  .cursor/skills/wechat-mp-writing/hotspot-deep-review.md \
  .cursor/skills/wechat-mp-writing/deepseek-writer-sop.md \
  .cursor/skills/wechat-mp-writing/anti-ai-voice.md
```

Expected: 无空白错误；差异仅包含本次字数口径及工作区原有的刚性字段修复。

- [ ] **Step 3: 汇报结果**

汇报新门禁、实际测试数量、Skill 校验结果，以及现有未提交修改未被覆盖。除非用户明确要求，不创建额外 Git 提交。
