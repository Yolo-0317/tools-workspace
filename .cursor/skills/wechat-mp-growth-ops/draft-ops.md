# 写稿 · 推草稿（增长导向）

> 文案金标准仍读 [evening-trilogy-templates.md](../wechat-mp-drafts/evening-trilogy-templates.md)。本节管 **何时写、写什么、怎么质检、怎么发**。

## 一、发表模型

| 时刻 | 动作 | 谁 |
|------|------|-----|
| **18:20** | `evening` / `weekend` 更新草稿 | launchd |
| **收盘后～晚间** | 人工 mp 后台 **1 次群发** | 用户 |
| 内容顺序 | `news` → `dragons` → `sector` | 同批 |
| 封面顺序 | 槽 1 牛马 → 2 多屏 → 3 财经 | 与正文 kind 解耦 |

跳过自动写稿：`echo YYYY-MM-DD > stock-ai/data/wechat_mp_skip_scheduled.date`

## 二、写稿前预检（Agent 必做）

```bash
cd stock-ai
# 1. 今天发什么
bash scripts/wechat_mp_draft_scheduled.sh --dry-run

# 2. eod / 数据（dragons 依赖）
# 若 scheduled 报错或 dragons 空榜 → 先修 stock-ai 数据，不硬推

# 3. 是否跳过大行情 market（见 growth-playbook 大行情 ≥2 条）
# 若要 market：先 evening 再 --kind market --edition close
```

## 三、推 evening 草稿

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_draft_batch --batch evening
# 校验结构（不覆盖已审稿时可 --dry-run 只看 notify）
```

**批次 env（脚本已设）**：`WECHAT_MP_HOT_STOCK_NEWS=1` · 快讯窗 36h · kinds = news, dragons, sector。

### 各篇增长要点

| kind | 槽位 | 标题 | 正文 |
|------|------|------|------|
| **news** | 头条 | 热股前置问句（单/双股分模板）；**禁**榜位「背景下」 | 10 条内；开篇 2 句「今日主线一句」 |
| **hotspot** | 次条 | `热点深评｜{具体事实}？` 如「市值前十红了9家，建行、工行创新高？」 | 纯段落长文；联网参考仿写；禁小标题 |

手动仍可用 `dragons` / `sector` / `market`（见下节）；定时 evening 默认 **hotspot 单篇**（`growth_focus.evening_mode=hotspot_only`）。

### hotspot 写稿（2026-07-30 定稿）

**Skill 真源**：[wechat-mp-writing/hotspot-deep-review.md](../wechat-mp-writing/hotspot-deep-review.md)

- **取材**：东财搜索同题报道（`wechat_mp_hotspot_research.py`），过滤跑题摘句
- **成稿**：LLM 读【参考文章·仿写】→ 二次仿写删 AI 套话
- **禁句**：`公开报道里有一条值得先记住`、`盘面一句`、`和A股啥关系`（标题）
- **排版**：每段 ≤130 字；指数涨跌全文 1 次
- **推稿**：`WECHAT_MP_HOTSPOT_TREND_ENRICH=0` 避免 OpenCLI 卡住

### hotspot 选题（来源）

- **来源**：微博热搜 + 百度热搜（`WECHAT_MP_HOTSPOT_SOURCE=trends`，默认）
- **预览**：`uv run python -m scripts.tools.wechat_mp_hot_trends --limit 10`
- **回退**：`WECHAT_MP_HOTSPOT_SOURCE=news` 或热搜抓取失败时回退快讯库
- **批次**：`evening_mode=hotspot_only` → 交易日只推 1 篇 hotspot（不再同批 news）
- **封面**：hotspot_only 时用 **牛马主图**（`banner.png` / sector 槽），非多屏

### 标题反例 / 正例（推稿必扫）

| 避免 | 推荐 |
|------|------|
| A股必读？（无股名） | 收盘值得看中际旭创？10条快讯拆开 |
| `…人气榜首背景下，中际旭创与太极…` | 禁 `背景下`；股名只出现一次 |
| `…内塔和A股有关系吗？` | `热点深评｜中东局势再升温，A股该关注啥？` |
| `升温A股该关注啥`（粘连） | `升温，A股该关注啥？` |
| 与同批另一篇标题雷同 | `wechat_mp_eval` / `_titles_too_similar` |

完整硬禁表：[wechat-mp-writing/sousou-content-rules.md](../wechat-mp-writing/sousou-content-rules.md) §标题硬禁。

## 四、手动槽（增长用途）

| kind | 频率 | 命令 |
|------|------|------|
| **market** | 大行情 0–1/周 | `uv run python -m scripts.tools.wechat_mp_draft --kind market --edition close` |
| **top5** | 手动、非定时 | `--kind top5` |
| **workspace** | ≤1/周 | `--kind workspace` |
| 时刻 | batch | 内容 | 状态 |
|------|-------|------|------|
| **11:00** | `tv_trial` | 影视热搜 → `tv_review` 草稿 + 飞书 | 自动 |
| **15:00 交易日** | `hotspot_afternoon` | 股市热搜 → `hotspot` 草稿 + 飞书 | 自动 |
| ~~18:00 evening~~ | — | news+hotspot | **已停用** |
| ~~15:15 guba~~ | — | 股吧飞书 | **已停用** |

**market 与 evening 同批**：用户后台勾选 4 篇一次发送；**禁止**第二次通知。

## 五、推稿质检（路线 A：batch 内自动门禁）

**evening 推稿前** `wechat_mp_draft_batch` 已自动跑 `wechat_mp_push_quality_gate`（默认开启）。未过则 **不 upsert**（`WECHAT_MP_QUALITY_GATE_STRICT=1`）。

```bash
cd stock-ai
# 推稿前单独验（与 batch 同门槛）
uv run python -m scripts.tools.wechat_mp_push_quality_gate --batch evening

# 单篇细查 + traffic
uv run python -m scripts.tools.wechat_mp_eval --kind news --traffic
uv run python -m scripts.tools.wechat_mp_eval --kind hotspot --traffic
# 手动槽另评：dragons / sector / market
```

**Agent 推稿后标题门禁（口头，10 秒）**：同一股名是否只出现一次？有无 `背景下` / 半截人名 / `升温A股` 粘连？不过 → 改标题或 `--kind` 重推，勿让用户直接发。

| 门槛 | 建议 |
|------|------|
| 总分 ≥75、AI 味 ≤20 | 可进草稿箱（门禁默认） |
| traffic 清单红灯 | 改标题/开篇；默认不阻断，设 `WECHAT_MP_QUALITY_TRAFFIC_BLOCK=1` 可硬拦 |
| **news 10 条去重** | 摘要/AI 点评不得 ≥3 条完全相同；见 [templates.md §news 去重](../wechat-mp-drafts/templates.md) |
| 合规红线 | 禁止发（`*ST` 标题复用等见 project-memory） |

改稿流程见 [wechat-mp-writing/revision-workflow.md](../wechat-mp-writing/revision-workflow.md)。

## 六、人工发表清单（每发布日）

> 起号必勾项详解：[cold-start-playbook.md](cold-start-playbook.md) §四

1. mp 草稿箱预览三篇顺序与封面  
2. **原创** + **允许推荐** + **合集**（固定三合集，≤5）+ `#` 与 `wechat_mp_seo_topics.md` 一致  
3. 标题无合规触发词（`sanitize_public_title` 对照）  
4. **一次**群发  
5. 记录发表标题 → 次日 analytics-sop 对阅读（picker=单日）  
6. slots 真源：`data/wechat_mp_draft_slots.json`

## 七、LLM

```bash
# stock-ai/.env
LLM_BACKEND=cursor
SOP_LLM_BACKEND=deepseek   # 仅东财 SOP 并发，勿改 cursor 写稿
```

## 八、故障

| 现象 | 动作 |
|------|------|
| 微信 ret=-2 | wechat-acp 发一条刷新 token |
| 封面错 | `COVER_THUMBS.md` · `cover_kind_for_content` |
| 行业题成「资金流」 | sector-discovery |
| 11:00 / 15:00 未跑 | `logs/host-job-wechat-mp-*.log` · skip 文件日期 · host-jobs health |

工程细节：[wechat-mp-drafts/reference.md](../wechat-mp-drafts/reference.md)

## 九、增长模型 CLI

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_growth_check
```

配置 `data/wechat_mp_growth_focus.json` · 批次 notify 自动附增长清单。
