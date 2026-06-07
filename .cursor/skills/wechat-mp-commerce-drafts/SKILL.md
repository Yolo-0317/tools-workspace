---
name: wechat-mp-commerce-drafts
description: >-
  Writes and pushes WeChat commerce/affiliate (带货) drafts for home/kitchen
  vertical (default home). Preview on finance AppID with isolated commerce slots.
  Reuses stock-ai CPS
  footer (mp-common-cpsad), traffic monetization hooks, draft API, and
  wechat_mp_commerce_draft CLI. Use for 带货公众号、种草稿、返佣商品、行业好物、
  WECHAT_MP_FOOTER_PRODUCT, separate from wechat-mp-drafts five-slot finance pipeline.
paths:
  - stock-ai/scripts/tools/wechat_mp_commerce_draft.py
  - stock-ai/scripts/tools/wechat_mp_commerce_slots.py
  - stock-ai/scripts/tools/wechat_mp_product.py
  - stock-ai/scripts/tools/wechat_mp_client.py
  - stock-ai/scripts/tools/wechat_mp_monetization.py
  - stock-ai/data/wechat_mp_commerce_slots.json
---

# 微信公众号带货草稿（stock-ai）— 简选小电 · 已搁置

> 用户说 **「公众号」** 默认指 **牛马也智能** → [wechat-mp-drafts](../wechat-mp-drafts/SKILL.md)。本 skill 仅 **简选小电** / 带货，用户未明确要求时不要执行。

与 [wechat-mp-drafts](../wechat-mp-drafts/SKILL.md) **分工**：

| Skill | 账号定位 | 成稿 |
|-------|----------|------|
| `wechat-mp-drafts` | 工具工作区 / A 股五槽 | `build_article(market\|news\|…)` + 定时批次 |
| **`wechat-mp-commerce-drafts`** | **「简选小电」** 租屋全品类小电（模板 **`jianxuan-v1` 定型**） | Agent 写 Markdown → `wechat_mp_commerce_draft` |

工作目录：`tools-workspace/stock-ai`。

## 当前策略（预览 → 独立带货号）

| 阶段 | 做法 |
|------|------|
| **现在** | **默认垂直 `home`**；用**当前财经号**同一套 `WECHAT_MP_APPID/SECRET` 推草稿，仅 **mp.weixin.qq.com 预览**版式与 CPS |
| **隔离** | Skill 与槽位独立：`wechat_mp_commerce_slots.json`（`guide`/`review`/`trend`），**不覆盖**五槽 `market/news/…` |
| **日后** | 新开带货号 → 换 `.env` 里 AppID/Secret、`DAIHUO_UIN`、封面素材；命令与 skill **不变** |

Agent 写带货稿时 **不要**走 `wechat_mp_draft --kind market`；财经定时批次 **不要**改带货槽位。

| 文档 | 内容 |
|------|------|
| [brand.md](brand.md) | **简选小电** 定位、简介、栏目、头像 GPT prompt、上线清单 |
| [template-jianxuan.md](template-jianxuan.md) | **v1 定型模板**（版式栈 / 节名契约 / 推稿命令） |
| [operations-sop.md](operations-sop.md) | **发布运营 SOP**（冷启动/稳定节奏、引流、复盘、文献） |
| [discovery.md](discovery.md) | **引流与搜一搜**（关键词、#话题；节奏摘要链到 SOP） |
| [photography-xhs-sop.md](photography-xhs-sop.md) | **小红书摄影号维护**（当前执行；简选已不做） |
| [xiaohongshu-sop.md](xiaohongshu-sop.md) | ~~简选小红书独立运营~~（**已搁置**，历史参考） |
| [writing-guide.md](writing-guide.md) | 种草写作 + **广告法/返佣披露** + 流量主完读 |
| [templates.md](templates.md) | 三种带货稿骨架与标题池 |
| [rules-implemented.md](rules-implemented.md) | 规则 ↔ 代码；与财经 skill 边界 |
| [reference.md](reference.md) | env、垂直选品词、模块表、与财经号共用能力 |

## Agent 两种任务

**A. 推带货草稿（工程）** → `wechat_mp_commerce_draft` + 下文「流水线」

**B. 写种草文案（写作）** → **只按** [template-jianxuan.md](template-jianxuan.md)（v1 定型）+ 金样 [jianxuan-guide-v1.md](../../stock-ai/output/templates/jianxuan-guide-v1.md) 改稿；品牌/引流见 brand、discovery

改完必须：`--dry-run` → 推稿 → mp.weixin.qq.com 预览 **文末 CPS 卡 + 流量主广告位**。

## 必备变现能力（从财经 skill 继承）

| 能力 | 开关 / 模块 | 说明 |
|------|-------------|------|
| **文末返佣 CPS** | `WECHAT_MP_FOOTER_PRODUCT=1` | `<mp-common-cpsad data-pid>`，Disclaimer **前**插入 |
| **自动选品** | `WECHAT_MP_FOOTER_PRODUCT_AUTO_PICK=1` | `daihuo` Select，按 `--vertical` 搜词取最高佣金 |
| **流量主广告** | 开通后微信发布时自动插底部/文中 | 正文**不要**留 `· · ·` 人工位（默认关 `WECHAT_MP_AD_CHECKPOINT`） |
| **完读 + 留言** | `WECHAT_MP_MONETIZE=1`、`WECHAT_MP_NEED_OPEN_COMMENT=1` | 文末互动问句（带货腔，非荐股） |

**真机制**：CPS 用 `data-pid`（`{warehouse}_{product_id}`），**不是** `getcardinfo` 的 `product_key`（JD 常 10170001）。

## 命令

```bash
cd stock-ai

# 选品（home 默认词：小家电 空气炸锅 收纳 厨房）
uv run python -m scripts.tools.wechat_mp_product --search 空气炸锅
uv run python -m scripts.tools.wechat_mp_product --pick --pick-keyword 小家电

# 带货草稿 → 先进当前财经号草稿箱预览（--vertical 默认 home，可省略）
uv run python -m scripts.tools.wechat_mp_commerce_draft \
  --title "厨房小家电怎么选？三类场景对照" \
  --digest "窄台面收纳件对照，按需购买。（文内有合作推广。）" \
  --body-file output/commerce_home.md \
  --dry-run

uv run python -m scripts.tools.wechat_mp_commerce_draft \
  --slot guide \
  --title "租房厨房只够一桌？三件小家电够用" \
  --body-file output/commerce_home.md

# 质量（复用 eval 逻辑时可手写检查；合规见 writing-guide）
uv run python -m scripts.tools.wechat_mp_check_whitelist
```

**垂直 `--vertical`**：默认 **`home`**；其它 `tech` `mother` `outdoor` `office` `beauty` 见 [reference.md](reference.md)。

**槽位 `--slot`**：默认 `guide`；同槽多次推稿会 **update 替换** 该槽旧稿（`data/wechat_mp_commerce_slots.json`）。

## 成稿流水线

1. Agent / 人工写 Markdown：`> 分节标题`、短段；**插图由 `inject_commerce_figures` 自动插入**（`home` 垂直 3 张，见 `HOME_COMMERCE_FIGURE_SLOTS`）
2. `build_commerce_article()`（对齐财经 `_article_shell`）：
   - `strip_markdown_for_wechat` + 列表拆段；`> 分节标题`；默认 **品牌头**（`WECHAT_MP_COMMERCE_MASTHEAD=1`）
   - 先 `split_disclaimer` 再 `text_to_html`；**CPS 插在正文 HTML 末、免责声明段之前**（勿插进 `<p>` 中间）
3. **`attach_footer_product`** → `upsert_commerce_draft(slot)`
4. 正文 Markdown **勿用 `**加粗**`**（用空行分条或 `·` 列表）

## 版式硬约束

| 项 | 要求 |
|----|------|
| 分节 | `> 标题` → 居中 17px `#1a5276`（同财经号 `compact`） |
| 标题 | ≤32 字；含场景或数字；可 `？` `！`，不标题党 |
| 摘要 | ≤128 字；须含 **推广/佣金** 提示词之一 |
| 披露 | 正文或摘要出现「推广」「佣金」「合作」类表述；文末统一免责 |
| emoji | **禁止**（与财经号一致） |
| 荐股 | **禁止**（勿混 A 股买卖暗示；垂直切到财经请用 `wechat-mp-drafts`） |
| 返佣卡 | 免责声明前；后台预览可见 `mp-common-cpsad` |

环境：`WECHAT_MP_SECTION_STYLE=compact`、`WECHAT_MP_RICH_HTML=1`、`WECHAT_MP_FOOTER_PRODUCT=1`、`WECHAT_MP_DAIHUO_UIN=…`。

## 与财经五槽的关系

- **勿**用 `wechat_mp_draft --kind market` 发带货长文（合规与 prompt 不同）。
- **预览期**：共用财经号 `WECHAT_MP_APPID`；草稿箱里会出现 **带货槽位标题**（与五槽并存），发布前勿误发。
- **勿**在带货预览稿勾财经原创分类后当盘面稿发；正式发布应在**未来带货号**。
- 财经五槽 CPS 词表见 `wechat-mp-drafts`；本 skill 固定 **`home`** 选品词（`reference.md`）。

## 发布前人工（API 做不到）

- [ ] 勾 **原创**（分类选「科技」「生活」等，勿误选荐股向财经）
- [ ] 发布后加 `#` 话题（须原创通过后，最多 5 个）
- [ ] 确认文末 **返佣商品卡** 与文中 **流量主广告** 显示正常
- [ ] 商品与正文场景一致（auto-pick 失败时手动 `--pick-keyword` + 固定 `FOOTER_PRODUCT_ID`）

## 扩展检查清单

- [ ] 新垂直 → `PICK_KEYWORDS_BY_VERTICAL`（`wechat_mp_commerce_draft.py`）+ reference 表
- [ ] 返佣：`FOOTER_PRODUCT=1` + `DAIHUO_UIN`；`inject_cpsad` 识别带货免责前缀
- [ ] pytest `test_wechat_mp_commerce_draft.py` + `test_wechat_mp_product.py`
- [ ] 独立带货号：单独 `.env` / 白名单 IP / 素材库封面

## 故障速查

| 现象 | 处理 |
|------|------|
| 文末无 CPS | `WECHAT_MP_FOOTER_PRODUCT=1`；正文含带货免责句；查 stderr `文末返佣` |
| auto-pick 失败 | 配 `WECHAT_MP_DAIHUO_UIN`；`--pick-keyword` 或 `WECHAT_MP_FOOTER_PRODUCT_ID` |
| 与财经稿混删 | 带货用 `wechat_mp_commerce_slots.json`，勿改五槽 `wechat_mp_draft_slots.json` |
| getcardinfo 10170001 | 正常；以 `data-pid` 为准 |

## 测试

```bash
uv run pytest tests/unit/test_wechat_mp_commerce_draft.py \
  tests/unit/test_wechat_mp_product.py -q
```
