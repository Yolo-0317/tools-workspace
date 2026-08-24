# 《典籍里的中国·孙子兵法》DeepSeek 讨论 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用已核验事实和明确创作边界，在固定 DeepSeek 网页会话中完成一次只讨论、不成稿的选题评审，并产出可供后续写稿决策的标题、开篇和风险建议。

**Architecture:** 将可靠事实、节目艺术想象边界与创作要求固化为一份研究笔记和一份发送提示词。通过现有 `wechat_mp_browser_workflow` 创建可追踪工作流，第一次确认后才由 OpenCLI 绑定固定 DeepSeek 会话发送；只提取本轮新增回复，再由 Agent 按事实安全、传播力和栏目一致性整理结论。

**Tech Stack:** Markdown、Python 3、`wechat_mp_browser_workflow`、`wechat_mp_browser_write`、OpenCLI、Chrome 中固定 DeepSeek 会话

## Global Constraints

- 核心钉子固定为“真正高明的兵法，不是教人逢战必赢，而是让人在开战前先问：这一仗的代价，国家和普通人承受得起吗？”
- 第一轮只讨论传播力、开篇、标题和风险，不要求 DeepSeek 写全文。
- 首选标题方向为“孙武最懂怎么赢，为何最后劝伍子胥停手？”。
- 兄弟决裂桥段必须标明为节目在史料空白处所作的艺术想象，不得写成确定史实。
- 不把《孙子兵法》包装成职场权谋或制胜技巧。
- 找不到可核对的节目逐字台词时不得编造引语。
- 普通人落点使用士卒、家庭、田地和归途等具体对象，不虚构采访或个案。
- 全流程使用固定 DeepSeek 网页会话 `f0cc031d-233f-4648-807d-354275738e61`，不调用 DeepSeek API。
- DeepSeek 未登录或当前标签不是固定会话时立即停止，提示用户登录或切换后再继续。
- 发送提示词前必须获得用户第一次明确确认。

---

## File Structure

- Create: `stock-ai/data/wechat_mp_reference_corpus/dianji-zhongguo/notes/dianji-sunzi-discussion.md` — 可复用的事实包、艺术边界和来源页。
- Create: `stock-ai/output/deepseek_sunzi_discussion_prompt.txt` — 本次仅讨论提示词；`output/` 文件不提交。
- Create: `stock-ai/output/wechat_mp_browser_workflows/` 下由现有模块按返回 ID 命名的 JSON 状态文件。
- Create: `stock-ai/output/deepseek_sunzi_discussion_workflow_id.txt` — 保存模块返回的精确工作流 ID，供后续命令读取。
- Create: `stock-ai/output/deepseek_sunzi_discussion_review.md` — Agent 对 DeepSeek 本轮回复的评审；`output/` 文件不提交。

### Task 1: 固化《孙子兵法》讨论事实包

**Files:**
- Create: `stock-ai/data/wechat_mp_reference_corpus/dianji-zhongguo/notes/dianji-sunzi-discussion.md`

**Interfaces:**
- Consumes: 央视网《安国全军的千年智慧》、央视节目主页、人民网《孙子兵法：古代第一兵书》、新华网《一路“狂飙”的〈孙子兵法〉，究竟怎么读？》及设计文档。
- Produces: Markdown sections `核心钉子`, `已核验事实`, `艺术想象边界`, `可用原文`, `禁用信息`, `公开来源`.

- [ ] **Step 1: Write the research note**

在 `已核验事实` 中只写入以下事实：

- 《典籍里的中国》第六期聚焦《孙子兵法》，官方概括的核心包括“重战”“慎战”“安国全军”。
- 节目把孙武著书立说、征战沙场与《孙子兵法》的思想结合呈现。
- 央视官方资料明确说明，攻入郢都后孙武劝伍子胥未果、兄弟决裂，是在孙武晚年史料有限情况下设计的艺术想象情节。
- 《孙子兵法》现存十三篇。
- 据《史记》相关记载，孙武与孙膑不是同一人，孙膑生活在孙武之后百余年。

在 `可用原文` 中列出“兵者，国之大事”“上兵伐谋”“不战而屈人之兵”“亡国不可以复存，死者不可以复生”，并注明终稿前仍需逐字回到可靠古籍文本核验。

- [ ] **Step 2: Record exact public source pages**

写入以下来源：

```text
https://tv.cctv.com/v/a/ARTIdtxvxgnPqBcVWlp0dioz210807.html
https://tv.cctv.com/lm/djldzg/
https://paper.people.com.cn/fcyym/html/2023-10/27/content_26025910.htm
https://www.news.cn/mil/2023-02/06/c_1211725661.htm
```

- [ ] **Step 3: Verify the research note**

Run:

```bash
rg -n "重战|慎战|安国全军|艺术想象|十三篇|孙武|孙膑|兵者，国之大事|亡国不可以复存" stock-ai/data/wechat_mp_reference_corpus/dianji-zhongguo/notes/dianji-sunzi-discussion.md
```

Expected: every required fact and boundary appears at least once; the note contains no unreferenced birth year, age, battle troop count, or private dialogue.

- [ ] **Step 4: Commit the research note**

```bash
git add stock-ai/data/wechat_mp_reference_corpus/dianji-zhongguo/notes/dianji-sunzi-discussion.md
git commit -m "资料：补充孙子兵法典籍稿事实包"
```

### Task 2: 创建待确认的 DeepSeek 讨论工作流

**Files:**
- Create: `stock-ai/output/deepseek_sunzi_discussion_prompt.txt`
- Create: `stock-ai/output/wechat_mp_browser_workflows/` 下由现有模块按返回 ID 命名的 JSON 状态文件。
- Create: `stock-ai/output/deepseek_sunzi_discussion_workflow_id.txt`

**Interfaces:**
- Consumes: Task 1 research note and the approved design spec.
- Produces: a `BrowserWritingWorkflow` with `kind="literary"`, `topic="典籍里的中国·孙子兵法"`, and status `awaiting_prompt_confirmation`.

- [ ] **Step 1: Write the exact discussion prompt**

Save this prompt verbatim to `stock-ai/output/deepseek_sunzi_discussion_prompt.txt`:

```text
我们准备写《典籍里的中国·孙子兵法》的公众号文章。请先做选题与爆点讨论，不要写全文。

一句话钉子：真正高明的兵法，不是教人逢战必赢，而是让人在开战前先问：这一仗的代价，国家和普通人承受得起吗？

首选标题方向：孙武最懂怎么赢，为何最后劝伍子胥停手？

拟用开篇：节目中，吴军攻入郢都后，伍子胥被复仇推着继续向前，孙武劝阻未果，两人走向决裂。请注意，央视官方资料明确说明，这段兄弟决裂是节目在孙武晚年史料有限的情况下所作的艺术想象，不能当作确定史实。找不到节目中可核对的逐字台词时，不得编造引语。

已核验事实：
1. 《典籍里的中国》第六期聚焦《孙子兵法》，官方概括的思想包括“重战”“慎战”“安国全军”。
2. 节目把孙武著书立说、征战沙场与典籍思想结合呈现。
3. 《孙子兵法》现存十三篇。
4. 孙武与孙膑不是同一人，孙膑生活在孙武之后百余年。
5. 可围绕“兵者，国之大事”“上兵伐谋”“不战而屈人之兵”“亡国不可以复存，死者不可以复生”展开，但成稿前还会逐字核验原文。

文章预计900—1100字，纯短段，不设小标题。不能写成职场权谋教程、文化节目安利、典籍知识堆砌或空泛和平口号。普通人落点是：冲突往往由少数人决定，代价却由士卒、家庭和百姓承担；写具体对象，但不虚构个案或采访。结尾希望形成站队：一个有能力赢的人选择不打，是软弱，还是更高一级的清醒？

请只回答以下六项：
1. “最会打仗的人为什么先劝人别打”是否具备公众号传播的反常识爆点，缺口是什么？
2. 兄弟决裂场面怎样开篇才抓人，又不把艺术想象冒充史实？
3. 哪些段落最容易写成说教、节目安利或空泛口号，具体怎样避免？
4. 普通人承担冲突代价这一落点，怎样写得具体而不生硬借题发挥？
5. 给出6个20字以内候选标题，按点击吸引力、事实安全和栏目一致性综合排序，并说明前3名理由。
6. 给出一个不超过150字的推荐开篇样稿；不得编造节目台词。
```

- [ ] **Step 2: Check the prompt boundaries**

Run:

```bash
python3 -c 'from pathlib import Path; p=Path("stock-ai/output/deepseek_sunzi_discussion_prompt.txt").read_text(); print({"discussion_only":"不要写全文" in p,"art_boundary":"艺术想象" in p,"no_fake_quote":"不得编造引语" in p,"six_tasks":all(f"{i}." in p for i in range(1,7)),"api_secret":any(x in p.lower() for x in ("cookie","api_key","token="))})'
```

Expected: the first four values are `True`; `api_secret` is `False`.

- [ ] **Step 3: Create the workflow without sending**

Run from `stock-ai/`:

```bash
.venv/bin/python -c 'from pathlib import Path; from scripts.tools.wechat_mp_browser_workflow import create_workflow; p=Path("output/deepseek_sunzi_discussion_prompt.txt").read_text(); w=create_workflow(kind="literary",topic="典籍里的中国·孙子兵法",prompt=p,research_urls=("https://tv.cctv.com/v/a/ARTIdtxvxgnPqBcVWlp0dioz210807.html","https://tv.cctv.com/lm/djldzg/","https://paper.people.com.cn/fcyym/html/2023-10/27/content_26025910.htm","https://www.news.cn/mil/2023-02/06/c_1211725661.htm")); Path("output/deepseek_sunzi_discussion_workflow_id.txt").write_text(w.workflow_id); print(w.workflow_id); print(w.status.value)'
```

Expected: one workflow ID and status `awaiting_prompt_confirmation`. This step must not contact DeepSeek.

- [ ] **Step 4: Display the complete prompt and request confirmation**

Show the complete prompt to the user. Do not run `confirm-prompt` or `write` until the user explicitly confirms this displayed version.

### Task 3: 发送提示词并提取本轮新回复

**Files:**
- Modify: Task 2 创建并由 `deepseek_sunzi_discussion_workflow_id.txt` 精确指向的工作流 JSON。

**Interfaces:**
- Consumes: the exact workflow ID created in Task 2 and the user’s explicit first confirmation.
- Produces: the same workflow in status `response_received`, with `raw_response` containing only the current DeepSeek turn.

- [ ] **Step 1: Record prompt confirmation**

Run from `stock-ai/`，命令直接读取 Task 2 保存的精确 ID：

```bash
.venv/bin/python -c 'from pathlib import Path; from scripts.tools.wechat_mp_browser_write import main; raise SystemExit(main(["confirm-prompt",Path("output/deepseek_sunzi_discussion_workflow_id.txt").read_text().strip()]))'
```

Expected: `OK 提示词已确认`.

- [ ] **Step 2: Verify the fixed DeepSeek tab is ready**

Keep Chrome’s current tab on:

```text
https://chat.deepseek.com/a/chat/s/f0cc031d-233f-4648-807d-354275738e61
```

If the page is logged out or the current tab is another conversation, stop and ask the user to log in or switch to this exact conversation. Do not open another automated window, read Cookie, or fall back to an API.

- [ ] **Step 3: Send and wait for the discussion response**

Run from `stock-ai/`，命令直接读取已保存的精确 ID：

```bash
.venv/bin/python -c 'from pathlib import Path; from scripts.tools.wechat_mp_browser_write import main; raise SystemExit(main(["write",Path("output/deepseek_sunzi_discussion_workflow_id.txt").read_text().strip(),"--timeout","240"]))'
```

Expected: `OK 已提取本轮 DeepSeek 回复`, and the workflow status becomes `response_received`. If login is required, use `resume-login` only after the user reports the fixed tab is ready.

- [ ] **Step 4: Verify workflow state**

```bash
.venv/bin/python -c 'from pathlib import Path; from scripts.tools.wechat_mp_browser_write import main; raise SystemExit(main(["show",Path("output/deepseek_sunzi_discussion_workflow_id.txt").read_text().strip()]))'
```

Expected: `kind: literary`, `topic: 典籍里的中国·孙子兵法`, `status: response_received`, and `response_chars` greater than `300`.

### Task 4: 评审 DeepSeek 的讨论建议

**Files:**
- Create: `stock-ai/output/deepseek_sunzi_discussion_review.md`

**Interfaces:**
- Consumes: `raw_response` from the `response_received` workflow and the Task 1 fact note.
- Produces: a user-facing decision memo with `可采纳`, `需修改`, `不能采用`, `推荐标题`, `推荐开篇`, and `下一轮成稿提示词调整` sections.

- [ ] **Step 1: Extract and classify every recommendation**

For each DeepSeek title, opening sentence and structural suggestion, classify it by:

- 传播力：是否有明确人物、动作、代价和疑问。
- 事实安全：是否把节目艺术想象写成确定史实，是否虚构台词。
- 栏目一致性：是否保持典籍场面进入、叙事者隐形、普通人落点和短段阅读。
- 说教风险：是否变成和平口号、节目安利或职场权谋。

- [ ] **Step 2: Write the decision memo**

Select one recommended title and one opening of at most 150 Chinese characters. Any modified wording must be visibly labeled as Agent editing rather than DeepSeek’s original wording. Do not promote DeepSeek’s discussion to a factual source.

- [ ] **Step 3: Run review checks**

Run:

```bash
rg -n "可采纳|需修改|不能采用|推荐标题|推荐开篇|下一轮成稿提示词调整|艺术想象|不得编造" stock-ai/output/deepseek_sunzi_discussion_review.md
```

Expected: every review section and both factual boundaries are present.

- [ ] **Step 4: Present the findings and stop before drafting**

Show the recommended title, opening, key DeepSeek judgments and rejected risks to the user. Ask whether to let DeepSeek write the full first draft. Do not create, stage, push or overwrite the `literary`公众号槽位 during this discussion plan.
