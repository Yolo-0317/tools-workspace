# 公众号正文排版模板（macro / Top5 等）

环境变量：`WECHAT_MP_LAYOUT=pulse|brief|chapter|report`（默认 `pulse`）  
节标题样式：`WECHAT_MP_SECTION_STYLE=compact|card`（默认 `compact` 左线）

## 模板 A · 专栏紧凑 `pulse`（**当前默认**）

**参考**：刘润、吴晓波类长文；36氪/财经号「一段一观点」。

| 元素 | 样式 |
|------|------|
| 节标题 | **居中**，17px 加粗、主题色 `#1a5276`（无引用块）；图后接标题上留白约 2px |
| 正文 | 段后 9px，行高 1.72 |
| 插图 | 贴上一段末（上 4px / 下 2px），图注 12px 灰字 |
| 结构 | 正文 → 图（小结）→ 下一节标题 |

适合：大盘分析、龙头复盘（信息多、要连续读）。

**快讯区**：`[利好/利空/中性]` 行之间的空行不再拆成多个 `<p>`（整段 `news_margin: 0 0 2px`，条间仅 `<br/>`）。

## 模板 B · 快讯简报 `brief`

**参考**：财联社电报体、券商「收盘 3 分钟」。

| 元素 | 样式 |
|------|------|
| 节标题 | **无左边框**，仅加粗 |
| 间距 | 全局再收一档 |
| 插图 | 几乎贴图注 |

适合：要闻列表多、字数偏短的宏观快评。

## 模板 C · 章节导图 `chapter`

**参考**：135/秀米「章节头图」模板；杂志分章。

| 元素 | 样式 |
|------|------|
| 顺序 | **先节标题 → 大图 → 正文**（与现 macro 相反，需改插图插入逻辑） |
| 插图 | 标题下 2px，正文前 8px 下留白 |

适合：强调视觉、每章一张主图。启用前需改 `inject_market_figures` 为 chapter 模式（待接开关）。

## 模板 D · 晨报体 `report`

**参考**：中金/中信晨报 PDF 转公众号；表格+列表。

| 元素 | 样式 |
|------|------|
| 节标题 | 左线，上下略松（16px / 5px） |
| 正文 | 段后 11px |
| 后续 | 要闻可改为 `<ul>` 列表（未默认开启） |

适合：条目多、要「官方简报」气质。

---

## 预览与切换

```bash
cd stock-ai
# 默认 pulse
uv run python -m scripts.tools.wechat_mp_draft --kind market --preview-html output/wechat_mp_market_preview.html

# 试其它模板
WECHAT_MP_LAYOUT=brief uv run python -m scripts.tools.wechat_mp_draft --kind market --preview-html output/preview-brief.html
```

推草稿：改 `.env` 中 `WECHAT_MP_LAYOUT` 后执行 `uv run python -m scripts.tools.wechat_mp_draft --kind market`。
