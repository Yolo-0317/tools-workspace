# 改稿工作流（revision-workflow）

## 原则

1. **先数据、后文笔**：dragons/sector 数字错 → 修 `stock-ai` 数据，不硬改正文糊弄。
2. **要有见解**：财经接宏观政策 + 主观判断；影视写立意，不只剧情梗概 → [depth-and-opinion.md](depth-and-opinion.md)
3. **小步改**：优先标题、开篇 2 段、合规禁词；正文列表与表格尽量不动生成逻辑。
3. **禁止 emoji**（全账号规则）。
4. **evening 同批**：news（10 条热股快讯）+ hotspot（单主题深评）；标题勿雷同。

## evening 两篇审阅顺序

1. **hotspot**（次条 · 每日热点深评，先过门禁）
2. **news**（头条 · 10 条热股快讯，最后精修标题）

### news（头条）

- [ ] 标题：热股名前置问句，或 **真宏观事件**+股名；含 `？`/`！`；**前 15 字可读**
- [ ] **硬禁**：同一股名 ≥2 次、`背景下`、`人气榜/榜首` 当事件、`甲与甲`（见 [sousou-content-rules.md](sousou-content-rules.md) §标题硬禁）
- [ ] 开篇：2 句「今日主线」；与标题事件一致；勿空洞「市场震荡」
- [ ] 10 条快讯：**摘要/AI 点评不得 3 条以上完全相同**（见 `templates.md` §news 去重）
- [ ] 禁词：怎么玩、还在榜、领衔（合规脚本会拦）

### hotspot（次条）

- [ ] 标题：`热点深评｜{完整短主题}` + 口语 A 股问句；**禁止半句话**（返…、暂…、内塔…）
- [ ] **硬禁**：通稿冒号后硬切人名；`升温A股` 类粘连（须 `升温，A股` 或 `升温对A股`）
- [ ] 「为啥盯这条」：只写本条价值；**禁止**候选几条/舍弃/相较其它标题（见 [sousou-content-rules.md](sousou-content-rules.md)）
- [ ] **禁止**「数据未获取」「样本个股…未获取」「交易时段…未获取」——缺数写板块/指数现象
- [ ] 单主题四段：先说事实 / 外面怎么传 / A股怎么动 / 我们怎么看
- [ ] 与 news 头条 **不重复深写**同一事件（分工：news 清单，hotspot 深评）

## Agent 改稿步骤

```text
1. push_quality_gate --batch evening  → 记下未过 kind 与 block_reason
2. sousou-content-rules.md：标题完整、单主题、开篇与标题一致
3. 打开对应模板节：evening-trilogy-templates.md（hotspot 见代码 HOTSPOT_SECTION_TITLES）
4. 按 anti-ai-voice.md 改开篇/连接词
5. 单篇重评：wechat_mp_eval --kind <k> --traffic
6. 满意后：wechat_mp_draft --kind <k>  或 整批 draft_batch --batch evening
```

## 人工后台群发前（30 秒）

- [ ] 草稿箱 **两篇**标题在列表里前 15 字可读、**语义完整**（硬禁见 sousou-content-rules）
- [ ] news 快讯扫一眼有无复制粘贴感；hotspot 勿成第二份清单
- [ ] 封面槽 1 牛马 / 2 多屏 顺序未乱

## 改不动时

| 现象 | 动作 |
|------|------|
| 总分低、结构薄 | 加 `>` 引用块或小标题 `一、` |
| AI 味高 | 删「综上所述」「值得注意的是」；换具体数字 |
| 合规失败 | 查 `rules-implemented.md` 与 `wechat_mp_public.py` 禁词 |
| traffic SEO 红灯 | `writing-guide.md` 搜一搜词表；改标题前 15 字 |
