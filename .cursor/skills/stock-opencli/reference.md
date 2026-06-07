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

```bash
cd stock-ai
uv run python -m scripts.tools.fetch_wechat_mp_analytics_opencli \
  --analytics-url 'https://mp.weixin.qq.com/misc/appmsganalysis?action=report&type=daily_v2&token=YOUR_TOKEN&lang=zh_CN' \
  --token YOUR_TOKEN \
  --detail-top 3 \
  --wait-login 0 \
  -o output/wechat_mp_analytics_latest.json
```

输出字段见脚本内 `EXTRACT_DAILY_JS` / `EXTRACT_DETAIL_JS`：

- `daily.traffic_sources_pct` — 含 **搜一搜** 占比
- `daily.articles[]` — `title`, `read_users`, `read_share_pct`
- `article_details[]` — `finish_read_rate`, `follow_after_read`, 单篇渠道

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
