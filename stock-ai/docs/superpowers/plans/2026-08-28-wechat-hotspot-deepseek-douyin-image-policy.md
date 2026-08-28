# 用户主动热点深评 DeepSeek 与抖音配图硬门禁 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户主动热点深评只能通过固定 DeepSeek 网页会话产出初稿，并强制先完成抖音封面检索；真实图片不足时允许少图，禁止创建或执行任何自动生图补位。

**Architecture:** 保留现有 `wechat_mp_browser_workflow` 两次确认状态机，把 `deepseek_browser` 来源写入持久状态并在 stage/push 双重校验；直接 `wechat_mp_draft --codex-draft` 不再接受主动热点。新增热点图片策略模块读取 `douyin-search.json` 与 `figure_sources.json`，只消费已核验真实图片；热点渲染走 verified-only 分支，封面至少一张、正文零至三张，银发与其他稿型继续使用原有图片策略。

**Tech Stack:** Python 3.11、dataclasses、JSON、pytest、Pillow、现有 OpenCLI DeepSeek 浏览器客户端与微信公众号草稿 API。

## Global Constraints

- 用户主动热点深评必须由固定 DeepSeek 网页会话直接产出标题和正文初稿，Agent 只做研究、核实与编辑。
- 第一次确认发生在提示词发送前；第二次确认发生在微信草稿写入前，二者不能复用或跳过。
- 配图必须先检索抖音，只读搜索结果卡片和封面，不打开、不播放视频。
- 抖音之后才允许补政务、官方媒体、正规新闻机构、法规页面等可追溯证据图。
- 热点深评禁止自动生成图片，不创建 `codex-image-request.json`，不调用 ChatGPT、ImageGen、DeepSeek 或其他生图渠道。
- 合格图片有几张用几张；正文允许 0—3 张，封面必须至少 1 张。
- 没有合格封面时停止推送，不使用品牌图、无关素材或生成图兜底。
- 不改变定时热点、文学、银发、原创小说、栀夏生活分享和其他稿型的既有模型与图片策略。
- 用户可见内容、测试名称说明和提交信息均使用中文，不使用 emoji。

---

## File Map

- Create: `stock-ai/scripts/tools/wechat_mp_hotspot_image_policy.py` — 抖音检索状态、来源清单和真实图片可用性校验的单一策略模块。
- Create: `stock-ai/tests/unit/test_wechat_mp_hotspot_image_policy.py` — 抖音优先状态及 0/1/2/4 图规则测试。
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_workflow.py` — 持久化并校验 `deepseek_browser` 回复来源。
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_write.py` — stage/push 校验 DeepSeek 来源与热点图片状态，输出第二次确认清单。
- Modify: `stock-ai/scripts/tools/wechat_mp_draft.py` — 禁止主动热点通过直接 `--codex-draft` 绕过 DeepSeek 工作流。
- Modify: `stock-ai/scripts/tools/wechat_mp_content.py` — 用户主动热点使用 verified-only 可变配图分支。
- Modify: `stock-ai/scripts/tools/wechat_mp_codex_images.py` — 为热点增加不创建补图请求的 verified-only 准备接口；保留银发等旧调用兼容性。
- Modify: `stock-ai/scripts/tools/wechat_mp_discussion_figures.py` — 增加不联网补洞、不使用原创占位的真实图片选择与注入接口。
- Modify: `stock-ai/tests/unit/test_wechat_mp_browser_workflow.py` — DeepSeek 来源状态测试。
- Modify: `stock-ai/tests/unit/test_wechat_mp_browser_write_cli.py` — stage 前来源与配图状态门禁测试。
- Modify: `stock-ai/tests/unit/test_wechat_mp_browser_push.py` — push 再校验与可变图集成测试。
- Modify: `stock-ai/tests/unit/test_wechat_mp_codex_hotspot.py` — 直接热点 `--codex-draft` 拒绝及少图渲染测试。
- Modify: `stock-ai/tests/unit/test_wechat_mp_codex_images.py` — 热点 verified-only 不创建补图请求；newspic、silver 旧行为回归。
- Modify: `stock-ai/tests/unit/test_wechat_mp_discussion_figures.py` — 真实图片选择、封面去重和零至三张正文图测试。
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md` — 统一主动热点模型和图片总规则。
- Modify: `.cursor/skills/wechat-mp-drafts/INDEX.md` — 路由到唯一 DeepSeek SOP。
- Modify: `.cursor/skills/wechat-mp-writing/deepseek-writer-sop.md` — 主动热点唯一成稿流程真源和图片确认清单。
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md` — 删除 Codex 推荐入口、固定四图和生成补图冲突。
- Modify: `.cursor/skills/wechat-mp-drafts/rules-implemented.md` — 记录规则到代码与测试的映射。

---

### Task 1: 锁定 DeepSeek 浏览器成稿来源

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_workflow.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_write.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_draft.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_browser_workflow.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_browser_write_cli.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_codex_hotspot.py`

**Interfaces:**
- Produces: `BrowserWritingWorkflow.response_provider: str`，仅允许成功浏览器回复写入 `deepseek_browser`。
- Produces: `require_deepseek_browser_response(workflow: BrowserWritingWorkflow) -> None`，状态或来源不合法时抛出 `WorkflowTransitionError`。
- Changes: `_validate_codex_draft_kinds(["hotspot"], path)` 必须拒绝直接热点 JSON，并提示使用 `wechat_mp_browser_write`。

- [ ] **Step 1: 写 DeepSeek 来源持久化与拒绝绕过的失败测试**

```python
def test_record_response_marks_deepseek_browser_provider(tmp_path: Path) -> None:
    workflow = create_workflow(kind="hotspot", topic="题目", prompt="提示", root=tmp_path)
    confirm_prompt(workflow.workflow_id, root=tmp_path)

    saved = record_response(workflow.workflow_id, "标题\n\n正文", root=tmp_path)

    assert saved.response_provider == "deepseek_browser"


def test_stage_rejects_hotspot_without_deepseek_browser_provider(tmp_path: Path) -> None:
    workflow = _response_workflow(tmp_path)
    payload = json.loads((_workflow_path(workflow.workflow_id, root=tmp_path)).read_text())
    payload["response_provider"] = ""
    (_workflow_path(workflow.workflow_id, root=tmp_path)).write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    result = browser_cli.main(
        ["stage", workflow.workflow_id, "--article", str(_valid_hotspot_json(tmp_path)), "--root", str(tmp_path)]
    )

    assert result == 2
    assert load_workflow(workflow.workflow_id, root=tmp_path).status == WorkflowStatus.RESPONSE_RECEIVED


def test_direct_hotspot_codex_draft_requires_browser_workflow(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="wechat_mp_browser_write"):
        draft_cli._validate_codex_draft_kinds(["hotspot"], tmp_path / "draft.json")
```

- [ ] **Step 2: 运行定点测试并确认按预期失败**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_browser_workflow.py \
  tests/unit/test_wechat_mp_browser_write_cli.py \
  tests/unit/test_wechat_mp_codex_hotspot.py -q
```

Expected: 新测试因缺少 `response_provider`、`require_deepseek_browser_response` 和直接入口拒绝逻辑而 FAIL。

- [ ] **Step 3: 实现最小 DeepSeek 来源门禁**

在 `BrowserWritingWorkflow` 增加兼容旧状态文件的默认字段：

```python
response_provider: str = ""
```

在 `record_response` 保存响应时写入：

```python
response_provider="deepseek_browser",
```

新增并在 `stage_edited_article`、`confirm_push`、`push_staged_workflow` 调用：

```python
def require_deepseek_browser_response(workflow: BrowserWritingWorkflow) -> None:
    if workflow.conversation_id != FIXED_CONVERSATION_ID:
        raise WorkflowTransitionError("热点深评必须来自指定 DeepSeek 固定会话")
    if workflow.response_provider != "deepseek_browser" or not workflow.raw_response.strip():
        raise WorkflowTransitionError("热点深评缺少 DeepSeek 浏览器初稿来源")
```

将 `wechat_mp_draft._validate_codex_draft_kinds` 的热点分支改为拒绝直接入口；`hot_business`、`silver`、`short_drama_feature` 保持原逻辑：

```python
if path is not None and kinds == ["hotspot"]:
    raise ValueError(
        "用户主动热点必须使用 scripts.tools.wechat_mp_browser_write 的 DeepSeek 双确认流程"
    )
```

- [ ] **Step 4: 运行定点测试并确认通过**

Run: 与 Step 2 相同。

Expected: 全部 PASS；现有登录失败、两次确认和文学工作流测试不回归。

- [ ] **Step 5: 提交 DeepSeek 来源门禁**

```bash
git add \
  stock-ai/scripts/tools/wechat_mp_browser_workflow.py \
  stock-ai/scripts/tools/wechat_mp_browser_write.py \
  stock-ai/scripts/tools/wechat_mp_draft.py \
  stock-ai/tests/unit/test_wechat_mp_browser_workflow.py \
  stock-ai/tests/unit/test_wechat_mp_browser_write_cli.py \
  stock-ai/tests/unit/test_wechat_mp_codex_hotspot.py
git commit -m "功能：锁定主动热点 DeepSeek 成稿流程"
```

---

### Task 2: 建立抖音优先检索状态与来源校验

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_hotspot_image_policy.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_hotspot_image_policy.py`

**Interfaces:**
- Produces: `DOUYIN_RESEARCH_FILENAME = "douyin-search.json"`。
- Produces: `DouyinCandidate`、`DouyinSearchRecord`、`VerifiedFigure`、`VerifiedHotspotImages` 四个冻结 dataclass。`VerifiedFigure` 固定包含 `path: Path`、`rel: str`、`caption: str`、`page_url: str`、`source_name: str`、`source_type: str`；`VerifiedHotspotImages` 固定包含 `cover_source: Path`、`body_figures: tuple[VerifiedFigure, ...]`、`source_meta: dict[str, dict[str, str]]`。
- Produces: `load_douyin_search(out_dir: Path, *, expected_topic: str) -> DouyinSearchRecord`。
- Produces: `validate_verified_hotspot_images(out_dir: Path, *, expected_topic: str, max_body: int = 3) -> VerifiedHotspotImages`。
- Consumes: 同目录 `figure_sources.json`、`cover_source.json`、`still-*` 图片。

- [ ] **Step 1: 写抖音状态和图片数量策略的失败测试**

测试文件包含以下完整行为：

```python
def test_missing_douyin_search_state_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="必须先完成抖音搜索"):
        validate_verified_hotspot_images(tmp_path, expected_topic="测试热点")


def test_zero_douyin_candidates_requires_reason_but_can_use_official_cover(tmp_path: Path) -> None:
    _write_douyin_state(
        tmp_path,
        topic="测试热点",
        candidates=[],
        fallback_reason="搜索结果无政务或正规媒体同题封面",
    )
    _write_verified_image(tmp_path, "still-01.jpg", source_type="official_media_webpage_screenshot")

    result = validate_verified_hotspot_images(tmp_path, expected_topic="测试热点")

    assert result.cover_source.name == "still-01.jpg"
    assert result.body_figures == ()


def test_douyin_candidate_must_match_verified_figure_source(tmp_path: Path) -> None:
    _write_douyin_state(
        tmp_path,
        topic="测试热点",
        candidates=[{
            "account": "浙江日报",
            "display_time": "1天前",
            "video_url": "https://www.douyin.com/video/123",
            "cover_url": "https://example.com/cover.jpg",
            "selected": True,
        }],
    )

    with pytest.raises(ValueError, match="所选抖音封面未写入 figure_sources"):
        validate_verified_hotspot_images(tmp_path, expected_topic="测试热点")


@pytest.mark.parametrize(
    ("image_count", "expected_body_count"),
    [(1, 0), (2, 1), (4, 3), (6, 3)],
)
def test_verified_images_use_one_cover_and_up_to_three_body_images(
    tmp_path: Path, image_count: int, expected_body_count: int
) -> None:
    _write_douyin_state_with_selected_cover(tmp_path, topic="测试热点")
    for index in range(1, image_count + 1):
        _write_verified_image(
            tmp_path,
            f"still-{index:02d}.jpg",
            source_type="douyin_cover" if index == 1 else "official_media_webpage_screenshot",
        )

    result = validate_verified_hotspot_images(tmp_path, expected_topic="测试热点")

    assert result.cover_source.name == "still-01.jpg"
    assert len(result.body_figures) == expected_body_count


def test_zero_verified_images_are_rejected(tmp_path: Path) -> None:
    _write_douyin_state(
        tmp_path,
        topic="测试热点",
        candidates=[],
        fallback_reason="搜索结果没有合格同题封面",
    )

    with pytest.raises(ValueError, match="缺少可追溯封面"):
        validate_verified_hotspot_images(tmp_path, expected_topic="测试热点")
```

测试 helper 必须写完整合法 JSON 字段和 800×600 测试图片。

- [ ] **Step 2: 运行新测试并确认失败**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest tests/unit/test_wechat_mp_hotspot_image_policy.py -q
```

Expected: FAIL，提示模块或接口不存在。

- [ ] **Step 3: 实现 JSON schema 与严格校验**

`douyin-search.json` 固定结构：

```json
{
  "schema_version": 1,
  "topic": "测试热点",
  "query": "测试热点",
  "completed_at": "2026-08-28T12:00:00+08:00",
  "fallback_reason": "",
  "candidates": [
    {
      "account": "浙江日报",
      "display_time": "1天前",
      "video_url": "https://www.douyin.com/video/123",
      "cover_url": "https://example.com/cover.jpg",
      "selected": true
    }
  ]
}
```

实现时执行以下不变量：

```python
if payload.get("schema_version") != 1:
    raise ValueError("抖音搜索状态 schema_version 必须为 1")
if record.topic != expected_topic:
    raise ValueError("抖音搜索状态与热点主题不一致")
if not record.candidates and not record.fallback_reason:
    raise ValueError("抖音无可用候选时必须记录原因")
if selected and not any(
    meta.get("source_type") == "douyin_cover"
    and meta.get("page_url") == candidate.video_url
    for meta in figure_sources.values()
):
    raise ValueError("所选抖音封面未写入 figure_sources")
```

只接受 `verified` 为布尔真或字符串 `"true"`、有效 `page_url`、完整来源名/日期/标题/图注，且图片通过现有尺寸与最小字节门禁。封面优先选 `cover_source.json` 指定且已核验的图片，否则从已选抖音图、其他核验图依次选取。正文排除封面并截取前三张。

- [ ] **Step 4: 运行新测试并确认通过**

Run: 与 Step 2 相同。

Expected: 全部 PASS。

- [ ] **Step 5: 提交抖音图片策略模块**

```bash
git add \
  stock-ai/scripts/tools/wechat_mp_hotspot_image_policy.py \
  stock-ai/tests/unit/test_wechat_mp_hotspot_image_policy.py
git commit -m "功能：增加热点抖音配图来源门禁"
```

---

### Task 3: 禁止热点自动补图并支持正文零至三图

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_codex_images.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_discussion_figures.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_codex_images.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_discussion_figures.py`

**Interfaces:**
- Produces: `prepare_verified_hotspot_topic_images(topic: dict[str, Any], *, max_body: int = 3) -> VerifiedHotspotImages`。
- Produces: `inject_verified_discussion_figures(body: str, topic: dict[str, Any], figures: tuple[VerifiedFigure, ...]) -> str`。
- Preserves: `prepare_newspic_topic_images` 与 silver 调用的旧生成协议不变。

- [ ] **Step 1: 把旧热点生成请求测试改写为 verified-only 失败测试**

删除只针对热点的以下旧期望：

- `test_prepare_hotspot_requests_cover_and_missing_body_slots`
- `test_prepare_hotspot_accepts_generated_cover_and_body_images`
- `test_prepare_hotspot_resume_skips_completed_network_fetch`

保留 newspic 原创图片测试。新增：

```python
def test_verified_hotspot_does_not_create_image_request_when_body_images_are_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cover_path = tmp_path / "topic" / "still-01.jpg"
    _valid_image(cover_path)
    prepared = VerifiedHotspotImages(
        cover_source=cover_path,
        body_figures=(),
        source_meta={"still-01.jpg": _source_meta("douyin_cover")},
    )
    monkeypatch.setattr(
        images_mod,
        "validate_verified_hotspot_images",
        lambda *_args, **_kwargs: prepared,
    )

    result = images_mod.prepare_verified_hotspot_topic_images(
        {"cover_slug": "topic", "trend_title": "事件"}, max_body=3
    )

    assert result.body_figures == ()
    assert not (tmp_path / "topic" / "codex-image-request.json").exists()


def test_verified_body_injection_accepts_zero_one_and_three_images() -> None:
    body = "第一段。\n\n第二段。\n\n第三段。\n\n第四段。"
    for count in (0, 1, 3):
        figures = tuple(
            VerifiedFigure(rel=f"discussion/topic/still-{index:02d}.jpg", caption=f"图源：来源{index}")
            for index in range(1, count + 1)
        )
        rendered = inject_verified_discussion_figures(body, _topic(), figures)
        assert rendered.count("[[fig:") == count
```

- [ ] **Step 2: 运行图片模块定点测试并确认失败**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_codex_images.py \
  tests/unit/test_wechat_mp_discussion_figures.py -q
```

Expected: 新接口缺失，测试 FAIL。

- [ ] **Step 3: 实现 verified-only 图片准备与注入**

在 `wechat_mp_codex_images.py` 新增：

```python
def prepare_verified_hotspot_topic_images(
    topic: dict[str, Any], *, max_body: int = 3
) -> VerifiedHotspotImages:
    out_dir = _out_dir(topic)
    return validate_verified_hotspot_images(
        out_dir,
        expected_topic=str(topic.get("trend_title") or topic.get("title_zh") or "").strip(),
        max_body=max_body,
    )
```

该函数不得调用 `_write_request`、`CodexImageGenerationRequired`、`_manual_paths` 或 `_supplement_missing_figures`。

在 `wechat_mp_discussion_figures.py` 新增只消费传入图片的注入函数，复用 `_distributed_inject_para_indices` 与现有 `[[fig:...]]` 标记生成，不调用 `ensure_discussion_body_figures`。零图直接返回清洗后的正文。

封面裁切增加明确来源参数：

```python
def ensure_discussion_cover_from_source(topic: dict[str, Any], source_path: Path) -> Path:
    """只裁切已核验来源图，不联网、不补图。"""
```

复用现有 2.35:1 裁切与 `_save_cover_source`，禁止在该函数中调用 `ensure_discussion_figures`。

- [ ] **Step 4: 运行图片模块测试并确认通过**

Run: 与 Step 2 相同。

Expected: 全部 PASS；newspic 旧原创流程测试仍通过，证明本次只收紧主动热点。

- [ ] **Step 5: 提交可变真实图片流程**

```bash
git add \
  stock-ai/scripts/tools/wechat_mp_codex_images.py \
  stock-ai/scripts/tools/wechat_mp_discussion_figures.py \
  stock-ai/tests/unit/test_wechat_mp_codex_images.py \
  stock-ai/tests/unit/test_wechat_mp_discussion_figures.py
git commit -m "功能：热点正文按真实图片数量排版"
```

---

### Task 4: 接入主动热点 stage、预演与 push

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_workflow.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_content.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_write.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_browser_workflow.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_codex_hotspot.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_browser_write_cli.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_browser_push.py`

**Interfaces:**
- Changes: `build_hotspot_article(..., image_policy: Literal["legacy", "verified_only"] = "legacy")`。
- Changes: 浏览器热点 stage 与 push 始终传入 `image_policy="verified_only"`。
- Changes: `BrowserWritingWorkflow.edit_notes: tuple[str, ...]` 保存 Agent 对 DeepSeek 初稿的主要修改；热点 stage 至少要求一条 `--edit-note`。
- Produces: `_hotspot_confirmation_summary(draft, workflow, images) -> tuple[str, ...]`，输出第二次确认清单字段。

- [ ] **Step 1: 写集成失败测试**

```python
def test_browser_hotspot_stage_requires_douyin_state_and_verified_cover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow = _hotspot_response_workflow(tmp_path)
    article_path = _valid_hotspot_json(tmp_path)
    monkeypatch.setattr(
        browser_cli,
        "prepare_verified_hotspot_topic_images",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("必须先完成抖音搜索")),
    )

    result = browser_cli.main(
        ["stage", workflow.workflow_id, "--article", str(article_path), "--root", str(tmp_path)]
    )

    assert result == 2
    assert load_workflow(workflow.workflow_id, root=tmp_path).status == WorkflowStatus.RESPONSE_RECEIVED


def test_browser_hotspot_stage_requires_agent_edit_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow = _hotspot_response_workflow(tmp_path)
    monkeypatch.setattr(
        browser_cli,
        "prepare_verified_hotspot_topic_images",
        lambda *_args, **_kwargs: _prepared_images(1),
    )

    result = browser_cli.main(
        ["stage", workflow.workflow_id, "--article", str(_valid_hotspot_json(tmp_path)), "--root", str(tmp_path)]
    )

    assert result == 2
    assert load_workflow(workflow.workflow_id, root=tmp_path).edit_notes == ()


@pytest.mark.parametrize(("body_count", "expected"), [(0, 0), (1, 1), (3, 3)])
def test_browser_hotspot_build_uses_actual_verified_body_count(
    monkeypatch: pytest.MonkeyPatch, body_count: int, expected: int
) -> None:
    prepared = _prepared_images(body_count)
    monkeypatch.setattr(content_mod, "prepare_verified_hotspot_topic_images", lambda *_a, **_k: prepared)

    article = content_mod.build_hotspot_article(
        codex_draft=_valid_draft(), image_policy="verified_only", upload_figures=False
    )

    assert article["body_text"].count("[[fig:") == expected


def test_browser_hotspot_push_rechecks_deepseek_and_image_policy(monkeypatch) -> None:
    workflow = _push_confirmed_hotspot_workflow(response_provider="deepseek_browser")
    calls: list[str] = []
    monkeypatch.setattr(
        content_mod,
        "build_hotspot_article",
        lambda *, codex_draft, upload_figures, image_policy: calls.append(image_policy)
        or {"title": codex_draft.title, "content": "<p>正文</p>"},
    )

    browser_cli.push_staged_workflow(workflow)

    assert calls == ["verified_only"]
```

- [ ] **Step 2: 运行集成测试并确认失败**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_codex_hotspot.py \
  tests/unit/test_wechat_mp_browser_write_cli.py \
  tests/unit/test_wechat_mp_browser_push.py -q
```

Expected: `image_policy`、图片准备门禁和确认摘要尚未接入，测试 FAIL。

- [ ] **Step 3: 实现 verified-only 集成**

`build_hotspot_article` 的社会热点配图分支按策略分流：

```python
if image_policy == "verified_only":
    prepared = prepare_verified_hotspot_topic_images(topic_dict, max_body=3)
    ensure_discussion_cover_from_source(topic_dict, prepared.cover_source)
    body_core = inject_verified_discussion_figures(
        polished,
        topic_dict,
        prepared.body_figures,
    )
else:
    # 保留定时热点与其他旧调用的现有逻辑
```

verified-only 分支不得读取 `WECHAT_MP_HOTSPOT_REQUIRE_FIGURES` 或用正文少于三图拒推。

在 hotspot stage 中完成：

1. `require_deepseek_browser_response(workflow)`；
2. 加载编辑稿；
3. `prepare_verified_hotspot_topic_images(draft.as_discussion_topic(), max_body=3)`；
4. `stage` 子命令增加可重复参数 `--edit-note`；热点至少一条，并由 `stage_edited_article(..., edit_notes=tuple(args.edit_note))` 持久化；
5. 输出标题、摘要、字数、来源数、DeepSeek 来源、Agent 编辑说明、实际图片总数、每张图来源与“本稿未自动生成图片”；
6. 校验成功后才转为 `EDITED`。

工作流字段和 stage 接口：

```python
edit_notes: tuple[str, ...] = ()

def stage_edited_article(
    workflow_id: str,
    article_path: Path,
    *,
    edit_notes: tuple[str, ...] = (),
    root: Path | None = None,
) -> BrowserWritingWorkflow:
    ...
```

push 前再次执行 DeepSeek 来源和图片策略校验，并调用：

```python
build_hotspot_article(
    codex_draft=draft,
    upload_figures=True,
    image_policy="verified_only",
)
```

- [ ] **Step 4: 运行集成测试并确认通过**

Run: 与 Step 2 相同。

Expected: 全部 PASS，stage/push 均失败关闭，0—3 张正文图均可构建。

- [ ] **Step 5: 提交主动热点集成**

```bash
git add \
  stock-ai/scripts/tools/wechat_mp_browser_workflow.py \
  stock-ai/scripts/tools/wechat_mp_content.py \
  stock-ai/scripts/tools/wechat_mp_browser_write.py \
  stock-ai/tests/unit/test_wechat_mp_browser_workflow.py \
  stock-ai/tests/unit/test_wechat_mp_codex_hotspot.py \
  stock-ai/tests/unit/test_wechat_mp_browser_write_cli.py \
  stock-ai/tests/unit/test_wechat_mp_browser_push.py
git commit -m "功能：接入主动热点双确认与少图推稿"
```

---

### Task 5: 清理 Skill 冲突并建立规则映射

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-drafts/INDEX.md`
- Modify: `.cursor/skills/wechat-mp-writing/deepseek-writer-sop.md`
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md`
- Modify: `.cursor/skills/wechat-mp-drafts/rules-implemented.md`

**Interfaces:**
- Consumes: Tasks 1—4 已实现的命令、状态字段与图片 schema。
- Produces: 用户主动热点唯一流程路由，不再出现 Codex 推荐、固定四图或缺图生成的相反指令。

- [ ] **Step 1: 记录修订前的冲突扫描结果**

Run:

```bash
rg -n \
  "用户主动.*热点|手动热点.*Codex|Codex 成稿入口|固定 4 张|不足.*生成|codex-image-request|内置 ImageGen|可走固定 DeepSeek" \
  .cursor/skills/wechat-mp-drafts \
  .cursor/skills/wechat-mp-writing
```

Expected: 能复现设计文档列出的相互冲突表述。

- [ ] **Step 2: 修改五份规则文档**

统一写入以下不可拆分的规则：

```text
用户主动热点深评必须走 deepseek-writer-sop：
Agent 研究并展示提示词 → 第一次确认 → 固定 DeepSeek 会话直接生成标题和初稿
→ Agent 核实编辑并先搜抖音封面 → 第二次确认 → 写微信草稿。
DeepSeek 失败时停止，不回退 Codex、Composer 或其他模型。
热点配图必须先搜抖音搜索结果封面，不打开视频；之后才能补权威网页证据图。
真实图片有几张用几张，正文允许 0—3 张；没有封面停止。
禁止创建原创补图请求或调用任何生图渠道。
```

从 `hotspot-deep-review.md` 删除或改写：

- “Codex 成稿入口（推荐）”；
- “固定 4 张”；
- “不足才生成原创事件图”；
- “读取 `codex-image-request.json` 后调用 ImageGen”；
- “正文少于 3 张拒推”。

在 `rules-implemented.md` 记录：`response_provider`、`douyin-search.json`、`verified_only`、零至三图测试和零图封面拒推。

- [ ] **Step 3: 验证 Skill 不再存在冲突路由**

Run:

```bash
rg -n \
  "手动热点.*Codex|Codex 成稿入口（推荐）|固定 4 张|不足.*生成原创|热点.*内置 ImageGen|可走固定 DeepSeek" \
  .cursor/skills/wechat-mp-drafts \
  .cursor/skills/wechat-mp-writing
```

Expected: 无匹配。随后运行：

```bash
rg -n \
  "必须走.*DeepSeek|必须先.*抖音|正文允许 0—3 张|禁止.*生成图片|没有.*封面.*停止" \
  .cursor/skills/wechat-mp-drafts \
  .cursor/skills/wechat-mp-writing
```

Expected: 入口、SOP、热点真源和代码映射均有一致命中。

- [ ] **Step 4: 提交 Skill 规则修订**

```bash
git add \
  .cursor/skills/wechat-mp-drafts/SKILL.md \
  .cursor/skills/wechat-mp-drafts/INDEX.md \
  .cursor/skills/wechat-mp-writing/deepseek-writer-sop.md \
  .cursor/skills/wechat-mp-writing/hotspot-deep-review.md \
  .cursor/skills/wechat-mp-drafts/rules-implemented.md
git commit -m "文档：统一热点 DeepSeek 与抖音配图规则"
```

---

### Task 6: 全量验证与真实预演检查

**Files:**
- Verify only: Tasks 1—5 的全部修改文件。

**Interfaces:**
- Consumes: 完整 DeepSeek 工作流、抖音研究状态、verified-only 图片和 skill 真源。
- Produces: 可供交付的测试证据与一次不写微信草稿的预演报告。

- [ ] **Step 1: 运行核心单元测试**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_browser_workflow.py \
  tests/unit/test_wechat_mp_browser_write_cli.py \
  tests/unit/test_wechat_mp_browser_push.py \
  tests/unit/test_wechat_mp_hotspot_image_policy.py \
  tests/unit/test_wechat_mp_codex_images.py \
  tests/unit/test_wechat_mp_discussion_figures.py \
  tests/unit/test_wechat_mp_codex_hotspot.py -q
```

Expected: 0 failed。

- [ ] **Step 2: 运行公众号相关回归测试**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest tests/unit/test_wechat_mp_*.py -q
```

Expected: 0 failed；若存在与当前改动无关的既有失败，记录完整测试名和错误，不把交付描述为通过。

- [ ] **Step 3: 用临时目录验证四种图片数量**

分别构造 0、1、2、4 张已核验图片：

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_hotspot_image_policy.py::test_zero_verified_images_are_rejected \
  tests/unit/test_wechat_mp_hotspot_image_policy.py::test_verified_images_use_one_cover_and_up_to_three_body_images -q
```

Expected: 0 图因缺封面拒绝；1 图为封面且正文 0 图；2 图为封面加正文 1 图；4 图为封面加正文 3 图。

- [ ] **Step 4: 验证不会产生原创补图请求**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_codex_images.py::test_verified_hotspot_does_not_create_image_request_when_body_images_are_missing -q
```

Expected: PASS，临时话题目录不存在 `codex-image-request.json` 和新建 `manual-*`。

- [ ] **Step 5: 复核最终差异与提交记录**

Run:

```bash
git diff --check
git status --short
git log -6 --oneline
```

Expected: 当前任务文件没有未提交差异；用户原有其他改动保持不变；最近提交均为中文且范围聚焦。
