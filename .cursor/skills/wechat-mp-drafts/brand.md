# 牛马也智能 — 公众号品牌（真源）

> **命名约定**：用户或 Agent 说 **「公众号」** = 本账号 **「牛马也智能」**（`WECHAT_MP_*` / `wechat-mp-drafts`）。  
> **不是** 带货号「简选小电」（`wechat-mp-commerce-drafts`，已搁置）。

---

## 定稿

| 项 | 内容 |
|----|------|
| **名称** | **牛马也智能** |
| **代码默认** | `wechat_mp_masthead.DEFAULT_ACCOUNT_NAME`；`.env` → `WECHAT_MP_ACCOUNT_NAME` |
| **定位** | **热点评论**：社会、文娱、职场与公共事件；有话题、有讨论度就写 |
| **气质** | 像转述公开报道的朋友聊天：有事实、有立场呈现、不震惊体、不喊单 |
| **写手角色** | **读者转述者**（群里聊热搜），不是分析师/政策稿/产业报告 → [social-commentary-voice.md](../wechat-mp-writing/social-commentary-voice.md) §零 |
| **改稿** | 用户指出一处问题 → **通篇 grep 禁词**，禁止只改一句 |
| **主稿型** | `hotspot`（11/15/18 热点深评）· `tv_review` / `discussion`（手动话题讨论） |
| **已淡化** | A 股收盘三篇（sector / dragons / top5）、清单型快讯、荐股观察 |

## 与简选小电的边界

| | 牛马也智能（本 skill） | 简选小电（commerce skill） |
|--|------------------------|----------------------------|
| AppID | `WECHAT_MP_APPID` / `SECRET` | `WECHAT_MP_COMMERCE_*`（独立，用户已不做） |
| 顶栏 | `assets/wechat_mp/banner.png` | `commerce/banner.png` |
| 定时主槽 | `tv_trial`（话题讨论）· `hotspot_afternoon` | guide / review / trend |
| Agent 任务 | 「公众号」「热点」「话题讨论」「推草稿」→ **本 skill** | 仅用户明确「简选」「带货」 |

## 槽位 slogan（顶栏，按 kind 轮换）

代码：`wechat_mp_masthead.KIND_SLOGANS`（财经 kind 仍保留兼容，新稿优先 hotspot / tv_review）

| kind | slogan |
|------|--------|
| `hotspot` | 热点在吵什么？先把事实摆桌上 |
| `tv_review` / discussion | 有话题就聊，不争输赢争清楚 |
| 默认 | 热点观察手记 |

## 读者与内容边界

- **是谁**：刷推荐流 / 搜一搜进来的路人；不一定关心股市  
- **要什么**：弄清「大家在吵什么」、多方观点、可核对的事实  
- **要写**：公开报道可核实信息；社会争议呈现多方，不替司法下定论  
- **不写**：荐股、买卖暗示、持仓卡、稿末硬塞「关注领资料」、财经清单复读（除非单篇财经深评）
- **可提供**：回复「写作」发放 `stock-ai/docs/share/牛马也智能-AI写作与公众号API笔记.md`（夸克；含 AI 技巧 + API，**不含选题**）

## 增长与引流

- **主引擎**：微信 **推荐流**（热点稿验证有效）+ 完读  
- **关注转化**：简介 + 被关注回复 + 稿末 1 句星标引导 → [follow-growth-copy.md](../wechat-mp-growth-ops/follow-growth-copy.md)  
- **搜一搜**：标题含可搜实体（案由、片名、金额、事件名），非 `#A股` 打头  

## 账号包装（公众平台后台）

**定稿文案与配置步骤** → [account-packaging.md](account-packaging.md)（介绍、菜单、自动回复）。

### 功能介绍（≤120 字，与 packaging 同步）

```text
热点观察：社会、文娱、职场与公共事件，有话题就写。整理公开信息与多方观点，供阅读与讨论。
```

## 素材

| 文件 | 路径 |
|------|------|
| 顶栏 banner | `stock-ai/assets/wechat_mp/banner.png` |
| 话题讨论配图 | `stock-ai/assets/wechat_mp/inline-discussion/` |
| 热点 / 通用插图 | `stock-ai/assets/wechat_mp/inline/` |

## 相关文档

- 文档导航：[INDEX.md](INDEX.md) · 发布节奏：`stock-ai/docs/WECHAT_MP_SCHEDULING.md`  
- 11:00 话题讨论：[tv-morning-discussion-sop.md](tv-morning-discussion-sop.md)  
- 社会民生写法：[social-commentary-voice.md](../wechat-mp-writing/social-commentary-voice.md)  
- 关注引流：[follow-growth-copy.md](../wechat-mp-growth-ops/follow-growth-copy.md)  
- 读者向分享笔记：`stock-ai/docs/share/牛马也智能-AI写作与公众号API笔记.md`
