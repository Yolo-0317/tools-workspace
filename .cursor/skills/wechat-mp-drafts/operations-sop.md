# 牛马也智能 · 公众号运营 SOP

> **真源**：本账号日常发布节奏与人工步骤。  
> 文档导航 [INDEX.md](INDEX.md) · 品牌 [brand.md](brand.md) · 工程 [SKILL.md](SKILL.md) · 定时 `wechat_mp_draft_batch.SCHEDULE_BATCHES` · `stock-ai/docs/WECHAT_MP_SCHEDULING.md`

---

## 一、原则

| 原则 | 说明 |
|------|------|
| **主轴是热点评论** | 社会 / 文娱 / 职场 / 公共事件；A 股收盘三篇已停用，仅 **手动** 偶发财经稿 |
| 成稿质量先于定时 | 热点深评定时推草稿；质量门禁不过则飞书告警，禁止静默兜底 |
| **成稿 LLM** | 定时稿只用 Codex CLI；用户主动的热点深评与文学/典籍稿由 Agent 给完整提示词、用户自行向 DeepSeek 取稿并贴回；任一路线失败都禁止回退 |
| 机器推草稿、人发正文 | API 可 `upsert` 草稿；**原创分类、部分 #** 仍后台人工 |
| **看稿方式** | **只进 mp 草稿箱**预览；Agent **勿**写 `output/wechat_mp_*_preview.html`（用户明确要求） |
| 质量 > 篇数 | 每天 **3 篇**热点深评（11/15/18）；个人号发表仍须同批群发，勿错开发通知 |
| 读者可见文案 | 简介/关注回复/稿末引导写「能得到什么」；**不外露**争议优先、讨论度、双榜等内部策略 → [follow-growth-copy.md](../wechat-mp-growth-ops/follow-growth-copy.md) §二 |
| 不说「公众号」却推简选 | 简选已搁置；带货走 commerce skill 且需用户明示 |

---

## 二、自动节奏（scheduler）

| 时刻 | batch | 篇数 | kinds | 备注 |
|------|-------|------|-------|------|
| **每天 11:00** | `hotspot_morning` | 1 | `hotspot` | 热搜热点深评；`edition=pre`；槽 `hotspot_morning` |
| **每天 15:00** | `hotspot_afternoon` | 1 | `hotspot` | `edition=midday`；槽 `hotspot_afternoon` |
| **每天 18:00** | `hotspot_evening` | 1 | `hotspot` | `edition=close`；槽 `hotspot_evening` |

**手动**（不在定时）：`tv_trial` 话题讨论稿见 [tv-morning-discussion-sop.md](tv-morning-discussion-sop.md)。

**已停用**：旧 18:00 `evening`/`weekend` 财经批次、15:15 股吧 guba。详见 `stock-ai/docs/WECHAT_MP_SCHEDULING.md`。

**不在定时里**（手动 `wechat_mp_draft --kind …`）：

| kind | 建议频率 |
|------|----------|
| `market` / `sector` / `news` | **仅偶发**财经深评或重大行情日；非主轴 |
| `workspace` | 全周最多 1 篇（工具/工程手记） |
| `temp` | 临时单篇，显式 `--kind temp` |
| `literary` | 典籍节目与文学类；用户自行向 DeepSeek 取稿并贴回，独立槽位，必须两次确认 |

### DeepSeek 手工交接双确认

1. Agent 完成选题、三个来源域以上的事实包和提示词，先给用户确认。
2. 用户确认后自行把完整提示词交给 DeepSeek，并把完整输出贴回当前任务。Agent 不打开、控制、调用或检查 DeepSeek。
3. Agent 核事实、编辑、高亮并寻找公开来源配图，展示推送前报告。
4. 用户第二次确认后才允许调用微信草稿 API。

未收到用户贴回的 DeepSeek 输出时暂停，不调用 DeepSeek，不检查登录状态，也不回退其他模型代写。用户贴回后继续核实编辑，不重复消耗第一次确认，也不绕过第二次确认。

```bash
cd stock-ai
bash scripts/install-wechat-mp-launchd.sh
bash scripts/wechat_mp_hotspot_draft_scheduled.sh hotspot_morning --dry-run
bash scripts/wechat_mp_hotspot_draft_scheduled.sh hotspot_afternoon --dry-run
bash scripts/wechat_mp_hotspot_draft_scheduled.sh hotspot_evening --dry-run
```

成功批次 → `wechat_mp_draft_notify`（微信 wechat-acp + 飞书，见 `WECHAT_MP_NOTIFY*`）。

### 写稿 ≠ 发表时刻

| 动作 | 谁做 | 说明 |
|------|------|------|
| **11:00 / 15:00 / 18:00 scheduler** | host-jobs | 各 1 篇热点深评草稿；自动调用 Codex CLI，失败不推草稿 |
| **发表** | mp 后台人工 | 个人号每天仅 1 次通知；多篇须同批群发 |
| **跳过今日写稿** | skip 文件 | 热点三时段共用 `wechat_mp_skip_scheduled.date` |

### 工具/生活类频次

`workspace`、英语带读、工具种草等——**全周最多 1 篇**，与热点主轴错开，不占主要更新带宽。

---

## 二点五、账号包装（一次性 / 季度复核）

真源 [account-packaging.md](account-packaging.md)。配置后在本节打勾：

- [ ] 功能介绍、头像已按 packaging 更新（**无 A 股复盘 / 荐股**）  
- [ ] 自定义菜单 3 项（更新节奏 / 近期文章 / 免责说明）  
- [ ] 关注自动回复 + 关键词 `写作`、`节奏`、`免责`  
- [ ] 小号取关重关自检通过  

---

## 二点六、关注引流（真源与分工）

> 完整话术、A/B、禁忌 → [follow-growth-copy.md](../wechat-mp-growth-ops/follow-growth-copy.md)  
> 后台粘贴步骤 → [account-packaging.md](account-packaging.md)  
> 稿末代码 → `wechat_mp_monetization.append_follow_hook`（`hotspot` / `tv_review`）

### 三层分工（不要混在一处）

| 层级 | 放什么 | 真源 |
|------|--------|------|
| **简介 + 被关注回复** | 写什么、星标理由；顺带「回复写作领取笔记」 | account-packaging §一、§三 A |
| **关键词「写作」** | 夸克链接：AI 写作 + API 笔记（**不含选题**） | `stock-ai/docs/share/牛马也智能-AI写作与公众号API笔记.md` |
| **稿末 1～2 句** | 仅星标引导（禁止「回复写作领笔记」） | follow-growth-copy §3.5 · 代码默认 |

**定稿稿末句**（`WECHAT_MP_FOLLOW_HOOK_TEXT` 可覆盖）：

```text
我们会继续整理社会与文娱热点；星标本号，下一篇不易漏看。
```

### 禁止

- 读者可见文案写「有争议优先」「讨论度」「双榜」等内部策略（见 follow-growth-copy §二）  
- 稿末禁止「关注/回复关键词领资料」式诱导（微信审核）；写作笔记仅后台关键词，**不写进正文**  
- `tv_review` 稿末加财经号「复盘的朋友」推荐 ♡（已默认关）

### 配置后自检（与 §二点五 合并执行）

- [ ] 关注回复含「写作」入口，**无** A 股复盘口吻  
- [ ] 私信 `写作` → 夸克链可打开（`{{QUARK_WRITING_GUIDE_URL}}` 已填）  
- [ ] 新发 1 篇 hotspot / discussion → 稿末有星标句、无「回复写作」诱导  
- [ ] 单篇「阅读后关注」有记录（内容分析）

### 衡量（每周一看一眼）

| 指标 | 哪里看 |
|------|--------|
| 阅读后关注 | 单篇内容分析 |
| 新增关注时段 | 发文后 2–6h 是否抬升 |
| 完读率 | 引流句加了若掉 &gt;3pt → 改短 |

---

## 三、发布日人工清单（每篇）

**审草稿（mp.weixin.qq.com）**

- [ ] 顶栏 **牛马也智能** + slogan 正常  
- [ ] 热点/讨论稿：**纯段落**，无「一、二、三」小标题（sector 等旧稿除外）  
- [ ] 插图位置、单处免责；社会稿有多方观点  
- [ ] `wechat_mp_eval` 无合规红线；AI 味可接受；社会民生对照 [social-commentary-voice.md](../wechat-mp-writing/social-commentary-voice.md)  

**点发布时**

- [ ] **原创**（能勾则勾）  
- [ ] 分类：**社会 / 娱乐 / 资讯**（按稿型最接近项）；**勿默认勾财经**（偶发财经单篇可单独选财经）  
- [ ] 终端/文末 **#话题**：热点稿优先 **实体词**（案由、片名、事件名），非 `#A股` 打头（见 [sousou-analytics-sop.md](sousou-analytics-sop.md)）  
- [ ] 可选：文末星标引导句；回复留言（`tv_review` 可弱化推荐 ♡）  

**发后 24h**

- [ ] 回复高价值留言  
- [ ] 记阅读来源（**推荐 / 搜一搜**）、完读、阅读后关注  

### 短剧推广门禁

普通公众号长文不自动插入 `short-play` 短剧返佣组件。只有用户明确要求制作 `short_drama_feature` 单剧推广稿时，才允许按以下流程手动使用：

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_short_drama --refresh --limit 40
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_short_drama --capture-sample-title "短剧组件测试-勿发"
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_short_drama --probe-component --drama-id 660409
```

- 自动归因使用公众号编辑器的 `minidrama?action=link` 建链接口。先创建本地忽略文件并收紧权限：

```bash
cd stock-ai
install -m 600 /dev/null data/wechat_mp_drama_web_session.json
chmod 600 data/wechat_mp_drama_web_session.json
```

文件是 JSON 对象，只填写从当前 Network 请求读取的 `cookie`、`token`、`fingerprint` 和可选 `lang`；不得把真实值写进命令、文档、测试或 Git。`.env` 仅保存文件路径：

```text
WECHAT_MP_DRAMA_WEB_SESSION_FILE=data/wechat_mp_drama_web_session.json
```

- 收益模型选出短剧后，程序优先复用仍匹配的本地归因；缺失或计划变更时自动请求该剧专属路径并原子更新归因缓存。
- 单独验证某部短剧的自动归因：`PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_short_drama --fetch-attribution --drama-id 1724744`。输出只能包含短剧 ID、计划 ID 和是否含票据。
- 会话过期、权限不是 `0600`、响应 ID/AppID 不匹配或缺少票据时必须停止推稿。重新登录后台并更新本地会话文件后再试。
- 若草稿 API 看不到后台编辑器草稿：在 DevTools Elements 搜索 `data-adtype="short-play"`，复制该标签 outerHTML 到忽略目录 `data/wechat_mp_short_drama_sample.html`，再运行 `PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_short_drama --capture-sample-file data/wechat_mp_short_drama_sample.html`。
- 后台预览探针草稿，确认卡片剧目、点击跳转和结算归因都正确。
- 人工确认前保持 `WECHAT_MP_SHORT_DRAMA=0`；确认后才在本地 `.env` 开启。
- 归因、候选、缓存或草稿回读任一失败都停止推稿，不得改回 `WECHAT_MP_FOOTER_PRODUCT=1`。
- 不得用候选池的 `exp_url` 或 `click_url` 冒充归因路径，也不得跨短剧复用票据。
- `short_drama_feature` 必须恰有一个 `data-adtype="short-play"`；其他普通长文必须为零，且不得含普通 `data-pid` 商品卡或 footer product key。

---

## 四、每周维护（运营者）

| 项 | 动作 |
|----|------|
| **运营周报** | 周一落盘 `stock-ai/output/wechat_mp_weekly/YYYY-MM-DD.md`（搜一搜 7 天 + 只调一类） |
| **搜一搜看板** | 周一 15min：[sousou-analytics-sop.md](sousou-analytics-sop.md)；内容分析：[stock-opencli](../stock-opencli/SKILL.md) |
| 白名单 IP | `uv run python -m scripts.tools.wechat_mp_check_whitelist` |
| 质量抽检 | 热点稿 `wechat_mp_eval --kind hotspot --traffic`；讨论稿对照 tv-morning §九 |
| 11:00 链路 | 抽查：合格缓存是否存在、配图、禁词 grep（勿假设定时任务用手改稿） |
| 选题 | 手动篇是否补缺；**勿**恢复 evening 三篇定时 |
| 变现 | 普通公众号长文不插短剧返佣；`short_drama_feature` 仅在用户明确要求时手动使用；普通 CPS 仅限独立 `commerce` |

---

## 五、Agent 任务路由

见 [INDEX.md](INDEX.md)「按任务选读顺序」。

---

## 六、修订

| 日期 | 说明 |
|------|------|
| 2026-08-16 | 长文推广改为短剧池；增加归因探针、写入前门禁和草稿回读，普通 CPS 仅限 commerce |
| 2026-08-03 | **定时改为 11/15/18 各 1 篇热点深评**（`hotspot_morning` / `afternoon` / `evening`）；`tv_trial` 移出手动 |
| 2026-08-03 | §二点六 关注引流三层分工 + 自检/衡量 |
| 2026-08-03 | **转型热点评论**：主轴 11:00 讨论 + 15:00 hotspot；停用 evening 三篇；发布分类与 SEO 口径 |
| 2026-06-08 | **一天一次通知**：多篇同批群发，禁止错开发表 |
| 2026-06-07 | 非财经全周≤1；周报目录 `output/wechat_mp_weekly/` |
| 2026-06-04 | 写稿/发表分离、skip 文件；初版 |
