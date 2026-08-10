# stock-ai 引流（牛马也智能 → home-hub 看板）

> 真源配置：`stock-ai/data/wechat_mp_growth_focus.json` → `stock_ai_cta`  
> 代码：`scripts/tools/wechat_mp_stock_ai_cta.py`

## 引流是什么

公众号 **不负责跑选股/情绪逻辑**（那是 `stock-ai` + MySQL + home-hub）。  
引流 = 让读者从 **微信阅读** → **打开你的工具看板** 继续对照。

**公网入口**：`https://hub.yoloworld.site:8883`（Caddy Basic Auth，需账号密码）

| 稿型 | 看板路径 | 读者得到什么 |
|------|----------|--------------|
| **news** | `/news` | 7×24 快讯流（路由 **meta.public**，可作「阅读原文」） |
| **dragons** | `/emotion` | 情绪周期、连板梯队（与 dragons 稿呼应） |
| **sector** | `/selection` | 选股池、行业样本 |
| **market** | `/advisor` | 投顾看板、持仓/盘面快照 |

## 已自动做的（`stock_ai_cta.enabled: true`）

1. **稿末一段** + hub 链接（news/dragons/sector 默认）  
2. **news「阅读原文」** → `https://hub.yoloworld.site:8883/news`（公开页）  
3. **18:20 通知** 会写「稿内已带看板链接」

关闭：`stock_ai_cta.enabled: false` 或 `WECHAT_MP_STOCK_AI_CTA=0`

## 你要做的（后台人工，一次性/季度）

见 [account-packaging.md](../wechat-mp-drafts/account-packaging.md)，建议加菜单：

| 菜单 | 类型 | 内容 |
|------|------|------|
| **工具看板** | 跳转网页 | `https://hub.yoloworld.site:8883/news`（或 `/advisor`） |
| **更新节奏** | 关键词 | 已有 `节奏` |
| **免责** | 关键词 | 已有 `免责` |

关键词 **`看板`**（可选新增）：

```text
工具看板（需登录）：
https://hub.yoloworld.site:8883/advisor
快讯公开页：
https://hub.yoloworld.site:8883/news
仅供个人学习，不构成投资建议。
```

## 怎么衡量引流有没有用

| 指标 | 怎么看 |
|------|--------|
| hub 登录次数 / `/news` 访问 | Caddy / home-hub 日志 |
| 公众号菜单点击 | mp 后台菜单分析 |
| 「阅读原文」点击 | 单篇内容分析（news） |

流量主收入 **不会** 因引流立刻涨；价值在 **工具使用与留存**。

## 与「只发 1 篇 news」的关系

`growth_focus.evening_mode`:

- `trilogy`（现在）：三篇 + 稿末链接 → 引流入口在 **头条 news**  
- `news_only`：只推 1 篇 news → 阅读更集中，**引流路径更短**（测 1～2 周可切换）

切换：改 JSON 里 `"evening_mode": "news_only"`，次日 18:20 生效。

## 合规

- 写清 **需登录、个人工具、非投顾**  
- 勿写「注册送福利」「必涨」  
- hub 看板勿暴露无鉴权的持仓明细到公开路由
