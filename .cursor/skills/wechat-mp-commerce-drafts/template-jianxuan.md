# 简选小电 · 成稿模板 v1（定型）

> **状态**：`jianxuan-v1` · **冻结** 2026-06-03  
> **变更规则**：改版式须新开 `jianxuan-v2` 文档并更新 `stock-ai/data/wechat_mp_commerce_template.json`；勿在 v1 上打补丁式混改。  
> 机器可读：`stock-ai/data/wechat_mp_commerce_template.json`  
> 金样正文：`stock-ai/output/templates/jianxuan-guide-v1.md`（与已推 `commerce_home.md` 同构）

品牌 / 引流：[brand.md](brand.md) · [discovery.md](discovery.md)

---

## v1 版式栈（自上而下）

```
┌─────────────────────────────┐
│ 封面 avatar（草稿列表）      │
├─────────────────────────────┤
│ commerce banner + 简选小电   │  masthead_html("commerce")
│ + slogan 暖色条              │
├─────────────────────────────┤
│ 开篇 1～2 段（编辑口吻）     │
├─────────────────────────────┤
│ #租房好物 #小家电 #买前对照  │  insert_hashtags_after_intro
│ （居中浅底条）               │  → commerce_hashtag_html
├─────────────────────────────┤
│ > 窄台面为什么先谈收纳       │
│   …正文… + 图①              │
│ > 三类容易买错的             │
│   …正文…                    │
│ > 两类通常更值的             │
│   图② + …正文…              │
│ > 买之前对照三件事           │
│   图③ + …正文…              │
├─────────────────────────────┤
│ 文末互动问句（可选）         │  polish_for_traffic commerce
├─────────────────────────────┤
│ CPS 返佣卡                   │  免责 HTML 之前
├─────────────────────────────┤
│ 免责（居中暖色高亮框）       │  disclaimer_html kind=commerce
└─────────────────────────────┘
```

---

## 默认环境（定型，勿随意关）

| 变量 | 值 | 作用 |
|------|-----|------|
| `WECHAT_MP_COMMERCE_MASTHEAD` | `1` | 简选 banner 顶栏 |
| `WECHAT_MP_COMMERCE_SEO` | `1` | 标题前缀、摘要补词、正文 #话题 |
| `WECHAT_MP_COMMERCE_ACCOUNT_NAME` | `简选小电` | 顶栏账号名 |
| `WECHAT_MP_FOOTER_PRODUCT` | `1` | 文末 CPS |
| `WECHAT_MP_SECTION_STYLE` | `compact` | 分节居中 17px |
| `WECHAT_MP_RICH_HTML` | `1` | 富文本样式 |
| `WECHAT_MP_AD_CHECKPOINT` | `0` | 流量主由微信自动插 |

素材路径见 `assets/wechat_mp/commerce/`（banner / avatar）。

---

## 标准推稿命令（`guide` + `home`）

```bash
cd stock-ai
cp output/templates/jianxuan-guide-v1.md output/my_article.md
# 编辑 my_article.md 后：

WECHAT_MP_FOOTER_PICK_KEYWORD="收纳 置物架 厨房收纳" \
uv run python -m scripts.tools.wechat_mp_commerce_draft \
  --slot guide \
  --vertical home \
  --title "小厨房台面不够用？收纳顺序可以参考" \
  --digest "窄台面先理顺调料和线缆，三类易买错的收纳件对照。" \
  --body-file output/my_article.md
```

终端应出现：`推荐 #话题: #租房好物 #小家电 #买前对照` 与 **生活/家居** 发布提醒。

---

## 正文 Markdown 契约（v1 冻结）

### 必须遵守

| 项 | 规则 |
|----|------|
| 分节 | 仅 `> 标题`；禁止「一、二、三」 |
| 插图节名 | **固定三节**（改节名 = 插图失效，须同步改代码） |
| 披露 | 摘要句尾 `（文内有合作推广）`；正文不插「本文含推广链接」 |
| emoji | 禁止 |
| 口吻 | 编辑盘点；不写假「我租过半年…」 |

### 插图节名（与代码绑定）

1. `> 窄台面为什么先谈收纳` → 图 `01-compact-kitchen.jpg`（段后插入）
2. `> 两类通常更值的` → 图 `02-small-kitchen.jpg`（段前插入）
3. `> 买之前对照三件事` → 图 `03-counter.jpg`（段前插入）

实现：`HOME_COMMERCE_FIGURE_SLOTS` · `wechat_mp_figures.py`

### 骨架（可复制）

见 [jianxuan-guide-v1.md](../../stock-ai/output/templates/jianxuan-guide-v1.md)。

栏目标题轮换（文首一行即可）：

| 周 | 前缀 | CPS 搜词示例 |
|----|------|----------------|
| 1 | 买前对照 · 厨房 | `小家电 空气炸锅 电水壶` |
| 2 | 买前对照 · 清洁 | `吸尘器 除螨 蒸汽拖把` |
| 3 | 买前对照 · 环境 | `加湿器 除湿机 暖风机` |
| 4 | 买前对照 · 个护 | `电吹风 电动牙刷` |

---

## 标题 / 摘要（v1）

| 字段 | 规则 |
|------|------|
| 标题 ≤32 | 前 15 字：**租屋/合租/单间** + 品类；脚本可补前缀 `租屋小电｜` |
| 摘要 ≤128 | 场景 + 价值；句尾 `（文内有合作推广）`；SEO 自动补「租屋、小家电」 |

---

## 槽位

| slot | 用途 |
|------|------|
| `guide` | **v1 默认**：买前对照体 + 上表插图 |
| `review` | 单品测评；#话题池不同 |
| `trend` | 季节热点 |

槽位文件：`data/wechat_mp_commerce_slots.json`（勿与财经五槽混用）。

---

## 发布检查单（人工）

节奏与冷启动见 **[operations-sop.md](operations-sop.md)**；以下为单篇：

- [ ] 预览：简选 banner、正文 #话题条、暖色免责、非财经图
- [ ] 原创 → 分类 **生活 / 家居**
- [ ] 发布后 `#`：`#租房好物` `#小家电` `#买前对照`（或终端推荐）
- [ ] CPS 品类与正文当周栏目一致
- [ ] 发文后 24h：朋友圈节选 + 回留言（SOP 第三节）

---

## 代码映射

详见 [rules-implemented.md](rules-implemented.md) · 版式测试 `tests/unit/test_wechat_mp_commerce_layout.py`
