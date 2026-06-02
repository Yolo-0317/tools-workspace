---
name: wechat-mp-drafts
description: >-
  Operates stock-ai WeChat Official Account (微信公众号) daily drafts via API
  (four slots: macro, Top5, dragons, workspace tech) and applies industry
  writing rules: titles, mobile layout, de-AI prose, digest SEO, compliance.
  Use for wechat_mp_* code, 公众号草稿, 改标题/去AI味/排版, WECHAT_MP_* env, or
  publishing to mp.weixin.qq.com.
paths:
  - stock-ai/scripts/tools/wechat_mp_*.py
  - stock-ai/tests/unit/test_wechat_mp_*.py
  - stock-ai/data/wechat_mp_draft_slots.json
---

# 微信公众号四槽位（stock-ai）

工作目录：`tools-workspace/stock-ai`。入口：`uv run python -m scripts.tools.wechat_mp_draft`。

| 文档 | 内容 |
|------|------|
| [writing-guide.md](writing-guide.md) | **行业写作法则**（标题/开头/排版/去AI/搜一搜）+ 本账号硬约束 |
| [reference.md](reference.md) | API、环境变量、模块表、历史踩坑 |

## Agent 两种任务

**A. 推草稿（工程）** → 下文「流水线」+ [reference.md](reference.md)

**B. 改文案（写作）** → 先读 [writing-guide.md](writing-guide.md)，再改对应 `*_article.py` 或静态 `generate_workspace_overview_body`

改完文案必须：`--dry-run` → 单篇 `--kind` → 后台预览版式。

## 四槽职责

| kind | 读者 | 成稿 | 模块 |
|------|------|------|------|
| `market` | 行情 | LLM + 盘面/要闻 | `wechat_mp_market_article.py` |
| `top5` | 行情 | LLM + 多策略 Top5 + 快采 | `wechat_mp_top5_article.py` |
| `dragons` | 行情 | LLM + 情绪 + 龙头快采 | `wechat_mp_dragons_article.py` |
| `workspace` | 工程 | **静态**，无行情 LLM | `wechat_mp_workspace_article.py` |

对外项目名：**工具工作区**（`PROJECT_NAME`）。正文勿用 `tools-workspace` 等目录名当品牌。

## 命令

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_check_whitelist
uv run python -m scripts.tools.wechat_mp_draft --list-materials
uv run python -m scripts.tools.wechat_mp_draft --dry-run
uv run python -m scripts.tools.wechat_mp_draft
uv run python -m scripts.tools.wechat_mp_draft --kind workspace

# 质量评分（改稿 / 推草稿前）
uv run python -m scripts.tools.wechat_mp_eval --kind all
uv run python -m scripts.tools.wechat_mp_eval --kind workspace --min-score 70 --max-ai-flavor 40
uv run python -m scripts.tools.wechat_mp_eval --file /path/to/draft.md --title "标题"
uv run python -m scripts.tools.wechat_mp_eval --kind top5 --json
```

**评分门槛（默认建议）**：总分 ≥75 且 AI 味 ≤40 → `可进草稿箱`；有合规项 → 必须先修。规则实现见 `scripts/tools/wechat_mp_eval.py`。

改代码后：`pytest tests/unit/test_wechat_mp_eval.py` + `test_wechat_mp_*.py` → 再推草稿。

## 成稿流水线

1. 数据就绪（Top5 选股、宏观行情、龙头检查表）
2. `build_article(kind)` → `wechat_mp_content.py`
3. 后处理：
   - **market/top5/dragons**：`humanize_mp_text` + `sanitize_public_mp_text`
   - **workspace**：仅 `strip_markdown` + `sanitize`（**禁止** humanize）
4. `text_to_html` + `wechat_mp_rich_html`（涨跌色、**引用块分块标题**）
5. `pick_thumb_for_draft_kind` → `upsert_draft_article`（`data/wechat_mp_draft_slots.json`）

## 写作速查（详见 writing-guide.md）

### 标题

- ≤32 字；关键词靠前；吸睛用 `？` `！`，**不**标题党
- 池：`wechat_mp_content._pick_clickbait_title` / `workspace_overview_title`

### 排版

- 短段；分块用 `> 标题` 或 `一、…`（自动 `blockquote` 科技风样式）
- **无 emoji**；行情可用 `[利好]/[利空]` 标签（富文本着色）

### 去 AI 味

- 场景 + 数字 + 踩坑；禁「首先其次最后」「赋能/一站式/留言即可」
- 工作区：静态人写语气，见 `test_wechat_mp_workspace_article._AI_PHRASES`
- 可参考开源 [Qson8/wechat-writing-skill](https://github.com/Qson8/wechat-writing-skill) 的 AI 味对照表（受众不同，禁词以本仓库为准）

### 公开稿红线

`PUBLIC_MP_WRITER_RULE`：无持仓/执行卡/荐股/Clash/substore/机场；技术稿无正文日期与系列抬头。

## API 要点

| 项 | 说明 |
|----|------|
| Token | `WECHAT_MP_APPID` + `SECRET` → `data/wechat_mp_token.json` |
| IP | `40164` → 白名单 / `wechat_mp_check_whitelist` |
| 草稿 | 槽位优先 **update**；`--prune-only` 清重复 |
| 封面 | 素材库 `WECHAT_MP_THUMB_NAME_*` + crop 字段 |
| 发布 | 默认仅草稿；`AUTO_PUBLISH=1` 或 `--publish` 才群发 |

## 扩展检查清单

- [ ] 新 kind → `DRAFT_KINDS`、slots、封面 env、title hints
- [ ] LLM prompt 注入 `PUBLIC_MP_WRITER_RULE`
- [ ] workspace 未走 humanize
- [ ] [writing-guide.md](writing-guide.md) 发布前总检
- [ ] pytest + `--dry-run`

## 故障速查

| 现象 | 处理 |
|------|------|
| `40164` | IP 白名单 |
| Top5 空 | 跑选股 |
| 封面找不到 | `--list-materials` |
| 草稿重复 | `--prune-only` |
| 工作区 AI 腔 | 改静态正文，勿加 LLM |

## 测试

```bash
uv run pytest tests/unit/test_wechat_mp_rich_html.py \
  tests/unit/test_wechat_mp_workspace_article.py \
  tests/unit/test_wechat_mp_top5_article.py \
  tests/unit/test_wechat_mp_dragons_article.py \
  tests/unit/test_wechat_mp_public.py -q
```
