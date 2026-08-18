# 公众号角色卡代码收口与旧测试修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将热点商业和银发角色卡代码完整纳入 Git，并按当前公众号规则修复影视与热点测试中的 14 个基线失败。

**Architecture:** 角色卡继续以 `account-role-card.md` 为唯一真源，四个稿型直接调用现有加载器。旧测试按根因分为热点清洗与标题、影视正文归一化、影视封面、稳定模板资源、过期试跑测试五组；每组独立验证和提交。影视模板从被忽略的 `data/` 迁到已跟踪的 `assets/wechat_mp/templates/`，运行缓存仍留在 `data/`。

**Tech Stack:** Python 3.11、pytest、Markdown、JSON、Git 精确暂存。

## Global Constraints

- 对外品牌固定为 `栀夏未完成`。
- 四个稿型继续共享 `.cursor/skills/wechat-mp-writing/account-role-card.md`，不得复制人格正文。
- prompt 顺序固定为“角色卡 → 稿型任务 → 选题与联网事实 → 输出规则”。
- 保留现有 JSON schema、来源、原创、长度、配图、安全和 Codex-only 门禁。
- 先用 `systematic-debugging` 定位每组根因，再按 TDD 验证 RED 和 GREEN。
- 不通过删除断言、跳过测试或放宽内容门禁换取通过。
- 当前 Skill/规格、当前生产行为、稳定用户决定优先于旧测试断言。
- 不暂存图片、缓存、`data/`、`.env`、Cookie、token、持仓或其他项目文件。
- 不修改微信发布接口、选题策略、`virtual_lifestyle` 人物母版或平台标识流程。
- Git 提交信息使用中文，每次提交只包含一个可独立审阅单元。

---

## 文件结构

- Track: `stock-ai/scripts/tools/wechat_mp_hot_business_article.py` — 热点商业研究、Codex prompt 与文章构建。
- Track: `stock-ai/scripts/tools/wechat_mp_silver_article.py` — 银发研究、Codex prompt 与文章构建。
- Track: `stock-ai/tests/unit/test_wechat_mp_hot_business_article.py` — 热点商业结构化写稿测试。
- Track: `stock-ai/tests/unit/test_wechat_mp_silver_article.py` — 银发结构化写稿测试。
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_polish.py` — 删除纯编审选题段。
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_article.py` — 超长地缘标题回退到语义完整的 section title。
- Modify: `stock-ai/tests/unit/test_wechat_mp_hotspot_article.py` — 热点两个回归用例。
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_figures.py` — 归一化只做结构清洗，保留小标题内容和 bullet。
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_polish.py` — bullet 转正文时保留场景标签。
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_figures.py` — 影视归一化回归。
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_polish.py` — 场景标签回归。
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_cover.py` — 封面缺失返回结构化错误。
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_morning_discussion.py` — 封面兜底回归。
- Create: `stock-ai/assets/wechat_mp/templates/tv_review_v2.json` — 已跟踪的机器可读影视模板。
- Create: `stock-ai/assets/wechat_mp/templates/teach_you_a_lesson.body_core.md` — 已跟踪的影视结构金样。
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_review_template.py` — 从已跟踪资源读取模板。
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_review_template.py` — 模板与金样测试。
- Modify: `stock-ai/docs/WECHAT_MP_TV_REVIEW.md` — 更新模板真源路径。
- Modify: `.cursor/skills/wechat-mp-drafts/tv-review-template.md` — 更新 Agent 真源路径。
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_trial.py` — 将历史固定片名断言改为稳定规则断言。

---

### Task 1: 将热点商业与银发完整纳入版本控制

**Files:**
- Track: `stock-ai/scripts/tools/wechat_mp_hot_business_article.py`
- Track: `stock-ai/scripts/tools/wechat_mp_silver_article.py`
- Track: `stock-ai/tests/unit/test_wechat_mp_hot_business_article.py`
- Track: `stock-ai/tests/unit/test_wechat_mp_silver_article.py`

**Interfaces:**
- Consumes: `account_role_prompt_block() -> str`、现有热点研究、银发研究与 Codex draft 数据类。
- Produces: Git 可追溯的 `generate_hot_business_draft()`、`build_hot_business_article()`、`generate_silver_draft()`、`build_silver_article()`。

- [ ] **Step 1: 扫描四个未跟踪文件中的凭据和个人数据**

Run:

```bash
rg -n "cookie|authorization|access_token|secret|password|持仓|WECHAT_MP_APPSECRET\s*=|DEEPSEEK_API_KEY\s*=" \
  stock-ai/scripts/tools/wechat_mp_hot_business_article.py \
  stock-ai/scripts/tools/wechat_mp_silver_article.py \
  stock-ai/tests/unit/test_wechat_mp_hot_business_article.py \
  stock-ai/tests/unit/test_wechat_mp_silver_article.py
```

Expected: 无真实凭据赋值、Cookie、token 或个人持仓；测试 URL 只使用 `.example` 或公开政务域名。

- [ ] **Step 2: 验证角色卡顺序和既有门禁**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_hot_business_article.py \
  tests/unit/test_wechat_mp_silver_article.py \
  tests/unit/test_wechat_mp_codex_hot_business.py \
  tests/unit/test_wechat_mp_codex_silver.py -q
```

Expected: PASS；热点商业与银发 prompt 均先出现 `## 账号角色卡（最先遵守）`，来源、长度和分方向安全规则不回退。

- [ ] **Step 3: 检查只纳入四个目标文件**

Run:

```bash
git status --short -- \
  stock-ai/scripts/tools/wechat_mp_hot_business_article.py \
  stock-ai/scripts/tools/wechat_mp_silver_article.py \
  stock-ai/tests/unit/test_wechat_mp_hot_business_article.py \
  stock-ai/tests/unit/test_wechat_mp_silver_article.py
```

Expected: 四个文件均显示 `??`，没有目录级 `git add`。

- [ ] **Step 4: 提交完整功能单元**

```bash
git add -- \
  stock-ai/scripts/tools/wechat_mp_hot_business_article.py \
  stock-ai/scripts/tools/wechat_mp_silver_article.py \
  stock-ai/tests/unit/test_wechat_mp_hot_business_article.py \
  stock-ai/tests/unit/test_wechat_mp_silver_article.py
git diff --cached --check
git commit -m "feat: 纳入热点商业与银发写稿模块"
```

---

### Task 2: 修复热点编审话术残留和标题语义截断

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_polish.py:250-325`
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_article.py:300-345,1680-1740`
- Modify: `stock-ai/tests/unit/test_wechat_mp_hotspot_article.py:160-190,280-305`

**Interfaces:**
- Consumes: `_HOTSPOT_SELECTION_LEAK_BANNED`、`HotspotTopic.section_title`、`_WECHAT_TITLE_MAX`。
- Produces: `_drop_pure_selection_meta(text: str) -> str`；语义完整且不超过微信限制的热点标题。

- [ ] **Step 1: 用现有失败用例确认 RED**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_hotspot_article.py::test_reflow_hotspot_why_section \
  tests/unit/test_wechat_mp_hotspot_article.py::test_build_hotspot_title_geo_no_mid_name_cut -q
```

Expected: 2 FAIL；一个残留“五条候选”，另一个标题含冒号且截成“企图针对？”。

- [ ] **Step 2: 增加正常数量事实不被误删的回归用例**

```python
def test_reflow_hotspot_keeps_public_fact_with_numbered_candidates_word() -> None:
    from scripts.tools.wechat_mp_hotspot_polish import reflow_hotspot_body

    raw = "公开名单显示，五条候选线路都经过同一片施工区域。"

    assert reflow_hotspot_body(raw) == raw
```

- [ ] **Step 3: 运行新增用例确认当前正常事实可保留**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_hotspot_article.py::test_reflow_hotspot_keeps_public_fact_with_numbered_candidates_word -q
```

Expected: PASS；后续修复必须继续保持该用例通过。

- [ ] **Step 4: 在进入通用小标题清洗前删除纯编审段**

在 `wechat_mp_hotspot_polish.py` 增加：

```python
_WHY_PICK_PREFIX_RE = re.compile(r"^>?\s*为什么选这一题")


def _drop_pure_selection_meta(text: str) -> str:
    kept: list[str] = []
    for paragraph in re.split(r"\n\n+", text or ""):
        stripped = paragraph.strip()
        if not stripped:
            continue
        if _WHY_PICK_PREFIX_RE.search(stripped) and any(
            marker in stripped for marker in _HOTSPOT_SELECTION_LEAK_BANNED
        ):
            continue
        kept.append(stripped)
    return "\n\n".join(kept).strip()
```

并将 `reflow_hotspot_body()` 的输入改为：

```python
    source = _drop_pure_selection_meta((text or "").strip())
    out = strip_hotspot_subheadings(
        humanize_hotspot_boilerplate(
            humanize_hotspot_field_labels(_normalize_hotspot_legacy_sections(source))
        )
    )
```

- [ ] **Step 5: 超长地缘标题优先使用 section title**

在 `build_hotspot_title()` 的 fallback 分支中，`sanitize_public_title(raw)` 之后、调用 `enrich_title_for_search()` 之前增加：

```python
    separators = ("：", ":")
    clipped_tail_risk = len(clean) > _WECHAT_TITLE_MAX and any(sep in clean for sep in separators)
    if clipped_tail_risk and topic.section_title:
        clean = f"{topic.section_title}，发生了什么？"
```

这里先判断未裁剪的 `clean` 长度，不能先调用 `_clip_wechat_title()`。地缘映射已经将该测试的 `section_title` 解析为“中东局势再升温”。

- [ ] **Step 6: 运行热点专项确认 GREEN**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest tests/unit/test_wechat_mp_hotspot_article.py tests/unit/test_wechat_mp_hot_trends.py -q
```

Expected: PASS，原先 2 个失败和新增正常事实用例全部通过。

- [ ] **Step 7: 精确暂存并提交**

`wechat_mp_hotspot_article.py` 当前还有用户既有“研究函数公开化”工作区改动，必须使用 `git add -p` 或等价的缓存补丁，只暂存标题修复 hunk；不得暂存 `attach_hotspot_research` 重命名。

```bash
git add -- stock-ai/scripts/tools/wechat_mp_hotspot_polish.py stock-ai/tests/unit/test_wechat_mp_hotspot_article.py
git add -p stock-ai/scripts/tools/wechat_mp_hotspot_article.py
git diff --cached --check
git diff --cached | rg "attach_hotspot_research" && exit 1 || true
git commit -m "fix: 清理热点编审话术并保护标题语义"
```

---

### Task 3: 分离影视结构归一化并保留剧情场景词

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_figures.py:600-645`
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_polish.py:10-35,90-100`
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_figures.py:30-60`
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_polish.py:15-40`

**Interfaces:**
- Consumes: `_clean_section_title()`、`_fix_merits_duplicate_character_bullets()`、`strip_recommend_hook()`。
- Produces: `normalize_tv_review_body()` 保留用于配图锚点的结构；`finalize_tv_review_body()` 被单独调用时保留场景词。

- [ ] **Step 1: 确认四个正文失败为同一调用链根因**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_tv_figures.py::test_normalize_tv_review_body_strips_bold \
  tests/unit/test_wechat_mp_tv_figures.py::test_normalize_strips_label_colon_section \
  tests/unit/test_wechat_mp_tv_figures.py::test_normalize_merits_relabels_duplicate_character_bullets \
  tests/unit/test_wechat_mp_tv_polish.py::test_finalize_tv_review_strips_subheadings -q
```

Expected: 4 FAIL；前三个在 `normalize_tv_review_body()` 尾部调用 `finalize_tv_review_body()` 后丢结构，第四个在 `merge_tv_bullets_to_prose()` 删除冒号前场景词。

- [ ] **Step 2: 让 normalize 只完成结构归一化**

将 `normalize_tv_review_body()` 末尾：

```python
    from scripts.tools.wechat_mp_monetization import strip_recommend_hook
    from scripts.tools.wechat_mp_tv_polish import finalize_tv_review_body

    return finalize_tv_review_body(strip_recommend_hook(text))
```

替换为：

```python
    from scripts.tools.wechat_mp_monetization import strip_recommend_hook

    return strip_recommend_hook(text)
```

这样评分和剧照锚点仍能看到 `> ` 小标题与 `· ` bullet；本步骤不改变 `inject_tv_review_figures()`。

- [ ] **Step 3: bullet 转正文时保留完整场景标签**

将 `merge_tv_bullets_to_prose()` 中：

```python
            body = _BULLET_LINE_RE.sub("", b).strip()
            body = re.sub(r"^[^：:]{1,12}[：:]\s*", "", body, count=1)
```

改为：

```python
            body = _BULLET_LINE_RE.sub("", b).strip()
```

`finalize_tv_review_body()` 的输出应包含“开篇送外卖：彼得翻窗进巷战。”，不能只剩“彼得翻窗进巷战。”。

- [ ] **Step 4: 运行影视正文专项确认 GREEN**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_tv_figures.py \
  tests/unit/test_wechat_mp_tv_polish.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交正文归一化修复**

```bash
git add -- \
  stock-ai/scripts/tools/wechat_mp_tv_figures.py \
  stock-ai/scripts/tools/wechat_mp_tv_polish.py \
  stock-ai/tests/unit/test_wechat_mp_tv_figures.py \
  stock-ai/tests/unit/test_wechat_mp_tv_polish.py
git diff --cached --check
git commit -m "fix: 保留影视正文结构与剧情场景词"
```

---

### Task 4: 将讨论稿封面缺失转换为结构化错误

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_cover.py:497-525`
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_morning_discussion.py:50-80`

**Interfaces:**
- Consumes: `ensure_discussion_cover(topic) -> Path`。
- Produces: `pick_discussion_draft_thumb(topic: dict[str, Any], *, force_reupload: bool = False) -> tuple[str | None, dict[str, Any] | None]` 在封面缺失时返回 `(None, error)`。

- [ ] **Step 1: 用现有封面用例确认 RED**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_tv_morning_discussion.py::test_pick_tv_draft_thumb_discussion_no_stock_fallback -q
```

Expected: FAIL，`FileNotFoundError: 缺事件配图` 直接穿透。

- [ ] **Step 2: 在讨论稿封面入口捕获文件缺失**

将：

```python
    cover_path = ensure_discussion_cover(topic)
```

替换为：

```python
    try:
        cover_path = ensure_discussion_cover(topic)
    except FileNotFoundError as exc:
        return None, {
            "errcode": -1,
            "errmsg": f"话题讨论封面不存在: {exc}",
        }
```

不得调用 `pick_tv_review_thumb()`、股票封面或品牌通用封面作为兜底。

- [ ] **Step 3: 运行讨论稿封面测试确认 GREEN**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest tests/unit/test_wechat_mp_tv_morning_discussion.py -q
```

Expected: PASS。

- [ ] **Step 4: 提交封面异常修复**

```bash
git add -- \
  stock-ai/scripts/tools/wechat_mp_tv_cover.py \
  stock-ai/tests/unit/test_wechat_mp_tv_morning_discussion.py
git diff --cached --check
git commit -m "fix: 规范影视讨论稿封面缺失错误"
```

---

### Task 5: 将影视模板迁到已跟踪的稳定资源目录

**Files:**
- Create: `stock-ai/assets/wechat_mp/templates/tv_review_v2.json`
- Create: `stock-ai/assets/wechat_mp/templates/teach_you_a_lesson.body_core.md`
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_review_template.py:1-65`
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_review_template.py`
- Modify: `stock-ai/docs/WECHAT_MP_TV_REVIEW.md:6-15`
- Modify: `.cursor/skills/wechat-mp-drafts/tv-review-template.md:6-16`

**Interfaces:**
- Consumes: 已跟踪 JSON 与 Markdown 资源。
- Produces: `load_tv_review_template() -> dict[str, Any]` 和 `load_golden_body_core() -> str` 在干净检出中可用。

- [ ] **Step 1: 用现有模板测试确认 RED**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest tests/unit/test_wechat_mp_tv_review_template.py -q
```

Expected: 3 FAIL，均因被忽略的 `data/wechat_mp_tv_review_template.json` 不存在。

- [ ] **Step 2: 创建机器可读模板**

`stock-ai/assets/wechat_mp/templates/tv_review_v2.json` 写入：

```json
{
  "template_id": "tv_review_v2",
  "version": 2,
  "reference": {
    "golden_body_core": "assets/wechat_mp/templates/teach_you_a_lesson.body_core.md"
  },
  "sections": [
    {"role": "conclusion", "example_heading": "连夜刷完10集，半夜却有点发虚", "content_hint": "场面钩子、主题和第一段观感"},
    {"role": "about", "example_heading": "看着像揍人爽剧，其实是在写老师失了势", "content_hint": "作品背景和反差立意"},
    {"role": "episode_guide", "example_heading": "分集速写：10集几乎没废场", "content_hint": "按集写具体桥段"},
    {"role": "audience", "example_heading": "爱这口的会熬夜，不吃这套的会更烦", "content_hint": "适合与劝退边界"},
    {"role": "try_it", "example_heading": "拿不准就开前两集", "content_hint": "试看建议和互动问题"}
  ],
  "heading_style": {
    "forbidden_section_titles": ["先说结论", "它是什么", "为什么值得看", "适合谁", "怎么判断"],
    "forbidden_heading_patterns": ["简单交代：", "分集速写："],
    "discouraged_heading_patterns": ["看着像X，其实是在Y", "爱X会追，Y会更烦"],
    "variation_note": "新稿只继承五节任务，不照抄金样小标题。"
  },
  "layout": {
    "figure_count": 10,
    "ratings_footnote": "评分数据来自公开页面，统计时间以正文标注为准。"
  }
}
```

- [ ] **Step 3: 创建最小但完整的结构金样**

`stock-ai/assets/wechat_mp/templates/teach_you_a_lesson.body_core.md` 写入五节正文；必须包含以下完整内容，并且不含 `[[fig:`：

```markdown
> 连夜刷完10集，半夜却有点发虚

《铁拳教育》最容易让人记住的是拳头落下去的痛快，可10集看完，真正留下来的不是谁又挨了揍，而是学校里的正常办法为什么一步步失效。爽感给了观众出口，后怕则来自同一个问题：当规则救不了人，越界会不会被误认成正义。

> 看着像揍人爽剧，其实是在写老师失了势

故事把“教权保护局”放进失控校园，让专员替普通老师处理校暴、恐龙家长和权力压迫。它最有意思的地方不是把暴力包装成答案，而是让每一次出手都暴露制度已经拖到了哪一步。

> 分集速写：10集几乎没废场

· 第1集（失控的教室）：老师连维持课堂都要付出尊严，专员的到来先像一场解气表演。

· 第3集（宣判之后）：纸面上的结论没有结束争议，受伤的人和旁观者仍要承担后果。

· 第5集（恐龙家长）：家长把爱变成控制，学校退让一次，普通教师就多失去一寸空间。

· 第8—10集（代价回来）：拳头解决了眼前冲突，却没有替所有人补上失灵的规则。

> 爱这口的会熬夜，不吃这套的会更烦

喜欢高密度冲突、校园议题和制度困境的观众容易一集接一集看下去。若无法接受用暴力制造爽点，或者更在意程序边界，这部剧也会不断让人不舒服。

> 拿不准就开前两集

前两集已经把爽感、争议和人物关系摆全。看到第二集结尾，如果仍然只觉得吵闹，就不必勉强；如果开始追问这些人还能怎么办，后面的分歧才真正值得看。你更在意出手时的痛快，还是出手之后谁来承担代价？
```

- [ ] **Step 4: 修改模板路径常量和模块说明**

```python
TEMPLATE_ROOT = ROOT / "assets" / "wechat_mp" / "templates"
TEMPLATE_PATH = TEMPLATE_ROOT / "tv_review_v2.json"
```

模块 docstring 改为：

```python
"""影视长文稳定模板（真源：assets/wechat_mp/templates/tv_review_v2.json）。"""
```

`golden_body_core_path()` 继续使用 JSON 中相对 `ROOT` 的路径，不增加环境变量或 data fallback。

- [ ] **Step 5: 更新两处文档真源路径**

将旧的 `data/wechat_mp_tv_review_template.json` 和 `data/wechat_mp_tv_review_golden/teach_you_a_lesson.body_core.md` 链接分别改为：

```text
assets/wechat_mp/templates/tv_review_v2.json
assets/wechat_mp/templates/teach_you_a_lesson.body_core.md
```

运行缓存 `data/wechat_mp_tv_body_cache/` 的说明保持不变。

- [ ] **Step 6: 运行模板测试确认 GREEN**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest tests/unit/test_wechat_mp_tv_review_template.py tests/unit/test_wechat_mp_tv_role_card.py -q
```

Expected: PASS；加载到 `tv_review_v2`、5 个 sections，金样含“连夜刷完10集”和“分集速写”，且无图片标记。

- [ ] **Step 7: 提交稳定模板资源**

```bash
git add -- \
  stock-ai/assets/wechat_mp/templates/tv_review_v2.json \
  stock-ai/assets/wechat_mp/templates/teach_you_a_lesson.body_core.md \
  stock-ai/scripts/tools/wechat_mp_tv_review_template.py \
  stock-ai/tests/unit/test_wechat_mp_tv_review_template.py \
  stock-ai/docs/WECHAT_MP_TV_REVIEW.md \
  .cursor/skills/wechat-mp-drafts/tv-review-template.md
git diff --cached --check
git commit -m "fix: 跟踪影视长文模板真源"
```

---

### Task 6: 将影视试跑测试与当前日期和评分规则对齐

**Files:**
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_trial.py:20-55,120-155`

**Interfaces:**
- Consumes: `tv_trial_active()`、`resolve_scheduled_batch()`、`rank_topics()`、`pick_tv_topic()` 的现有公开行为。
- Produces: 不依赖本地忽略文件、不把某部作品永久写死为第一名的稳定测试。

- [ ] **Step 1: 记录四个旧断言为何失效**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_tv_trial.py::test_tv_trial_active_when_enabled \
  tests/unit/test_wechat_mp_tv_trial.py::test_resolve_scheduled_batch_tv_trial \
  tests/unit/test_wechat_mp_tv_trial.py::test_curated_hot_prefers_euphoria \
  tests/unit/test_wechat_mp_tv_trial.py::test_pick_tv_topic_skips_harlots -q
```

Expected: 4 FAIL；前两个依赖不存在的忽略配置，后两个仍把《亢奋》写死为第一名，而当前 2026-06-17 加权排名第一是《铁拳教育》。

- [ ] **Step 2: 用临时配置验证试跑期限，不依赖 data 文件**

将 `test_tv_trial_active_when_enabled` 改为：

```python
def test_tv_trial_active_respects_enabled_until(tmp_path: Path, monkeypatch) -> None:
    trial = tmp_path / "trial.json"
    trial.write_text(
        json.dumps(
            {"enabled": True, "until": "2026-06-24", "queue": [{"title_en": "Test"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.tools.wechat_mp_tv_topics.TRIAL_PATH", trial)

    assert tv_trial_active(
        when=datetime(2026, 6, 17, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert not tv_trial_active(
        when=datetime(2026, 6, 25, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
```

- [ ] **Step 3: 将批次测试改为当前无试跑配置的稳定行为**

```python
def test_resolve_scheduled_batch_without_trial_uses_market_calendar(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_tv_topics.TRIAL_PATH", tmp_path / "missing.json"
    )

    weekend = resolve_scheduled_batch(
        now=datetime(2026, 6, 21, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    weekday = resolve_scheduled_batch(
        now=datetime(2026, 6, 17, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )

    assert weekend == "weekend"
    assert weekday == "evening"
```

- [ ] **Step 4: 将固定片名排名断言改为评分公式断言**

```python
def test_curated_hot_ranking_follows_score_and_expiry() -> None:
    on = datetime(2026, 6, 17).date()
    ranked = rank_topics(CURATED_HOT, on=on)

    assert ranked
    assert ranked == sorted(ranked, key=_score_topic, reverse=True)
    assert ranked[0]["title_en"] == "Teach You a Lesson"
    assert all(str(topic.get("hot_until") or "") >= on.isoformat() for topic in ranked)
```

该日期的第一名由当前公式 `heat*0.45 + controversy*0.25 + write*0.30` 算出，不再要求《亢奋》永久第一。

- [ ] **Step 5: 修正队列 fixture 的日期并继续验证禁用项**

在 `test_pick_tv_topic_skips_harlots` 中先定义 `when`，再用同一天构造队列：

```python
    when = datetime(2026, 6, 17, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    trial.write_text(
        json.dumps(
            {
                "enabled": True,
                "until": "2026-06-24",
                "queue": rank_topics(CURATED_HOT, on=when.date()),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
```

末尾断言改为：

```python
    assert topic["title_en"] == "Teach You a Lesson"
    assert "Harlots" not in str(topic.get("title_en") or "")
    title = build_tv_review_title(topic, now=when)
    assert audit_recommendation_safety(title=title, body="", digest="") == []
    assert title == "追完《铁拳教育》，爽完为什么没特痛快？"
```

- [ ] **Step 6: 运行影视试跑测试确认 GREEN**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest tests/unit/test_wechat_mp_tv_trial.py -q
```

Expected: PASS。

- [ ] **Step 7: 提交稳定试跑测试**

```bash
git add -- stock-ai/tests/unit/test_wechat_mp_tv_trial.py
git diff --cached --check
git commit -m "test: 对齐影视试跑当前规则"
```

---

### Task 7: 全量验证与工作区边界审计

**Files:**
- Verify only: `stock-ai/tests/unit/test_wechat_mp_*.py`
- Verify only: 当前 Git 工作区与最近提交。

**Interfaces:**
- Consumes: Tasks 1-6 的全部改动。
- Produces: 可复现的公众号全量测试结果和无关改动隔离证据。

- [ ] **Step 1: 运行角色卡和 Codex 核心回归**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_role_card.py \
  tests/unit/test_wechat_mp_codex_client.py \
  tests/unit/test_wechat_mp_codex_hotspot.py \
  tests/unit/test_wechat_mp_codex_hot_business.py \
  tests/unit/test_wechat_mp_codex_silver.py \
  tests/unit/test_wechat_mp_hot_business_article.py \
  tests/unit/test_wechat_mp_silver_article.py \
  tests/unit/test_wechat_mp_tv_role_card.py -q
```

Expected: PASS。

- [ ] **Step 2: 运行公众号单元测试全集**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest tests/unit/test_wechat_mp_*.py -q
```

Expected: PASS；若出现新的失败，按失败文件和测试名报告，不能用专项通过替代全量结果。

- [ ] **Step 3: 运行语法和差异检查**

Run:

```bash
cd stock-ai
.venv/bin/python -m py_compile \
  scripts/tools/wechat_mp_hot_business_article.py \
  scripts/tools/wechat_mp_silver_article.py \
  scripts/tools/wechat_mp_hotspot_article.py \
  scripts/tools/wechat_mp_hotspot_polish.py \
  scripts/tools/wechat_mp_tv_figures.py \
  scripts/tools/wechat_mp_tv_polish.py \
  scripts/tools/wechat_mp_tv_cover.py \
  scripts/tools/wechat_mp_tv_review_template.py
cd ..
git diff --check
```

Expected: Python 编译成功，Git 无新增空白错误。

- [ ] **Step 4: 审计提交和剩余工作区**

Run:

```bash
git log -10 --oneline
git status --short
git show --stat --oneline HEAD
```

Expected: 本轮提交只包含代码、测试、模板和文档；图片、缓存、凭据与其他项目改动仍保持原有未提交状态。

---

## 完成验收

- 热点商业和银发四个文件已被 Git 跟踪，角色卡注入测试通过。
- “五条候选”纯编审段被删除，正常公开数量事实保留。
- 地缘热点标题不再留下冒号残句或缺宾语问句。
- 影视归一化保留配图锚点结构，单独执行最终清洗时仍保留剧情场景词。
- 讨论稿封面缺失返回结构化错误且不回退股票图。
- 影视模板和金样位于已跟踪资源目录，干净检出可加载。
- 影视试跑测试不依赖忽略文件，排名遵守当前评分和有效期。
- `tests/unit/test_wechat_mp_*.py` 全量通过，或剩余失败被逐项证明不在本规格范围内。
- 所有提交均未包含图片素材、运行缓存、凭据、持仓或其他无关改动。
