# 11:00 热搜话题讨论稿 SOP

> **定位**：每天 11:00 从微博+百度双榜取**关注度最高、可写的文娱/话题**，写**话题讨论稿**（不是剧评、不是行业影响力分析）。  
> **代码**：`wechat_mp_tv_morning_discussion.py` · `wechat_mp_tv_morning_draft.py` · `wechat_mp_discussion_research.py` · `wechat_mp_discussion_figures.py` · `wechat_mp_tv_review_article.py`

---

## 零、为什么老出问题（根因，2026-08-03 复盘）

| 现象 | 根因 | 不是 |
|------|------|------|
| 无图 / 错图 / 模板正文 | **11:00 定时任务直推 LLM 首稿**（或 DeepSeek 失败走兜底），**没走手改缓存** | 不是 repush 命令写错 |
| AI 味、热榜播报、抬格调 | **生成 prompt 落后于 §六**；禁词靠聊天后补，模型没见过 | 不是「再强调一次口吻」就够 |
| 选题偏、无推荐流量 | **§八 四关只在文档**，`pick_morning_discussion_topic` 仍主要看 `discussion_score` | 不是单篇没选好 |
| 每篇都要人工改很多遍 | **缺少推稿前硬性清单**；SOP 是禁词表，不是顺序流程 | 不是 Agent 不认真 |

**结论**：当前最大错位是——**SOP 假定「手改缓存 → repush 定稿」，定时任务却「现选现写现推」**。两边打架，问题就会反复出现。

---

## 零·二、正确流程（必须按顺序，禁止跳步）

```
当日 10:00 前（或前晚）
  ① 四关选题（§八）→ 定 cover_slug，写入/确认缓存元数据
  ② 同题报道仿写 → 手改 body_core（金样口吻，非 LLM 首稿直出）
  ③ 配图：research_urls + still-01/02/03 目检
  ④ 推稿前检查清单（§九）全过 → repush 草稿箱

11:00 定时任务（目标态）
  · 仅推送「当日已有合格缓存」的 cover_slug
  · 无缓存 / preflight 不过 → 飞书告警，禁止推兜底模板
  · 禁止：11:00 现场 DeepSeek 全文 + 直接进草稿箱
```

**人工定稿是唯一真源**：`data/wechat_mp_tv_body_cache/{cover_slug}.json`。聊天里改好的稿，必须落盘后再 repush；**不要假设 11:00 会自动用你刚改的缓存**（选题 slug 不一致就不会读）。

---

## 一、和旧流程的区别

| 项 | 旧（影视试跑） | 新（11:00 话题讨论） |
|----|----------------|----------------------|
| 选题 | `is_tv_trend` 过滤，偏片单/剧评 | 双榜 **attention_score + 文娱加权** |
| 成稿 | tv_review 五节剧评 | **纯段落**，仿同题公开报道 + 蜘蛛侠金样口吻 |
| 取材 | 东财财经搜索 | **360 新闻检索**热搜原句 + `research_urls` |
| 正文配图 | 财经 inline 池 | **同题报道高清图**（≥80KB，网易优先） |
| 封面 | 影视剧照 | **sector 牛马主图**（与正文事件图分开） |

---

## 二、选题规则

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_tv_morning_discussion --limit 8
uv run python -m scripts.tools.wechat_mp_tv_morning_discussion --pick
```

社会争议话题可写（出轨、胚胎等），合规见原 SOP §社会争议。

---

## 三、成稿规则

### 必须做

1. **同题报道仿写**：`fetch_discussion_research` → 【参考文章·仿写】→ `WECHAT_MP_DISCUSSION_IMITATE_REWRITE=1`
2. **口吻金样**：`data/wechat_mp_tv_review_golden/spider_man_brand_new_day.body_core.md` + `tv-review-voice.md` §朋友分享  
3. **社会民生稿**（案由、劳动者、公共事件）：另读 `wechat-mp-writing/social-commentary-voice.md` — 短段、物件立人、通报 vs 民间记忆对照、引用块、克制感情  
4. **首段直接写人+事**，禁止导读句（见 §六 禁词表）  
5. **事件配图**：正文 2/4/6 段后注入；**封面用 sector 牛马主图**

### 人工定稿缓存

`data/wechat_mp_tv_body_cache/{cover_slug}.json`：

```json
{
  "content_mode": "discussion",
  "cover_slug": "...",
  "trend_title": "...",
  "research_urls": ["https://m.163.com/dy/article/...", "..."],
  "body_core": "纯段落，无免责"
}
```

---

## 四、推送命令

```bash
# 预览
uv run python -m scripts.tools.wechat_mp_tv_morning_draft --dry-run

# 定时推
bash scripts/wechat_mp_tv_draft_scheduled.sh

# 手改缓存后重推（不重写 LLM）
WECHAT_MP_DISCUSSION_FIGURES_FORCE=1 \
  uv run python -m scripts.tools.wechat_mp_repush_tv_review_draft --title-en {cover_slug}
```

| 变量 | 默认 | 说明 |
|------|------|------|
| `WECHAT_MP_DISCUSSION_RESEARCH` | 1 | 360 新闻检索 |
| `WECHAT_MP_DISCUSSION_FIGURES` | 1 | 正文事件配图 |
| `WECHAT_MP_DISCUSSION_IMITATE_REWRITE` | 1 | 对照参考稿二次仿写 |
| `WECHAT_MP_DISCUSSION_FIGURES_FORCE` | 0 | 1=强制重下配图 |

---

## 五、配图踩坑

| 现象 | 原因 | 处理 |
|------|------|------|
| K 线/财报图 | 东财泛搜「婚姻」「试管婴儿」 | 只用 360 同题检索 + `research_urls` |
| 图糊（~26KB） | 新浪 front 横幅小图 | `ensure_discussion_figures` 全页候选 **≥80KB** 按体积 Top3；网易 dingyue 优先 |
| 下载 403 | Referer 用了图片 URL | Referer 用**报道页 URL** |
| 封面用了事件图 | 误走 `pick_discussion_thumb` | `tv_topic_uses_brand_cover` → `pick_thumb_for_draft_kind('sector')` |
| 只有 1–2 张图 | 候选图 <25KB 被滤掉 / repush 无张数校验 | 阈值 22KB；**至少 3 张**；不足则 `FIGURES_FORCE=1` 或补 `research_urls` |
| 文末推荐 junk 图 | 网易 `QTng` / `YYYY/MM/DD` 路径大图被按体积选中 | 过滤 junk + 优先正文靠前图；手改 `assets/.../still-*.jpg` 后 repush |
| **横幅缩略图** | 160×90 等城市夜景/广告条体积仍 >25KB | 代码已加 **最小 320×240**；不符则手换 `still-03.jpg` 后 repush |
| **政策引用吞字** | `>` 行在 HTML 里变成 `&gt;`，微信当引用符吞行首；长文件全称 +「」更严重 | **不写总局文件全称**；用「广电21条」简称；短引语才用 `>`（代码已转真 `<blockquote>`） |
| **无图 + 模板正文** | DeepSeek 失败走 `_fallback_discussion_body`；`research_urls` 未写入缓存 | 默认 **拒绝推送**（`WECHAT_MP_DISCUSSION_REQUIRE_FIGURES=1`）；手改缓存 + `WECHAT_MP_DISCUSSION_FIGURES_FORCE=1` repush |

---

## 六、语气 / AI 味踩坑（改稿 grep 自检）

### 格式硬禁

- Markdown 加粗：正文禁止 `**……**`（公众号不渲染，草稿箱原样显示星号）→ 改用单句成段
- 分论点腔 / 分析报告腔：`与其说` · `不如说` · `对…来说` · `不等于` · `预期天然` · `叙事` · `调节奏` · `真正卡住的往往不是`
- 导读：`刷到这条热搜`、`第一反应`、`往下翻才知道` · `不是几句口水` · `今天我们来聊`

### 热榜播报腔禁止

`百度把…送上热搜` · `微博词条#…#也在转` · `热度破亿` · `吵上热搜` · `热搜前列` — 改成写观众在吵什么；榜单/词条最多一处自然带过，勿连读平台名+词条名

### 抬格调禁止

`这事闹这么大` · `也跟…大背景有关` · `闹成那样` — 选角争议、剧集吐槽别写成社会大案；用「吵了一架」「算不上大事但…」等收着写

### 结构套话禁止

`第一/二条线` · `一块…另一块` · `分成两块` · `不是A而是B` · `惹眼…其实是` · `吵得最凶` · `说到底` · `值得注意的是` · `二次发酵` · `写到这儿就够`

### 假口语禁止

`挺寒的` · `从别的口子` · `惹另一拨人起火` · `基本盘` · `落锤` · `条线上` · `掰扯一摞` · `这茬` · `拆不掉的账`

### 压缩怪句 / 弹幕缩写禁止

正文叙述用**完整人话**；弹幕、网友评论可保留引号内原话，叙述层禁止仿弹幕缩写。

| 禁止（叙述层） | 改用 |
|----------------|------|
| `进度飞` · `节奏飞` | 剧情推进得太快 / 节奏赶 |
| `眼里没光` · `班味儿` · `贴角色` | 写出具体观感（除非在引号内转述网友） |
| `演技能补` · `扮嫩` · `熟脸上阵` | 演技能不能把年龄差盖住 / 硬扮年轻 / 用熟脸演员换话题 |
| `添了乱` · `更碎` · `对不上` | 又惹出一摊吵 / 更难入戏 / 和角色年龄差太多 |
| `往上走` · `碰运气` · `分流火气` | 播放量一直在涨 / 碰运气（改完整句）/ 分担一部分骂声 |
| `赛道` · `魔改` · `劝退`（作动词） | 这类戏 / 改编离谱 / 一看就不想继续看 |

**句式**：禁止逗号串三字、四字短语当独立分句（`戏份砍了不少，进度飞，台词听不懂`）。一句只说一件事，下一句再换角度。

改稿 grep：`进度飞|眼里没光|班味儿|贴角色|演技能补|扮嫩|添了乱|更碎|对不上|往上走|分流点|熟脸上阵|魔改，|劝退，`

### 首段示范

- × 刷到这条热搜，第一反应是：又要吵。
- √ 上海朱女士，2006年结婚……2019年肺癌做完手术，丈夫却跟第三者拿假结婚证去医院做试管。

定稿后优先 **手改 `body_core` 缓存 + repush**，不要每次重跑 DeepSeek 全文。

### 生成 prompt 须与 §六 同步（Agent 改 SOP 时必查）

`_discussion_voice_prompt_block()` 须包含：热榜播报腔、抬格调、压缩怪句、**有人举/服化道/举例正反例**、社会民生排版（短段/物件立人/通报对照，见 `social-commentary-voice.md`）、字数 1700+。  
生成后须过 `scan_report_voice`（代码已门禁）；手改缓存 repush 前亦须 0 命中。

---

## 八、推荐流量选题（2026-08-02 复盘）

> 目标不只是微博有吵，而是**微信推荐池愿意推给路人**。牛马也智能主标签仍是财经/资讯，文娱讨论稿须过下面四关再推。

### 推稿前四关

| 关 | 问什么 | 过线示例 | 不过线示例 |
|----|--------|----------|------------|
| **路人** | 不追星的人看标题，能否秒懂发生啥 | 伪造结婚证做试管、暑期档70亿八仙 | 罗正跪谢、赞达亚耳环 |
| **站队** | 能否自然分两拨且愿留言 | 原配 vs 劝和；国产黑马 vs 好莱坞 | 明星卖惨真假（路人多反感） |
| **热度** | 微博「热/沸」或双榜，非仅「新」 | 胚胎案 weibo+baidu；明星哭穷 weibo热 | 赞达亚仅 weibo#8「新」 |
| **搜索** | 标题前15字含可搜实体（案由/片名/金额） | 伪造结婚证、八仙、70亿 | 艺人小名「罗正」 |

### 2026-08-02 实证

| 稿 | 推荐 | 原因摘要 |
|----|------|----------|
| 伪造结婚证/胚胎案 | 有 | 国民婚育+医院规则+具体故事+强站队 |
| 暑期档·八仙 | 有 | 大众片名+票房数据+选片讨论+档期内长尾 |
| 罗正哭穷 | 无 | 三线艺人+需识人+卖惨反感+偏离账号标签 |

### 选题加权（待落代码）

- 加分：双榜、`热/沸` 标签、标题含公共实体词、社会规则/公共数据角度
- 减分：仅微博「新」、标题强人名、纯明星八卦、无百度

---

## 九、推稿前检查清单（全勾才 repush / 才允许 11:00 推）

> 一篇稿出问题，多半是跳了其中某一步。Agent 改稿结束必须跑完本表并汇报结果。

### A. 选题与缓存

- [ ] **§八 四关**已过（路人 / 站队 / 双榜或热档 / 搜索实体）
- [ ] 缓存文件存在：`data/wechat_mp_tv_body_cache/{cover_slug}.json`
- [ ] 含 `content_mode: discussion`、`research_urls`（≥2 条同题报道）
- [ ] `topic_key` / `cover_slug` 与 repush 的 `--title-en` **一致**

### B. 正文

- [ ] **角色**：全文像「读者转述评论」，不像政策/产业分析（`brand.md` · `social-commentary-voice.md` §零）
- [ ] **通改**：用户只点名一句问题时，仍须 **通篇 grep**，禁止只改一处
- [ ] 运行：`uv run python -m scripts.tools.wechat_mp_report_voice --file data/wechat_mp_tv_body_cache/{cover_slug}.json` → 0 命中
- [ ] 无 `**` Markdown 加粗（grep `\\*\\*`）
- [ ] 首段：人+事，无导读（§六）
- [ ] grep 禁词无命中（§六 + `social-commentary-voice.md` 分析报告腔表）  
- [ ] 社会民生题：短段、物件立人、无震惊体连发  
- [ ] 对照金样 `spider_man_brand_new_day.body_core.md`：读出声像朋友转述

### C. 配图

- [ ] `assets/wechat_mp/inline-discussion/{cover_slug}/` 有 **still-01/02/03**
- [ ] 每张 **≥320×240**，且与正文事件相关（目检，非城市横幅/国旗/表情包）
- [ ] repush 后正文含 **3 处** `[[fig:discussion/...]]`

### D. 推送

```bash
cd stock-ai
WECHAT_MP_DISCUSSION_FIGURES_FORCE=1 \
  uv run python -m scripts.tools.wechat_mp_repush_tv_review_draft --title-en {cover_slug}
```

- [ ] 命令输出 `OK recreated media_id=...`
- [ ] 摘要无「百度热搜#N」式榜单播报
- [ ] 稿末含星标引导句（hotspot/tv_review 默认；见 [follow-growth-copy.md](../wechat-mp-growth-ops/follow-growth-copy.md) §3.5）

### E. 定时任务（待代码落地）

- [ ] `WECHAT_MP_DISCUSSION_PREFLIGHT=1`：无合格缓存则 **fail 不推**（当前已部分落地：无图/模板兜底会拒推）

---

## 七、故障

| 现象 | 处理 |
|------|------|
| AI 味仍重 | grep §六 禁词；对照蜘蛛侠金样改 `body_core` |
| 配图不对 | 加 `research_urls`（优先网易稿）+ `FIGURES_FORCE=1` |
| 仍走旧剧评五节 | `WECHAT_MP_TV_PICK_MODE=discussion` |

---

*确立：2026-08-02 · 修订：2026-08-03（§零根因+§九推稿清单+social-commentary 链）*
