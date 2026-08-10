# 内容分析 · 流量来源抓取 SOP

> **页面**：`https://mp.weixin.qq.com/misc/appmsganalysis?action=report&type=daily_v2&token=…&lang=zh_CN`  
> **代码**：`stock-ai/scripts/tools/fetch_wechat_mp_analytics_opencli.py` · `wechat_mp_analytics_page.py`  
> **OpenCLI**：[stock-opencli](../stock-opencli/SKILL.md)  
> **与搜一搜看板区别**：本页 = **已发文章各渠道阅读占比**；plugin 10071 = **搜索词 / 搜索后阅读**（[sousou-analytics-sop.md](sousou-analytics-sop.md)）

---

## 一、页面上看哪里

| 区块 | DOM | 控制什么 |
|------|-----|----------|
| **数据概况** | `.weui-desktop-tag`（昨日 / 最近 7 天 / 最近 30 天） | 顶部 **阅读 / 分享 / 留言** |
| **流量分析** | `.weui-desktop-picker__date-range` | 趋势图 + **流量来源柱图** |
| **流量来源柱图** | `.highcharts-container` | 各渠道 **占比 %**（**唯一抓取真源**） |

**Agent 必做（单日 / 逐日复盘）**：先把流量 picker 设为 **`YYYY-MM-DD` 至 同 day**，再读柱图。勿用页面默认范围（常为 **5/17–6/15**）。

---

## 二、口径陷阱（必读）

| 现象 | 错读 | 正读 |
|------|------|------|
| 点「昨日」概况读 76 | 柱图 推荐 7.3% = 昨日 | 7.3% 来自 **未改的 picker 累计** |
| picker = **6/15–6/15** | — | 推荐 **3.9%**，阅读总人数 **76** |
| API `begin=end=6/15` | 与柱图对齐 | **不对齐**（API 曾报 18.5%）；**禁止用 API** |
| 阅读总人数 2,097 | 等于概况 484 | 各渠道加总，同人多渠道重复计 |

**禁止**：用 API、或未改 picker 的柱图，写「某日推荐占比」。

---

## 三、抓取命令

```bash
cd stock-ai

# 单日 / 区间 → 读柱图（须先设 picker）
uv run python -m scripts.tools.fetch_wechat_mp_analytics_opencli \
  --token YOUR_TOKEN \
  --begin-date 2026-06-15 --end-date 2026-06-15 \
  -o output/wechat_mp_analytics_latest.json

# 逐日渠道（推荐 + 搜一搜 + 全渠道）
uv run python -m scripts.tools.fetch_wechat_mp_analytics_opencli \
  --token YOUR_TOKEN \
  --daily-series --series-begin 2026-06-02 --series-end 2026-06-16 \
  -o output/wechat_mp_recommend_daily_page.json
```

未登录：`--wait-login 120`。

**Picker 自动化**：`SET_FLOW_DATE_RANGE_JS` — 点「MM月」选月（头栏常无右箭头）→ 点非 `faded` 的日期 `<a>`。

---

## 四、输出 JSON

### 单次 `--begin-date / --end-date`

| 路径 | 内容 |
|------|------|
| `daily.traffic_sources_pct` | 柱图渠道占比 |
| `daily.traffic_meta.from` | `highcharts-container` |
| `daily.highcharts_traffic.paired` | 标签与 % 的 cx 对齐结果 |
| `daily.overview.read_users_total` | 流量块「阅读总人数」 |
| `daily.date_set_result.dates` | picker 实际值（校验是否设对） |

### `--daily-series`

| 路径 | 内容 |
|------|------|
| `days[].date` | 自然日 |
| `days[].traffic_sources_pct` | 全渠道（含 **搜一搜**、**推荐**） |
| `days[].推荐` | 快捷字段 |
| `days[].read_users_total` | 当日流量块阅读总人数 |
| `days[].picker_ok` | picker 是否等于 D–D |

---

## 五、牛马也智能 · 6/2–6/15 页面实测（2026-06-16）

> 真源：`output/wechat_mp_recommend_daily_page_20260602_20260616.json` · picker=单日

| 日期 | 阅读总人数 | 搜一搜 | 推荐 | 备注 |
|------|-----------|--------|------|------|
| 6/02 | 168 | — | — | 柱图未解析 |
| 6/03 | 733 | 15.6% | 2.7% | 聊天 49.9%，大读 burst |
| 6/04 | 253 | 31.6% | 8.7% | |
| 6/05 | 95 | **60.0%** | 2.1% | 限推窗口起点 |
| 6/06 | 168 | 13.7% | 29.8% | 推荐 spike（结构特殊） |
| 6/07 | 127 | 11.8% | 7.9% | 周日 |
| 6/08 | 63 | 49.2% | 23.8% | evening 三篇首日 |
| 6/09 | 80 | **60.0%** | 11.3% | |
| 6/10 | 79 | **63.3%** | 11.4% | 限推期内仍有存量推荐 |
| 6/11 | 52 | 28.8% | 5.8% | |
| 6/12 | 82 | 40.2% | 6.1% | 后台「不适合推荐」 |
| 6/13 | 82 | 12.2% | 6.1% | 聊天+朋友圈主导 |
| 6/14 | 33 | — | — | 周六单篇 |
| 6/15 | 76 | 30.3% | **3.9%** | 合规新标题；推荐仍偏低 |

**账号渠道结论**（结合 [growth-playbook](../wechat-mp-growth-ops/growth-playbook.md) §渠道底盘）：

- **主引擎**：搜一搜（多个交易日 **50%+**）
- **推荐流**：限推后 **3%–7%** 为主，未回到健康档；「不适合推荐」压 **增量** 非 **归零**
- **推送**：公众号消息长期 **~1%–8%**
- **恢复 KPI**：picker=单日 **推荐%** 从 ~4% 缓升；后台 **已发违规稿** 改标题

---

## 六、Agent 分析模板

```markdown
## 牛马也智能 · YYYY-MM-DD（页面 · picker=单日）

| 阅读总人数 | 搜一搜 | 推荐 | 朋友圈 | 聊天 |
（来自 highcharts）

### 与限推时间线
- 当日是否在 6/5–6/12 违规窗口
- 推荐% 低是「限推」还是「阅读基数小」

### 下一步（只调一类）
- 搜一搜：标题词 / news 热股名
- 推荐：后台改旧稿 + 新稿 audit
- 完读：流量主曝光
```

流量主入账：[analytics-sop.md](../wechat-mp-growth-ops/analytics-sop.md) §三。

---

## 七、勿做清单

- 用 **API** 或默认 picker 柱图写单日占比。
- 把 **plugin 搜一搜看板** 与本页「搜一搜渠道%」混为一谈。
- 从 SVG **固定顺序**配 %（会搞反渠道）。
- 认为限推后 **推荐必为 0%**。

---

## 修订

| 日期 | 说明 |
|------|------|
| 2026-06-16 | 初版 API + picker |
| 2026-06-16 | **改页面真源**；弃 API；`--daily-series`；6/2–6/15 实测表；限推×渠道解读 |
