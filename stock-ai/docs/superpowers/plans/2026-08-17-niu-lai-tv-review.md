# 《牛来》影视长文 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成一篇 2200—2800 字的《牛来》剧情型影视长文，让“普通人”判断从可核验的动物行动与处境中自然生长，并通过来源、原创、排版和公开配图门禁。

**Architecture:** 先建立影片事实、剧情场面、观众观感和传闻边界四层研究台账，再把影片注册进既有 `tv_review` 题库与本地剧照锚点。正文写入手工金样和按题缓存，现有影视链路只负责清洗、插图、短剧选择与预演，不调用模型重写定稿。

**Tech Stack:** 公开网页研究、Markdown、JSON、Python、pytest、`scripts.tools.wechat_mp_tv_body_cache`、`scripts.tools.wechat_mp_draft --kind tv_review`。

## Global Constraints

- 标题暂定 `《牛来》笑到后来，有点难受`，不超过 20 个汉字。
- 开篇必须写剧透预警。
- 正文去空白后为 2200—2800 字，院线单片纯段落排版，每段 2—4 句，单段不超过约 220 字。
- 不使用 Markdown 小标题、编号、问答模板、一句一段排版或第一人称。
- 剧情必须占主体，至少 5 个经过交叉核验的具体桥段。
- “普通人”判断必须由角色动作承托；禁止虚构观众经历、采访、工作或家庭困境，禁止脱离剧情另写“普通人赞歌”。
- 区分影片事实、观众评价与文章判断；“全面下架”、票房暴涨倍数、制作内幕和创作者意图未经权威来源确认不得写成事实。
- 正文至少 3 张公开图，另有独立横版封面；不使用观众摄屏、账号截图、来源不明二次拼图或生成剧情剧照。
- 质量评分不低于 75，AI 味不高于 20，原创增量门禁必须通过。
- 短剧组件最多 1 个且必须含 `wxTicket`；普通返佣商品为 0。
- 本轮先完成 `--dry-run`；用户明确说“推送”前不得调用微信草稿写入接口。

---

## File Structure

- Create: `stock-ai/output/niu_lai_research.md` — 元数据、剧情桥段、观众观感与传闻边界台账。
- Create: `stock-ai/output/niu_lai_quality.json` — 来源、原创判断、剧情锚点和不可写声明。
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_topics.py` — 注册 `Niu Lai` 题目与研究入口。
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_figures.py` — 注册 `niu-lai` 正文图锚点。
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_trial.py` — 验证题目元数据与标题长度。
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_figures.py` — 验证公开图按剧情顺序注入。
- Create: `stock-ai/data/wechat_mp_tv_review_golden/niu-lai.body_core.md` — 无评分、无图标记的正文金样。
- Create: `stock-ai/data/wechat_mp_tv_body_cache/niu-lai.json` — 标题、摘要与正文缓存。
- Create: `stock-ai/assets/wechat_mp/inline-tv/niu-lai/figure_sources.json` — 封面和正文图来源。
- Create: `stock-ai/assets/wechat_mp/inline-tv/niu-lai/cover.jpg` — 独立横版封面。
- Create: `stock-ai/assets/wechat_mp/inline-tv/niu-lai/still-01.jpg` — 前段牛群或主角场面。
- Create: `stock-ai/assets/wechat_mp/inline-tv/niu-lai/still-02.jpg` — 中段鸟、豹子或狼群场面。
- Create: `stock-ai/assets/wechat_mp/inline-tv/niu-lai/still-03.jpg` — 后段情绪转向场面。

### Task 1: 建立事实、剧情与传闻边界台账

**Files:**
- Create: `stock-ai/output/niu_lai_research.md`
- Create: `stock-ai/output/niu_lai_quality.json`

**Interfaces:**
- Consumes: 官方海报或预告、票务平台影片页、公开媒体报道、豆瓣完整观影记录和其他可回到原页的观影材料。
- Produces: 至少 3 个独立来源域、5 个完整剧情锚点、影片元数据、普通人落点证据和明确排除的传闻。

- [ ] **Step 1: 核验影片元数据**

检索 `《牛来》 电影 官方 海报 导演 片长 上映`、`《牛来》 猫眼`、`《牛来》 淘票票` 和国家电影局公示。只有官方或票务平台页面出现时，才记录导演、出品方、上映日、片长和官方梗概；无法确认的字段放入内部 `unknown_fields`，不进入正文。

- [ ] **Step 2: 核验五个剧情锚点**

围绕牛群、鸟、豹子、三只狼和后段悲剧转向分别寻找两个独立材料，或以官方预告与一篇完整观影记录交叉印证。每个锚点写全 `scene`、`character`、`action`、`pressure`、`consequence`、`stage`、`source_urls` 七个字段；没有直接后果的网络截图不算完整锚点。

- [ ] **Step 3: 分离观感、判断和事实**

把“前 10 分钟笑声密集”“30 分钟后新鲜感衰减”“粗糙建模形成统一风格”等放进 `audience_observations` 并绑定来源。把“无体面形象也仍要承担生活”等放进 `ordinary_people_inferences`，每条绑定前一步剧情动作，不虚构观众职业、收入、家庭或影院经历。

- [ ] **Step 4: 排除高风险传闻**

把“全国下架”“票房暴涨千倍”“政府抵欠款发龙标”“导演故意审丑”等列入 `rejected_claims`。除非找到官方通知、权威票房平台时间序列或主创原话，否则不得出现在标题、摘要和正文事实句中。

- [ ] **Step 5: 验证台账完整性**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python - <<'PY'
import json
from urllib.parse import urlparse
from pathlib import Path
d=json.loads(Path('output/niu_lai_quality.json').read_text())
anchors=d['plot_anchors']
domains={urlparse(u).hostname for u in d['research_urls']}
assert len(anchors) >= 5
assert len(domains) >= 3
assert all(set(a) >= {'scene','character','action','pressure','consequence','stage','source_urls'} for a in anchors)
assert all(len(a['source_urls']) >= 2 for a in anchors)
assert len(d['original_thesis']) >= 20
assert '全国下架' in ''.join(d['rejected_claims'])
print({'anchors':len(anchors),'domains':len(domains),'rejected':len(d['rejected_claims'])})
PY
```

Expected: 至少 5 个七字段剧情锚点、至少 3 个来源域，原创判断与传闻排除均非空。

### Task 2: 注册影片和三图锚点

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_topics.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_figures.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_trial.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_figures.py`

**Interfaces:**
- Consumes: Task 1 核验的中文片名、年份、题目和剧情顺序。
- Produces: `CURATED_HOT` 中 `title_en="Niu Lai"` 的题目，以及 `CURATED_TV_STILLS["niu-lai"]` 的三图配置。

- [ ] **Step 1: 写影片注册失败测试**

```python
def test_niu_lai_builds_fixed_public_title() -> None:
    topic = next(t for t in CURATED_HOT if t["title_en"] == "Niu Lai")
    assert topic["title_zh"] == "牛来"
    assert topic["cover_slug"] == "niu-lai"
    assert topic["type"] == "film"
    assert topic["title_override"] == "《牛来》笑到后来，有点难受"
    assert len(topic["title_override"]) <= 20
```

- [ ] **Step 2: 运行题目测试确认失败**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_wechat_mp_tv_trial.py -k niu_lai`

Expected: FAIL，当前找不到 `Niu Lai`。

- [ ] **Step 3: 添加影片题目**

在 `CURATED_HOT` 添加 `title_en="Niu Lai"`、`title_zh="牛来"`、`type="film"`、`year="2026"`、`platform="院线电影"`、`cover_slug="niu-lai"`、固定标题、Task 1 的研究 URL 与普通人剧情切口。评分字段只在当天能从原始评分页核验时填写，否则保持空值。

- [ ] **Step 4: 写三图顺序失败测试**

在 `test_wechat_mp_tv_figures.py` 构造含 Task 1 最终三个完整锚点短语的正文，调用 `inject_tv_figures()`，断言 `still-01.jpg`、`still-02.jpg`、`still-03.jpg` 各出现一次且索引严格递增。

- [ ] **Step 5: 运行测试确认失败**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_wechat_mp_tv_figures.py -k niu_lai`

Expected: FAIL，当前没有 `niu-lai` 配图配置。

- [ ] **Step 6: 添加配置并运行回归**

在 `CURATED_TV_STILLS` 添加 `source="local"` 和三个 `after_anchor`；锚点必须是正文中唯一出现的完整动作短语。运行：

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_wechat_mp_tv_trial.py tests/unit/test_wechat_mp_tv_figures.py
```

Expected: 新增与既有影视测试全部 PASS。

### Task 3: 完成剧情型正文金样与缓存

**Files:**
- Create: `stock-ai/data/wechat_mp_tv_review_golden/niu-lai.body_core.md`
- Create: `stock-ai/data/wechat_mp_tv_body_cache/niu-lai.json`

**Interfaces:**
- Consumes: Task 1 的五个剧情锚点、观众观感边界和普通人判断。
- Produces: 可由 `normalize_tv_review_body()` 处理的正文，以及 `load_tv_body_cache(topic_key="niu-lai")` 可读取的缓存。

- [ ] **Step 1: 写剧透预警和前段笑声**

首段固定以“剧透预警：下文涉及《牛来》的主要剧情与结局。”开头。紧接一个已核验的动物动作，写造型、动作、音乐和短镜头如何让笑声发生，不先写票房、热搜或抽象审美争论。

- [ ] **Step 2: 沿五个桥段写情绪转向**

按剧情顺序覆盖 Task 1 的五个锚点。每个锚点写清角色动作、压力和后果；“笑到后来难受”必须由场面变化证明，不能只靠形容词宣布。

- [ ] **Step 3: 把普通人判断挂在动作上**

在两个至三个剧情段末尾写有限判断：没有漂亮形象、无法解释自己、仍要承担后果的人为何让普通观众认出熟悉处境。每个判断前一至两句必须仍是影片动作，不新增虚构职业、账单、家庭或人生故事。

- [ ] **Step 4: 写制作评价、受众和结尾**

区分造型统一造成的陌生喜感、剪辑与音乐完成的情绪推动、后半程重复和制作不足造成的疲惫。明确“被玩梗不等于佳作”，也明确几张丑图不能替代完整观影；结尾只留一个自然互动问题。

- [ ] **Step 5: 做语言与排版清洗**

删除“戏眼”“意象”“正向反馈”“遮羞布”“场面堆叠”“真正的问题是”“值得注意的是”“综上所述”等影评腔；保证无第一人称、无 Markdown 小标题、无一句一段，每段 2—4 句。

- [ ] **Step 6: 保存缓存并验证规格**

用 `save_tv_body_cache()` 保存固定标题、42 字以内摘要和金样正文。运行：

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python - <<'PY'
import json,re
from pathlib import Path
b=Path('data/wechat_mp_tv_review_golden/niu-lai.body_core.md').read_text()
paras=[x.strip() for x in b.split('\n\n') if x.strip()]
d=json.loads(Path('data/wechat_mp_tv_body_cache/niu-lai.json').read_text())
assert 2200 <= len(re.sub(r'\s+','',b)) <= 2800
assert max(map(len,paras)) <= 220
assert b.startswith('剧透预警')
assert len(d['title']) <= 20 and len(d['digest']) <= 42
assert not re.search(r'(^|\n)[#>]|^[-*+] |^[0-9]+[.、]', b, re.M)
print({'chars':len(re.sub(r'\s+','',b)),'paras':len(paras),'max_para':max(map(len,paras))})
PY
```

Expected: 字数、段落、标题、摘要和纯段落排版全部通过。

### Task 4: 获取封面和三张公开剧情图

**Files:**
- Create: `stock-ai/assets/wechat_mp/inline-tv/niu-lai/figure_sources.json`
- Create: `stock-ai/assets/wechat_mp/inline-tv/niu-lai/cover.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-tv/niu-lai/still-01.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-tv/niu-lai/still-02.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-tv/niu-lai/still-03.jpg`

**Interfaces:**
- Consumes: Task 1 核验过的官方物料、票务平台、媒体报道和公开影视资料页。
- Produces: 1 张独立横版封面、3 张互不重复正文图和逐图来源记录。

- [ ] **Step 1: 建立候选清单**

按官方海报或预告、票务平台影片页、可追溯媒体报道、豆瓣或 TMDB 公开资料页的顺序找图。每张记录 `file`、`page_url`、`image_url`、`source_name`、`scene`、`verified`、`reuse_note`；微博和百度只作发现入口。

- [ ] **Step 2: 下载并视觉检查**

封面选择横图或可安全裁为 900×383 的物料；三张正文图分别对应前段笑声、中段角色遭遇和后段转向。检查分辨率、水印、二维码、个人信息和重复画面，不采用观众摄屏。

- [ ] **Step 3: 缺图时失败关闭**

不足 1 张封面和 3 张可追溯正文图时停止预演并报告缺失槽位；不生成替代剧情剧照，不把同一海报重复裁切成多图。

- [ ] **Step 4: 验证文件与来源**

```bash
cd stock-ai
shasum -a 256 assets/wechat_mp/inline-tv/niu-lai/cover.jpg assets/wechat_mp/inline-tv/niu-lai/still-0*.jpg
PYTHONPATH=. .venv/bin/python - <<'PY'
import json
from pathlib import Path
from PIL import Image
root=Path('assets/wechat_mp/inline-tv/niu-lai')
files=['cover.jpg','still-01.jpg','still-02.jpg','still-03.jpg']
d=json.loads((root/'figure_sources.json').read_text())
assert [x['file'] for x in d['images']] == files
assert all(x['page_url'].startswith('http') and x['source_name'] and x['verified'] for x in d['images'])
print({f:Image.open(root/f).size for f in files})
PY
```

Expected: 四个哈希互不相同，Pillow 均可打开，每图都能回到原页面。

### Task 5: 原创、质量、短剧与草稿干跑

**Files:**
- Read: `stock-ai/output/niu_lai_quality.json`
- Read: `stock-ai/data/wechat_mp_tv_body_cache/niu-lai.json`
- Read: `stock-ai/assets/wechat_mp/inline-tv/niu-lai/figure_sources.json`

**Interfaces:**
- Consumes: Task 1—4 的研究、正文、缓存和四图。
- Produces: 原创、质量、三图与短剧注入预演；不产生微信 `media_id`。

- [ ] **Step 1: 运行原创与质量门禁**

调用现有 `film_longform` 原创门禁，要求 `gate_passed == True`、完整锚点不少于 5、近 30 天无同作品重复稿。对最终文章调用 `assess_article_for_push(article, "tv_review")`，要求总分不低于 75、AI 味不高于 20、合规失败为空；人工检查“普通人”每次出现前后均有《牛来》专属动作。

- [ ] **Step 2: 运行影视草稿干跑**

```bash
cd stock-ai
set -a; source .env; set +a
WECHAT_MP_TV_TOPIC=牛来 WECHAT_MP_TV_RESEARCH=0 PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_draft --kind tv_review --dry-run
```

Expected: 标题正确；正文来自缓存；剧透预警存在；3 张正文图可注入；短剧组件为 0 或 1，若为 1 则含 `wxTicket`；普通返佣商品为 0；没有 `media_id`。

- [ ] **Step 3: 运行新鲜最终验证**

重新执行 Task 1 台账验证、Task 2 两组 pytest、Task 3 正文规格、Task 4 四图检查，以及 Task 5 的原创、质量和 `--dry-run`，不得复用此前输出。

- [ ] **Step 4: 交付并等待推送指令**

交付标题、正文去空白字数、来源域数量、剧情锚点、四图状态、质量分、AI 味、原创门禁和短剧状态，明确尚未写入草稿箱。只有用户明确回复“推送”后，才执行不带 `--dry-run` 的命令并回读核对。
