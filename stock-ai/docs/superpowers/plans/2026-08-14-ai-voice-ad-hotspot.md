# AI 声线广告热点深评 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成一篇关于“AI 使用配音演员声线接商业广告”的 2026 年 8 月 14 日公众号热点深评，并通过原创、正文、合规与配图门禁。

**Architecture:** 先把当日热搜事实、既有争议案例和法律依据分层取材，再以结构化 Codex JSON 交给现有 `wechat_mp_draft` 链路。正文和原创判断由人工写作完成，Python 只负责清洗、原创报告、配图与草稿预演；本轮不调用微信草稿写入接口。

**Tech Stack:** Web 公开资料、JSON、`scripts.tools.wechat_mp_draft`、公众号原创增量门禁、ImageGen（仅在配图缺口出现时）。

## Global Constraints

- 事件事实至少覆盖 3 个不同来源域，并区分当事人说法、制作方回应与法律解释。
- 不把尚无司法结论的争议写成已经构成侵权。
- 标题不超过 32 字，前 15 字包含“AI 声线”或“配音演员”。
- 正文去空白后 2200—2800 字，纯段落、短段落，不设小标题。
- `original_thesis` 不少于 20 字，且必须是可被反驳和检验的原创核心判断。
- 配图不得伪造广告现场、真实人物、品牌声明或法院结论。
- 本轮只运行 `--dry-run`，不写入公众号草稿箱。

---

## File Structure

- Create: `output/hotspot_codex_20260814_ai_voice.json` — 标题、摘要、正文、原创判断、来源 URL 和槽位的唯一成稿真源。
- Create when requested: `assets/wechat_mp/inline-discussion/AI声线广告争议/manual-*.jpg` — 自动取图不足时的原创解释图。
- Read: `docs/superpowers/specs/2026-08-14-ai-voice-ad-hotspot-design.md` — 已确认的事实边界与文章结构。

### Task 1: 当日事实与法律取材

**Files:**
- Read: `docs/superpowers/specs/2026-08-14-ai-voice-ad-hotspot-design.md`
- Create later in Task 2: `output/hotspot_codex_20260814_ai_voice.json`

**Interfaces:**
- Consumes: 2026 年 8 月 14 日热搜条目“AI用配音演员声线接广告”。
- Produces: 至少 4 条可核对事实、至少 3 个不同来源域、明确的事实边界。

- [ ] **Step 1: 核验当日热搜与具体事件**

从公开热搜、当事人公开发言及可信媒体报道确认：涉事广告、配音演员主张、广告或内容处置、制作方或品牌回应。若当日热搜只是旧闻再传播，在正文明确写出原事件日期，不伪装成当天新发生。

- [ ] **Step 2: 收集三个层次的来源**

来源必须分别覆盖：事件报道、配音行业或当事人主张、法律或裁判规则。优先使用新闻媒体原页、全国人大网、法院或检察机关，避免仅依赖聚合转载。

- [ ] **Step 3: 形成事实边界清单**

明确哪些是已经确认的行为，哪些只是当事人指控，哪些属于本文基于法律和行业流程的推论；正文不得越过这一边界。

### Task 2: 写入结构化长文 JSON

**Files:**
- Create: `output/hotspot_codex_20260814_ai_voice.json`

**Interfaces:**
- Consumes: Task 1 的事实、来源 URL 和边界清单。
- Produces: 可由 `load_codex_hotspot_draft()` 读取的 UTF-8 JSON。

- [ ] **Step 1: 确定标题、摘要与原创判断**

标题优先采用 `AI声线接广告，谁替本人同意了？`；摘要在 128 字内回答文章要解决的问题；`original_thesis` 明确写出“复制成本下降不等于同意成本消失”。

- [ ] **Step 2: 完成 2200—2800 字正文**

正文按“事件落地—声音为何不只是数据—三层授权—三方责任—可执行规则”推进。事实段一句一段，解释段一至两句一段；至少出现 4 个可核对事实，不使用小标题、编号和模板化金句。

- [ ] **Step 3: 写入来源与槽位**

JSON 包含 `title`、`digest`、`body`、`topic`、`research_urls`、`original_thesis` 和 `slot_key=hotspot_afternoon`。用 `jq -e` 验证字段存在，并计算正文去空白字数及来源域数量。

### Task 3: 原创门禁与完整草稿预演

**Files:**
- Read: `output/hotspot_codex_20260814_ai_voice.json`
- Create when requested: `assets/wechat_mp/inline-discussion/AI声线广告争议/codex-image-request.json`

**Interfaces:**
- Consumes: Task 2 的成稿 JSON。
- Produces: `原创增量报告 [PASS]` 和完整热点草稿预演输出，或准确的阻断原因。

- [ ] **Step 1: 运行结构与原创预检**

Run:

```bash
cd stock-ai
PYTHONPATH=. uv run python -m scripts.tools.wechat_mp_draft \
  --kind hotspot \
  --codex-draft output/hotspot_codex_20260814_ai_voice.json \
  --dry-run
```

Expected: 正文和原创门禁通过；若失败，按 `text_too_short`、`sources_too_few`、`missing_original_thesis` 或正文质量错误修改 JSON 后重试。

- [ ] **Step 2: 处理配图缺口**

若生成 `codex-image-request.json`，读取全部 `slots` 与 `safety_rules`，每个槽位单独调用一次内置 ImageGen，保存为请求中的 `output_path`。每张图使用不同的信息作用和构图，不重复图片，不伪造事件现场。

- [ ] **Step 3: 重跑完整预演**

重复 Step 1 命令，直到命令退出码为 0、原创增量报告 PASS、封面和 3 张正文图全部满足门禁。

### Task 4: 完成前验证与交付

**Files:**
- Read: `output/hotspot_codex_20260814_ai_voice.json`
- Read: `assets/wechat_mp/inline-discussion/AI声线广告争议/figure_sources.json`

**Interfaces:**
- Consumes: Task 3 的最终预演结果。
- Produces: 用户可审阅的标题、核心判断、字数、来源域、门禁结果和本地成稿路径。

- [ ] **Step 1: 运行新鲜的最终预演**

使用 Task 3 Step 1 的同一命令重新运行，不复用先前输出；读取完整退出状态和原创报告。

- [ ] **Step 2: 检查没有发生微信写入**

确认命令包含 `--dry-run`，输出中不存在 `media_id=`、`已新建` 或 `已更新` 草稿记录。

- [ ] **Step 3: 向用户交付**

报告最终标题、正文去空白字数、独立来源域数量、原创报告和配图状态，并链接 `output/hotspot_codex_20260814_ai_voice.json`。等待用户明确说“推送”后，才允许去掉 `--dry-run`。
