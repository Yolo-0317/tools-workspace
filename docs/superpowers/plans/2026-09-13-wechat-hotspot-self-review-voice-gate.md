# WeChat Hotspot Self-Review Voice Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 拦截热点稿提示词和正文中的自我审稿腔，并用自然表述重建当前北大复读稿。

**Architecture:** 在提示词入口拒绝把写作指令混入事实包，在公开文案门禁增加一个高置信度的连续解释性否定模式。两层规则分别处理污染源和最终输出；通过测试后再修改文章 JSON，并沿既有双确认工作流重建同一独立草稿槽位。

**Tech Stack:** Python 3、`re`、pytest、微信公众号草稿 API、现有 `wechat_mp_browser_write` 工作流。

## Global Constraints

- 已核验事实只写可公开陈述的事实，不混入面向写作者的否定指令。
- 不笼统封禁“不能把”，正常的责任判断和政策边界必须继续放行。
- 编辑质量七项评分只表示结构完整度，不作为去 AI 感总分。
- 修改草稿时保留现有标题、摘要、其他正文内容、封面及正文图片。
- 工作区已有未提交改动；只改与本任务直接相关的行，不覆盖或提交其他改动。

---

### Task 1: 提示词事实包写作指令门禁

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_prompt.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_browser_prompt.py`

**Interfaces:**
- Consumes: `build_browser_prompt(kind, topic, thesis, fact_lines, research_urls) -> str`
- Produces: 对含写作指令的 `fact_lines` 抛出 `ValueError("已核验事实包含写作或审校指令")`

- [ ] **Step 1: 写入失败测试**

在 `test_wechat_mp_browser_prompt.py` 增加：

```python
def test_rejects_editorial_instruction_inside_fact_lines() -> None:
    with pytest.raises(ValueError, match="已核验事实包含写作或审校指令"):
        build_browser_prompt(
            kind="hotspot",
            topic="陆远迪复读",
            thesis="复读决定必须在不知道第二年结果时评估风险和替代路径。",
            fact_lines=(
                "图灵班采用多轮招生机制，不能把个案写成复读后直接锁定图灵班。",
            ),
            research_urls=(
                "https://news.example.com/a",
                "https://school.example.edu/b",
                "https://media.example.org/c",
            ),
        )
```

- [ ] **Step 2: 运行失败测试**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_wechat_mp_browser_prompt.py::test_rejects_editorial_instruction_inside_fact_lines -q`

Expected: FAIL，因为当前 `build_browser_prompt` 会原样接受该事实行。

- [ ] **Step 3: 实现最小提示词门禁**

在 `wechat_mp_browser_prompt.py` 增加只覆盖写作动作的正则和校验：

```python
_FACT_EDITORIAL_INSTRUCTION_RE = re.compile(
    r"(?:不能|不要|不应)(?:再|直接|简单)?(?:把|将).{0,40}"
    r"(?:写成|改写成|理解成|解读为|视为|当成)"
)


def _reject_editorial_fact_lines(facts: Sequence[str]) -> None:
    if any(_FACT_EDITORIAL_INSTRUCTION_RE.search(line) for line in facts):
        raise ValueError("已核验事实包含写作或审校指令")
```

在 `build_browser_prompt` 清洗 `facts` 后、拼接 `source_block` 前调用 `_reject_editorial_fact_lines(facts)`。

- [ ] **Step 4: 增加正常事实放行测试**

```python
def test_allows_positive_boundary_fact_line() -> None:
    prompt = build_browser_prompt(
        kind="hotspot",
        topic="陆远迪复读",
        thesis="复读决定必须在不知道第二年结果时评估风险和替代路径。",
        fact_lines=("图灵班存在多轮招生机制，高考录取并非唯一选拔环节。",),
        research_urls=(
            "https://news.example.com/a",
            "https://school.example.edu/b",
            "https://media.example.org/c",
        ),
    )
    assert "高考录取并非唯一选拔环节" in prompt
```

- [ ] **Step 5: 运行提示词测试**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_wechat_mp_browser_prompt.py -q`

Expected: PASS。

- [ ] **Step 6: 检查并隔离本任务差异**

Run: `git diff --check -- stock-ai/scripts/tools/wechat_mp_browser_prompt.py stock-ai/tests/unit/test_wechat_mp_browser_prompt.py`

Expected: 无空白错误；不得覆盖文件中已有的其他未提交修改。

---

### Task 2: 正文连续自我辩护句门禁

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_quality_gate.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_hotspot_quality_gate.py`

**Interfaces:**
- Consumes: `scan_hotspot_public_copy(title, digest, body, research_urls) -> tuple[HotspotGateFinding, ...]`
- Produces: 命中连续解释性否定时返回 `code="self_review_voice"` 的 finding

- [ ] **Step 1: 写入当前问题句的失败测试**

```python
def test_rejects_paired_self_review_voice() -> None:
    body = (
        "公开资料显示，北大图灵班采用多轮招生机制，并非只有高考招生这一条进入路径。"
        "因此，不能把这个结果简单理解成‘复读1年就能直接锁定图灵班’，"
        "更不能把个案当成可以复制的升学方案。"
    )
    findings = scan_hotspot_public_copy(
        title="孩子已被北大录取，家长该不该支持他复读？",
        digest="讨论复读选择的风险。",
        body=body,
        research_urls=("https://www.pku.edu.cn/article",),
    )
    assert any(item.code == "self_review_voice" for item in findings)
```

- [ ] **Step 2: 运行失败测试**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_wechat_mp_hotspot_quality_gate.py::test_rejects_paired_self_review_voice -q`

Expected: FAIL，因为当前门禁没有 `self_review_voice` finding。

- [ ] **Step 3: 增加高置信度组合模式**

在 `wechat_mp_hotspot_quality_gate.py` 增加：

```python
_SELF_REVIEW_VOICE_PATTERNS = (
    re.compile(
        r"(?:不能|不应|不要)把[^。！？\\n]{0,60}"
        r"(?:理解成|解读为|视为|当成)[^。！？\\n]{0,90}[，；]"
        r"(?:更|也)?(?:不能|不应|不要)把[^。！？\\n]{0,90}"
        r"(?:理解成|解读为|视为|当成)"
    ),
)
```

在 `scan_hotspot_public_copy` 的过程语言扫描后增加独立扫描，命中时生成：

```python
_finding(
    "self_review_voice",
    field,
    text,
    "出现向读者解释文章应如何理解的连续自我辩护句",
    match,
)
```

- [ ] **Step 4: 增加防误伤测试**

```python
@pytest.mark.parametrize(
    "body",
    (
        "学校不能把管理成本转嫁给家长。",
        "不能把地方政策写成全国统一政策。",
        "家长不能把一次考试失利当成孩子能力不足的证明。",
    ),
)
def test_allows_single_real_world_boundary_judgment(body: str) -> None:
    findings = scan_hotspot_public_copy(
        title="教育政策怎样落到家庭？",
        digest="讨论家庭承担的现实成本。",
        body=body,
        research_urls=("https://www.moe.gov.cn/policy",),
    )
    assert not any(item.code == "self_review_voice" for item in findings)
```

- [ ] **Step 5: 运行正文门禁测试**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_wechat_mp_hotspot_quality_gate.py -q`

Expected: PASS。

- [ ] **Step 6: 运行相关回归测试**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_wechat_mp_browser_prompt.py tests/unit/test_wechat_mp_hotspot_quality_gate.py tests/unit/test_wechat_mp_browser_write_cli.py tests/unit/test_wechat_mp_browser_push.py -q`

Expected: PASS，零失败。

---

### Task 3: 更新写作规范说明

**Files:**
- Modify: `.cursor/skills/wechat-mp-writing/anti-ai-voice.md`
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md`

**Interfaces:**
- Consumes: Task 1 的事实包入口规则、Task 2 的 `self_review_voice` finding
- Produces: 人工编辑与自动门禁一致的文档真源

- [ ] **Step 1: 补充反例与改写原则**

在 `anti-ai-voice.md` 的 hotspot 元叙述部分补充：

```markdown
- 禁止自我审稿腔：不要用“不能简单理解成……更不能把个案当成……”向读者解释文章该如何被理解。
- 把审校边界改成事实和现实后果：先说明招生机制，再说明其他家庭仍要承担成绩与招生安排的不确定性。
```

- [ ] **Step 2: 补充事实包规则和评分说明**

在 `hotspot-deep-review.md` 的用户主动成稿入口与公开文案门禁部分补充：

```markdown
- 事实包只写正向可核验事实，不得混入“不能写成”“不要理解为”等编辑指令。
- 编辑质量 7 项只表示结构完整度，不代表去 AI 感、事实准确性和图片门禁全部通过。
```

- [ ] **Step 3: 检查文档差异**

Run: `git diff --check -- .cursor/skills/wechat-mp-writing/anti-ai-voice.md .cursor/skills/wechat-mp-writing/hotspot-deep-review.md`

Expected: 无空白错误；保留两份文档中已有的其他未提交修改。

---

### Task 4: 修改并重建北大复读草稿

**Files:**
- Modify: `stock-ai/output/hotspot_beida_repeat_codex.json`
- Reuse: `stock-ai/assets/wechat_mp/inline-discussion/陆远迪放弃北大医学部录取复读进入图灵班/cover_source.json`
- Create: `stock-ai/output/wechat_mp_browser_workflows/` 下由 `prepare` 返回 UUID 命名的新工作流 JSON

**Interfaces:**
- Consumes: 通过 Task 1 和 Task 2 门禁的文章 JSON；独立槽位 `hotspot_beida_repeat_20260913_new`
- Produces: 标题不变、正文表述自然、正文保留一张图片的新微信公众号草稿

- [ ] **Step 1: 替换问题段落**

使用 `apply_patch` 将原来的自我审稿段替换为：

```text
北大图灵班存在多轮招生机制，高考成绩并不是唯一的选拔环节。陆远迪最终进入心仪方向，是他的个人结果；对其他家庭而言，复读能否换来更合适的专业，仍取决于第二年的成绩和当年的招生安排。
```

- [ ] **Step 2: 运行文章公开文案门禁**

Run: 使用 `.venv/bin/python -c` 加载 `hotspot_beida_repeat_codex.json`，调用 `require_hotspot_public_copy` 和 `require_hotspot_editorial_quality`。

Expected: 两个门禁均通过，且正文不再包含“不能把这个结果简单理解成”和“更不能把个案当成”。

- [ ] **Step 3: 创建新的重建工作流**

Run: `cd stock-ai && .venv/bin/python -m scripts.tools.wechat_mp_browser_write prepare ...`

事实行必须改为正向表述：`图灵班存在多轮招生机制，高考录取并非唯一选拔环节。`

Expected: 生成新的 workflow id，提示词中不含写作或审校指令。

- [ ] **Step 4: 复用已确认的 DeepSeek 初稿并完成两道确认状态**

依次执行 `confirm-prompt`、`record-pasted`、`stage`、`confirm-push`；stage 输出必须显示封面一张、正文一张、编辑质量至少五项通过。

- [ ] **Step 5: 重建同一独立槽位草稿**

Run: 将 Step 3 返回的 UUID 记为任务专用变量 `BEIDA_WORKFLOW_ID`，执行 `cd stock-ai && .venv/bin/python -m scripts.tools.wechat_mp_browser_write push "$BEIDA_WORKFLOW_ID"`。

Expected: 返回新的 `media_id`；独立槽位 `hotspot_beida_repeat_20260913_new` 指向新草稿。

- [ ] **Step 6: 回读微信公众号草稿**

通过 `draft_batchget(no_content=False)` 核对：

- 标题仍为“孩子已被北大录取，家长该不该支持他复读？”
- 正文包含新段落，不包含旧问题句。
- 正文 HTML 含一个 `<img data-src=...>` 标签。
- 草稿箱没有因本次重建产生同题重复稿。

- [ ] **Step 7: 最终检查**

Run: `git diff --check` 针对本任务修改文件；重新运行 Task 2 的回归测试。

Expected: 所有检查通过。实现文件若含任务开始前的未提交修改，不得整体提交；只报告本任务差异和验证结果。
