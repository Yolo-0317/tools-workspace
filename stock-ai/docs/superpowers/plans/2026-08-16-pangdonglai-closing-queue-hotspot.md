# 胖东来闭店排队热点深评 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出一篇可通过「牛马也智能」热点深评原创门禁、但暂不推送微信草稿箱的胖东来闭店排队长文。

**Architecture:** 先将热榜标题拆成可核对事实与待证网络说法，建立至少三个独立来源域的研究记录；再按“现场—确定性—信任形成—复制边界—实体商业”写成结构化 Codex JSON。最后通过现有 `--codex-draft` 路由完成正文、原创度、配图和合规干跑，不修改生产代码。

**Tech Stack:** Python 3.11、现有 `wechat_mp_hot_trends` / `wechat_mp_draft` / `wechat_mp_originality` 流水线、Markdown、JSON、公开新闻源。

## Global Constraints

- 标题前 15 字包含“胖东来闭店”，标题与首段同题。
- 正文纯段落，无小标题、编号和热榜播报；去空白后不少于 1920 字，建议 2100—2600 字。
- 至少三个不同来源域、四个可核对事实；租金数字和房东动机没有原始可靠出处时不得写成事实。
- 核心判断固定为：消费者排队告别，本质是在为一种“不必处处提防商家”的消费确定性投票。
- 图片必须来自可回溯的同题报道页，或明确标注“原创新闻插画”；不得伪造现场。
- 本轮只成稿和干跑，不调用微信草稿写入 API。

---

### Task 1: 建立事实清单与来源边界

**Files:**
- Create: `output/pangdonglai_closing_queue_research.md`
- Create: `output/pangdonglai_closing_queue_quality.json`

**Interfaces:**
- Consumes: 热榜题目“胖东来将闭门店28个收银口排长龙”、设计稿 `docs/superpowers/specs/2026-08-16-pangdonglai-closing-queue-hotspot-design.md`
- Produces: `research_urls: list[str]`、`verified_facts: list[dict]`、`disputed_claims: list[dict]`、`history_posts: list[dict]`

- [ ] **Step 1: 回源检索同题报道**

检索并打开胖东来官方渠道、河南当地媒体和至少一家全国性媒体的同题页面。查询词固定覆盖：

```text
胖东来 闭店 28个收银口 排长龙
胖东来 生活广场 闭店 官方回应
于东来 关店 租约 房租 官方原文
```

只把能够从原页面确认的门店名、现场时间、闭店安排、收银口数量、经营数据和公开回应写入 `verified_facts`。

- [ ] **Step 2: 记录争议信息而不采信**

在研究文件中单列 `disputed_claims`，至少检查以下两项：

```json
[
  {"claim": "租金从800多万元涨到2400万元", "status": "仅在找到原始公开表述或两家可靠媒体交叉确认后可用"},
  {"claim": "有企业或个人从中使坏", "status": "没有可核对证据时禁止进入正文"}
]
```

- [ ] **Step 3: 写入质量输入 JSON**

`output/pangdonglai_closing_queue_quality.json` 使用以下字段：

```json
{
  "title": "胖东来闭店前排长队，顾客舍不得什么？",
  "topic": "胖东来闭店排队",
  "original_thesis": "消费者排队告别不是单纯抢购，而是在为一种不必处处提防商家的消费确定性投票。",
  "research_urls": [],
  "verified_facts": [],
  "disputed_claims": [],
  "history_posts": []
}
```

完成时 `research_urls` 至少包含三个不同域名，`verified_facts` 至少四项，每项含 `fact`、`source_url` 和 `source_type`。

- [ ] **Step 4: 验证研究数据结构**

Run:

```bash
cd stock-ai
.venv/bin/python -c 'import json,urllib.parse; from pathlib import Path; q=json.loads(Path("output/pangdonglai_closing_queue_quality.json").read_text()); hosts={urllib.parse.urlsplit(u).netloc for u in q["research_urls"]}; assert len(hosts)>=3; assert len(q["verified_facts"])>=4; assert len(q["original_thesis"])>=20; print({"hosts":sorted(hosts),"facts":len(q["verified_facts"])})'
```

Expected: 输出至少 3 个域名和 `facts` 大于等于 4。

---

### Task 2: 写成 Codex 热点深评 JSON

**Files:**
- Create: `output/hotspot_pangdonglai_closing_queue_codex.json`

**Interfaces:**
- Consumes: Task 1 的 `research_urls`、`verified_facts`、`disputed_claims`、`history_posts`
- Produces: `wechat_mp_draft --kind hotspot --codex-draft` 可直接读取的单篇 JSON

- [ ] **Step 1: 写标题、摘要和正文**

JSON 必须包含以下固定字段和值；`body` 直接写入本步骤完成的全文，`research_urls` 直接复制 Task 1 已核验的原始页面 URL，不保留说明性占位文本：

```json
{
  "title": "胖东来闭店前排长队，顾客舍不得什么？",
  "digest": "一家仍被顾客需要的门店为什么会迎来告别？排队背后，是消费者对确定交易体验的珍惜。",
  "body": "",
  "topic": "胖东来闭店排队",
  "research_urls": [],
  "original_thesis": "消费者排队告别不是单纯抢购，而是在为一种不必处处提防商家的消费确定性投票。",
  "slot_key": "hotspot_morning"
}
```

保存前将 `body` 填为去空白后不少于 1920 字、建议 2100—2600 字的完整纯段落正文，将 `research_urls` 填为 Task 1 核验通过的至少三个不同域名原始页面；禁止以空字符串或空数组完成此步骤。

正文按以下因果链写作，但不显示小标题：现场排队与闭店事实 → 顾客舍不得的是确定性 → 信任来自商品、售后、员工与经营克制的长期一致 → 排队不等于企业没有问题 → 模式受地域和管理半径限制 → 实体商业最终竞争的是长期经验。

- [ ] **Step 2: 执行文本自检**

Run:

```bash
cd stock-ai
.venv/bin/python -c 'import json,re; from pathlib import Path; p=Path("output/hotspot_pangdonglai_closing_queue_codex.json"); q=json.loads(p.read_text()); b=q["body"]; n=len(re.sub(r"\s+","",b)); banned=[x for x in ["刷到这条热搜","第一反应是","值得注意的是","不难发现","需要指出的是"] if x in b]; assert n>=1920,(n,"too short"); assert not banned,banned; assert not re.search(r"(^|\n)\s*(#{1,6}|[一二三四五六七八九十]+[、.])",b); print({"chars":n,"paragraphs":len([x for x in b.split("\n\n") if x.strip()])})'
```

Expected: `chars` 大于等于 1920，无断言失败。

- [ ] **Step 3: 检查事实与观点边界**

逐段对照 Task 1：所有具体数字、门店安排和引语都能指向 `verified_facts`；`disputed_claims` 中未核验的内容不得出现在正文。删除“良心企业”“商业神话已经证明”等先验赞美，把判断落到具体交易体验。

---

### Task 3: 通过原创、配图与草稿干跑门禁

**Files:**
- Modify if generated: `assets/wechat_mp/inline-discussion/<topic-slug>/figure_sources.json`
- Modify if generated: `assets/wechat_mp/inline-discussion/<topic-slug>/cover.jpg`
- Modify if generated: `assets/wechat_mp/inline-discussion/<topic-slug>/figure-*.jpg`

**Interfaces:**
- Consumes: `output/hotspot_pangdonglai_closing_queue_codex.json`
- Produces: 完整 HTML 预览输出、原创度报告、1 张封面和 3 张正文配图的来源记录

- [ ] **Step 1: 运行正式路径的只读干跑**

Run:

```bash
cd stock-ai
WECHAT_MP_HOTSPOT_TREND_ENRICH=0 PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_draft --kind hotspot --codex-draft output/hotspot_pangdonglai_closing_queue_codex.json --dry-run
```

Expected: 输出标题、摘要、原创增量报告 `PASS` 和正文 HTML；不得调用 `draft/add` 或 `draft/update`。

- [ ] **Step 2: 处理配图缺口**

若干跑生成 `codex-image-request.json`，逐项读取 `slots` 和 `safety_rules`。每个缺口单独生成一张解释图，并复制到请求中的绝对 `output_path`；画面只表现“闭店告别、排队结账、实体商业信任”的抽象场景，不出现胖东来商标、具体员工面孔、虚构门店地址或未经证实的租金数字。随后重跑 Step 1。

- [ ] **Step 3: 核对图片来源和去重**

确认封面与三张正文图不重复；每张报道图在 `figure_sources.json` 中有 `page_url`、`image_url`、`source_name`、`source_type` 和 `verified`。生成图必须标注 `原创新闻插画`，不得标成公开报道。

- [ ] **Step 4: 运行最终验证**

Run:

```bash
cd stock-ai
git diff --check
.venv/bin/python -c 'import json,re,urllib.parse; from pathlib import Path; q=json.loads(Path("output/hotspot_pangdonglai_closing_queue_codex.json").read_text()); b=q["body"]; assert len(re.sub(r"\s+","",b))>=1920; assert len({urllib.parse.urlsplit(u).netloc for u in q["research_urls"]})>=3; assert len(q["original_thesis"])>=20; print({"title":q["title"],"body_chars":len(re.sub(r"\s+","",b)),"sources":len(q["research_urls"])})'
```

Expected: `git diff --check` 无输出；标题正确、正文长度和来源数量均达门禁。

- [ ] **Step 5: 提交实现文件**

只在用户要求保留仓库产物时提交可追溯图片与代码配置；`output/` 成稿和研究缓存保持忽略，不提交。未得到“推送”指令时，到此结束，不执行非 `--dry-run` 命令。
