# 热点稿编辑泄漏与公众号写作门禁 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 阻止编辑指令进入热点稿正文，并把可验证的公众号标题、开头、结构与论证要求接入入库和推送前门禁。

**Architecture:** 新建一个无网络、无副作用的热点公开文案门禁模块，分别输出高置信度阻断项和可解释的编辑评分。用户粘贴 DeepSeek 初稿后的入库路径与最终推送路径调用同一接口；热点写作 Skill 保存需要人工判断的规则，避免用宽泛正则误伤正常评论。

**Tech Stack:** Python 3、dataclass、正则表达式、pytest、现有公众号双确认工作流。

## Global Constraints

- 只拦截面向写作者、编辑者或模型的过程性指令，不拦截正常事实限定。
- 不使用“不等于”“不能”等单词级规则直接阻断发布。
- 入库和最终推送前各检查一次，推送检查必须发生在上传图片或调用微信接口之前。
- 标题准确、清晰并兑现正文；不得通过仿冒通知、扩大政策范围或无依据数字制造点击。
- 主观写作质量通过多项评分综合判断，不允许单个情绪词或连接词决定通过与否。
- 保持 DeepSeek 用户手工交接、至少三个来源域、真实图片、双确认和 IP 白名单流程不变。

---

### Task 1: 公开文案阻断扫描器

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_hotspot_quality_gate.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_hotspot_quality_gate.py`

**Interfaces:**
- Produces: `HotspotGateFinding(code: str, field: str, excerpt: str, message: str)`。
- Produces: `scan_hotspot_public_copy(*, title: str, digest: str, body: str, research_urls: Sequence[str]) -> tuple[HotspotGateFinding, ...]`。
- Produces: `require_hotspot_public_copy(...) -> None`，命中时抛出 `ValueError("热点公开文案未通过门禁：...")`。

- [ ] **Step 1: 写编辑指令泄漏失败测试**

```python
def test_rejects_editorial_instruction_leak() -> None:
    findings = scan_hotspot_public_copy(
        title="辽宁中考3科不再计分，减负会不会变成偏科？",
        digest="辽宁调整中考计分科目。",
        body="这是辽宁的地方政策，更不能写成全国统一取消历史、地理和生物计分。",
        research_urls=("https://jyt.ln.gov.cn/policy",),
    )
    assert [item.code for item in findings] == ["editorial_instruction_leak"]
```

- [ ] **Step 2: 写正常论述反例测试**

```python
@pytest.mark.parametrize(
    "sentence",
    (
        "不计入总分不等于取消课程。",
        "不能据此推断全国统一调整。",
        "不能把管理成本转嫁给家长。",
    ),
)
def test_allows_reader_facing_argument(sentence: str) -> None:
    assert not scan_hotspot_public_copy(
        title="辽宁中考调整会带来什么？",
        digest="辽宁调整部分科目计分方式。",
        body=f"辽宁省教育厅发布调整。\n\n{sentence}\n\n家长仍需等待细则。",
        research_urls=("https://jyt.ln.gov.cn/policy",),
    )
```

- [ ] **Step 3: 写标题夸大、承诺未兑现和重复段落测试**

```python
def test_rejects_banned_marketing_title() -> None:
    findings = scan_hotspot_public_copy(
        title="重磅！全国所有学生彻底取消中考3科",
        digest="辽宁发布地方调整。",
        body="辽宁省教育厅发布地方调整。\n\n其他地区方案不同。",
        research_urls=("https://example.com/report",),
    )
    assert {item.code for item in findings} >= {"title_hype", "unsupported_scope"}


def test_rejects_unfulfilled_title_number_and_duplicate_paragraph() -> None:
    body = "辽宁调整中考科目。\n\n家长等待细则。\n\n家长等待细则。"
    findings = scan_hotspot_public_copy(
        title="辽宁中考5项变化",
        digest="辽宁调整中考科目。",
        body=body,
        research_urls=("https://jyt.ln.gov.cn/policy",),
    )
    assert {item.code for item in findings} >= {"title_number_unfulfilled", "duplicate_paragraph"}
```

- [ ] **Step 4: 运行测试并确认失败**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_hotspot_quality_gate.py -q`

Expected: FAIL，模块或接口尚不存在。

- [ ] **Step 5: 实现最小扫描器**

```python
@dataclass(frozen=True)
class HotspotGateFinding:
    code: str
    field: str
    excerpt: str
    message: str


def scan_hotspot_public_copy(*, title, digest, body, research_urls):
    findings = []
    # 仅匹配“写成、表述为、正文、标题、稿件、提示词、审稿、配图建议”等编辑语境。
    # 检查固定营销词、无权威来源支撑的绝对政策范围、标题数字兑现及完全重复段落。
    return tuple(findings)
```

实现时将片段压缩至 80 个可见字符；“全国统一”“全面取消”等词只有在标题出现且 `research_urls` 不含 `.gov.cn`、`gov.cn` 或教育主管部门官方域名时才产生 `unsupported_scope`，正文中的正常否定不触发。

- [ ] **Step 6: 运行测试并确认通过**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_hotspot_quality_gate.py -q`

Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add stock-ai/scripts/tools/wechat_mp_hotspot_quality_gate.py stock-ai/tests/unit/test_wechat_mp_hotspot_quality_gate.py
git commit -m "修复：拦截热点稿编辑指令与标题夸大"
```

### Task 2: 可解释的编辑质量评分

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_quality_gate.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_hotspot_quality_gate.py`

**Interfaces:**
- Produces: `HotspotEditorialScore(score: int, total: int, passed: bool, checks: tuple[HotspotEditorialCheck, ...])`。
- Produces: `evaluate_hotspot_editorial_quality(*, title: str, body: str, topic: str, original_thesis: str, research_urls: Sequence[str]) -> HotspotEditorialScore`。
- Produces: `require_hotspot_editorial_quality(...) -> HotspotEditorialScore`，低于 5/7 时抛出带失败检查名的 `ValueError`。

- [ ] **Step 1: 写评分通过与失败测试**

```python
def test_editorial_score_rewards_complete_commentary() -> None:
    report = evaluate_hotspot_editorial_quality(
        title="辽宁中考3科不再计分，减负会不会变成偏科？",
        topic="辽宁中考科目调整",
        original_thesis="减少计分科目能否减负，取决于课时、等级使用和录取配套是否公开。",
        research_urls=("https://a.gov.cn/1", "https://b.cn/2", "https://c.cn/3"),
        body=(
            "辽宁省教育厅发布中考科目调整，历史、地理和生物改为等级考查。\n\n"
            "家长关心的不是少考三科，而是课时、等级和录取规则会怎样变化。\n\n"
            "支持者认为减少计分项目能够减轻刷题压力，这个方向有现实依据。\n\n"
            "但如果压力全部转向语数外物理，学生总负担未必降低。\n\n"
            "这是辽宁的地方政策，各地中考方案不同，不能据此推断全国统一调整。\n\n"
            "如果历史、地理和生物不计总分，你更担心压力转移还是课程被边缘化？"
        ),
    )
    assert report.passed is True
    assert report.score >= 5


def test_editorial_score_rejects_news_summary_without_argument() -> None:
    report = evaluate_hotspot_editorial_quality(
        title="辽宁中考调整",
        topic="辽宁中考科目调整",
        original_thesis="",
        research_urls=("https://a.gov.cn/1",),
        body="辽宁发布通知。\n\n三科调整为考查。\n\n消息受到关注。",
    )
    assert report.passed is False
```

- [ ] **Step 2: 运行评分测试并确认失败**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_hotspot_quality_gate.py -q`

Expected: FAIL，评分接口尚不存在。

- [ ] **Step 3: 实现七项评分**

七项分别为：原创核心判断不少于 20 字、至少三个来源域、首段出现题目或事件实体、正文前 1/3 出现具体人群或成本、存在对立理由及边界表达、结尾有由正文推出的具体问句、至少五段且单段不超过 180 字。每项 1 分，至少 5 分通过；任何单项失败都不单独阻断。

- [ ] **Step 4: 运行评分测试并确认通过**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_hotspot_quality_gate.py -q`

Expected: PASS，并且报告包含七项检查名称和布尔结果。

- [ ] **Step 5: 提交**

```bash
git add stock-ai/scripts/tools/wechat_mp_hotspot_quality_gate.py stock-ai/tests/unit/test_wechat_mp_hotspot_quality_gate.py
git commit -m "功能：增加热点深评写作质量评分"
```

### Task 3: 接入入库与推送前双门禁

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_write.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_browser_write_cli.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_browser_push.py`

**Interfaces:**
- Consumes: `require_hotspot_public_copy(...)` 和 `require_hotspot_editorial_quality(...)`。
- Produces: 第二次确认摘要中的 `编辑质量: N/7`。

- [ ] **Step 1: 写入库先于配图的失败测试**

```python
def test_hotspot_stage_rejects_editorial_leak_before_images(tmp_path, monkeypatch):
    from scripts.tools import wechat_mp_codex_hotspot as hotspot_mod
    from scripts.tools import wechat_mp_codex_images as images_mod

    article = tmp_path / "hotspot.json"
    article.write_text(json.dumps({
        "title": "辽宁中考3科不再计分",
        "digest": "辽宁调整中考计分科目。",
        "body": "辽宁发布调整。\n\n这是地方政策，更不能写成全国统一取消三科计分。",
        "topic": "辽宁中考科目调整",
        "original_thesis": "减少计分科目能否减负，取决于课时、等级和录取配套。",
        "research_urls": ["https://a.gov.cn/1", "https://b.cn/2", "https://c.cn/3"],
    }, ensure_ascii=False), encoding="utf-8")
    workflow = create_workflow(kind="hotspot", topic="辽宁中考科目调整", prompt="提示词", root=tmp_path)
    monkeypatch.setattr(hotspot_mod, "validate_codex_hotspot_originality", lambda *a, **k: None)
    image_calls = []
    monkeypatch.setattr(images_mod, "prepare_hotspot_topic_images", lambda *a, **k: image_calls.append(1))
    with pytest.raises(ValueError, match="editorial_instruction_leak"):
        browser_cli._validate_staged_article(workflow, article, edit_notes=("已核实",))
    assert image_calls == []
```

- [ ] **Step 2: 写推送先于构建和上传的失败测试**

```python
def test_hotspot_push_rechecks_public_copy_before_build(tmp_path, monkeypatch):
    article = tmp_path / "hotspot.json"
    article.write_text(json.dumps({
        "title": "辽宁中考3科不再计分",
        "digest": "辽宁调整中考计分科目。",
        "body": "辽宁发布调整。\n\n这是地方政策，更不能写成全国统一取消三科计分。",
        "topic": "辽宁中考科目调整",
        "original_thesis": "减少计分科目能否减负，取决于课时、等级和录取配套。",
        "research_urls": ["https://a.gov.cn/1", "https://b.cn/2", "https://c.cn/3"],
    }, ensure_ascii=False), encoding="utf-8")
    workflow = BrowserWritingWorkflow(
        workflow_id="00000000-0000-0000-0000-000000000099",
        kind="hotspot",
        topic="辽宁中考科目调整",
        prompt="提示词",
        prompt_sha256="hash",
        conversation_id=FIXED_CONVERSATION_ID,
        status=WorkflowStatus.PUSH_CONFIRMED,
        raw_response="DeepSeek 初稿",
        response_provider="deepseek_user_paste",
        edit_notes=("核对政策原文",),
        article_path=str(article),
    )
    build_calls = []
    monkeypatch.setattr(wechat_mp_content, "build_hotspot_article", lambda **k: build_calls.append(k))
    with pytest.raises(ValueError, match="热点公开文案未通过门禁"):
        browser_cli.push_staged_workflow(workflow, root=tmp_path)
    assert build_calls == []
```

- [ ] **Step 3: 运行两个定点测试并确认失败**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_browser_write_cli.py::test_hotspot_stage_rejects_editorial_leak_before_images tests/unit/test_wechat_mp_browser_push.py::test_hotspot_push_rechecks_public_copy_before_build -q`

Expected: FAIL，现有流程仍会先准备图片或构建文章。

- [ ] **Step 4: 在两个入口调用同一门禁**

`_validate_staged_article` 在原创性检查之后、`prepare_hotspot_topic_images` 之前调用公开文案与评分门禁；`push_staged_workflow` 在读取 `CodexHotspotDraft` 后、`build_hotspot_article` 之前再次调用。入库摘要增加评分，不改变文学稿路径。

- [ ] **Step 5: 运行工作流测试**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_browser_write_cli.py tests/unit/test_wechat_mp_browser_push.py -q`

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add stock-ai/scripts/tools/wechat_mp_browser_write.py stock-ai/tests/unit/test_wechat_mp_browser_write_cli.py stock-ai/tests/unit/test_wechat_mp_browser_push.py
git commit -m "修复：热点稿入库与推送前执行双门禁"
```

### Task 4: 更新公众号热点写作 Skill

**Files:**
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md`
- Modify: `.cursor/skills/wechat-mp-drafts/rules-implemented.md`

**Interfaces:**
- Documents: 阻断门禁与编辑评分门禁的适用边界、外部参考及代码映射。

- [ ] **Step 1: 写入外部经验与门禁分层**

在“改稿检查清单”前新增“公开文案门禁”小节，列出标题兑现、事实与判断分离、核心论点、普通人成本、反方边界、结尾问题、移动端段落七项；明确“不能写成”等过程语言拒绝，“不等于”等正常论述不拒绝。

- [ ] **Step 2: 更新规则到代码映射**

在 `rules-implemented.md` 记录 `wechat_mp_hotspot_quality_gate.py`、入库入口和推送入口，注明阻断项与 5/7 评分阈值。

- [ ] **Step 3: 校验 Skill 与差异**

Run: `python3 /Users/huan.yu/.codex/skills/.system/skill-creator/scripts/quick_validate.py .cursor/skills/wechat-mp-drafts`

Expected: `Skill is valid!`。

Run: `git diff --check -- .cursor/skills/wechat-mp-writing/hotspot-deep-review.md .cursor/skills/wechat-mp-drafts/rules-implemented.md`

Expected: 无输出。

- [ ] **Step 4: 提交**

```bash
git add .cursor/skills/wechat-mp-writing/hotspot-deep-review.md .cursor/skills/wechat-mp-drafts/rules-implemented.md
git commit -m "文档：固化公众号热点写作门禁"
```

### Task 5: 修正辽宁稿并回归验证

**Files:**
- Modify: `stock-ai/output/hotspot_codex_liaoning_exam.json`

**Interfaces:**
- Consumes: 新公开文案与编辑评分门禁。
- Produces: 不含编辑指令泄漏的公众号草稿。

- [ ] **Step 1: 修正问题句**

```text
这是辽宁的地方政策，各地中考方案并不相同，辽宁的调整不代表全国统一安排。
```

- [ ] **Step 2: 运行定点门禁和相关回归测试**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_hotspot_quality_gate.py tests/unit/test_wechat_mp_browser_write_cli.py tests/unit/test_wechat_mp_browser_push.py tests/unit/test_wechat_mp_hotspot_article.py -q`

Expected: PASS。

- [ ] **Step 3: 创建新的手工交接工作流并完成两次确认**

使用现有 `wechat_mp_browser_write` 命令依次执行 `prepare`、`confirm-prompt`、`record-pasted`、`stage`、`confirm-push`。沿用原有 DeepSeek 初稿留痕和三张抖音封面，不调用 DeepSeek，不新增或生成图片。

- [ ] **Step 4: 推送修正版并检查草稿状态**

推送时临时设置 `WECHAT_MP_API_RESOLVE_IP=`，避免旧固定路由覆盖当前白名单出口；成功标准为新工作流状态 `drafted`、返回非空 `media_id`，且公众号草稿正文中不存在“不能写成”。

- [ ] **Step 5: 检查最终差异**

Run: `git diff --check`

Expected: 无本次修改引入的空白错误；不处理工作区内用户已有的其他改动。
