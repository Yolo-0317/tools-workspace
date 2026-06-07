# 牛马也智能 · 公众号运营 SOP

> **真源**：本账号日常发布节奏与人工步骤。  
> 文档导航 [INDEX.md](INDEX.md) · 品牌 [brand.md](brand.md) · 工程 [SKILL.md](SKILL.md) · 定时 `wechat_mp_draft_batch.SCHEDULE_BATCHES` · `stock-ai/docs/WECHAT_MP_SCHEDULING.md`

---

## 一、原则

| 原则 | 说明 |
|------|------|
| 数据先于成稿 | 选股、快讯、情绪周期 `eod` 失败则先修数据，不硬推空稿 |
| **成稿 LLM** | `LLM_BACKEND=cursor`（`agent login`）；东财 SOP 并发终审固定 `SOP_LLM_BACKEND=deepseek` |
| 机器推草稿、人发正文 | API 可 `upsert` 草稿；**原创、部分 #** 仍后台人工 |
| 晚间三篇是主轴 | 交易日 `sector` + `dragons` + `top5` 对齐 [evening-trilogy-templates.md](evening-trilogy-templates.md) |
| **看稿方式** | **只进 mp 草稿箱**预览；Agent **勿**写 `output/wechat_mp_*_preview.html`（用户明确要求） |
| 质量 > 篇数 | 工作日发布 **2～3 篇** 为宜；过多篇推荐衰减（见 writing-guide） |
| 不说「公众号」却推简选 | 简选已搁置；带货走 commerce skill 且需用户明示 |

---

## 二、自动节奏（launchd 每日 18:20）

| 日历 | batch | 篇数 | kinds | 备注 |
|------|-------|------|-------|------|
| **A 股交易日** | `evening` | 3 | `sector` + `dragons` + `top5` | `edition=close`；龙头 `eod` |
| **周日/法定节假日休市** | `weekend` | 1 | `news` | **不装快讯定时 sync**；18:20 时 OpenCLI 拉 48h 快讯 + 热股 Top10 逐股匹配 |
| **周六休市** | — | 0 | — | 不自动推（`weekend_skip`） |

**不在定时里**（手动 `wechat_mp_draft --kind …`）：

| kind | 建议频率 |
|------|----------|
| `market` | 交易日有需要时手动（盘前/午间/收盘） |
| `news` | 周 2～3 或重大新闻日 |
| `workspace` | **全周最多 1 篇**（工具/工程手记；与英语带读、生活类等非财经合计） |
| `temp` | 临时单篇，显式 `--kind temp` |

```bash
cd stock-ai
bash scripts/install-wechat-mp-launchd.sh
bash scripts/wechat_mp_draft_scheduled.sh --dry-run
# 日志 logs/launchd-wechat-mp-draft-scheduled.{out,err}.log
```

成功批次 → `wechat_mp_draft_notify`（微信 wechat-acp + 飞书，见 `WECHAT_MP_NOTIFY*`）。

### 写稿 19:00 ≠ 发表 19:00

| 动作 | 谁做 | 说明 |
|------|------|------|
| **18:20 launchd** | Mac 脚本 | 生成/更新**草稿**；`LLM_BACKEND=cursor` |
| **定时发表** | mp 后台人工 | 建议 **18:30 / 18:40 / 18:50** 三篇错开；与 launchd 独立 |
| **跳过今日写稿** | `data/wechat_mp_skip_scheduled.date` | 内容为 `YYYY-MM-DD`；不卸 launchd |

草稿已定稿、只后台发表时：写 skip 文件，避免 18:20 覆盖已审内容。

### 非财经频次（2026-06-07 定）

`workspace`、英语带读、飞书/工具种草、生活类——**任意组合，全周最多 1 篇**。  
财经主轴仍是交易日 `evening` 三篇 + 周日 `news`；非财经不占搜一搜选题带宽。

---

## 二点五、账号包装（一次性 / 季度复核）

真源 [account-packaging.md](account-packaging.md)。配置后在本节打勾：

- [ ] 功能介绍、头像已按 packaging 更新  
- [ ] 自定义菜单 3 项（更新节奏 / 近期文章 / 免责说明）  
- [ ] 关注自动回复 + 关键词 `节奏`、`免责`  
- [ ] 小号取关重关自检通过  

---

## 三、发布日人工清单（每篇）

**审草稿（mp.weixin.qq.com）**

- [ ] 顶栏 **牛马也智能** + slogan 正常  
- [ ] 分节标题居中、无「一、二、三」序号  
- [ ] 彩色开篇、插图位置、单处免责  
- [ ] `wechat_mp_eval` 无合规红线；AI 味可接受  

**点发布时**

- [ ] **原创**（能勾则勾）  
- [ ] 终端/文末 **#话题** 与 `stock-ai/docs/wechat_mp_seo_topics.md` 一致  
- [ ] 行情稿分类勿选生活/家居；技术稿用工程免责  
- [ ] 可选：文末引导「推荐 ♡」、回复留言  

**发后 24h**

- [ ] 回复高价值留言  
- [ ] 记阅读来源（推荐 / 搜一搜）、完读  

---

## 四、每周维护（运营者）

| 项 | 动作 |
|----|------|
| **运营周报** | 周一落盘 `stock-ai/output/wechat_mp_weekly/YYYY-MM-DD.md`（搜一搜 7 天 + 只调一类） |
| **搜一搜看板** | 周一 15min：[sousou-analytics-sop.md](sousou-analytics-sop.md)；内容分析抓取：[stock-opencli](../stock-opencli/SKILL.md) |
| 白名单 IP | `uv run python -m scripts.tools.wechat_mp_check_whitelist` |
| 质量抽检 | `uv run python -m scripts.tools.wechat_mp_eval --kind all` 或改稿后单 kind |
| 数据 | 快讯 `sync_macro_news`、选股、情绪 `sync_emotion_cycle` 日志无长期失败 |
| 选题 | 手动篇：`market` / `news` / `workspace` 是否补缺 |
| 变现 | 流量主完读；CPS 仅 `WECHAT_MP_FOOTER_PRODUCT=1` 且品类与正文一致 |

---

## 五、Agent 任务路由

见 [INDEX.md](INDEX.md)「按任务选读顺序」。

---

## 六、修订

| 日期 | 说明 |
|------|------|
| 2026-06-07 | 18:20 定时；非财经全周≤1；周报目录 `output/wechat_mp_weekly/` |
| 2026-06-04 | 写稿/发表分离、skip 文件、发表错开；导航迁至 INDEX |
| 2026-06-04 | 初版；「公众号」= 牛马也智能 |
