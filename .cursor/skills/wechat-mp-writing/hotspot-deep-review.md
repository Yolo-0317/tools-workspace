# 热点深评（hotspot）写稿真源

> **2026-08-05 定稿**：社会/文娱/职场/公共事件 **热点深评**；纯段落长文 + 同题报道取材 + 口语评论口吻。  
> 代码：`wechat_mp_hot_trends.py` · `wechat_mp_discussion_research.py` · `wechat_mp_hotspot_article.py` · `wechat_mp_discussion_figures.py` · `wechat_mp_hotspot_polish.py`

用户说 **热点深评、hotspot 太水、像 AI、标题很怪、凑字数、配图不够、参考报道仿写** → **先读本文件**，再动 prompt / 模板。

---

## 稿型定位

| 项 | 要求 |
|----|------|
| 定时 | **09 / 11 / 15 / 18** 各 1 篇（`hotspot_early` / `morning` / `afternoon` / `evening`） |
| 选题 | 微博 + 百度热搜（`WECHAT_MP_HOTSPOT_SOURCE=trends`） |
| 形态 | **纯段落**，禁止 `> ` / `##` / 「一、二、三」小标题 |
| 长度 | **1800—2200 字**；Codex 手写稿门禁 ≥1800，信息完整后优先完读，不为凑字重复观点 |
| 口吻 | **[social-commentary-voice.md](social-commentary-voice.md)**：读者转述者，摆事实、摆说法 |
| 用户主动成稿 | 固定 DeepSeek Chrome 会话直接产出标题和初稿，Agent 核实编辑；两次确认 |
| 配图 | 至少 1 张可追溯真实图作封面；正文 0—3 张，有几张用几张；封面可按需复用并计入上限；禁止生成图 |

**默认主轴是社会热点**，不是 A 股收盘复盘。仅当热搜条目本身带盘面/个股关键词时，代码才走财经 `fetch_hotspot_research` 分支。

---

## 流水线（Agent 勿跳步）

```text
双榜热搜选题（自动避当日已用标题）
  → fetch_discussion_research（360/搜狗/百度新闻 + 报道页正文补摘要）
  → 用户主动稿：第一次确认后由固定 DeepSeek 会话直接产出标题和初稿
  → Agent 核事实、编辑并记录 edit notes
  → 可选：对照参考二次仿写（WECHAT_MP_HOTSPOT_IMITATE_REWRITE，默认关）
  → scan_report_voice 门禁 → 不足则重写（最多 2 轮）
  → 清洗元叙述 + 拆短段（reflow_hotspot_layout）
  → 抖音优先：只读搜索结果卡片与封面，禁止打开/播放视频
  → 再补政府官网、官方媒体或法条页面证据图
  → 封面至少 1 张；正文 0—3 张；封面可按需复用并计入上限；禁止生成或自动补图
  → 展示预演摘要，第二次确认后 upsert 分槽草稿
```

**耗时预期**（单篇）：

| 阶段 | 约耗时 | 说明 |
|------|--------|------|
| 取材 | 20～60s | 多门户检索 + 逐页抓摘要 |
| LLM 成稿 | 50～90s | 固定 DeepSeek 网页会话本轮回复；失败即停 |
| 配图 | 20～90s | 抖音搜索卡片封面优先，再补权威证据图；不生成 |
| 推草稿 | 5～15s | 微信 API |

推稿务必：`export WECHAT_MP_HOTSPOT_TREND_ENRICH=0`（避免东财 enrich 污染社会稿且变慢）。

### 推稿命令

```bash
cd stock-ai
export WECHAT_MP_HOTSPOT_TREND_ENRICH=0
export WECHAT_MP_HOTSPOT_TOPIC="赛格商场坠亡"   # 可选：手动定题
uv run python -m scripts.tools.wechat_mp_draft_batch --batch hotspot_afternoon --no-notify
```

四槽：`hotspot_early` · `hotspot_morning` · `hotspot_afternoon` · `hotspot_evening`

单篇质检：

```bash
uv run python -m scripts.tools.wechat_mp_push_quality_gate --kind hotspot
uv run python -m scripts.tools.wechat_mp_eval --kind hotspot --traffic
```

---

## 联网取材（社会热点核心）

成稿前 **必须** 有同题公开报道（`fetch_discussion_research`），写入 prompt：

1. **【联网事实】** — 可核对的时间、人物、机构、数字、通报表述  
2. **【参考文章·仿写】** — 2～3 篇同题稿摘要 + 开头示范（学第一句怎么直接写人+事）

仿写节奏（学澎湃/新浪/网易同题稿，不照搬）：

- **首段**：谁 + 在哪 + 发生了什么（与标题同题，50 字内落地）  
- **中段**：可核对细节、通报 vs 民间说法、多方观点  
- **末段**：一句后续观察或可讨论问句；**禁止**股市盘面、指数、个股  

二次仿写（`WECHAT_MP_HOTSPOT_IMITATE_REWRITE=1`，默认关）：删导读腔、补遗漏可核对事实。质量不稳时可手动开。

---

## 用户主动成稿入口（强制）

Agent 先研究并展示提示词，用户第一次确认后，固定 DeepSeek Chrome 会话直接产出标题和初稿；Agent 再核实编辑并记录改动。直接 `--codex-draft` 绕过该 workflow 会被拒绝：

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_browser_write --help
```

编辑稿 JSON 必填 `title`、`digest`、`body`、`topic`、`original_thesis` 和 `research_urls`；`slot_key` 可选。`research_urls` 至少覆盖 3 个不同来源域，`original_thesis` 须用不少于 20 字写出可被反驳和检验的原创核心判断。正文去空白后少于 1800 字，或未过来源多样性、原创观点、段落、套话、真实配图或合规门禁时直接拒绝，由 Agent 修改源 JSON 后重试。

## 旧自动写稿 LLM（兼容路径）

未传 `--codex-draft` 的旧自动生成路径仍使用 Composer（`call_wechat_mp_llm` → `agent --model composer-2.5`），不经 DeepSeek API。该路径仅作兼容；当前热点定时已暂停。

| 变量 | 默认 | 含义 |
|------|------|------|
| `WECHAT_MP_LLM_MODEL` | `composer-2.5` | 模型 slug |
| `WECHAT_MP_CURSOR_MAX_RETRIES` | `1` | agent 调用失败重试 |
| `WECHAT_MP_CURSOR_TIMEOUT_SECONDS` | `420` | 单次 agent 超时 |
| `WECHAT_MP_HOTSPOT_MIN_BODY_SLACK` | `80` | 社会热点字数容差（门禁 2000−80=1920） |

---

## 配图（抖音优先、只用真实图）

| 项 | 说明 |
|----|------|
| 开关 | `WECHAT_MP_HOTSPOT_SOCIAL_FIGURES=1`（trends 默认开） |
| 正文图 | 0—3 张，按已核验真实图数量注入；封面可由 Agent 根据内容按需复用，复用后计入上限 |
| 封面 | 至少 1 张可追溯真实图，裁成 2.35:1；零图拒推 |
| 第一来源 | 已登录抖音的搜索结果卡片与封面；禁止点击、打开或播放视频 |
| 后续来源 | 政府官网、官方媒体、法条页面等可追溯证据图 |
| 留痕 | `douyin-search.json` 记录主题、检索词、完成时间、候选或无候选原因；`figure_sources.json` 记录来源与核验状态 |
| 封面复用 | 需要复用时在 `cover_source.json` 显式设置 `"reuse_in_body": true`；未声明或为 `false` 时不复用 |
| 数量原则 | 有几张用几张，正文允许少图；除显式复用封面外，不得使用搬运图、重复帧、无关画面或生成图 |
| 门禁 | 所选抖音候选须匹配 `douyin_cover` 来源；没有可追溯封面即拒推 |

封面复用是单篇稿件的内容判断，不是默认动作。只有封面能够自然承接正文段落、且复用不会降低阅读体验时才启用；不得为增加图片数量机械复用。

配图不足不是生成图片的理由。抖音无合格候选时必须写明原因，再补权威网页证据图；正文不足 3 张照常使用现有图片，正文 0 张也可继续。若连封面所需的一张可追溯真实图都没有，则停止并报告，不创建 `codex-image-request.json`，不调用 ChatGPT、ImageGen、DeepSeek 或其他图片生成能力，也不退回默认品牌封面。

---

## 禁止元叙述（AI 味重灾区）

**不要** 在正文里出现「我在引用资料」的导读句。以下 **一律禁止**（`strip_hotspot_meta_commentary` / eval 会扣）：

| 禁句示例 |
|----------|
| 刷到这条热搜 / 第一反应是 / 往下翻才知道 |
| 公开报道里有一条值得先记住 |
| 热搜在聊「…」 / 双榜讨论偏… |
| 值得注意的是 / 不难发现 / 需要指出的是 |
| 叙事溢价 / 情绪溢价 / 硬验证 / 露馅 |

**正确开头示例**（社会热点）：

```text
8 月 3 日，青岛大学一名宿管大爷在值班室热射病去世。
学校通报里写「已启动调查」，没写空调有没有、值班室多大。
```

---

## 标题路牌

- 格式：`{可搜实体 + 反常结果}？`（疑问句优先）  
- **前 15 字**含案由/地名/片名/数字，表意完整  
- **硬禁**：震惊体、`和A股啥关系`、平台名连读（`百度把…送上热搜`）、编审过程（`候选五条`）  
- **好例子**：`儿子病逝留 87 个游戏号，遗产该归谁？`  
- **坏例子**：`返…` `暂…` 半句话截断

详见 [sousou-content-rules.md](sousou-content-rules.md) · [traffic-copy-craft.md](traffic-copy-craft.md)

---

## 排版（移动端）

- 采用**混合短段**：事实落点、场景切换、转折和关键判断优先 **一句一段**；解释、证据与必要限定可 **两句一段**，单段原则上 ≤130 字。
- “一句一行”在成稿中指一句与下一句之间留空行，形成独立段落；不是只插软换行，也不是把一个完整逻辑拆成语义残片。
- 推荐节奏：`短事实 → 稍长解释 → 单句判断`。连续 5 段以上句长相近会像提词器；连续使用十几字的空泛金句会像鸡汤号，均须合并或补充事实。
- 一句一段只解决手机端阅读压力，不等于降低信息密度。法条适用、事实边界和因果解释不能为了排版被拆散。
- 段间空一行；禁止编号清单（`delist_hotspot_body`）  
- 社会稿 **禁止** 指数涨跌复读（财经分支才做 `dedupe_hotspot_index_mentions`）

### 一句一段参考（2026-08-12）

近期公众号排版资料普遍强调短段、留白和“一句话或一个完整观点即可分段”，核心原因是手机端以扫读为主，读者会先判断眼前这一屏是否读得完。这个方向与 [social-commentary-voice.md](social-commentary-voice.md) 的“多数段落 1～3 行、关键事实可单句成段”一致。

外部参考只用于观察排版趋势，不作为平台官方推荐机制结论：[TypeZen 2026 微信公众号排版法则](https://typezen.online/blog/wechat-typography-rules-2026) · [人间社区：一篇好内容，从排版开始](https://people.fukan.my/2026/02/%E4%BB%8E%E6%8E%92%E7%89%88%E5%BC%80%E5%A7%8B/)。

热点深评不机械执行“每个句号都换段”：

```text
× 系统出错了。

× 门店道歉了。

× 消费者不接受。

√ 门店承认结算结果有误，并称可能是系统识别问题。

但系统只能解释错误发生在哪一环，不能替经营者承担责任。
```

当前 `reflow_hotspot_layout` 仍按 ≤130 字重排并可能合并过短段落；本节先作为 DeepSeek 初稿后的 Agent 编辑参考。若要让自动稿稳定执行“一句一段”，应另开代码改造与 A/B 数据验证，不在文档修订中静默改变生产行为。

---

## 环境变量

| 变量 | 默认 | 含义 |
|------|------|------|
| `WECHAT_MP_HOTSPOT_SOURCE` | `trends` | 微博+百度热搜选题 |
| `WECHAT_MP_DISCUSSION_RESEARCH` | `1` | 社会同题报道取材 |
| `WECHAT_MP_HOTSPOT_TREND_ENRICH` | `0` | **保持 0**；1=东财 enrich（慢，污染社会稿） |
| `WECHAT_MP_HOTSPOT_IMITATE_REWRITE` | `0` | 对照参考二次仿写 |
| `WECHAT_MP_HOTSPOT_SOCIAL_FIGURES` | `1` | 社会布局配图 |
| `WECHAT_MP_HOTSPOT_REQUIRE_FIGURES` | `1` | 旧自动链路兼容变量；用户主动稿以真实封面门禁为准 |
| `WECHAT_MP_DISCUSSION_BODY_FIGURES` | `3` | 正文图上限；用户主动稿实际为 0—3 张 |
| `WECHAT_MP_DISCUSSION_FIGURES_FORCE` | `0` | 1=忽略缓存重抓配图 |
| `WECHAT_MP_HOTSPOT_TOPIC` | — | 手动定题关键词 |
| `WECHAT_MP_LLM_MODEL` | `composer-2.5` | Composer 模型 slug |
| `WECHAT_MP_QUALITY_GATE_STRICT` | `1` | 推稿调试可 `=0` |

---

## 改稿检查清单

- [ ] 首段 **50 字内**落地标题事件（人+事）  
- [ ] 至少 **4 个可核对事实**（来自报道，非编造）  
- [ ] 无导读腔 / 热榜播报 / 财经盘面套话  
- [ ] 标题路牌完整、与开篇同题  
- [ ] 情绪主语+具体代价+两侧张力已在正文前 1/3 内体现；文末有清晰读者选择
- [ ] 已先检索抖音，且只读取搜索结果卡片/封面，没有打开或播放视频
- [ ] 至少 1 张可追溯真实封面；正文 0—3 张，均与事件相关；如复用封面，已在 `cover_source.json` 显式声明且计入上限
- [ ] 没有创建图片生成请求，也没有自动生成图片

---

## 故障排查

| 现象 | 原因 | 处理 |
|------|------|------|
| 构建失败「未达 2000 字」 | 取材薄 / LLM 短稿 | `TREND_ENRICH=0` 重跑；换素材更足的题；查 `web_research_blob` 长度 |
| 构建失败「缺少可追溯封面」 | 抖音和权威网页均无合格真实图 | 记录抖音无候选原因，换同题检索词或补权威来源；仍无封面则停止 |
| 单篇 3～5 min | 多轮 LLM + 配图抓取 | 默认已关仿写、2 轮上限；`DISCUSSION_FIGURES_FORCE=0` |
| 总分 <75 且正文几百字 | 旧短模板 fallback | 社会稿应已禁止；查 `generate_hotspot_body` 日志 |
| 文末「复盘的朋友」 | 财经增长句误注入 | `hotspot` 已在 `_NO_RECOMMEND_HOOK_KINDS` |

---

## 附录：财经热搜分支（少见）

热搜标题含 A 股/板块/个股关键词时，代码走 `fetch_hotspot_research`（东财）+ 盘面数字口吻。  
**定时四槽默认不会触发**；手动财经深评才需要。勿把财经仿写规则套到社会稿。

---

## 交叉引用

- 社会口吻：[social-commentary-voice.md](social-commentary-voice.md)  
- 引流节奏：[traffic-copy-craft.md](traffic-copy-craft.md)  
- 搜一搜路牌：[sousou-content-rules.md](sousou-content-rules.md)  
- 去 AI 味：[anti-ai-voice.md](anti-ai-voice.md)  
- eval 门禁：[eval-gates.md](eval-gates.md)  
- 定时批次：`stock-ai/docs/WECHAT_MP_SCHEDULING.md`  
- 代码映射：`wechat-mp-drafts/rules-implemented.md` §18
