# 简选小电 — 品牌与账号（带货号）

Agent 写稿、起名、配图、上线独立号前 **先读本节**。工程流水线见 [SKILL.md](SKILL.md)。

## 定稿

| 项 | 内容 |
|----|------|
| **公众号名** | **简选小电** |
| **AppID** | `wx47f3ff18739ab54a`（`.env` → `WECHAT_MP_COMMERCE_APPID`） |
| **定位** | 小空间、插排有限：**全品类小电器** 买前对照，少占地、少闲置 |
| **气质** | 无印式克制（够用、反堆砌）+ 名创式轻快（好选、不严肃）；**编辑盘点**，非假日记、非参数百科 |
| **默认垂直** | `home`（代码与选品词仍以 `home` 键；正文覆盖厨房/清洁/环境/个护） |

**弃用/备选名**（勿与无印、名创商标混用）：家用好物手记、租屋小电器单、小住无堆、小住优品。

## 公众号简介（≤120 字，可直接用）

> 厨房、清洁、环境、个护小电器怎么选才不占地、不闲置；按场景给清单和对照，够用就好，不是参数百科。（文内合作推广）

独立号上线后在公众平台「介绍」粘贴；预览期财经号可不改名，文内用固定栏目前缀培养识别度。

## 读者与内容边界

- **是谁**：一线/新一线租房；厨房小、插排少；常外卖，小电吃灰风险高  
- **要什么**：「该不该买 / 买哪类 / 别占地方」——清单对照，不是种草喊买  
- **全品类范围**：厨房小电、清洁类、环境类、个护小电（见下「首月栏目」）  
- **不写**：医疗功效、全网最低、未实测的「我用了半年」、荐股、敏感工具（同 `writing-guide.md`）

## 固定栏目前缀（文内 / 标题）

每周稿在标题或首段点明系列（与槽位可混用）：

| 周次 | 栏目前缀 | 品类 | auto-pick 词（`WECHAT_MP_FOOTER_PICK_KEYWORD`） |
|------|----------|------|-----------------------------------------------|
| 1 | **买前对照 · 厨房** | 炸锅/水壶/电饭煲/破壁机 | `小家电 空气炸锅 电水壶` |
| 2 | **买前对照 · 清洁** | 吸尘器/拖把/除螨 | `吸尘器 除螨 蒸汽拖把` |
| 3 | **买前对照 · 环境** | 加湿/除湿/暖风机/净化 | `加湿器 除湿机 暖风机` |
| 4 | **买前对照 · 个护** | 吹风/牙刷/剃毛 | `电吹风 电动牙刷` |

槽位建议：`guide` = 上表对照稿；`review` = 单品类稍深；`trend` = 季节（回南天、供暖季）。

## 标题公式

```
[租屋/单间/合租] + [品类] + [结果]？
```

示例：

- 合租单间，环境小电怎么配才不抢插排？  
- 厨房小电器怎么二选一？窄台面先淘汰哪三类  

前 15 字给 **处境 + 品类**；可 `？`；禁震惊、必买、错过亏亿。

## 正文分节（全品类默认）

与 `templates.md` 编辑盘点体统一，优先用：

```
> 什么情况下才需要
> 三类容易买错的
> 两类通常更值的
> 买之前对照三件事
```

（量 / 问 / 想）——末段可并推广披露；摘要句尾带「文内有合作推广」见 `writing-guide.md`。

文末 CPS：**只挂本篇主品类 1 件**，勿跨类。

## 成稿模板与运营

- **v1 定型（默认）**：[template-jianxuan.md](template-jianxuan.md) · 金样 `stock-ai/output/templates/jianxuan-guide-v1.md`
- **发布节奏 SOP**：[operations-sop.md](operations-sop.md)（独立号冷启动周 3 篇 → 常态每周 2～3 篇）
- 机器可读：`stock-ai/data/wechat_mp_commerce_template.json`（含 `publishing_rhythm`）
- 搜一搜词表：[discovery.md](discovery.md)

## 头像（GPT / DALL·E）

**规格**：1:1，1024×1024；主体在中心 70%（微信圆形裁切）；无财经 K 线、无样板间空厨房。

### 主 Prompt（英文，直接复制）

```text
Design a WeChat official account profile avatar, square 1:1, 1024x1024.

Brand name concept: "简选小电" (simple curated small appliances for young renters in big-city shared apartments).

Visual style:
- Minimal, warm, lifestyle e-commerce brand mark
- MUJI-like restraint: off-white / warm beige background (#F5F0E8), soft shadows, no clutter
- MINISO-like friendliness: slightly rounded shapes, approachable, not corporate
- Flat illustration or soft 3D clay style (choose one cohesive style)

Main icon composition (centered, safe for circular crop):
- A small corner of a rental kitchen counter (narrow space feeling)
- Three simplified appliance silhouettes in one scene, evenly spaced:
  1) electric kettle
  2) compact stick vacuum or handheld vacuum
  3) small humidifier or air purifier cube
- Optional: a power strip with 2 plugs to suggest "limited outlets in rental room"
- Subtle dish rack or one mug to feel lived-in, not showroom-empty

Color palette:
- Background: warm off-white or light oat
- Icons: soft charcoal, muted sage green, warm terracotta accent (only one accent color)
- No neon, no gold luxury, no red stock-market colors

Typography (optional, only if it reads at tiny size):
- Two Chinese characters "简选" OR four "简选小电" in clean sans-serif, bold, dark gray
- Place text below icons or integrated in a small label bar
- Must remain legible when scaled to 48px circle

Mood: practical, calm, for Gen-Z renters; "buy only what fits your small room"

Negative prompts / avoid:
- photorealistic messy room, people, faces, hands
- luxury penthouse kitchen, marble, empty showroom
- finance charts, arrows, coins
- crowded collage, 10 appliances, sale badges, "BEST", "SALE", explosion stickers
- MUJI or MINISO logo, trademark imitation
- English slogans, watermarks, borders
```

### 变体

- **无字纯图标**（小头像更清晰）：删掉 Typography，改为 `No text. Icon-only: line-art power strip + three tiny appliance icons, warm gray on off-white.`  
- **略活泼**：`Soft 3D clay style, pastel mint + coral accent on cream, cute proportions not childish.`

### 生成后自检

缩至 48px 圆仍可辨认「小电器」；背景够浅；若带字，「简」字勿贴边。

## 素材与预览期

| 文件 | 仓库路径 | 用户本机（可选覆盖） |
|------|----------|----------------------|
| 正文顶栏 banner | `stock-ai/assets/wechat_mp/commerce/banner.png` | `~/Pictures/简选小电banner.png` 或 `~/picture/` 同名 |
| 草稿列表封面 | `stock-ai/assets/wechat_mp/commerce/avatar.png` | `~/Pictures/简选小电头像.png` |

环境变量（见 `reference.md`）：

- `WECHAT_MP_COMMERCE_BANNER_PATH` — 顶栏图  
- `WECHAT_MP_COMMERCE_THUMB_PATH` — 封面图  
- `WECHAT_MP_COMMERCE_MASTHEAD=1`（默认开）— 正文顶 **简选 banner + 暖色 slogan 条**  
- `WECHAT_MP_COMMERCE_ACCOUNT_NAME=简选小电`

| 项 | 预览期（财经 AppID） | 独立号上线后 |
|----|----------------------|--------------|
| 名称 / 简介 | 可暂不改 | 公众平台改 **简选小电** + 简介 |
| 头像 | 用 `avatar.png` 上传公众平台 | 同左 |
| 正文顶栏 | 已用 `commerce/banner.png` | 换图后重推草稿（banner 缓存含 md5） |
| 插图 | `inline-commerce/home/` | 换图按 md5 重传 |

## 命名参考（为何叫「简选」）

| 参考 | 借什么 | 不借什么 |
|------|--------|----------|
| 无印良品 | 少噱头、够用、反堆砌 | 「无印」「良品」字样 |
| 名创优品 | 短、好记、年轻、像「好选」 | 「名创」「优品严选」整词 |

「简选」= 简单选、帮租屋的人做减法；「小电」= 全品类小电器，比「好物」「手记」更窄、更好搜。
