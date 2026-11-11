# 参考文阅读与提炼 SOP

> **用途**：**扩容**写稿语料库时用（你丢对标文、季度复盘）。日常写稿只读 [voice-corpus.md](voice-corpus.md) / [voice-corpus-dianji.md](voice-corpus-dianji.md)，**不必**每篇走本 SOP。

---

## 一、为什么要单独做提炼

| 问题 | 根因 | 提炼解决什么 |
|------|------|----------------|
| 像 AI 叙事 | 模型按「节目介绍/观后感」模板写 | 用真人稿的 **首句、钉子、收束** 当硬约束 |
| 像央视通稿 | 只读了节目官方稿 | 对照 **煽情软文** 列反例禁句 |
| eval 过了仍难看 | 门禁卡套话，不卡「好不好读」 | 人工金样 + **开头 80 字过关** 才允许推稿 |
| 每篇改很多遍 | 无真源，聊天里改不落盘 | 提炼表落盘 → 下次同题直接读 |

---

## 二、参考文分档（每题至少 3 篇）

| 档位 | 找什么 | 读什么 | 不做什么 |
|------|--------|--------|----------|
| **A 事实链** | 门户深度稿、央视稿、学会解读 | 时间、人物、数字、篇名、地名、可核对台词 | 不抄抒情段 |
| **B 好读范本** | 你觉得「想继续划」的公众号/媒体（可跨题） | **首段怎么落地**、段长、一句钉子、怎么收 | 不照搬立场 |
| **C 反例** | 观后感、煽情软文、百度百科式介绍 | 记下 **恶心句** 进禁词表 | 不当作风格来源 |

典籍专栏目录与首批链接：`stock-ai/data/wechat_mp_reference_corpus/dianji-zhongguo/sources.json`

---

## 三、单篇提炼表（Agent 填完再写 `body_core`）

复制到 `stock-ai/data/wechat_mp_reference_corpus/<series>/notes/{cover_slug}.md`：

```markdown
# {标题} · 阅读提炼

## 钉子（本篇只讲一件事）
- 一句话：

## A 事实（可核对，带出处 URL）
1.
2.
3.

## B 好句借法（改写，非原文照抄）
- 开头仿写（80 字内，可直接作首段草稿）：
- 收束仿写（一句，禁说教）：

## C 反例句（本文禁止出现同类）
-
-

## 段落节奏
- 目标段数：4～6
- 每段功能：（事实 / 代价 / 一句引语 / 今天的一个画面）

## 是否可推稿
- [ ] 开头仿写人工点头
- [ ] 钉子与标题同题
- [ ] 无 C 档反例句
```

**硬门禁**：`开头仿写` 未人工确认 → 禁止 `repush`（可 `--dry-run` 预览结构）。

---

## 四、Agent 工作流（禁止跳步）

```text
定题（cover_slug + nail）
  → 读 sources.json 该集 links（A≥2，C≥1）
  → 可选：fetch_discussion_research 补当日同题稿
  → 填提炼表 notes/{cover_slug}.md
  → 写开头仿写 + 全文草稿进 body_cache
  → scan_report_voice + wechat_mp_eval
  → 人工改开头仿写（最多改这一段也可）
  → repush
```

命令：

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_reference_corpus checklist --series dianji-zhongguo --ep 1
uv run python -m scripts.tools.wechat_mp_reference_corpus notes-path --series dianji-zhongguo --slug dianji-shangshu

# 爆款素材：检索 → 登记 sources.json → 归档开头片段
uv run python -m scripts.tools.wechat_mp_reference_fetch search --query "典籍里的中国 伏生"
uv run python -m scripts.tools.wechat_mp_reference_fetch archive-episode --slug dianji-shangshu --tier B_voice
```

---

## 五、好文进 skill 的格式（长期沉淀）

每积累 5 篇提炼，把 **可复用规律**（不是全文）合并进：

- 专栏专题：`dianji-zhongguo-column.md`
- 或稿型专题：`hotspot-deep-review.md` / `social-commentary-voice.md`

每条规律须附 **1 个反例 + 1 个仿写例**，避免空规则。

---

## 六、用户可参与的方式

1. **丢链接**：把喜欢的公众号文章 URL 发给 Agent，注明「学开头 / 学收束 / 反例」→ 写入 `sources.json`
2. **丢段落**：粘贴 2～3 段你认为好的正文 → Agent 只提炼结构，不入库原文
3. **定金样**：你改好的 `body_core` 存 `data/wechat_mp_tv_review_golden/{slug}.body_core.md`，标 `human_final`

---

## 交叉引用

- 典籍专栏写法：[dianji-zhongguo-column.md](dianji-zhongguo-column.md)
- 热点深评取材：[hotspot-deep-review.md](hotspot-deep-review.md) §联网取材
- 社会口吻：[social-commentary-voice.md](social-commentary-voice.md)
- 去 AI 味：[anti-ai-voice.md](anti-ai-voice.md)
