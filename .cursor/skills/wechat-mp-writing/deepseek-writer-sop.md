# DeepSeek 写稿分工

> **适用**：用户主动要求的热点深评，以及文学/典籍稿。
> **Agent**：研究、定题、给提示词，并在推送前完成事实编辑。
> **DeepSeek 交接**：Agent 只把完整提示词交给用户；用户自行与 DeepSeek 交流并贴回输出。
> **两次确认**：提示词交付前一次，微信草稿写入前一次。

## 默认流水线

```text
Agent 研究并定题（钉子、禁假钩子、32字内）
  → 展示来源包和完整提示词，等待第一次确认
  → 用户自行把提示词交给 DeepSeek，并将完整输出贴回当前任务
  → 未收到贴回稿件时暂停，不调用 DeepSeek，也不回退其他模型代写
  → Agent 核事实并编辑，在原句里包 2～3 处 [[hl:…]]；热点先查抖音搜索卡片封面
  → 展示 DeepSeek 来源、Agent 编辑记录、标题、摘要、字数、来源、真实图片与门禁报告，等待第二次确认
  → hotspot 写目标热点槽位；文学/典籍写 literary 独立槽位
```

Agent 禁止打开、绑定、操作或检查 DeepSeek 网页，禁止调用 DeepSeek API、OpenCLI DeepSeek 浏览器写稿命令或其他自动发送方式，也不处理 DeepSeek 登录状态、Cookie、会话 ID。DeepSeek 交流完全由用户完成；用户贴回的完整输出是 Agent 进入核实编辑阶段的唯一输入。禁止回退其他模型代写初稿。

## Agent 定题时交什么

- 一句话钉子（本篇只讲一件事）
- 建议标题方向（热点用实体/反常结果；文学用场面/代价/数字；禁作者「我」）
- 轻量 prompt（下面模板，按集替换）
- 不要塞语料库全文

## 热点深评 prompt（完整复制给用户）

```text
写一篇微信公众号热点深评，正文约1800—2200字，纯段落，不要小标题。

主题：【具体热点】
核心判断：【一句可被反驳和检验的判断】
已核实事实与来源：【只放本次研究得到的事实、时间线、法条和链接】

要求：
1. 直接产出标题和初稿；第一行标题，空一行后写正文
2. 标题32字以内，前15字出现可搜索实体或案由，不用震惊体
3. 开头50字内落地谁、在哪里、发生了什么；区分事实、当事人说法和待核部分
4. 不编造采访、场景、引语、动机或内部信息，不把推断写成定论
5. 解释规则、利益与普通人的具体代价，不堆口号，不写“值得注意的是”等导读腔
6. 只输出标题和正文，不写写作说明、来源列表或配图建议
```

## 文学/典籍轻量 prompt（完整复制给用户）

```text
写一篇微信公众号讨论稿，约800字，纯段落，不要小标题。

主题：【钉子，如：典籍里的中国·尚书·伏生护书】
标题：32字以内，不要作者「我」；数字必须属实（尚书是二十八篇，不是二十八个字）。

要求：
1. 第一段必须是戏里场面+对白+现场一个人的反应，不要用「某年某月开播」开头
2. 叙事人隐形；戏里台词可以有「我」
3. 不要安利、不要「我哭了」、不要升华口号
4. 结尾可停在一句问号上，再加一句轻互动（评论区聊聊…）
5. 只输出：第一行标题，空一行，然后正文
```

## DeepSeek 返回初稿后 Agent 做什么

1. 接收用户贴回的完整 DeepSeek 输出；未收到时暂停。
2. 核验标题、数字、人物、时间、引语和来源；文学/典籍稿还要核开篇是否有具体场面。
3. 编辑为结构化终稿，在原句里包 2～3 处 `[[hl:…]]`，补至少三个公开来源域，并以可重复的 `--edit-note` 记录核实和改动。
4. 用户主动热点配图必须先检索抖音，只查看搜索结果卡片与封面，禁止打开或播放视频；再按需补政府官网、官方媒体或法条页面证据图。正文允许 0—3 张，至少一张真实图作为封面；禁止任何自动生成图片或 `codex-image-request.json`。
5. 暂存终稿并展示 DeepSeek 来源、Agent 编辑记录、标题、摘要、字数、来源、封面与正文图数量，以及“本稿未自动生成图片”，等待第二次确认。
6. 用户确认后才登记推送许可并写入微信草稿箱：热点写指定热点槽位，文学/典籍写 `literary`。

用户贴回初稿后的暂存与推送命令：

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_browser_write stage \
  <workflow-id> --article <edited-json> \
  --edit-note "核对关键事实与来源" \
  --edit-note "删除无法回源的推断"
uv run python -m scripts.tools.wechat_mp_browser_write confirm-push \
  <workflow-id>
uv run python -m scripts.tools.wechat_mp_browser_write push \
  <workflow-id>
```

`confirm-push` 只能在用户第二次明确确认后执行。`push` 失败时保留在 `push_confirmed`，修复网络或微信白名单后可重试，不重复生成正文。

## 禁止的自动写稿路线

`scripts.tools.wechat_mp_deepseek_write`、`scripts.tools.wechat_mp_deepseek_browser` 以及 `wechat_mp_browser_write write` 均不属于本流程。热点深评和文学/典籍稿不得用任何自动化方式把提示词发给 DeepSeek，也不得绕过两次确认。

推稿代码：`scripts/tools/wechat_mp_browser_write.py`（仅用于用户贴回稿件后的暂存、确认和写草稿，不执行 `write`）
规律沉淀：`stock-ai/data/wechat_mp_reference_corpus/dianji-zhongguo/distilled-patterns.md`
