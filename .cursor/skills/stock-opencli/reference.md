# stock-opencli · 参考

## OpenCLI CLI 速查

```bash
export PATH="$HOME/.nvm/versions/node/v24.14.1/bin:$PATH"

opencli --version
opencli browser state
opencli browser open 'https://example.com'
opencli browser wait time 3
opencli browser eval 'JSON.stringify(document.title)'
opencli browser click <ref>    # 优先用 eval 点击，ref 易变
opencli browser close
opencli daemon stop            # 卡住时配合 cleanup 脚本
```

脚本内统一走 `fetch_eastmoney_quotes._run_opencli`，已处理 **NO_PROXY** 与 **PATH**。

---

## 公众号后台 URL 模板

替换 `YOUR_TOKEN`（勿提交 git）：

| 页面 | URL |
|------|-----|
| 首页 | `https://mp.weixin.qq.com/cgi-bin/home?t=home/index&token=YOUR_TOKEN&lang=zh_CN` |
| **内容分析 daily** | `https://mp.weixin.qq.com/misc/appmsganalysis?action=report&type=daily_v2&token=YOUR_TOKEN&lang=zh_CN` |
| 用户分析 | `https://mp.weixin.qq.com/misc/useranalysis?&token=YOUR_TOKEN&lang=zh_CN` |
| 微信搜一搜插件入口 | `https://mp.weixin.qq.com/misc/pluginloginpage?pluginuin=10071&token=YOUR_TOKEN&lang=zh_CN` |

### 抓取内容分析

真源模块：`wechat_mp_analytics_page.py`（`SET_FLOW_DATE_RANGE_JS` · `EXTRACT_HIGHCHARTS_TRAFFIC_JS`）。**不用 API**。

**解读**：[content-analytics-sop.md](../wechat-mp-drafts/content-analytics-sop.md)

```bash
cd stock-ai
# 单日柱图（picker 设为 D–D）
uv run python -m scripts.tools.fetch_wechat_mp_analytics_opencli \
  --token YOUR_TOKEN \
  --begin-date 2026-06-15 --end-date 2026-06-15 \
  -o output/wechat_mp_analytics_latest.json

# 逐日全渠道（推荐 + 搜一搜 + …）
uv run python -m scripts.tools.fetch_wechat_mp_analytics_opencli \
  --token YOUR_TOKEN \
  --daily-series --series-begin 2026-06-02 --series-end 2026-06-16 \
  -o output/wechat_mp_recommend_daily_page.json
```

| CLI | 说明 |
|-----|------|
| `--begin-date` / `--end-date` | 设流量 picker；**单日复盘须 begin=end** |
| `--daily-series` | 循环 D–D，输出 `days[]` |
| `--series-begin` / `--series-end` | 配合 `--daily-series` |
| `--period` | 仅点数据概况 tag（**不改**流量 picker） |
| `--detail-top N` | 单篇详情页渠道 |

输出字段（2026-06，**页面**）：

- `daily.traffic_sources_pct` / `days[].traffic_sources_pct` — **highcharts 柱图**
- `daily.traffic_meta.from` — `highcharts-container`
- `daily.overview.read_users_total` / `days[].read_users_total` — 流量块阅读总人数
- `daily.date_set_result.dates` — 校验 picker 是否设对

**勿混**：概况 tag 阅读 ≠ picker 柱图占比；**勿用 API** 对照柱图。

### 搜一搜看板（bind 复用已有 tab）

**不要**对看板 URL 用 `browser default open`（易「遇到问题」）。在 Chrome 已打开：

`https://mp.weixin.qq.com/misc/pluginloginpage?pluginuin=10071&token=YOUR_TOKEN&lang=zh_CN`

且 tab 为**前台**时：

```bash
cd stock-ai
uv run python -m scripts.tools.fetch_wechat_mp_sousou_opencli \
  --expect-url-substr 'pluginuin=10071' \
  -o output/wechat_mp_sousou_latest.json
```

或纯 CLI：

```bash
opencli browser mp bind
opencli browser mp eval 'JSON.stringify({url:location.href, t:(document.body.innerText||"").slice(0,500)})'
opencli browser mp unbind
```

解读流程：[sousou-analytics-sop.md](../wechat-mp-drafts/sousou-analytics-sop.md)。

---

## 东财常用 CLI（`fetch_eastmoney_quotes` 模块 main）

```bash
cd stock-ai
uv run python -m scripts.tools.fetch_eastmoney_quotes 600995
uv run python -m scripts.tools.fetch_eastmoney_quotes 600995 000001 --sop
```

编程调用见 [SKILL.md](SKILL.md) 场景表。

---

## 清理

```bash
bash stock-ai/scripts/opencli_browser_cleanup.sh
bash stock-ai/scripts/opencli_browser_cleanup.sh --stop-daemon
```

Python：`force_close_opencli_browser()` from `fetch_eastmoney_quotes`。

---

## 写新 `*_opencli.py` 检查清单

- [ ] `ensure_repo_root_on_path()` 后 import `_open_page` / `_eval_js`
- [ ] 页面 `innerText` / 选择器变更时只改 `EXTRACT_*_JS`
- [ ] `finally` 里 `close_browser` 或调用方统一 cleanup
- [ ] 登录页检测（`请重新登录`）
- [ ] 更新 [SKILL.md](SKILL.md) 场景路由表
