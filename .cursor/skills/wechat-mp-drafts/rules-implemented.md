# 公众号当前规则与代码映射

本表只覆盖仍在维护的链路。旧 `top5`、`dragons`、`commerce_draft` 与增长提醒已退役。

| 规则 | 代码真源 | 主要测试 |
|---|---|---|
| 公开稿型与别名 | `wechat_mp_content.py` | `test_wechat_mp_retired_kinds.py` |
| 草稿创建、更新与封面 | `wechat_mp_draft.py`、`wechat_mp_client.py` | `test_wechat_mp_thumb_kind.py` |
| 晚间固定批次 | `wechat_mp_draft_batch.py` | `test_wechat_mp_draft_notify.py` |
| 标题、摘要与话题 | `wechat_mp_seo.py` | `test_wechat_mp_seo.py` |
| 热点标题具体化与合成情境引子 | `wechat_mp_clickworthy.py`、`wechat_mp_hotspot_article.py`、`wechat_mp_content.py` | `test_wechat_mp_clickworthy.py`、`test_wechat_mp_hotspot_article.py` |
| 公开稿合规清洗 | `wechat_mp_public.py` | `test_wechat_mp_public.py` |
| 完读、互动与广告检查点 | `wechat_mp_monetization.py`、`wechat_mp_read_hooks.py` | `test_wechat_mp_monetization.py`、`test_wechat_mp_read_hooks.py` |
| HTML 排版 | `wechat_mp_client.py`、`wechat_mp_rich_html.py` | `test_wechat_mp_rich_html.py` |
| 图片池与上传缓存 | `wechat_mp_figure_pool.py`、`wechat_mp_figures.py` | `test_wechat_mp_figure_upload_cache.py` |
| 热点研究与补图 | `wechat_mp_hotspot_article.py`、`wechat_mp_discussion_research.py` | `test_wechat_mp_hot_trends_enrich.py` |
| 通知 | `wechat_mp_draft_notify.py` | `test_wechat_mp_draft_notify.py` |
| 质量与流量检查 | `wechat_mp_eval.py`、`wechat_mp_traffic_checklist.py`、`wechat_mp_empathy_checklist.py` | `test_wechat_mp_eval.py`、`test_wechat_mp_traffic_checklist.py`、`test_wechat_mp_empathy_checklist.py` |

## 当前门禁

- 普通长文不自动插返佣商品或短剧卡。
- stock-ai CTA 只在显式环境变量开启时生效，默认关闭。
- 通知失败和热点研究失败必须可见，不得静默伪装成功。
- 自动批次不得重新引入已退役稿型。
- `WECHAT_MP_TITLE_VIRAL_MODE=1` 才启用自动热点/热点商业的具体化标题与合成情境引子；人工标题、Codex 手写稿和研究不足稿保持原样。合成情境必须披露且紧随可核验事实，不能写成采访、私信或内部信息。
