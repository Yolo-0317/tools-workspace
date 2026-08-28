# 赵一鸣牛肉干称重争议热点深评 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成一篇关于赵一鸣牛肉干称重争议的 2000～2500 字公众号热点深评，并通过本地热点稿门禁，但不推送公众号草稿箱。

**Architecture:** 先把事件报道与权威规则整理成可追溯事实表，再据此写入 Codex 热点稿 JSON。最后仅通过 `--dry-run` 触发正文、标题、配图与合规门禁，失败则回到 JSON 修订，不调用自动 Composer 扩写。

**Tech Stack:** 公开网页检索、中华人民共和国消费者权益保护法与计量相关权威网页、UTF-8 JSON、`scripts.tools.wechat_mp_draft --kind hotspot --codex-draft`。

## Global Constraints

- 暂定标题：`4块牛肉干64元，真能只怪系统出错吗？`
- 正文 2000～2500 字，且不得低于 1920 字。
- 正文为纯段落，6～9 个自然段，无编号、小标题和列表。
- 至少交叉核验两篇同题报道，并使用权威来源核验消费者权益与计量规则。
- 不把当事人说法写成监管结论，不推断主观欺诈，不对整个品牌或行业作无证据指控。
- 本轮只成稿和干跑验证，不调用公众号写入接口。

---

### Task 1: 建立事件与规则事实表

**Files:**
- Create: `output/hotspot-beef-jerky-research.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-12-beef-jerky-weighing-hotspot-design.md`
- Produces: 带 URL 的事件事实、争议说法、权威规则和不可下结论事项，供 Task 2 成稿使用。

- [ ] **Step 1: 核验同题报道**

检索并打开至少两篇同题公开报道，记录购物地点、日期、票据重量、复称重量、两组金额、门店回应与赔偿说法。相同稿源的转载不得算作独立交叉验证。

- [ ] **Step 2: 核验权威规则**

从政府或国家法律法规数据库确认经营者的信息披露、计量准确、责任承担与消费者救济相关条文。事实表只摘录文章真正会使用的规则，不堆砌法条。

- [ ] **Step 3: 标注证据等级**

将每条材料标为“多源确认”“单方说法”“权威规则”或“作者判断”；明确列出不能写成事实的内容，包括主观故意、系统故障原因、影响门店范围和监管定性。

- [ ] **Step 4: 检查事实表**

Run: `rg -n 'https?://|多源确认|单方说法|权威规则|不能确认' output/hotspot-beef-jerky-research.md`

Expected: 至少两条同题报道 URL、一条权威规则 URL，并包含四类证据边界。

### Task 2: 写结构化热点长文

**Files:**
- Create: `output/hotspot_codex_beef_jerky.json`

**Interfaces:**
- Consumes: `output/hotspot-beef-jerky-research.md`
- Produces: `title`、`digest`、`body`、`topic`、`research_urls`、`slot_key` 字段完整的 Codex 热点稿 JSON。

- [ ] **Step 1: 写开篇与事件复盘**

首段 50 字内写清“4 块牛肉干、小票 0.299 千克和 64.58 元、复称约 0.08 千克和 17.29 元”的反差；随后区分消费者说法、门店回应和仍待查清之处。

- [ ] **Step 2: 完成三层论证**

正文依次回答：系统为何不是责任主体；散装称重的信息差为何让小额错误容易被放过；连锁品牌应怎样公开排查范围、复核流程与纠错机制。每个判断都紧跟事实或权威规则，不写泛泛消费鸡汤。

- [ ] **Step 3: 写结尾和摘要**

结尾落在“让称重流程可检查、可追责”，不煽动网暴，不替监管部门定性。摘要用一至两句说明文章回答的问题，不重复标题。

- [ ] **Step 4: 运行结构检查**

Run:

```bash
.venv/bin/python -c 'import json; from pathlib import Path; d=json.loads(Path("output/hotspot_codex_beef_jerky.json").read_text()); b=d["body"].strip(); ps=[p for p in b.split("\n\n") if p.strip()]; print({"title_chars":len(d["title"]),"body_chars":len(b),"paragraphs":len(ps),"sources":len(d["research_urls"])}); assert 1920 <= len(b) <= 2500; assert 6 <= len(ps) <= 9; assert len(d["research_urls"]) >= 3'
```

Expected: 标题表意完整，正文 1920～2500 字、6～9 段、来源不少于 3 个。

### Task 3: 执行热点稿干跑质量门禁

**Files:**
- Modify: `output/hotspot_codex_beef_jerky.json`（仅在门禁失败时修改）

**Interfaces:**
- Consumes: `output/hotspot_codex_beef_jerky.json`
- Produces: 通过热点稿构建与质量检查的本地成稿；不创建或更新远端草稿。

- [ ] **Step 1: 运行干跑**

Run:

```bash
WECHAT_MP_HOTSPOT_TREND_ENRICH=0 PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_draft \
  --kind hotspot \
  --codex-draft output/hotspot_codex_beef_jerky.json \
  --dry-run
```

Expected: 命令退出码为 0；正文长度、段落、标题、合规与来源门禁通过。若流程要求补图，保留缺图请求，不进行远端草稿写入，并将正文验证与配图准备状态分别汇报。

- [ ] **Step 2: 复核禁用表达**

Run:

```bash
rg -n '刷到这条热搜|第一反应是|值得注意的是|不难发现|需要指出的是|在这个时代|综上所述|一、|二、|三、' output/hotspot_codex_beef_jerky.json
```

Expected: 无匹配。

- [ ] **Step 3: 交付正文**

向用户提供最终标题、摘要和可直接复制的正文，并明确“尚未推送公众号草稿箱”。
