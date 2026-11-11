# 典籍里的中国 · 一集一点

> **专栏**：`典籍里的中国 · 一集一点` · 两季 22 集选题表 `stock-ai/data/wechat_mp_dianji_zhongguo_topics.json`
> **稿型**：`tv_review` + `content_mode: discussion` · 800～1200 字 · 纯段落
> **写前必读**：[voice-corpus.md](voice-corpus.md) + 本文件 + [account-role-card.md](account-role-card.md)
> **不必每篇读** `reference-reading-sop` / `sources.json`（仅扩容语料库时用）。

---

## 定位（一句话）

一集只钉 **一个可转述的问题或画面**，不是节目说明书，不是课文摘要，不是观后感。

---

## 与节目通稿/观后感的分界

| 通稿/观后感（反例） | 本专栏（正例） |
|-------------------|----------------|
| 节目旨在… / 创新之处… / 声情并茂 | 大年初一播了哪一集，戏里谁先出场 |
| 鼻头一酸、泪流满面、史诗感 | 妻子不让烧简、儿子死于兵劫（事实） |
| 演技炸裂、神助攻、太精彩了 | 倪大红演到哪句，撒贝宁哪句红了眼眶（可核对） |
| 古今对话是亮点 | 国图玻璃柜里一本、手机屏上一本（画面） |
| 民本思想源远流长… | 「民惟邦本」出现在哪场戏，蒙曼补一句即可 |
| 值得深思 / 强烈推荐 | 删。用具体物件收束 |

完整反例库：`stock-ai/data/wechat_mp_reference_corpus/dianji-zhongguo/distilled-patterns.md` §反例

---

## 结构（4～6 段，无小标题）

1. **落地**：时间 + 集名/典籍 + 一个镜头（50 字内）
2. **钉子**：本篇唯一问题（与 `topics.json` 的 `nail` 一致）
3. **代价链**：谁为这件事付出了什么（具体动作、数字、地名）
4. **一句引语**：戏里台词或嘉宾一句，≤30 字，不堆专家段
5. **今天的一个画面**：图书馆、课本、手机、某句还在被引用——禁「读者你选择」
6. **可选收束**：一句生活账（和古人比的轻重），不升华

---

## 钉子示例（E1 尚书）

-  nail：`伏生护书与「民惟邦本」如何落在具体人身上`
-  不写：尚书五经地位、彭马田全段、节目制作一年
-  要写：二十八篇、章丘、晁错口传、妻不让烧简

---

## 写稿流程（Agent 自动，非用户逐句改）

```text
初稿（事实来自 topics.nail + 史料）
  → 全文 human-say-pass（对照 human-say-pass.md §二 表，整篇改写一遍）
  → scan_report_voice（剧评/meta 正则）
  → 与 voice-corpus-dianji §五 金样比节奏（不是比句子）
  → 落 body_cache → repush
```

用户只判断「这篇能不能发」；**不要**等用户一句句抠才改下一句。

---

## 推稿

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_reference_corpus checklist --series dianji-zhongguo --ep <N>
# 正文真源
# stock-ai/data/wechat_mp_tv_body_cache/{cover_slug}.json
uv run python -m scripts.tools.wechat_mp_repush_tv_review_draft --title-en <cover_slug> --slot-key tv_review
```

配图：`inline-discussion/{cover_slug}/` + `codex-images-ready.json` 防抓取覆盖。

---

## 金样（人类定稿优先）

| 文件 | 状态 |
|------|------|
| `data/wechat_mp_tv_review_golden/dianji-shangshu.body_core.md` | human-say-pass 示范稿（2026-08-19） |
| `data/wechat_mp_tv_body_cache/dianji-shangshu.json` | 当前推稿缓存 |

**规则**：金样存在且标 `human_final: true` 时，Agent 只改错别字，不重写结构。
