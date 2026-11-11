# 公众号情绪共鸣与讨论张力软门禁 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `hotspot`、`hot_business`、`silver`、`tv_review` 增加可解释的情绪共鸣与讨论张力检查，并保证这些检查始终只作 advisory 提示、不阻断草稿。

**Architecture:** 新建独立的纯文本检查模块，输出与流量清单解耦的 `EmpathyDiscussionCheck`；现有 `wechat_mp_traffic_checklist` 负责把结果适配为带 `advisory=True` 的清单项，现有质量门禁只收集非 advisory 的自动失败项。写作规范同步加入“情绪主语、具体代价、真实张力、读者选择”四要素，机器只检测结构迹象，最终由人工判断。

**Tech Stack:** Python 3.11、`dataclasses`、`re`、pytest、现有公众号 `traffic_checklist` / `push_quality_gate`。

## Global Constraints

- 只适用于 `hotspot`、`hot_business`、`silver`、`tv_review`。
- 所有新检查默认和未来都只作 advisory；即使 `WECHAT_MP_QUALITY_TRAFFIC_BLOCK=1`，也不得改变质量门禁 `ok`。
- 不虚构人物、采访、现场或经历，不为了过检查强行煽情或制造对立。
- 明确违法侵害不要求替侵害方构造合理性，检查受影响者面对的现实代价或选择即可。
- 不改变原创度、来源域、合规、字数、图片和返佣规则。
- 工作树已有大量用户修改；每次只暂存本任务明确列出的文件和相关补丁，不覆盖、不整理无关改动。

---

### Task 1: 建立独立的共鸣与讨论纯文本检查器

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_empathy_checklist.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_empathy_checklist.py`

**Interfaces:**
- Produces: `EmpathyDiscussionCheck(id: str, label: str, passed: bool, hint: str)`
- Produces: `run_empathy_discussion_checks(*, title: str, body: str, kind: str) -> list[EmpathyDiscussionCheck]`
- Produces exactly four IDs for supported kinds: `empathy_subject_early`, `concrete_cost_before_third`, `balanced_tension_before_third`, `reader_choice_connected`
- Returns `[]` for unsupported kinds.

- [ ] **Step 1: 写失败测试，固定四类文章的期望行为**

在 `test_wechat_mp_empathy_checklist.py` 写真实文本测试，不 mock 检查器：

```python
from scripts.tools.wechat_mp_empathy_checklist import run_empathy_discussion_checks


def _by_id(*, title: str, body: str, kind: str):
    return {
        item.id: item
        for item in run_empathy_discussion_checks(title=title, body=body, kind=kind)
    }


def test_hotspot_passes_with_person_cost_tension_and_connected_choice() -> None:
    body = (
        "15岁的孩子站在技校和普通高中之间，父母先算的是三年学费和毕业后的第一份工资。"
        "企业能把真实设备和岗位带进课堂，但孩子如果过早绑定一家工厂，转岗时技能是否仍被承认？\n\n"
        "学校需要稳定生源，家庭也需要确定就业；两边都有现实理由，代价却最终落在孩子的选择权上。\n\n"
        "如果是你的孩子，你更看重毕业即就业，还是三年后仍能换方向的能力？"
    )
    checks = _by_id(title="董明珠任校长，格力技校能改命吗？", body=body, kind="hotspot")
    assert set(checks) == {
        "empathy_subject_early",
        "concrete_cost_before_third",
        "balanced_tension_before_third",
        "reader_choice_connected",
    }
    assert all(item.passed for item in checks.values())


def test_macro_copy_with_generic_tail_gets_actionable_advisories() -> None:
    body = (
        "有关部门发布最新数据，行业规模继续增长，市场发展受到广泛关注。" * 12
        + "\n\n综上所述，未来值得期待。你怎么看？"
    )
    checks = _by_id(title="行业规模继续增长意味着什么？", body=body, kind="hot_business")
    assert all(not item.passed for item in checks.values())
    assert "人物" in checks["empathy_subject_early"].hint
    assert "代价" in checks["concrete_cost_before_third"].hint
    assert "两种" in checks["balanced_tension_before_third"].hint
    assert "正文" in checks["reader_choice_connected"].hint


def test_hot_business_rejects_product_preference_only_question() -> None:
    body = (
        "观众小周看完电影后搜索周边，四元立牌先满足了他的购买冲动。"
        "片方需要控制库存，但正版来得太晚，第一次消费关系会被低价商品抢走。"
        "观众省了钱，片方也承担错过热度窗口的代价。\n\n"
        "如果推出正版周边，你想买毛绒、徽章还是设定集？"
    )
    checks = _by_id(title="《牛来》爆红后，流量怎么变周边？", body=body, kind="hot_business")
    assert not checks["reader_choice_connected"].passed


def test_silver_recognizes_autonomy_and_family_protection_tension() -> None:
    body = (
        "晚上九点，母亲正要在直播间付款，女儿伸手想替她关掉页面。"
        "女儿担心养老钱被骗，母亲却不愿每一次消费都先向孩子报备。"
        "保护能减少损失，但完全接管也会拿走老人的尊严和选择权。\n\n"
        "如果家里老人反复下单，你会直接接管支付，还是和她约定一段冷静时间？"
    )
    checks = _by_id(title="直播间越催下单，越要停十分钟", body=body, kind="silver")
    assert all(item.passed for item in checks.values())


def test_tv_review_requires_character_action_not_generic_theme() -> None:
    generic = "这部电影讲述自由、成长和人生选择，也让现代职场人产生很多共鸣。" * 15
    checks = _by_id(title="20年后，安迪为什么离开", body=generic, kind="tv_review")
    assert not checks["empathy_subject_early"].passed
    assert not checks["concrete_cost_before_third"].passed


def test_clear_abuse_does_not_require_defending_abuser() -> None:
    body = (
        "母亲接到诈骗电话后失去八万元养老钱，报案回执和转账记录都在。"
        "骗局没有合理性，真正的两难是她要不要告诉子女：隐瞒能暂时保住体面，却可能错过止损时间。\n\n"
        "如果是你的家人，你会先追问责任，还是先帮她止损并保住尊严？"
    )
    checks = _by_id(title="八万元养老钱被骗后，她为什么不敢告诉孩子？", body=body, kind="silver")
    assert checks["balanced_tension_before_third"].passed


def test_unsupported_kind_has_no_empathy_advisories() -> None:
    assert run_empathy_discussion_checks(title="A股收盘", body="正文", kind="market") == []
```

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_empathy_checklist.py -q
```

Expected: collection fails with `ModuleNotFoundError: scripts.tools.wechat_mp_empathy_checklist`，证明新能力尚不存在。

- [ ] **Step 3: 实现最小纯文本检查模块**

在新模块中实现：

```python
SUPPORTED_KINDS = {"hotspot", "hot_business", "silver", "tv_review"}


@dataclass(frozen=True)
class EmpathyDiscussionCheck:
    id: str
    label: str
    passed: bool
    hint: str


def run_empathy_discussion_checks(
    *, title: str, body: str, kind: str
) -> list[EmpathyDiscussionCheck]:
    if kind not in SUPPORTED_KINDS:
        return []
    plain = _normalize_body(body)
    early = _compact(plain)[:150]
    first_third = _first_third(plain)
    tail = _tail_block(plain)
    return [
        _check_early_subject(early, kind=kind),
        _check_concrete_cost(first_third),
        _check_balanced_tension(first_third),
        _check_reader_choice(title=title, opening=first_third, tail=tail, kind=kind),
    ]
```

实现细节必须满足：

- `_normalize_body` 去除 `[[fig:...]]`、资料说明和通用关注/推荐尾巴，保留正文段落。
- `_first_third` 至少取 220 字，最多取正文去空白长度的三分之一，避免短样例被截成几十字。
- 情绪主语使用“身份/角色词 + 动作或处境词”的组合；仅出现“大家、人们、社会、行业、市场”不通过。影视稿必须出现角色名/身份并同时出现动作或选择词。
- 具体代价识别时间、金额、工资、学费、岗位、失去、尊严、关系、健康、风险、选择权等信号；只出现“影响、压力、问题”不通过。
- 张力识别至少两种目标或主体与 `但、却、同时、如果、还是、一边、另一边、既、又` 等关系；诈骗、索贿、违法、侵权等明确侵害场景可由受影响者自身的两难通过，不要求替侵害方辩护。
- 结尾拒绝单独的“你怎么看/大家怎么看/欢迎留言”；`hot_business` 额外拒绝只问“买哪个/最想买/毛绒、徽章还是设定集”等商品偏好。
- 有效结尾需包含选择表达，并与标题或正文前三分之一共享至少一个非停用的二字词，或者复用同一类代价词。
- 每个失败 `hint` 都指出缺的是人物、代价、两种目标或正文连接，不建议增加煽情词。

- [ ] **Step 4: 运行测试并确认 GREEN**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_empathy_checklist.py -q
```

Expected: `7 passed`。

- [ ] **Step 5: 重构正则常量并保持测试通过**

把主体词、动作词、代价词、张力词、明确侵害词和泛问句集中为模块级不可变元组；每个 helper 只负责一个判断，不在 `run_empathy_discussion_checks` 内堆叠长正则。

- [ ] **Step 6: 提交 Task 1**

```bash
git add stock-ai/scripts/tools/wechat_mp_empathy_checklist.py stock-ai/tests/unit/test_wechat_mp_empathy_checklist.py
git commit -m "feat(stock-ai)：增加公众号共鸣讨论检查器"
```

---

### Task 2: 把 advisory 语义接入阅读量清单

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_traffic_checklist.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_traffic_checklist.py`

**Interfaces:**
- Consumes: `run_empathy_discussion_checks(...)`
- Extends: `TrafficCheckItem(..., advisory: bool = False)`
- Produces: `TrafficChecklistReport.advisory_pending -> list[TrafficCheckItem]`
- Existing `auto_passed`、`auto_total` and `verdict` count only non-manual, non-advisory automatic items.

- [ ] **Step 1: 写失败测试固定 advisory 统计与报告**

追加：

```python
def test_empathy_items_are_advisory_and_excluded_from_auto_verdict() -> None:
    body = "有关部门发布数据，行业规模继续增长。" * 100 + "\n\n你怎么看？"
    rep = run_traffic_checklist(
        title="行业规模继续增长意味着什么？",
        digest="热点观察：行业规模继续增长。",
        body=body,
        kind="hot_business",
    )
    empathy = [item for item in rep.items if item.id.startswith((
        "empathy_", "concrete_cost_", "balanced_tension_", "reader_choice_"
    ))]
    assert len(empathy) == 4
    assert all(item.advisory for item in empathy)
    assert len(rep.advisory_pending) == 4
    assert rep.auto_total == len([i for i in rep.items if not i.manual and not i.advisory])
    report = format_traffic_report(rep)
    assert "共鸣与讨论" in report
    assert "只作编辑提示" in report
    assert "禁止为了过项虚构人物或强行制造对立" in report


def test_empathy_checker_error_degrades_to_non_blocking_advisory(monkeypatch) -> None:
    def fail(**_kwargs):
        raise RuntimeError("check failed")

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_traffic_checklist.run_empathy_discussion_checks",
        fail,
    )
    rep = run_traffic_checklist(
        title="董明珠任校长，格力技校能改命吗？",
        digest="热点观察：企业技校如何兑现就业承诺。",
        body="15岁的孩子正在选择学校。" * 100,
        kind="hotspot",
    )
    error = next(item for item in rep.items if item.id == "empathy_check_error")
    assert error.advisory
    assert not error.passed
```

再加一个正向测试，确认四项通过时仍显示分组，但 `advisory_pending == []`。

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_traffic_checklist.py -q
```

Expected: `TrafficCheckItem` 没有 `advisory` 或报告中没有新分组。

- [ ] **Step 3: 最小接入 advisory 数据模型**

修改数据模型：

```python
@dataclass
class TrafficCheckItem:
    id: str
    label: str
    passed: bool
    hint: str = ""
    manual: bool = False
    advisory: bool = False
```

新增：

```python
@property
def advisory_pending(self) -> list[TrafficCheckItem]:
    return [i for i in self.items if i.advisory and not i.passed]
```

调整 `auto_passed`、`auto_total`、`verdict`，统一排除 `manual` 和 `advisory`。在 `run_traffic_checklist` 的基础自动项之后、后台人工项之前，调用纯文本检查器并转换：

```python
for check in run_empathy_discussion_checks(title=t, body=plain, kind=kind):
    items.append(
        TrafficCheckItem(
            id=check.id,
            label=check.label,
            passed=check.passed,
            hint=check.hint,
            advisory=True,
        )
    )
```

调用外围用 `try/except Exception` 降级；异常时追加 `id="empathy_check_error"`、`advisory=True` 的失败提示，不得把异常继续抛给推稿流程。

`format_traffic_report` 把 advisory 单独置于“共鸣与讨论”分组，失败使用 `[提示]`，通过使用 `[已覆盖]`；非 verbose 模式也输出 advisory 失败摘要，但不得把它们写成“自动项未通过”。末尾固定加一句：

```text
自动检查只能发现结构迹象，只作编辑提示；禁止为了过项虚构人物或强行制造对立。
```

- [ ] **Step 4: 运行测试并确认 GREEN**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_traffic_checklist.py tests/unit/test_wechat_mp_empathy_checklist.py -q
```

Expected: 全部通过。

- [ ] **Step 5: 提交 Task 2**

```bash
git add stock-ai/scripts/tools/wechat_mp_traffic_checklist.py stock-ai/tests/unit/test_wechat_mp_traffic_checklist.py
git commit -m "feat(stock-ai)：接入公众号共鸣讨论软提示"
```

---

### Task 3: 保证 quality gate 永远不被 advisory 阻断

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_push_quality_gate.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_push_quality_gate.py`

**Interfaces:**
- Consumes: `TrafficCheckItem.advisory`
- `QualityGateResult.traffic_failures` remains the list of block-eligible automatic failures only.
- Adds: `QualityGateResult.traffic_advisories: list[str]` for failed advisory items.

- [ ] **Step 1: 写失败测试验证 traffic 硬阻断开启时 advisory 仍不阻断**

新增测试，用一份只含 advisory 的真实 `TrafficChecklistReport` 隔离其他 traffic 项，精确验证阻断语义：

```python
def test_empathy_advisories_never_block_even_when_traffic_block_is_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WECHAT_MP_QUALITY_TRAFFIC_BLOCK", "1")
    monkeypatch.setenv("WECHAT_MP_QUALITY_MIN_SCORE", "0")
    monkeypatch.setenv("WECHAT_MP_QUALITY_MAX_AI_FLAVOR", "100")
    report = TrafficChecklistReport(
        kind="hot_business",
        title="行业规模继续增长意味着什么？",
        edition=None,
        items=[
            TrafficCheckItem(
                id="empathy_subject_early",
                label="前150字有情绪主语",
                passed=False,
                advisory=True,
            )
        ],
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_push_quality_gate.run_traffic_checklist",
        lambda **_kwargs: report,
    )
    art = _sample_article(title=report.title, body="一名消费者正在作出选择。")
    result = assess_article_for_push(art, "hot_business")
    assert result.ok
    assert result.traffic_advisories == ["empathy_subject_early:前150字有情绪主语"]
    assert result.traffic_failures == []
    assert result.block_reason == ""
```

另写一项同结构测试，把 item 改为 `id="title_banned"`、`advisory=False`，确认它进入 `traffic_failures`、`result.ok is False` 且 `block_reason` 包含 `title_banned`，防止过滤条件过宽。测试文件需从 `wechat_mp_traffic_checklist` 导入 `TrafficCheckItem` 和 `TrafficChecklistReport`。

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_push_quality_gate.py -q
```

Expected: `QualityGateResult` 尚无 `traffic_advisories`，或 advisory 被错误收入 `traffic_failures`。

- [ ] **Step 3: 实现 advisory 与 block-eligible failure 分流**

修改 dataclass 和收集逻辑：

```python
traffic_failures = [
    f"{i.id}:{i.label}"
    for i in traffic.items
    if not i.manual and not i.advisory and not i.passed
]
traffic_advisories = [
    f"{i.id}:{i.label}"
    for i in traffic.items
    if i.advisory and not i.passed
]
```

`format_quality_gate_report` 在 traffic 提示后追加：

```text
【共鸣与讨论提示】需人工确认（不阻断推稿）：...
```

`QualityGateResult.to_dict()` 通过 `asdict` 保留 `traffic_advisories`，不更改既有字段含义。

- [ ] **Step 4: 运行测试并确认 GREEN**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_push_quality_gate.py tests/unit/test_wechat_mp_traffic_checklist.py tests/unit/test_wechat_mp_empathy_checklist.py -q
```

Expected: 全部通过，且坏标题仍按原逻辑阻断。

- [ ] **Step 5: 提交 Task 3**

```bash
git add stock-ai/scripts/tools/wechat_mp_push_quality_gate.py stock-ai/tests/unit/test_wechat_mp_push_quality_gate.py
git commit -m "fix(stock-ai)：确保共鸣提示不阻断公众号推稿"
```

---

### Task 4: 把四要素写入角色卡和稿型规范

**Files:**
- Modify: `.cursor/skills/wechat-mp-writing/account-role-card.md`
- Modify: `.cursor/skills/wechat-mp-writing/traffic-copy-craft.md`
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md`
- Modify: `.cursor/skills/wechat-mp-drafts/templates.md`
- Modify: `.cursor/skills/wechat-mp-drafts/tv-review-template.md`
- Modify: `.cursor/skills/wechat-mp-drafts/rules-implemented.md`
- Modify: `stock-ai/tests/unit/test_wechat_mp_role_card.py`

**Interfaces:**
- Writing contract text must contain the four stable labels: `情绪主语`、`具体代价`、`双方张力`、`读者选择`.
- Role-card runtime prompt remains the single shared source for all four kinds.

- [ ] **Step 1: 写失败测试固定角色卡四要素和反煽情边界**

在 `test_wechat_mp_role_card.py` 增加：

```python
def test_account_role_card_contains_empathy_discussion_contract() -> None:
    card = load_account_role_card()
    for marker in ("情绪主语", "具体代价", "双方张力", "读者选择"):
        assert marker in card
    assert "不为了过检查强行煽情或制造对立" in card
```

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_role_card.py -q
```

Expected: 缺少四要素标记而失败。

- [ ] **Step 3: 更新角色卡和各稿型规范**

在角色卡增加“写前讨论母题”小节，明确：

```text
动笔前写清情绪主语、具体代价、双方张力和读者选择。正文前150字落人或场景，前三分之一出现代价与张力，结尾问题连接正文核心矛盾。不为了过检查强行煽情或制造对立；明确侵害不替侵害方找理由。
```

在各稿型文档分别补充：

- `hotspot-deep-review.md`：热点与热点商业分别落到权利责任、消费者/员工/小经营者成本；禁止只问商品偏好。
- `templates.md`：银发稿强调自主权与家庭保护、便利与风险、节省与体验的真实两难。
- `tv-review-template.md`：角色、剧情动作、角色代价必须先于现实类比；结尾保留角色选择复杂性。
- `traffic-copy-craft.md`：将原“站队问句”升级为与正文同题的读者选择，不再鼓励简单二选一凑互动。
- `rules-implemented.md`：登记 `wechat_mp_empathy_checklist.py`、traffic advisory 和 quality gate 分流及对应测试。

这些文件已有用户修改时，只在目标章节插入最小段落，提交前逐文件检查 diff，禁止覆盖现有内容。

- [ ] **Step 4: 运行角色卡测试并确认 GREEN**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_role_card.py tests/unit/test_wechat_mp_tv_role_card.py -q
```

Expected: 全部通过。

- [ ] **Step 5: 提交 Task 4**

```bash
git add .cursor/skills/wechat-mp-writing/account-role-card.md .cursor/skills/wechat-mp-writing/traffic-copy-craft.md .cursor/skills/wechat-mp-drafts/templates.md .cursor/skills/wechat-mp-drafts/tv-review-template.md .cursor/skills/wechat-mp-drafts/rules-implemented.md stock-ai/tests/unit/test_wechat_mp_role_card.py
git add -p -- .cursor/skills/wechat-mp-writing/hotspot-deep-review.md
git commit -m "docs(stock-ai)：固化公众号共鸣讨论写作契约"
```

`hotspot-deep-review.md` 在实施前已有用户修改，交互暂存时只选择本任务新增的“讨论母题”小节，拒绝其他 hunk。

---

### Task 5: 用代表性稿件回归并完成整体验证

**Files:**
- Modify if needed only for test correctness: files created or modified in Tasks 1–4
- Do not edit generated drafts or current WeChat draft slots.

**Interfaces:**
- Verification only; no new behavior.

- [ ] **Step 1: 用固定文本复核代表性正反例**

使用单元测试中的固定节选复核：

- 《穿普拉达的女王》式剧情选择应通过人物、代价和张力。
- “行业规模增长 + 你怎么看”应产生四项 advisory。
- 《牛来》式“买毛绒还是徽章”应提示读者选择过浅。
- 银发“子女保护与本人自主权”应通过。

不得直接依赖 `output/` 或草稿缓存，避免测试随日常写稿变化。

- [ ] **Step 2: 运行聚焦测试**

Run:

```bash
cd stock-ai
uv run pytest \
  tests/unit/test_wechat_mp_empathy_checklist.py \
  tests/unit/test_wechat_mp_traffic_checklist.py \
  tests/unit/test_wechat_mp_push_quality_gate.py \
  tests/unit/test_wechat_mp_role_card.py \
  tests/unit/test_wechat_mp_tv_role_card.py -q
```

Expected: 全部通过。

- [ ] **Step 3: 运行公众号相关测试集**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_*.py -q
```

Expected: 全部通过；若存在与本任务无关的既有失败，记录测试名与基线证据，不修改无关功能。

- [ ] **Step 4: 运行静态与 diff 检查**

Run:

```bash
git diff --check
git status --short
```

逐文件确认：

- advisory 未进入 `traffic_failures`。
- `WECHAT_MP_QUALITY_TRAFFIC_BLOCK=1` 只阻断原有自动项。
- 所有用户已有修改仍然保留。
- 没有暂存 `output/`、素材、`.env`、证书或其他无关文件。

- [ ] **Step 5: 处理验证结果**

若无需修正，不创建空提交。若本任务文件需要修正，回到对应 Task 的 RED-GREEN 步骤补测试，并使用该 Task 已列出的精确 `git add` 文件清单提交；与本任务无关的既有失败只记录，不修改、不暂存。
