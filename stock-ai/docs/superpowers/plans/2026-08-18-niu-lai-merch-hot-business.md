# 《牛来》周边热点商业稿 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成并更新一篇分析《牛来》热度与民间周边生意的 `hot_business` 微信草稿，并通过 OpenCLI 分散插入三张明确披露为“未标注官方授权”的返佣商品卡。

**Architecture:** 正文继续走现有 Codex JSON、公开图片、质量门禁和微信草稿 upsert 流程，不修改全局普通 CPS 安全策略。纯内容草稿写入后，再绑定用户已登录的微信后台，由 OpenCLI 完成一次性的三商品选择、位置调整、保存和回读。

**Tech Stack:** Python 3、现有 `wechat_mp_draft`/热点商业校验链路、JSON 研究稿、微信公众平台、OpenCLI Chrome 会话。

## Global Constraints

- 用户可见内容与汇报不使用 emoji。
- 标题不超过 20 个汉字，正文约 2200 至 2800 个汉字。
- 至少引用 3 个不同域名的公开来源，事实与推断分开。
- 返佣商品最多 3 张，商品页未显示官方授权时不得称为官方或正版周边。
- 第一张商品卡前保留明确披露；商品卡不得连续出现，不在开篇前 25% 插入。
- 不插入短剧返佣组件，不调用发表接口。
- `output/` 成稿不提交；不覆盖或提交工作区其他未完成改动。

---

### Task 1: 研究事实与公开图片复核

**Files:**
- Inspect: `stock-ai/assets/wechat_mp/inline-tv/niu-lai/figure_sources.json`
- Create: `stock-ai/output/niu_lai_merch_hot_business_research.json`

**Interfaces:**
- Consumes: 设计稿中的文章主线、微信小店弹窗中 9 件“牛来”商品的现场检索结果。
- Produces: 供 Task 2 使用的来源 URL、可写事实、推断、拒绝说法和图片清单。

- [ ] **Step 1: 核验三类公开来源**

逐页核验以下来源，只记录页面明确支持的事实：

```text
https://www.bjnews.com.cn/detail/1786942510019697.html
https://k.sina.cn/article_7879849295_1d5acf54f06801jtr2.html
https://www.chinafilm.gov.cn/xwzx/ywxx/202602/t20260211_949903.html
```

- [ ] **Step 2: 写入研究 JSON**

写入 `stock-ai/output/niu_lai_merch_hot_business_research.json`，顶层键固定为：

```json
{
  "source_urls": [],
  "verified_facts": [],
  "inferences": [],
  "rejected_claims": [],
  "product_observations": [],
  "figure_files": []
}
```

`rejected_claims` 至少包含“片方完全没有推出官方商品”“返佣池商品均为侵权商品”“后台月销量等于全网销量”。

- [ ] **Step 3: 校验来源域与图片文件**

Run:

```bash
cd stock-ai
python3 -c 'import json,pathlib,urllib.parse; p=json.loads(pathlib.Path("output/niu_lai_merch_hot_business_research.json").read_text()); print(len({urllib.parse.urlparse(u).netloc for u in p["source_urls"]}), all(pathlib.Path(x).exists() for x in p["figure_files"]))'
```

Expected: 第一项不小于 `3`，第二项为 `True`。

### Task 2: 编写并干跑热点商业稿

**Files:**
- Create: `stock-ai/output/niu_lai_merch_hot_business_codex.json`
- Test: `stock-ai/tests/unit/test_wechat_mp_codex_hot_business.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_hot_business_cli.py`

**Interfaces:**
- Consumes: Task 1 的研究 JSON。
- Produces: 现有 `--codex-draft` 契约可读取的热点商业稿件。

- [ ] **Step 1: 写入成稿 JSON**

固定标题为 `《牛来》火了，正版周边在哪`，正文第一张预定商品位置前写入：

```text
说明一下：下方商品来自微信小店返佣池，商品页没有标注《牛来》官方授权，本文不把它们当作正版周边。它们出现在这里，是为了观察一部电影的热度怎样被民间商品最快接住。
```

JSON 顶层必须包含：

```json
{
  "title": "《牛来》火了，正版周边在哪",
  "digest": "",
  "body": "",
  "topic": "《牛来》热度与电影IP周边生意",
  "research_urls": [],
  "original_thesis": "",
  "business_question": "《牛来》形成网络热度后，为什么微信返佣池里先出现民间自制商品，而不是可验证的官方授权周边？",
  "facts": [],
  "inferences": [],
  "rejected_claims": [],
  "slot_key": "hot_business"
}
```

- [ ] **Step 2: 运行契约和回归测试**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_codex_hot_business.py tests/unit/test_wechat_mp_hot_business_cli.py -q
```

Expected: PASS。

- [ ] **Step 3: 运行草稿干跑**

Run:

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_draft --kind hot_business --codex-draft output/niu_lai_merch_hot_business_codex.json --dry-run
```

Expected: 正文去空白不少于 1920 字、来源域不少于 3、原创增量与质量门禁通过；无微信草稿写入。

- [ ] **Step 4: 人工完读检查**

确认首 300 字交代热度、商品现象和核心问题；每 300 至 500 字有新事实或新判断；至少两处可转述颗粒；多数段落 1 至 3 行；结尾只保留一个具体问题。

### Task 3: 更新纯内容草稿

**Files:**
- Modify through API: `hot_business` 微信草稿槽位
- Inspect: `stock-ai/data/wechat_mp_draft_slots.json`

**Interfaces:**
- Consumes: Task 2 通过干跑的成稿 JSON。
- Produces: 不含商品卡和短剧卡的微信热点商业草稿。

- [ ] **Step 1: 正式更新草稿槽位**

Run:

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_draft --kind hot_business --codex-draft output/niu_lai_merch_hot_business_codex.json
```

Expected: 只更新 `hot_business` 槽位，不调用发表接口。

- [ ] **Step 2: 记录草稿标识并检查槽位**

Run:

```bash
cd stock-ai
python3 -c 'import json; x=json.load(open("data/wechat_mp_draft_slots.json")); print(x["slots"]["hot_business"] if "slots" in x else x["hot_business"])'
```

Expected: 标题为 `《牛来》火了，正版周边在哪`，草稿 media ID 非空。

### Task 4: 用 OpenCLI 插入三张商品卡

**Files:**
- Modify through UI: Task 3 创建的微信草稿

**Interfaces:**
- Consumes: 微信后台已登录会话、Task 3 的草稿、设计稿中的三商品策略。
- Produces: 已保存的三商品卡热点商业草稿。

- [ ] **Step 1: 绑定并打开草稿**

Run:

```bash
opencli browser mp bind
```

从草稿箱打开标题 `《牛来》火了，正版周边在哪`，不进入发表页面。

- [ ] **Step 2: 搜索并选择三件商品**

在“小店返佣商品”中搜索 `牛来`，优先选择：

```text
【我们真的看懂牛来了吗】……亚克力立牌（月销246，售价4.3元，预计佣金0.21元）
牛来抽象毛绒玩偶公仔挂件……（月销28，售价15.8元，预计佣金1.10元）
【爆款电影牛来周边】小牛亚克力挂件……（月销145，售价4.77元，预计佣金0.23元）
```

若标题、销量或佣金发生变化，以现场页面为准；任何商品显示下架或搜索不到则跳过，剩余少于 2 件时停止商品插入。

- [ ] **Step 3: 分散商品卡位置**

第一张置于披露语之后，第二张置于“情绪陪伴商品”论证之后，第三张置于“搜索结果被低价民间周边占据”论证之后。三张卡之间至少隔两个完整正文段落。

- [ ] **Step 4: 保存但不发表**

点击保存草稿，不点击发表、群发或定时发表。

### Task 5: 保存后回读与交付

**Files:**
- Inspect through UI: 已保存微信草稿

**Interfaces:**
- Consumes: Task 4 保存后的草稿。
- Produces: 最终核验报告。

- [ ] **Step 1: 回读结构**

用 OpenCLI 读取编辑页正文，确认标题不超过 20 字、披露语存在、正文图片不少于 3 张、商品组件恰好 3 个、短剧组件为 0。

- [ ] **Step 2: 回读商品属性**

确认三个商品组件对应预定标题，且相邻正文仍能解释商品卡为何出现；不得出现“官方授权”“正版商品”等定性。

- [ ] **Step 3: 解除会话绑定**

Run:

```bash
opencli browser mp unbind
```

- [ ] **Step 4: 汇报结果**

汇报标题、草稿 media ID、正文长度、图片数量和来源、三件商品的现场销量/售价/佣金、质量门禁、商品卡数量、短剧卡数量及未发表状态。
