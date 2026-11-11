# “兔子警官”辅警身份争议热点深评 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出一篇事实可追溯、制度边界准确、配有四张公开来源图片的公众号热点深评，并在用户二次确认后写入草稿箱。

**Architecture:** 先建立事实包，将人物事实、最新回应和辅警制度依据分开记录；再基于事实包生成结构化 Codex 稿件。图片按“抖音搜索页封面优先、官方网页截图补充”准备，最后通过现有公众号流水线完成原创度、篇幅、配图和草稿唯一性核验。

**Tech Stack:** Python 3.11、现有 `scripts.tools.wechat_mp_*` 工具、公众号草稿 API、抖音搜索结果页、公开政府与主流媒体网页。

## Global Constraints

- 文章主轴是辅警身份与民警职权边界，辅以流量审视，不评价个人外貌或猜测营销动机。
- 纯段落长文，不设小标题，去空白后不少于 1920 字，目标 2000—2600 字。
- 至少三个独立来源域，其中至少一个公安机关、政府法制或法律法规来源。
- 抖音只读取搜索结果页封面、账号、发布时间和原视频链接，不点击、不打开、不播放视频。
- 配图目标为一张封面加三张正文图，每张登记来源与页面链接。
- 推入公众号草稿箱前必须由用户二次确认。

---

### Task 1: 建立可追溯事实包

**Files:**
- Create: `stock-ai/output/hotspot_rabbit_police_research_20260828.json`

**Interfaces:**
- Consumes: 浙江公安、浙江在线、潮新闻等人物资料；本人最新回应；国家或浙江省辅警法规与公安机关解释。
- Produces: 包含 `person_facts`、`latest_response`、`legal_boundaries`、`source_urls`、`prohibited_inferences` 的 JSON 对象。

- [ ] **Step 1: 核实人物身份和最新回应**

检索并保存至少两条人物来源，逐条记录标题、发布机构、发布时间、URL和可直接支持的事实。不得把“兔子警官”写成正式警衔。

- [ ] **Step 2: 核实辅警制度边界**

优先使用政府、公安机关或法规原文，确认辅警的协助性定位、不得独立从事的执法行为和身份标识要求。法规适用地域必须在事实包中标明。

- [ ] **Step 3: 写入研究 JSON**

输出格式：

```json
{
  "topic": "兔子警官回应辅警身份争议",
  "person_facts": [],
  "latest_response": [],
  "legal_boundaries": [],
  "source_urls": [],
  "prohibited_inferences": [
    "不推断营销安排",
    "不推断转正、收入或内部任用",
    "不把网络昵称写成正式警衔"
  ]
}
```

- [ ] **Step 4: 验证来源数量和权威来源**

Run:

```bash
jq '{sources:(.source_urls|length),legal:(.legal_boundaries|length),forbidden:(.prohibited_inferences|length)}' stock-ai/output/hotspot_rabbit_police_research_20260828.json
```

Expected: `sources >= 3`、`legal >= 1`、`forbidden = 3`。

### Task 2: 形成结构化热点稿

**Files:**
- Create: `stock-ai/output/hotspot_codex_rabbit_police_20260828.json`

**Interfaces:**
- Consumes: Task 1 的研究 JSON和已确认设计稿。
- Produces: 可被 `load_codex_hotspot_draft` 读取的 `title`、`digest`、`topic`、`body`、`research_urls`、`original_thesis`、`slot_key`。

- [ ] **Step 1: 写出完整正文**

正文按“本人回应—争议来源—制度边界—流量双刃剑—机构说明责任”展开。只写事实包能够支持的事实，法律分析使用“依据公开规则”“通常情况下”等准确限定。

- [ ] **Step 2: 写入结构化 JSON**

标题使用：`“兔子警官”是辅警，为什么这件事会引发争议？`

摘要控制在40字以内并形成完整句，避免公众号接口截断。正文保留2—4个 `[[hl:...]]` 高亮标记，不设置小标题。

- [ ] **Step 3: 运行静态校验**

Run:

```bash
cd stock-ai && .venv/bin/python -c 'from pathlib import Path; from scripts.tools.wechat_mp_codex_hotspot import load_codex_hotspot_draft; d=load_codex_hotspot_draft(Path("output/hotspot_codex_rabbit_police_20260828.json")); print({"title":d.title,"body_chars":len("".join(d.body.split())),"sources":len(d.research_urls)})'
```

Expected: 标题完整、`body_chars >= 1920`、`sources >= 3`。

### Task 3: 准备四张可追溯配图

**Files:**
- Create: `stock-ai/assets/wechat_mp/inline-discussion/兔子警官回应辅警身份争议/still-01.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/兔子警官回应辅警身份争议/still-02.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/兔子警官回应辅警身份争议/manual-01.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/兔子警官回应辅警身份争议/figure_sources.json`
- Generated: `stock-ai/assets/wechat_mp/inline-discussion/兔子警官回应辅警身份争议/cover.jpg`

**Interfaces:**
- Consumes: 抖音搜索结果页两张认证媒体封面、官方人物报道截图、辅警制度页面截图。
- Produces: 一张自动裁切封面和三张正文图；`figure_sources.json` 为每张源图提供 `page_url`、`image_url`、`source_name`、`published_at`、`source_type`、`verified`、`caption`。

- [ ] **Step 1: 提取抖音搜索页封面**

只在搜索页读取卡片，不触发点击。优先认证的浙江媒体、公安机关或全国法治媒体账号；若只有普通自媒体，不纳入来源图。

- [ ] **Step 2: 截取两张官方网页证据图**

一张展示人物辅警身份或本人回应，一张展示辅警职责边界。截图须保留能够识别来源页面的标题或机构标识。

- [ ] **Step 3: 写入来源元数据并检查图片**

Run:

```bash
cd stock-ai && sips -g pixelWidth -g pixelHeight assets/wechat_mp/inline-discussion/兔子警官回应辅警身份争议/*.{jpg,png}
```

Expected: 每张图宽度至少280像素、高度至少200像素、文件不少于8KB；元数据中至少两条为 `douyin_cover`，至少一条为官方网页截图。

### Task 4: 完成公众号预演和二次确认

**Files:**
- Modify: `stock-ai/output/hotspot_codex_rabbit_police_20260828.json`（仅在预演发现摘要、事实限定或排版问题时）

**Interfaces:**
- Consumes: Task 2 稿件和 Task 3 图片。
- Produces: 通过原创与配图门禁的公众号 HTML 预演结果。

- [ ] **Step 1: 运行完整预演**

Run:

```bash
cd stock-ai && .venv/bin/python -m scripts.tools.wechat_mp_draft --kind hotspot --codex-draft output/hotspot_codex_rabbit_police_20260828.json --dry-run
```

Expected: 退出码0，原创增量报告为 `PASS`，无图片缺口异常。

- [ ] **Step 2: 核对正文图片标签**

Run:

```bash
cd stock-ai && .venv/bin/python -c 'from pathlib import Path; from scripts.tools.wechat_mp_draft import _build_for_kind; from scripts.tools.wechat_mp_codex_hotspot import load_codex_hotspot_draft; d=load_codex_hotspot_draft(Path("output/hotspot_codex_rabbit_police_20260828.json")); a=_build_for_kind("hotspot",edition=None,market_title=None,variant=None,codex_draft=d,upload_figures=False); c=str(a["content"]); print({"body_images":c.count("<img"),"captions":c.count("图源：")})'
```

Expected: `body_images = 3`、`captions = 3`。

- [ ] **Step 3: 向用户提交二次确认清单**

汇报标题、摘要、正文字数、来源数量、封面与正文图片数量、原创门禁结果。只有用户明确回复“推送”后才能调用公众号写入命令。

### Task 5: 写入草稿箱并只读复核

**Files:**
- No repository file changes expected.

**Interfaces:**
- Consumes: 用户二次确认和通过预演的稿件。
- Produces: 公众号草稿 `media_id`，以及标题、摘要、正文图片数和同标题草稿数量的只读核验结果。

- [ ] **Step 1: 写入公众号草稿**

Run:

```bash
cd stock-ai && .venv/bin/python -m scripts.tools.wechat_mp_draft --kind hotspot --codex-draft output/hotspot_codex_rabbit_police_20260828.json
```

Expected: 返回 `OK [hotspot]` 和新草稿 `media_id`。

- [ ] **Step 2: 只读复核草稿**

调用 `fetch_draft_news_item` 核对标题、完整摘要、3张正文图和3条图源说明；调用 `list_all_drafts` 确认同标题草稿仅1篇。若出现重复，只删除较旧的同标题草稿并再次核验。

- [ ] **Step 3: 报告最终状态**

明确说明稿件已进入草稿箱但尚未正式发布，并报告任何被删除的旧重复稿及其不可恢复性。
