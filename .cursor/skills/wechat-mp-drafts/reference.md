# 微信公众号草稿 — 参考

写作法则与发布前总检见 [writing-guide.md](writing-guide.md)。

## 外部参考（非本仓库维护）

| 来源 | 用途 |
|------|------|
| [Qson8/wechat-writing-skill](https://github.com/Qson8/wechat-writing-skill) | 去 AI 味对照表、标题/结构模板（MIT，受众为独立开发者） |
| [微信公众号爆文方法论](https://xiangyugongzuoliu.com/wechat-article-creation-strategies-core-methodology/) | 标题 15–28 字、三三排版 |
| [刘润团队 2025 写作法则](https://news.qq.com/rain/a/20250801A055SU00) | 跳读、短段、标题即有收获 |
| [Cursor Skills 文档](https://cursor.com/docs/context/skills) | Skill 目录与 `paths` frontmatter |

## 模块文件表

| 文件 | 职责 |
|------|------|
| `scripts/tools/wechat_mp_draft.py` | CLI 入口 |
| `scripts/tools/wechat_mp_content.py` | `build_*_article`、`DRAFT_KINDS`、标题/摘要 |
| `scripts/tools/wechat_mp_client.py` | Token、草稿 CRUD、素材封面、`text_to_html` |
| `scripts/tools/wechat_mp_draft_slots.py` | 四槽 `media_id` 持久化、upsert |
| `scripts/tools/wechat_mp_rich_html.py` | 着色、引用块分块标题 |
| `scripts/tools/wechat_mp_prose.py` | `humanize_mp_text`（行情三篇） |
| `scripts/tools/wechat_mp_public.py` | `PUBLIC_MP_WRITER_RULE`、公开稿清洗 |
| `scripts/tools/wechat_mp_market_article.py` | 宏观正文 |
| `scripts/tools/wechat_mp_top5_article.py` | Top5 交易员体例 + prompt |
| `scripts/tools/wechat_mp_dragons_article.py` | 龙头四节稿 |
| `scripts/tools/wechat_mp_workspace_article.py` | 工具工作区静态稿、`PROJECT_NAME` |
| `scripts/tools/wechat_mp_sop_fast.py` | 东财快采（公众号隔离） |
| `scripts/tools/wechat_mp_eval.py` | 五维评分 + 合规 + AI 味 0–100 |
| `data/wechat_mp_draft_slots.json` | 槽位状态（勿手删除非重建） |

## 环境变量（摘自 `.env.example`）

```bash
WECHAT_MP_APPID=
WECHAT_MP_SECRET=
WECHAT_MP_WHITELIST_IP=          # 公众平台白名单
WECHAT_MP_PUBLIC_IP=             # 可选，跳过 ipify
WECHAT_MP_AUTHOR=R2D2
WECHAT_MP_SOURCE_URL=            # 可选原文链接
WECHAT_MP_AUTO_PUBLISH=0

# 四槽封面（素材库文件名子串）
WECHAT_MP_THUMB_NAME_MARKET=封面-交易所屏-双封面
WECHAT_MP_THUMB_NAME_TOP5=封面-手机看盘-双封面
WECHAT_MP_THUMB_NAME_DRAGONS=封面-K线暗色-双封面
WECHAT_MP_THUMB_NAME_WORKSPACE=封面-数据大屏-双封面

WECHAT_MP_DRAGON_SLOT=eod
WECHAT_MP_DRAGON_SOP=1
WECHAT_MP_DRAGON_SOP_MAX=3
WECHAT_MP_TOP5_SOP=1
WECHAT_MP_TOP5_STRATEGIES=combined,five_factor,ma5,watch
WECHAT_MP_TOP5_SCORE_ONLY=1
WECHAT_MP_MARKET_NEWS_HOURS=36
WECHAT_MP_RICH_HTML=1            # 0 关闭富文本
```

## API 调用链（实现级）

```
get_access_token()
  → GET cgi-bin/token

pick_thumb_for_draft_kind(kind)
  → batchget_material / 缓存 thumb

build_article(kind) → dict(title, author, digest, content HTML)

upsert_draft_article:
  有 slots[kind].media_id → draft_update
  否则 → draft_add → 写入 slots json

attach_cover_crop_fields(article, thumb_media_id)
  → 按素材宽高算 crop 字段（竖图→公众号头图比例）
```

错误码常见：`40001` token 失效（刷新 token）；`40164` IP；`45009` 接口限额。

## 工作区技术稿专用约定

- `PROJECT_NAME = "工具工作区"`，`SERIES_TAG` 仅用于代码标识，**不进**正文。
- 开头：用「收盘后一刻钟会跑完什么」切入，不用文件夹名。
- 分块：`> 它是什么`、`> 里面分几块` 等；正文无 `月X日`、无 `工具工作区技术分享 · 总览` 抬头。
- `build_workspace_article` 后处理链：

```python
strip_markdown_for_wechat → normalize_wechat_spacing → sanitize_public_mp_text
# 不经过 humanize_mp_text
```

## 行情三篇 LLM 提示要点

- System 注入：公开稿、非持仓、非荐股、非聊天机器人腔。
- 宏观：四节从「一、盘面一览」起，禁止「研究员札记 |」抬头。
- Top5：每只四行（地位/量价资金/博弈/结论），覆盖名单内全部标的。
- 龙头：情绪 + 最多 N 只快采（`WECHAT_MP_DRAGON_SOP_MAX`）。
- 成稿后：`strip_journal_title_lines` 去掉历史抬头行。

## 历史踩坑（对话沉淀）

1. **UTF-8 / HTML**：早期乱码 → 统一 `encoding=utf-8`，HTML 必须 `_escape_html` 再插标签。
2. **封面**：本地文件上传易尺寸不合 → 改素材库竖图 + 按 kind 匹配 + crop 字段。
3. **草稿爆炸**：每次 `draft_add` → 槽位 json + update 优先 + `prune_obsolete_drafts`。
4. **Top5 只读 combined 4 条** → 改多策略 merge + 按总分重选。
5. **快采拖慢 SOP** → 独立 `wechat_mp_sop_fast` 缓存目录。
6. **工作区走 humanize** → 语气更「模板」→ 工作区改静态 + 轻清洗。
7. **项目命名**：避免生僻绰号（如「盘后坞」）；统一「工具工作区」。
8. **标题随机到怪句** → 工作区标题池固定 4 条吸睛句，勿塞目录名。
9. **分块标题丑** → 引用块统一样式，`一、` 与 `>` 均识别。
10. **订阅号审阅**：脚本只写草稿箱，发布前人工在 mp.weixin.qq.com 看图文版式。

## launchd（可选）

`stock-ai/scripts/install-wechat-mp-launchd.sh` — IP 白名单变更告警；定时草稿由业务调度（见 `docs/SCHEDULING.md`）另配。
