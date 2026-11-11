# 公众号散文式评论写作 Skill 升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户主动的教育与社会热点稿以有作者判断的散文式评论成文，同时保留事实、来源、双确认和草稿安全边界。

**Architecture:** 保留 `.cursor/skills/wechat-mp-writing/SKILL.md` 一个入口，新增只供用户主动热点读取的文章写作参考；现有 DeepSeek 手工提示词及 `prepare` 确定性提示词同步采用该方向。事实审校和草稿工程继续由既有文档、代码承担，不新建并行 Skill。

**Tech Stack:** Markdown Skill、Python 确定性提示词、pytest、Skill frontmatter 校验。

## Global Constraints

- 以当前工作树为基线，相关文件已有未提交修改，不回退、不整文件覆盖，也不把用户既有修改混进本任务提交。
- 不修改公众号草稿、发布权限、配图协议、来源数量、双确认和工程硬门禁。
- 第一人称只表达作者关注、疑问、取舍与价值判断；不得伪装家长、教师、采访者或现场亲历者，不补写无来源细节。
- 文学手法可选，不强制比喻、典故、反问、单句成段、固定钩子或固定论证顺序。
- 其他稿型（财经自动稿、典籍、小说、影视）的语气不因本次调整而改变。
- 本计划只改本地 Skill 与热点提示词；离线对照不推送或覆盖微信草稿。

---

## File Map

| 文件 | 单一责任 |
| --- | --- |
| `.cursor/skills/wechat-mp-writing/essay-commentary-craft.md` | 用户主动热点散文式写稿与文章级改稿方法 |
| `.cursor/skills/wechat-mp-writing/SKILL.md` | 在写稿、编辑、审校、草稿工程间正确路由 |
| `.cursor/skills/wechat-mp-writing/deepseek-writer-sop.md` | 人工 DeepSeek 交接的完整提示词与收稿编辑顺序 |
| `stock-ai/scripts/tools/wechat_mp_browser_prompt.py` | `prepare` 命令的确定性提示词，热点与文学分支分开 |
| `stock-ai/tests/unit/test_wechat_mp_browser_prompt.py` | 守住新热点风格和文学分支不变的回归行为 |
| `.cursor/skills/wechat-mp-writing/social-commentary-voice.md`、`hotspot-deep-review.md`、`human-say-pass.md`、`anti-ai-voice.md`、`traffic-copy-craft.md`、`eval-gates.md` | 只清理用户主动热点路径上与散文式评论冲突的固定公式，保留真实约束 |

### Task 1: 写作参考与路由

**Files:**
- Create: `.cursor/skills/wechat-mp-writing/essay-commentary-craft.md`
- Modify: `.cursor/skills/wechat-mp-writing/SKILL.md`

**Interfaces:**
- Consumes: 已确认设计中的作者声音与事实边界。
- Produces: `SKILL.md` 的用户主动热点写稿路径链接；Task 2 的提示词与 Task 3 的旧规则整理以该文档为写作真源。

- [ ] **Step 1: 确认当前文件状态。** 读取 `git diff --` 所列两个路径，并确认新参考文件不存在；不要用 `HEAD` 内容覆盖工作树。
- [ ] **Step 2: 写入写作参考。** 使用 `apply_patch` 建立短文档：标题承诺与真实细节决定主问题；按证据引出的变化推进段落；允许有依据的第一人称判断；朗读调整句子长短；事实审校、来源与运营要求另由既有真源负责。明确禁止伪造亲历，不列固定段落模板或修辞数量。
- [ ] **Step 3: 路由。** 在 `SKILL.md` 的用户主动热点/DeepSeek 写稿与改稿路径上链接新参考；事实核验仍只在收稿后按 `editorial-evidence-gate.md` 加载，草稿工程仍走 `wechat-mp-drafts`。
- [ ] **Step 4: 验证。** 运行 `python3 /Users/huan.yu/.codex/skills/.system/skill-creator/scripts/quick_validate.py .cursor/skills/wechat-mp-writing`；检查新链接目标存在，并人工阅读入口是否仅加载命中参考。

### Task 2: 同步两条 DeepSeek 提示词路径

**Files:**
- Modify: `.cursor/skills/wechat-mp-writing/deepseek-writer-sop.md`
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_prompt.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_browser_prompt.py`

**Interfaces:**
- Consumes: Task 1 的散文式写作真源。
- Produces: 人工复制提示词与 `wechat_mp_browser_write prepare --kind hotspot` 的一致写作方向；`literary` 分支现有保护保持不变。

- [ ] **Step 1: 先写失败测试。** 在现有测试文件加以下行为测试，使用 `apply_patch`，不修改既有安全测试：

```python
def test_hotspot_prompt_requests_essay_voice_without_fake_experience() -> None:
    prompt = build_browser_prompt(
        kind="hotspot",
        topic="幼儿园费用规则",
        thesis="家长能否核对每项费用，比看到一张收费公示表更影响缴费判断。",
        fact_lines=("本区已公示收费项目与标准｜来源：区发展改革局",),
        research_urls=(
            "https://a.example/notice",
            "https://b.example/rule",
            "https://c.example/report",
        ),
    )
    assert "有依据的个人判断" in prompt
    assert "不得虚构亲历" in prompt
    assert "事实、责任边界和普通人处境逐层推进" not in prompt
    assert "900—1100字" in prompt
```
- [ ] **Step 2: 运行红灯。** `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_wechat_mp_browser_prompt.py -q`；预期新增热点风格断言失败，而现有来源与敏感字段测试仍通过。
- [ ] **Step 3: 最小修改提示词。** 用 `apply_patch` 修改热点 `craft` 段和 `deepseek-writer-sop.md` 热点提示词：请求“有依据的个人判断”，明确“不得虚构亲历”，围绕一条可核事实形成思考线索，不采用固定六步结构。热点 `prepare` 的长度改为现行用户主动稿目标“900—1100字”，文学分支仍保留现有“1600—2400字”；保留标题32字、无虚构、来源限制、纯段落和具体讨论问题等原有真约束。不要触碰事实包指令拒绝或敏感字段拒绝。
- [ ] **Step 4: 运行绿灯。** 重跑上一步完整测试文件，确认新增测试与原有测试均通过；再用同一事实包分别生成热点和文学提示词，人工比较两者语气边界。

### Task 3: 清理冲突公式与改稿顺序

**Files:**
- Modify: `.cursor/skills/wechat-mp-writing/social-commentary-voice.md`
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md`
- Modify: `.cursor/skills/wechat-mp-writing/human-say-pass.md`
- Modify: `.cursor/skills/wechat-mp-writing/anti-ai-voice.md`
- Modify: `.cursor/skills/wechat-mp-writing/traffic-copy-craft.md`
- Modify: `.cursor/skills/wechat-mp-writing/eval-gates.md`

**Interfaces:**
- Consumes: Task 1 的文章写作真源与 Task 2 的提示词。
- Produces: 用户主动热点的改稿路径：核事实和适用范围 → 查文章主线和段落转折 → 朗读节奏与轻量去模板；运营提示与安全硬约束继续独立。

- [ ] **Step 1: 定位冲突而非全文件重写。** 用 `rg -n '微信群|一拨|前 1/3|300.?500|每 300|固定|禁词优先|必须|钩子'` 限定六个文件，列出只影响用户主动热点的条目。
- [ ] **Step 2: 按命中段落做小补丁。** 用户主动热点默认转为散文式评论；“群里转述”保留为 `discussion` 或自动社会稿的可选口吻。将定额钩子、单句比例、统一结尾和词语黑名单改为失败时检查的软提示；首段真实事件、政策边界、来源、图片数量、Markdown `**`、地域门禁及固定运营句等硬要求不动。
- [ ] **Step 3: 明确改稿顺序。** 在 `hotspot-deep-review.md` 与 `human-say-pass.md` 指出事实查核先于语言润色；文章级问题先于逐词扫描；同义复述删除但不能删去必要事实限定。`anti-ai-voice.md` 只负责成稿后的模板风险，不作初稿提纲。
- [ ] **Step 4: 验证交叉引用和差异。** 运行 `git diff --check`；逐一核对六文件的链接和受影响稿型，确认未改配图、草稿或文学/影视路径。运行 `quick_validate.py` 检查 Skill 入口。

### Task 4: 离线行为对照与交付

**Files:**
- Read only: 两篇既有、公开来源完整的教育评论及其事实包。
- Test: `stock-ai/tests/unit/test_wechat_mp_browser_prompt.py` 和相关热点公开文案测试。

**Interfaces:**
- Consumes: Tasks 1–3 的本地写作规范与提示词。
- Produces: 可审阅的前后对照结论，不修改微信草稿。

- [ ] **Step 1: 选样。** 优先选既有的“广州编外教师”稿和一篇教育费用稿；若本地无完整事实包，则只用可回源的段落，不补新场景或作者经历。
- [ ] **Step 2: 离线比较。** 对两篇各检查：标题承诺是否兑现、每段新信息或转折是什么、第一人称是否只是有依据的判断、必要限定是否还在、句式是否重复。记录具体原句与建议改法，不把这些实验稿写入草稿箱。
- [ ] **Step 3: 完整验证。** `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_wechat_mp_browser_prompt.py tests/unit/test_wechat_mp_codex_hotspot.py -q`；再执行 Skill 校验和 `git diff --check`。
- [ ] **Step 4: 审阅改动范围。** `git diff --` 只看本计划命中的文件，确认已有工作树变更仍在，且没有 `.env`、凭证、草稿 JSON 或用户个人资料进入本任务变更。报告验证结果与尚未触碰的草稿。

## Execution Boundary

如用户选择当前任务内联执行，而相应 Superpowers 执行 skill 在环境中不可用，按上述任务顺序内联完成并逐项验证。只有用户明确要求委派时才创建子任务。由于命中文件已有用户未提交修改，实施阶段不自动提交这些交织的修改；只在用户明确要求 Git 提交时，才审阅和暂存精确目标。
