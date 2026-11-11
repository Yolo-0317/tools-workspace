# 公众号教育候选四城地域门禁实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将北京、上海、广州、深圳新闻发生地要求固化为公众号人工教育热点候选的前置硬门禁。

**Architecture:** 以 `hotspot-deep-review.md` 作为执行真源，定义入选与排除边界；以 `memory-python.mdc` 保存简短用户决定并指向真源。只改变人工候选规范，不修改自动评分、定时任务、发布流程或历史草稿。

**Tech Stack:** Markdown 规则文档、Git。

## Global Constraints

- 候选新闻的发生地或政策发布主体必须是北京、上海、广州、深圳。
- 全国政策只有在四城之一形成可核验的本地实施事实时才可入选。
- 广州、深圳不得扩大为广东全省；北京、上海包含各自所辖区。
- 四城之外的新闻在展示候选组之前直接排除。
- 继续保留教育费用优先、家长利益、时效、来源可靠性和近期去重规则。
- 不修改自动定时、自动评分、发布权限或历史草稿。

---

### Task 1: 更新热点深评执行真源

**Files:**
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md:24-44`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-09-13-wechat-education-topic-city-gate-design.md` 中的地域边界。
- Produces: 人工教育候选选题时直接执行的“四城地域硬门禁”。

- [ ] **Step 1: 在近期教育选题偏好前加入四城地域硬门禁**

写明：候选必须以北京、上海、广州或深圳为新闻发生地；北京、上海包含所辖区，广州、深圳不扩大为广东全省；全国政策须有四城本地实施通知、执行案例、收费标准、办理流程或家庭账单变化，并以本地事实为文章主体。

- [ ] **Step 2: 写明排除条件和筛选顺序**

写明：外地热点、只有全国文件而无四城落地、只有专家观点或无法确认发生地的内容不进入候选；先做地域过滤，再按费用、择校升学、托管接送、校园服务和其他家庭利益排序。

- [ ] **Step 3: 核对与原有规则不存在冲突**

Run: `rg -n "四城地域|北京|上海|广州|深圳|全国政策|教育费用政策优先" .cursor/skills/wechat-mp-writing/hotspot-deep-review.md`

Expected: 同时命中四城硬门禁、全国政策本地落地条件和原有费用优先规则；不得仍保留“全国统一政策优先”作为无条件入选规则。

### Task 2: 更新项目记忆索引

**Files:**
- Modify: `.cursor/rules/memory-python.mdc:196-202`

**Interfaces:**
- Consumes: Task 1 的执行真源标题和规则摘要。
- Produces: 后续公众号任务可快速检索的用户决定。

- [ ] **Step 1: 记录2026-09-13用户决定**

在“公众号热点 · 教育政策选题范围”下增加一条：人工教育候选仅保留北京、上海、广州、深圳新闻；全国政策须有四城本地落地事实；外地新闻不得进入候选；费用政策仍优先。

- [ ] **Step 2: 将旧范围表述改为历史背景而非现行规则**

把“全国统一政策优先、高讨论度地方新政可纳入”的旧表述改为：主题仍聚焦教育政策、招生考试和升学规则，但现行地域范围以四城硬门禁为准，避免两个规则同时生效。

- [ ] **Step 3: 验证文档格式和规则一致性**

Run: `git diff --check -- .cursor/skills/wechat-mp-writing/hotspot-deep-review.md .cursor/rules/memory-python.mdc`

Expected: 无空白错误。

Run: `rg -n "四城地域|仅保留北京、上海、广州、深圳|全国政策须有四城" .cursor/skills/wechat-mp-writing/hotspot-deep-review.md .cursor/rules/memory-python.mdc`

Expected: 两个文件都能检索到一致的地域边界，且项目记忆指向执行真源。

- [ ] **Step 4: 只提交本次两处规则修改和实施计划**

```bash
git add .cursor/skills/wechat-mp-writing/hotspot-deep-review.md .cursor/rules/memory-python.mdc docs/superpowers/plans/2026-09-13-wechat-education-topic-city-gate.md
git commit -m "规范教育热点四城候选范围"
```
