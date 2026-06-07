# 牛马也智能 — 公众号品牌（真源）

> **命名约定**：用户或 Agent 说 **「公众号」** = 本账号 **「牛马也智能」**（`WECHAT_MP_*` / `wechat-mp-drafts`）。  
> **不是** 带货号「简选小电」（`wechat-mp-commerce-drafts`，已搁置）。

---

## 定稿

| 项 | 内容 |
|----|------|
| **名称** | **牛马也智能** |
| **代码默认** | `wechat_mp_masthead.DEFAULT_ACCOUNT_NAME`；`.env` → `WECHAT_MP_ACCOUNT_NAME` |
| **定位** | **打工人视角的 A 股复盘 + 自选观察**；辅以 **工具工作区** 技术稿（自动化/数据管线） |
| **气质** | 会复盘、不喊单；研究员口吻；带一点自嘲「牛马」感，**不**震惊体、不荐股 |
| **对外技术品牌** | 正文用 **工具工作区**（`PROJECT_NAME`），勿用仓库目录名 `tools-workspace` |

## 与简选小电的边界

| | 牛马也智能（本 skill） | 简选小电（commerce skill） |
|--|------------------------|----------------------------|
| AppID | `WECHAT_MP_APPID` / `SECRET` | `WECHAT_MP_COMMERCE_*`（独立，用户已不做） |
| 顶栏 | `assets/wechat_mp/banner.png` 青框 FinTech | `commerce/banner.png` 暖色 |
| 槽位 | 定时：`sector`+`top5`+`dragons`；`all` 含 `workspace`；手动 `market`/`news`；`temp` | guide / review / trend |
| Agent 任务 | 说「公众号」「推草稿」「晚间三篇」→ **本 skill** | 仅用户明确「简选」「带货」时 |

## 槽位 slogan（顶栏，按 kind 轮换）

代码：`wechat_mp_masthead.KIND_SLOGANS`

| kind | slogan |
|------|--------|
| `sector` | 今天资金盯哪条链？先拆行业再盯票 |
| `market` | 牛马下班别躺平，先看一眼大盘魂 |
| `news` | 消息比外卖还快，筛十条够你吹 |
| `top5` | 五只备选不喊单，自选自负莫甩锅 |
| `dragons` | 龙头一时爽，退潮火葬场——先看情绪 |
| `workspace` | 代码和 K 线之间，还隔着一个 launchd |
| 默认 | 打工人的智能复盘手记 |

## 读者与内容边界

- **是谁**：上班族/自学投资者；手机读、跳读、先扫标题和小标题  
- **要什么**：盘面结构、行业热点、观察名单、情绪周期；**不要**直接买卖指令  
- **要写**：数字、机制、可跟踪指标；工具工作区能力 **读者向** 表述  
- **不写**：持仓执行卡原文、荐股、仓位、Clash/机场/substore、编排话术（临稿栏/五槽给 Agent 看的那套）

## 账号包装（公众平台后台）

**定稿文案与配置步骤** → [account-packaging.md](account-packaging.md)（介绍、头像、菜单、关注/关键词自动回复）。

### 功能介绍（≤120 字，与 packaging 同步）

```text
打工人视角的A股收盘复盘：行业产业链、情绪龙头梯队、自选观察名单；周日发周末要闻精选。附工具工作区自动化手记。仅供参考，不构成投资建议。
```

## 素材

| 文件 | 路径 |
|------|------|
| 顶栏 banner | `stock-ai/assets/wechat_mp/banner.png` |
| 正文插图池 | `stock-ai/assets/wechat_mp/inline/`（A 股/科技/交易屏） |
| 封面 | 留档 `stock-ai/assets/wechat_mp/COVER_THUMBS.md`：**top5** 财经亮屏、**dragons** 多屏亮行情（本地 `*-dual.jpg` 优先）；**sector** = `banner.png` |

## 相关文档

- 文档导航：[INDEX.md](INDEX.md) · 发布节奏：[operations-sop.md](operations-sop.md)  
- 定时批次：`stock-ai/docs/WECHAT_MP_SCHEDULING.md`  
- 晚间定稿三篇：[evening-trilogy-templates.md](evening-trilogy-templates.md)
