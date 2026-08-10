# 数据抓取 · 联合分析 SOP

## 一、抓什么

| 数据源 | URL 模式 | 用途 |
|--------|----------|------|
| 内容分析 | `misc/appmsganalysis?action=report&type=daily_v2&token=…` | **数据概况阅读**、**流量分析**来源占比（须指定日期） |
| 流量主概览 | `…/publisher/publisher_overview&token=…` | **累计、昨日 +X（权威入账）** |
| 流量主明细 | `…/publisher/publisher_report&pos=1&token=…` | 拉取/曝光/eCPM 趋势 |
| 搜一搜 | `pluginloginpage?pluginuin=10071` | 搜索词（需 Chrome tab bind） |

**Token**：从 `mp.weixin.qq.com/cgi-bin/home?…&token=XXXX` 取；过期则用户重新登录后提供。**勿提交 git**。

## 二、抓取命令

```bash
cd stock-ai
# 单日 / 区间柱图（须设 picker）
uv run python -m scripts.tools.fetch_wechat_mp_analytics_opencli \
  --token TOKEN \
  --begin-date 2026-06-15 --end-date 2026-06-15 \
  -o output/wechat_mp_analytics_latest.json

# 逐日推荐+搜一搜（页面 · --daily-series）
uv run python -m scripts.tools.fetch_wechat_mp_analytics_opencli \
  --token TOKEN \
  --daily-series --series-begin 2026-06-02 --series-end 2026-06-16 \
  -o output/wechat_mp_recommend_daily_page.json

# 搜一搜 plugin 看板（Chrome tab bind）
uv run python -m scripts.tools.fetch_wechat_mp_sousou_opencli
```

内容分析解读：[content-analytics-sop.md](../wechat-mp-drafts/content-analytics-sop.md) · OpenCLI：[stock-opencli](../stock-opencli/SKILL.md)

OpenCLI 联合脚本（Agent 可 inline Python）：见历史 `fetch_eastmoney_quotes._open_page` + `_eval_js`；输出 `output/wechat_mp_ops_latest.json` / `output/wechat_mp_publisher_latest.json`。

## 三、收入口径（必读）

| 字段 | 可信 | 说明 |
|------|------|------|
| 概览 **「昨日 +X」** | ✅ | **6/9 = +1.23、6/10 = +1.42** 以此为准 |
| 概览 **累计收入** | ✅ | 与累计差分应一致 |
| 明细表 **当日收入行** | ⚠️ | 常滞后；6/10 行 0 但概览 +1.42 |
| 明细 **关键数据区合计** | ⚠️ | 页内筛选周期，非累计 |

**禁止**：用明细行 0.27 否定概览 1.23。

## 四、联合分析模板

用户要「分析 X 月 X 日」时，Agent 输出：

```markdown
## 牛马也智能 · YYYY-MM-DD

### 核心指标
| 阅读 | 分享 | 概览入账 | 累计 | 明细曝光 |
（环比前日）

### 当日群发（draft_slots）
news / dragons / sector 标题

### 渠道
朋友圈 / 搜一搜 / 聊天 / 推送（**与 content-analytics 同一 begin/end**；概况阅读 ≠ 阅读总人数）

### 判断
- 阅读档：底盘 / 上一阶 / outlier
- 流量主：入账 vs 阅读是否同向
- 策略：是否只调一类

### 下一步（1–3 条）
```

## 五、benchmark（organic，排除 321）

| 日型 | 阅读 | 概览入账 |
|------|------|----------|
| evening 三篇 · 过渡 | 60–65 | ¥0.3–0.5 |
| evening 三篇 · 稳态 | **75–85** | **¥1.2–1.5** |
| 周日单篇 news | 100–130 | ¥0.8–1.2 |
| 大行情 + market | 100–150+ | ¥2+（偶发） |

## 六、周报复盘

写入 `stock-ai/output/wechat_mp_weekly/YYYY-WW.md`：

1. 5 日阅读均值、概览入账合计  
2. 搜一搜 Top 搜索词（若有）  
3. **本周只调一类** 的结论  
4. 下周是否安排 market  

搜一搜流程：[sousou-analytics-sop.md](../wechat-mp-drafts/sousou-analytics-sop.md)

## 七、渠道底盘（页面 · picker=单日 · 2026-06-16）

真源：`output/wechat_mp_recommend_daily_page_20260602_20260616.json` · 详见 [content-analytics-sop.md](../wechat-mp-drafts/content-analytics-sop.md) §五。

| 维度 | 现状 | 运营含义 |
|------|------|----------|
| **搜一搜** | 多个交易日 **30%–63%** | 主引擎；news 热股名标题有效 |
| **推荐** | 限推后多数 **3%–7%**；6/15 **3.9%** | 未恢复；勿用默认 picker 的 7.3% 当单日 |
| **限推** | 约 6/5–6/12「不适合推荐」 | 压 **新进推荐池**；存量推荐读仍可 >0 |
| **阅读** | 交易日 **76–82**（6/12–6/15） | 底盘稳；不靠推荐活着 |
| **恢复 KPI** | 推荐% 从 ~4% 缓升；后台改旧稿 | 1–2 周观察；代码只护新批 |

**Agent 复盘限推**：并列 **搜一搜% + 推荐%**（同 JSON），勿只报推荐。
