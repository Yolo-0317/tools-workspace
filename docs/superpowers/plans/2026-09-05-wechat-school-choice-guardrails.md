# 北上广深择校文章与门禁实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将北京、上海、广州、深圳的义务教育与高中择校正式纳入公众号教育垂类，并拦截明确的招生承诺和择校中介营销表达。

**Architecture:** 新增一份按需读取的择校专题规则，由现有热点深评文档和写作 Skill 路由；需要理解政策语境的风险由 Agent 回源核验，只有高置信度招生承诺进入自动公开文案门禁。自动门禁沿用 `scan_hotspot_public_copy` 的 finding 模型，在 stage 和 push 前自然生效，不新建发布链路或数据采集系统。

**Tech Stack:** Markdown Skill 文档、Python 3、标准库 `re`、pytest、现有微信公众号热点写稿与公开文案门禁。

## Global Constraints

- 首期只覆盖北京、上海、广州、深圳的幼升小、小升初和高中选校；大学志愿不进入本专题。
- 区级规则不得写成全市规则，四座城市的规则不得互相套用。
- 当前入学资格、材料、日期、招生范围、积分、批次、收费和计划必须回到当年官方原文。
- 不建立学校排名、梯队表、个人录取概率预测或学区房投资建议。
- 自动门禁只拦截明确肯定或营销式招生承诺；否定、反诈骗和批评语境必须放行。
- 用户主动热点继续执行 DeepSeek 手工交接、Agent 核实编辑、抖音真实配图和双确认流程。
- 用户可见内容和提交信息不使用 emoji；Git 提交信息使用中文。
- 保留工作区已有修改，每次只暂存本任务列出的文件。

---

## 文件结构

- Create: `.cursor/skills/wechat-mp-writing/school-choice-policy.md` — 北上广深择校专题的范围、来源、四城差异、文章结构和风险门禁真源。
- Modify: `.cursor/skills/wechat-mp-writing/SKILL.md` — 将“择校、学区、幼升小、小升初、高中选校”路由到热点深评，再由专题规则承接。
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md` — 记录用户确认的择校范围，并增加专题文档路由，不复制完整细则。
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_quality_gate.py` — 增加择校上下文识别、分句和高风险承诺扫描。
- Modify: `stock-ai/tests/unit/test_wechat_mp_hotspot_quality_gate.py` — 覆盖肯定承诺、否定语境、反诈骗语境和非择校稿回归。
- Modify: `.cursor/skills/wechat-mp-drafts/rules-implemented.md` — 记录择校专题与自动门禁的代码映射。
- Modify: `.cursor/rules/memory-python.mdc` — 记录稳定用户偏好和执行真源，不重复专题全文。

---

### Task 1: 新增择校专题规则并接入写作路由

**Files:**
- Create: `.cursor/skills/wechat-mp-writing/school-choice-policy.md`
- Modify: `.cursor/skills/wechat-mp-writing/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md`

**Interfaces:**
- Consumes: `wechat-mp-writing/SKILL.md` 的单专题路由规则和 `hotspot-deep-review.md` 的用户主动热点工作流。
- Produces: `school-choice-policy.md`，供北上广深义务教育和高中择校选题、提示词、编辑与发布前核验使用。

- [ ] **Step 1: 在写作 Skill 中增加可发现路由**

在 `.cursor/skills/wechat-mp-writing/SKILL.md` 的“何时用本 skill”表中加入：

```markdown
| **择校 / 学区 / 幼升小 / 小升初 / 高中选校** | **[hotspot-deep-review.md](hotspot-deep-review.md)**，再按其中路由读取 [school-choice-policy.md](school-choice-policy.md) |
```

该行只负责发现，不要求普通教育热点加载择校专题。

- [ ] **Step 2: 创建择校专题真源**

创建 `.cursor/skills/wechat-mp-writing/school-choice-policy.md`，正文至少包含以下确定内容：

```markdown
# 北上广深择校政策与家庭决策

## 适用范围

只处理北京、上海、广州、深圳的幼升小、小升初和高中选校。大学志愿、留学择校、国际学校商业推荐、学校排行榜和学区房投资建议不适用。

每次成稿前先确定：城市、区县或市级范围、学段、入学年度、政策状态、适用家庭。缺少会改变结论的任一项时，不给出确定判断。

## 来源层级

1. 当年教育行政部门、考试院、区政府和官方招生平台的正式文件。
2. 配套政策问答、流程图和报考指南。
3. 经主管部门备案或公开发布的当年学校招生简章，仅用于学校自述、计划、收费和课程安排。
4. 新华社、人民日报、光明日报、中国教育报等可靠媒体的采访和深度报道。
5. 家长经验、论坛、中介、房产平台和培训机构只作待核线索。

涉及资格、材料、日期、范围、积分、批次、收费和计划时，必须回到当年官方原文。
```

继续写入设计文档已经确认的四城专项边界、选题规则、学校比较允许维度、硬门禁、900—1100字正文顺序和发布前检查清单。不得复制旧年份政策作为当前事实；旧文章只列为写法参考。

- [ ] **Step 3: 在热点深评真源中加入短路由**

在“用户近期选题偏好：全国教育政策与升学规则”后增加：

```markdown
#### 北上广深择校专题

用户确认择校首期只覆盖北京、上海、广州、深圳的义务教育与高中选校；大学志愿仍归入高考政策与志愿填报。涉及择校、学区、幼升小、小升初、高中选校、积分入学、公民同招或学校比较时，必须完整读取 [school-choice-policy.md](school-choice-policy.md)。普通教育政策稿不加载该专题。
```

- [ ] **Step 4: 验证路由和专题关键边界可发现**

Run:

```bash
rg -n "school-choice-policy|北上广深择校专题|大学志愿仍归入" .cursor/skills/wechat-mp-writing/SKILL.md .cursor/skills/wechat-mp-writing/hotspot-deep-review.md
rg -n "北京|上海|广州|深圳|区级规则|买房必上|内部名额|900—1100" .cursor/skills/wechat-mp-writing/school-choice-policy.md
python3 /Users/huan.yu/.codex/skills/.system/skill-creator/scripts/quick_validate.py .cursor/skills/wechat-mp-writing
```

Expected: 两条路由均指向专题文件；专题能命中四城、地域边界、承诺门禁和字数规则；Skill 校验通过。

- [ ] **Step 5: 提交专题规则**

```bash
git add .cursor/skills/wechat-mp-writing/SKILL.md .cursor/skills/wechat-mp-writing/hotspot-deep-review.md .cursor/skills/wechat-mp-writing/school-choice-policy.md
git commit -m "规则：新增北上广深择校写作专题"
```

---

### Task 2: 用测试定义招生承诺自动门禁

**Files:**
- Modify: `stock-ai/tests/unit/test_wechat_mp_hotspot_quality_gate.py`

**Interfaces:**
- Consumes: `scan_hotspot_public_copy(title: str, digest: str, body: str, research_urls: Sequence[str]) -> tuple[HotspotGateFinding, ...]`。
- Produces: finding code `school_choice_admission_promise` 的行为契约；肯定承诺拒绝，否定、批评和非择校上下文放行。

- [ ] **Step 1: 写肯定承诺的失败测试**

向 `test_wechat_mp_hotspot_quality_gate.py` 添加：

```python
@pytest.mark.parametrize(
    ("title", "body"),
    (
        ("买学区房必上这所小学", "北京某区今年公布义务教育入学细则。"),
        ("深圳小升初怎么选？", "我们有内部名额，可以保证录取。"),
        ("广州高中选校指南", "缴纳费用即可花钱保录取。"),
        ("上海民办初中怎么报？", "报名这项课程可以百分百录取。"),
    ),
)
def test_rejects_school_choice_admission_promises(title: str, body: str) -> None:
    findings = scan_hotspot_public_copy(
        title=title,
        digest="家长关注当年招生规则。",
        body=body,
        research_urls=("https://edu.example.gov.cn/policy",),
    )

    assert "school_choice_admission_promise" in {item.code for item in findings}
```

- [ ] **Step 2: 写否定、反诈骗与非择校回归测试**

添加：

```python
@pytest.mark.parametrize(
    "body",
    (
        "买学区房也不能保证入学，最终要看当年区级审核和派位结果。",
        "警方查处宣称百分百录取的入学骗局，家长不要相信内部名额。",
        "教育部门明确禁止学校收取所谓择校费，也不存在花钱保录取。",
    ),
)
def test_allows_school_choice_warning_context(body: str) -> None:
    assert not scan_hotspot_public_copy(
        title="北京义务教育入学规则怎么变？",
        digest="解读当年区级招生政策。",
        body=body,
        research_urls=("https://jw.beijing.gov.cn/policy",),
    )


def test_school_choice_promise_scan_does_not_affect_unrelated_hotspot() -> None:
    findings = scan_hotspot_public_copy(
        title="平台会员承诺引发退款争议",
        digest="消费者要求平台兑现服务。",
        body="商家宣称百分百退款，双方对合同理解不同。",
        research_urls=("https://example.com/report",),
    )

    assert "school_choice_admission_promise" not in {item.code for item in findings}
```

- [ ] **Step 3: 运行新增测试并确认失败**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest tests/unit/test_wechat_mp_hotspot_quality_gate.py -q
```

Expected: 新增的肯定承诺用例失败，因为 `school_choice_admission_promise` 尚未实现；原有测试继续通过。

- [ ] **Step 4: 暂存测试但不提交**

保留失败测试供 Task 3 实现。不要在没有实现的状态提交。

---

### Task 3: 实现择校上下文和否定语境识别

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_quality_gate.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_hotspot_quality_gate.py`

**Interfaces:**
- Consumes: Task 2 定义的 finding code 和测试语句。
- Produces: `_has_school_choice_context(text: str) -> bool`、`_matching_clause(text: str, match: re.Match[str]) -> str`、`_is_school_choice_warning(clause: str) -> bool`，并由 `scan_hotspot_public_copy` 返回 `school_choice_admission_promise`。

- [ ] **Step 1: 增加高置信度常量**

在现有标题和范围常量附近加入：

```python
_SCHOOL_CHOICE_CONTEXT_MARKERS = (
    "择校",
    "学区",
    "学位",
    "幼升小",
    "小升初",
    "小学",
    "初中",
    "高中",
    "学校入学",
    "积分入学",
    "电脑派位",
    "公民同招",
)
_SCHOOL_CHOICE_PROMISE_PATTERNS = (
    re.compile(
        r"(?:买|购买).{0,4}(?:学区房|房产).{0,10}"
        r"(?:必上|稳上|包上|保证(?:入学|学位|录取))"
    ),
    re.compile(
        r"(?:落户|租房|缴纳?社保|报名(?:课程|培训)).{0,10}"
        r"(?:必上|稳上|包上|保证(?:入学|学位|录取)|百分百录取)"
    ),
    re.compile(
        r"(?:内部名额|关系入学|花钱保录取|包录取|保录取|保证进名校|百分百录取)"
    ),
)
_SCHOOL_CHOICE_WARNING_MARKERS = (
    "不能",
    "无法",
    "并非",
    "不是",
    "没有",
    "不存在",
    "严禁",
    "禁止",
    "不要相信",
    "警惕",
    "骗局",
    "诈骗",
    "查处",
)
```

- [ ] **Step 2: 实现分句与警示语境辅助函数**

在 `_normalized_paragraphs` 前加入：

```python
def _has_school_choice_context(text: str) -> bool:
    compact = _compact(text)
    return any(marker in compact for marker in _SCHOOL_CHOICE_CONTEXT_MARKERS)


def _matching_clause(text: str, match: re.Match[str]) -> str:
    start = max(
        (text.rfind(mark, 0, match.start()) for mark in "。！？；\n"),
        default=-1,
    )
    ends = [text.find(mark, match.end()) for mark in "。！？；\n"]
    valid_ends = [index for index in ends if index >= 0]
    end = min(valid_ends) if valid_ends else len(text)
    return text[start + 1 : end]


def _is_school_choice_warning(clause: str) -> bool:
    compact = _compact(clause)
    return any(marker in compact for marker in _SCHOOL_CHOICE_WARNING_MARKERS)
```

分句只使用句号、问号、叹号、分号和换行。逗号不截断，使“买学区房也不能保证入学”中的否定与承诺保持在同一判断单元。

- [ ] **Step 3: 在公开文案扫描中加入择校承诺 finding**

在标题夸大检查之后、范围检查之前加入：

```python
    school_choice_text = "\n".join((title or "", digest or "", body or ""))
    if _has_school_choice_context(school_choice_text):
        for field, text in (("title", title), ("digest", digest), ("body", body)):
            for pattern in _SCHOOL_CHOICE_PROMISE_PATTERNS:
                for match in pattern.finditer(text or ""):
                    clause = _matching_clause(text or "", match)
                    if _is_school_choice_warning(clause):
                        continue
                    findings.append(
                        _finding(
                            "school_choice_admission_promise",
                            field,
                            text,
                            "出现学位或录取的确定性承诺，请改为当年主管部门审核边界",
                            match,
                        )
                    )
                    break
                else:
                    continue
                break
```

每个字段最多返回一个同类 finding，避免一篇稿件重复刷屏。现有 finding 顺序保持“编辑指令—标题营销—择校承诺—政策范围—数字兑现—格式”。

- [ ] **Step 4: 运行质量门禁测试**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest tests/unit/test_wechat_mp_hotspot_quality_gate.py -q
```

Expected: 全部通过；肯定承诺返回 `school_choice_admission_promise`，三条警示语境和非择校稿无该 finding。

- [ ] **Step 5: 增加一个句内正反并存回归并验证**

添加测试确保否定不能掩盖下一句肯定承诺：

```python
def test_warning_in_previous_sentence_does_not_hide_later_promise() -> None:
    findings = scan_hotspot_public_copy(
        title="深圳积分入学怎么准备？",
        digest="核对当年区级招生细则。",
        body="普通渠道不能保证录取。我们另有内部名额，可以确保孩子入学。",
        research_urls=("https://www.sz.gov.cn/policy",),
    )

    assert "school_choice_admission_promise" in {item.code for item in findings}
```

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest tests/unit/test_wechat_mp_hotspot_quality_gate.py -q
```

Expected: PASS。

- [ ] **Step 6: 提交自动门禁与测试**

```bash
git add stock-ai/scripts/tools/wechat_mp_hotspot_quality_gate.py stock-ai/tests/unit/test_wechat_mp_hotspot_quality_gate.py
git commit -m "门禁：拦截择校招生确定性承诺"
```

---

### Task 4: 更新规则映射、稳定记忆并完成回归验证

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/rules-implemented.md`
- Modify: `.cursor/rules/memory-python.mdc`
- Verify: `.cursor/skills/wechat-mp-writing/school-choice-policy.md`
- Verify: `stock-ai/scripts/tools/wechat_mp_hotspot_quality_gate.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_hotspot_quality_gate.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_browser_write_cli.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_browser_push.py`

**Interfaces:**
- Consumes: Task 1 的专题路由和 Task 3 的 `school_choice_admission_promise` finding。
- Produces: 可检索的规则到代码映射、稳定用户偏好，以及 stage/push 不回归的验证证据。

- [ ] **Step 1: 更新规则与代码映射**

在 `.cursor/skills/wechat-mp-drafts/rules-implemented.md` 的映射表中增加：

```markdown
| 北上广深义务教育与高中择校专题、招生承诺门禁 | `wechat-mp-writing/school-choice-policy.md`、`wechat_mp_hotspot_quality_gate.py` | `test_wechat_mp_hotspot_quality_gate.py` |
```

在“当前门禁”中增加：

```markdown
- 北上广深择校稿必须明确城市、区县或市级范围、学段、入学年度和政策状态；自动门禁拦截明确的学位或录取承诺，否定和反诈骗语境放行。
```

- [ ] **Step 2: 更新稳定记忆索引**

在 `.cursor/rules/memory-python.mdc` 的“公众号热点 · 教育政策选题范围”条目中追加：

```markdown
- **择校专题**：首期只覆盖北京、上海、广州、深圳的义务教育与高中选校；大学志愿仍归高考政策线。区分市级原则、区级细则和学校自述，不做学校排名、录取承诺或学区房投资建议。执行真源：`.cursor/skills/wechat-mp-writing/school-choice-policy.md`。
```

- [ ] **Step 3: 运行专题 Skill 校验**

Run:

```bash
python3 /Users/huan.yu/.codex/skills/.system/skill-creator/scripts/quick_validate.py .cursor/skills/wechat-mp-writing
```

Expected: `Skill is valid!` 或等价成功结果，无未完成占位符。

- [ ] **Step 4: 运行相关回归测试**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest tests/unit/test_wechat_mp_hotspot_quality_gate.py tests/unit/test_wechat_mp_browser_write_cli.py tests/unit/test_wechat_mp_browser_push.py -q
```

Expected: 全部通过；stage 与 push 仍调用同一个公开文案门禁，现有双确认、Agent 编辑记录和图片策略测试不回归。

- [ ] **Step 5: 检查差异范围与格式**

Run:

```bash
git diff --check
git status --short
git diff -- .cursor/skills/wechat-mp-writing/SKILL.md .cursor/skills/wechat-mp-writing/hotspot-deep-review.md .cursor/skills/wechat-mp-writing/school-choice-policy.md .cursor/skills/wechat-mp-drafts/rules-implemented.md .cursor/rules/memory-python.mdc stock-ai/scripts/tools/wechat_mp_hotspot_quality_gate.py stock-ai/tests/unit/test_wechat_mp_hotspot_quality_gate.py
```

Expected: 无空白错误；差异只包含本计划的择校专题、门禁、测试、映射和记忆修改。若目标文件存在任务开始前的相关改动，逐块核对并只暂存本任务新增内容。

- [ ] **Step 6: 提交文档与记忆映射**

```bash
git add .cursor/skills/wechat-mp-drafts/rules-implemented.md .cursor/rules/memory-python.mdc
git commit -m "文档：记录北上广深择校门禁"
```

- [ ] **Step 7: 汇报验证证据**

最终汇报包含：新增专题文件、四城范围、自动拦截与放行示例、Skill 校验结果、pytest 通过数量及三个提交编号。不得声称自动门禁能够判断政策是否过期或区级规则是否被外推；这两项仍由 Agent 回源核验。
