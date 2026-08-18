# 「栀夏未完成」账号角色卡实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `hotspot`、`hot_business`、`silver`、`tv_review` 的自动 Codex 写稿和当前 Codex 手写流程接入同一份“栀夏未完成”隐形作者角色卡，并在角色卡缺失或不完整时失败关闭。

**Architecture:** 在仓库级 Skill 目录保存唯一人格真源，由一个小型 Python 加载器负责路径解析、完整性校验和 prompt 区块包装。四个稿型只调用加载器，不复制人格正文；热点和影视的首稿、扩写、参考稿改写都重新带入同一区块，防止后处理丢失人格约束。现有来源、字数、原创、配图、合规和 Codex 来源门禁保持不变。

**Tech Stack:** Python 3.11+、pytest、Markdown Skill 文档、现有 `call_wechat_mp_llm` Codex 路由。

## Global Constraints

- 对外品牌固定为 `栀夏未完成`。
- 采用隐形作者人格，正文不写“我是栀夏”“作为栀夏”或“栀夏认为”。
- 优先观察普通人付出的时间、金钱、尊严和选择成本。
- 区分事实、当事人说法、公开争议和作者判断，不把推断写成结论。
- 不冒充记者、当事人、专家或内部人士，不编造亲历、采访和现场细节。
- 正文不重复声明 AI 身份；平台发表环节按平台规则统一处理标识。
- 第一阶段只覆盖 `hotspot`、`hot_business`、`silver`、`tv_review`；不得接入 `virtual_lifestyle`、财经旧模板、简选带货、股吧转载或短剧推广。
- 角色卡只决定观察者、价值排序和语言边界；稿型 Skill 继续决定结构、长度与专属禁区。
- 事实纪律和合规规则优先于角色语气；任何加载或校验失败都停止写稿，不静默回退。
- 公众号 AI 写稿继续只用 Codex，不恢复 DeepSeek 或其他后端。
- 不提交 `.env`、Cookie、token、证书、订阅链接或任何个人凭据。

---

## 文件结构

- Create: `.cursor/skills/wechat-mp-writing/account-role-card.md` — 账号人格唯一真源，包含可读规则和运行时关键边界。
- Create: `stock-ai/scripts/tools/wechat_mp_role_card.py` — 定位、读取、校验并包装角色卡 prompt。
- Create: `stock-ai/tests/unit/test_wechat_mp_role_card.py` — 加载器失败关闭、区块格式和敏感信息扫描测试。
- Modify: `stock-ai/scripts/tools/wechat_mp_hot_business_article.py` — 热点商业结构化 Codex prompt 注入。
- Modify: `stock-ai/tests/unit/test_wechat_mp_hot_business_article.py` — 热点商业注入顺序测试。
- Modify: `stock-ai/scripts/tools/wechat_mp_silver_article.py` — 银发结构化 Codex prompt 注入。
- Modify: `stock-ai/tests/unit/test_wechat_mp_silver_article.py` — 银发注入顺序测试。
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_article.py` — 社会热点、财经热点、扩写及参考稿改写 prompt 注入。
- Modify: `stock-ai/tests/unit/test_wechat_mp_hotspot_article.py` — 热点各生成分支注入与顺序测试。
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_review_article.py` — 影视安利、热搜讨论及参考稿改写 prompt 注入。
- Create: `stock-ai/tests/unit/test_wechat_mp_tv_role_card.py` — 影视两种正文模式和改写链路注入测试。
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md` — 当前 Codex 手写前置读取顺序。
- Modify: `.cursor/skills/wechat-mp-writing/SKILL.md` — 写稿/改稿前置读取顺序和唯一真源链接。

---

### Task 1: 建立唯一角色卡真源和失败关闭加载器

**Files:**
- Create: `.cursor/skills/wechat-mp-writing/account-role-card.md`
- Create: `stock-ai/scripts/tools/wechat_mp_role_card.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_role_card.py`

**Interfaces:**
- Consumes: 仓库根目录 `.cursor/skills/wechat-mp-writing/account-role-card.md`。
- Produces: `load_account_role_card() -> str`；`account_role_prompt_block() -> str`；模块常量 `ACCOUNT_ROLE_CARD_PATH: Path`。

- [ ] **Step 1: 写加载成功、失败关闭和安全扫描的失败测试**

```python
from pathlib import Path

import pytest

from scripts.tools import wechat_mp_role_card as role_card
from scripts.tools.wechat_mp_codex_client import _assert_prompt_safe


VALID_CARD = """# 栀夏未完成账号角色卡

## 运行时关键边界
- 隐形作者人格
- 普通人生活成本：时间、金钱、尊严和选择成本
- 事实与推断分开
- 禁止虚构亲历
- 禁止显性自称栀夏
"""


def test_load_account_role_card_returns_non_empty_text(tmp_path, monkeypatch):
    path = tmp_path / "account-role-card.md"
    path.write_text(VALID_CARD, encoding="utf-8")
    monkeypatch.setattr(role_card, "ACCOUNT_ROLE_CARD_PATH", path)

    assert role_card.load_account_role_card() == VALID_CARD.strip()


def test_account_role_prompt_block_has_stable_heading(tmp_path, monkeypatch):
    path = tmp_path / "account-role-card.md"
    path.write_text(VALID_CARD, encoding="utf-8")
    monkeypatch.setattr(role_card, "ACCOUNT_ROLE_CARD_PATH", path)

    block = role_card.account_role_prompt_block()

    assert block.startswith("## 账号角色卡（最先遵守）\n")
    assert "隐形作者人格" in block
    _assert_prompt_safe(block)


def test_load_account_role_card_rejects_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(role_card, "ACCOUNT_ROLE_CARD_PATH", tmp_path / "missing.md")

    with pytest.raises(RuntimeError, match="角色卡文件不存在"):
        role_card.load_account_role_card()


@pytest.mark.parametrize("content", ["", "# 只有标题\n隐形作者人格"])
def test_load_account_role_card_rejects_empty_or_incomplete(content, tmp_path, monkeypatch):
    path = tmp_path / "account-role-card.md"
    path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(role_card, "ACCOUNT_ROLE_CARD_PATH", path)

    with pytest.raises(RuntimeError, match="角色卡为空|角色卡缺少关键边界"):
        role_card.load_account_role_card()
```

- [ ] **Step 2: 运行测试确认因模块不存在而失败**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_role_card.py -q`

Expected: FAIL，报 `ModuleNotFoundError` 或无法导入 `wechat_mp_role_card`。

- [ ] **Step 3: 写入完整角色卡真源**

在 `.cursor/skills/wechat-mp-writing/account-role-card.md` 写入设计规格中的身份、稳定人格、语言边界和四稿型适配，并保留以下机器校验段原文：

```markdown
## 运行时关键边界

- 隐形作者人格：让读者从观察角度识别作者，不在正文播报“我是栀夏”。
- 普通人生活成本：优先观察时间、金钱、尊严和选择成本。
- 事实与推断分开：区分可核验事实、当事人说法、公开争议和作者判断。
- 禁止虚构亲历：不编造亲眼看见、采访、交流、现场或内部信息。
- 禁止显性自称栀夏：不用“作为栀夏”“我是栀夏”“栀夏认为”。
```

角色卡其余正文不得要求固定开头、固定金句或固定结尾，以免形成新的模板味。

- [ ] **Step 4: 实现最小加载器**

```python
"""Load and validate the single account-level writing persona for WeChat."""

from __future__ import annotations

from pathlib import Path


ACCOUNT_ROLE_CARD_PATH = (
    Path(__file__).resolve().parents[3]
    / ".cursor"
    / "skills"
    / "wechat-mp-writing"
    / "account-role-card.md"
)

_REQUIRED_BOUNDARIES = (
    "隐形作者人格",
    "时间、金钱、尊严和选择成本",
    "事实与推断分开",
    "禁止虚构亲历",
    "禁止显性自称栀夏",
)


def load_account_role_card() -> str:
    path = ACCOUNT_ROLE_CARD_PATH
    if not path.is_file():
        raise RuntimeError(f"公众号账号角色卡文件不存在: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"公众号账号角色卡为空: {path}")
    missing = [marker for marker in _REQUIRED_BOUNDARIES if marker not in text]
    if missing:
        raise RuntimeError(f"公众号账号角色卡缺少关键边界: {'、'.join(missing)}")
    return text


def account_role_prompt_block() -> str:
    return f"## 账号角色卡（最先遵守）\n{load_account_role_card()}"
```

- [ ] **Step 5: 运行加载器测试确认通过**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_role_card.py -q`

Expected: PASS，5 个测试用例全部通过。

- [ ] **Step 6: 提交角色卡基础设施**

```bash
git add .cursor/skills/wechat-mp-writing/account-role-card.md \
  stock-ai/scripts/tools/wechat_mp_role_card.py \
  stock-ai/tests/unit/test_wechat_mp_role_card.py
git commit -m "feat: 新增公众号账号角色卡"
```

---

### Task 2: 接入热点商业和银发结构化写稿

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_hot_business_article.py:1-115`
- Modify: `stock-ai/tests/unit/test_wechat_mp_hot_business_article.py:65-96`
- Modify: `stock-ai/scripts/tools/wechat_mp_silver_article.py:1-174`
- Modify: `stock-ai/tests/unit/test_wechat_mp_silver_article.py:56-106`

**Interfaces:**
- Consumes: `account_role_prompt_block() -> str` from Task 1。
- Produces: 热点商业与银发传给 `call_wechat_mp_llm` 的 user prompt，首区块均为账号角色卡。

- [ ] **Step 1: 写热点商业 prompt 顺序的失败测试**

在现有 `test_generate_hot_business_prompt_contains_completion_rules` 中追加：

```python
    assert "## 账号角色卡（最先遵守）" in prompt
    assert prompt.index("## 账号角色卡（最先遵守）") < prompt.index("热点：")
    assert prompt.index("## 账号角色卡（最先遵守）") < prompt.index("文章必须围绕")
```

- [ ] **Step 2: 写银发 prompt 顺序的失败测试**

新增：

```python
def test_silver_prompt_starts_with_account_role_card(monkeypatch) -> None:
    captured: list[str] = []
    monkeypatch.setattr(article_mod, "resolve_silver_topic", lambda **_: _topic())
    monkeypatch.setattr(article_mod, "research_silver_topic", lambda _: _research("relation"))

    def fake_llm(messages, **_kwargs):
        captured.append(messages[-1]["content"])
        return json.dumps(_payload(), ensure_ascii=False)

    monkeypatch.setattr(article_mod, "call_wechat_mp_llm", fake_llm)
    article_mod.generate_silver_draft()

    prompt = captured[0]
    assert "## 账号角色卡（最先遵守）" in prompt
    assert prompt.index("## 账号角色卡（最先遵守）") < prompt.index("方向：")
    assert prompt.index("## 账号角色卡（最先遵守）") < prompt.index("写作要求：")
```

- [ ] **Step 3: 运行两个测试文件确认新增断言失败**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_hot_business_article.py tests/unit/test_wechat_mp_silver_article.py -q`

Expected: FAIL，prompt 中找不到 `## 账号角色卡（最先遵守）`。

- [ ] **Step 4: 在两个模块导入并前置角色区块**

两个模块都增加：

```python
from scripts.tools.wechat_mp_role_card import account_role_prompt_block
```

热点商业 prompt 开头改为：

```python
    prompt = f"""{account_role_prompt_block()}

## 稿型任务：热点商业
你为公众号“栀夏未完成”撰写一篇热点商业深稿。

热点：{title}
```

银发 prompt 开头改为：

```python
    prompt = f"""{account_role_prompt_block()}

## 稿型任务：银发生活
你为公众号“栀夏未完成”撰写一篇面向 50—65 岁、临近或刚退休读者的文章。

方向：{topic.lane}
```

其余 JSON schema、来源白名单、完读约束和分方向安全规则保持原样。

- [ ] **Step 5: 运行两个测试文件确认通过**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_hot_business_article.py tests/unit/test_wechat_mp_silver_article.py -q`

Expected: PASS。

- [ ] **Step 6: 提交两个结构化稿型接入**

```bash
git add stock-ai/scripts/tools/wechat_mp_hot_business_article.py \
  stock-ai/tests/unit/test_wechat_mp_hot_business_article.py \
  stock-ai/scripts/tools/wechat_mp_silver_article.py \
  stock-ai/tests/unit/test_wechat_mp_silver_article.py
git commit -m "feat: 热点商业和银发稿接入角色卡"
```

---

### Task 3: 接入社会热点、财经热点及热点二次改写

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_article.py:830-930,1260-1490`
- Modify: `stock-ai/tests/unit/test_wechat_mp_hotspot_article.py`

**Interfaces:**
- Consumes: `account_role_prompt_block() -> str` from Task 1。
- Produces: `_generate_trends_hotspot_body`、`generate_hotspot_body`、`_rewrite_trends_hotspot_against_references`、`_rewrite_hotspot_against_references` 的每次 Codex user prompt 都带同一角色卡区块。

- [ ] **Step 1: 写热点首稿和改写 prompt 包装函数的失败测试**

为避免测试依赖联网选题，在 `wechat_mp_hotspot_article.py` 增加可单测的内部纯函数接口，并先在测试中按接口写失败用例：

```python
def test_hotspot_prompt_with_role_places_role_before_kind_and_facts():
    from scripts.tools.wechat_mp_hotspot_article import _hotspot_prompt_with_role

    prompt = _hotspot_prompt_with_role(
        kind_label="社会热点深评",
        prompt="【联网事实】某公开事实\n\n## 写作要求\n只写已核验事实",
    )

    assert prompt.index("## 账号角色卡（最先遵守）") < prompt.index("## 稿型任务：社会热点深评")
    assert prompt.index("## 稿型任务：社会热点深评") < prompt.index("【联网事实】")


def test_hotspot_rewrite_prompt_keeps_account_role_card(monkeypatch):
    from scripts.tools import wechat_mp_hotspot_article as hotspot

    captured: list[str] = []
    monkeypatch.setattr(hotspot, "is_wechat_mp_llm_configured", lambda: True)
    monkeypatch.setattr(
        hotspot,
        "call_wechat_mp_llm",
        lambda messages, **_: captured.append(messages[-1]["content"]) or ("正文。" * 900),
    )

    hotspot._rewrite_trends_hotspot_against_references(
        "初稿。" * 900,
        reference_block="参考报道",
    )

    assert "## 账号角色卡（最先遵守）" in captured[0]
    assert captured[0].index("## 账号角色卡（最先遵守）") < captured[0].index("【参考文章】")
```

- [ ] **Step 2: 运行新增热点测试确认失败**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_hotspot_article.py -q`

Expected: FAIL，`_hotspot_prompt_with_role` 尚不存在，改写 prompt 也没有角色区块。

- [ ] **Step 3: 实现热点 prompt 统一包装函数**

增加导入和纯函数：

```python
from scripts.tools.wechat_mp_role_card import account_role_prompt_block


def _hotspot_prompt_with_role(
    *,
    kind_label: str,
    prompt: str,
) -> str:
    return (
        f"{account_role_prompt_block()}\n\n"
        f"## 稿型任务：{kind_label}\n"
        f"{prompt.strip()}"
    ).strip()
```

这里保持角色卡和稿型任务位于原 prompt 之前；原 prompt 内部的事实、写作要求与输出格式不移动，避免无关重构。

- [ ] **Step 4: 用统一包装函数改造两个首稿分支**

社会热点 `_generate_trends_hotspot_body` 保留当前三引号 prompt 的全部内容，只修改账号名，并在三引号结束后增加包装调用：

```diff
-    prompt = f"""为微信公众号「牛马也智能」写一篇**社会热点深评**（单主题纯段落长文）。
+    prompt = f"""为微信公众号「栀夏未完成」写一篇**社会热点深评**（单主题纯段落长文）。
@@
 只输出正文。"""
+    prompt = _hotspot_prompt_with_role(
+        kind_label="社会热点深评", prompt=prompt
+    )
```

财经热点 `generate_hotspot_body` 同样在现有完整 prompt 构造完成后调用：

```python
    prompt = _hotspot_prompt_with_role(kind_label="财经热点深评", prompt=prompt)
```

`PUBLIC_MP_WRITER_RULE`、`HOTSPOT_RESEARCHER_VOICE_RULE`、`PLATFORM_PROPERTY_RISK_RULE`、`context`、全部写作要求及 `monetization_prompt_block("hotspot")` 保持原位。扩写继续复用已经带角色卡的 `prompt`，不得二次包装。

- [ ] **Step 5: 给两个参考稿改写 prompt 前置角色卡**

两个改写函数都在现有 prompt 构造完成后调用统一包装函数，不改变原有长度和事实要求：

```python
    prompt = _hotspot_prompt_with_role(
        kind_label="热点深评参考稿改写",
        prompt=prompt,
    )
```

- [ ] **Step 6: 补充财经首稿、社会首稿和两个改写函数的捕获断言**

测试须分别捕获四条路径传给 `call_wechat_mp_llm` 的 user prompt，并对每条执行：

```python
assert "## 账号角色卡（最先遵守）" in prompt
assert prompt.index("## 账号角色卡（最先遵守）") < prompt.index("## 稿型任务：")
```

社会/财经首稿再断言稿型任务位于 `【联网事实】` 或上下文事实标记之前；扩写 prompt 断言角色卡只出现一次：

```python
assert prompt.count("## 账号角色卡（最先遵守）") == 1
```

- [ ] **Step 7: 运行热点测试确认通过**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_hotspot_article.py tests/unit/test_wechat_mp_hot_trends.py -q`

Expected: PASS。

- [ ] **Step 8: 提交热点接入**

```bash
git add stock-ai/scripts/tools/wechat_mp_hotspot_article.py \
  stock-ai/tests/unit/test_wechat_mp_hotspot_article.py
git commit -m "feat: 热点长文全链路接入角色卡"
```

---

### Task 4: 接入影视安利、影视讨论及参考稿改写

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_review_article.py:150-410`
- Create: `stock-ai/tests/unit/test_wechat_mp_tv_role_card.py`

**Interfaces:**
- Consumes: `account_role_prompt_block() -> str` from Task 1。
- Produces: `generate_tv_review_body`、`generate_tv_discussion_body`、`_rewrite_discussion_against_references` 的每次 Codex user prompt 都带角色卡；`virtual_lifestyle` 无任何变化。

- [ ] **Step 1: 写影视安利、话题讨论和参考改写的失败测试**

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.tools import wechat_mp_tv_review_article as tv


NOW = datetime(2026, 8, 18, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def _topic(mode: str = "review") -> dict[str, object]:
    return {
        "title_zh": "测试电影",
        "title_en": "Test Film",
        "platform": "院线",
        "type": "film",
        "year": "2026",
        "hook": "一个普通人不得不重新选择的故事",
        "content_mode": "discussion" if mode == "discussion" else "review",
        "trend_title": "测试电影里的选择为什么引发争议",
        "reference_angles": [],
        "sources": [],
        "from_trend": False,
    }


def _capture_prompt(monkeypatch, response: str):
    captured: list[str] = []
    monkeypatch.setattr(tv, "is_wechat_mp_llm_configured", lambda: True)
    monkeypatch.setattr(
        tv,
        "call_wechat_mp_llm",
        lambda messages, **_: captured.append(messages[-1]["content"]) or response,
    )
    return captured


def test_tv_review_prompt_starts_with_account_role_card(monkeypatch):
    captured = _capture_prompt(monkeypatch, "> 第一节\n" + "正文。" * 500)
    monkeypatch.setenv("WECHAT_MP_TV_RESEARCH", "0")
    tv.generate_tv_review_body(_topic(), now=NOW)
    assert captured[0].index("## 账号角色卡（最先遵守）") < captured[0].index("## 稿型任务：影视长文")


def test_tv_discussion_prompt_starts_with_account_role_card(monkeypatch):
    captured = _capture_prompt(monkeypatch, "正文。" * 900)
    monkeypatch.setenv("WECHAT_MP_TV_RESEARCH", "0")
    tv.generate_tv_discussion_body(_topic("discussion"), now=NOW)
    assert captured[0].index("## 账号角色卡（最先遵守）") < captured[0].index("## 稿型任务：影视话题讨论")


def test_tv_reference_rewrite_keeps_account_role_card(monkeypatch):
    captured = _capture_prompt(monkeypatch, "正文。" * 900)
    tv._rewrite_discussion_against_references("初稿。" * 900, reference_block="参考报道")
    assert "## 账号角色卡（最先遵守）" in captured[0]
    assert captured[0].index("## 账号角色卡（最先遵守）") < captured[0].index("【参考文章】")
```

- [ ] **Step 2: 运行新测试确认失败**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_tv_role_card.py -q`

Expected: FAIL，三个 prompt 都缺少角色卡标题或稿型任务标题。

- [ ] **Step 3: 在影视模块导入角色卡并前置三个 prompt**

增加：

```python
from scripts.tools.wechat_mp_role_card import account_role_prompt_block
```

三个 prompt 只改开头，后续原有内容逐字保留：

```diff
-    prompt = f"""为微信公众号「牛马也智能」写一篇影视安利稿（个人观感，非官方通稿）。
+    prompt = f"""{account_role_prompt_block()}
+
+## 稿型任务：影视长文
+为微信公众号「栀夏未完成」写一篇影视安利稿（个人观感，非官方通稿）。
```

```diff
-    prompt = f"""为微信公众号「牛马也智能」写一篇**热搜话题讨论稿**（社会观察，非剧评）。
+    prompt = f"""{account_role_prompt_block()}
+
+## 稿型任务：影视话题讨论
+为微信公众号「栀夏未完成」写一篇**热搜话题讨论稿**（社会观察，非剧评）。
```

```diff
-    prompt = f"""对照【参考文章】的写法，重写下面这篇热搜讨论初稿。
+    prompt = f"""{account_role_prompt_block()}
+
+## 稿型任务：影视话题参考稿改写
+对照【参考文章】的写法，重写下面这篇热搜讨论初稿。
```

保留 `_discussion_voice_prompt_block()`、`template_prompt_block()`、`tv_depth_prompt_block()` 和所有原有事实、剧情、长度与排版约束。不得修改 `.cursor/skills/wechat-mp-virtual-lifestyle/` 或其人物母版。

- [ ] **Step 4: 运行影视角色卡和原有影视回归测试**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_tv_role_card.py tests/unit/test_wechat_mp_tv_review_template.py tests/unit/test_wechat_mp_tv_trial.py tests/unit/test_wechat_mp_tv_morning_discussion.py -q`

Expected: PASS。

- [ ] **Step 5: 提交影视接入**

```bash
git add stock-ai/scripts/tools/wechat_mp_tv_review_article.py \
  stock-ai/tests/unit/test_wechat_mp_tv_role_card.py
git commit -m "feat: 影视长文全链路接入角色卡"
```

---

### Task 5: 更新手写工作流文档并完成整体回归

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-writing/SKILL.md`

**Interfaces:**
- Consumes: `.cursor/skills/wechat-mp-writing/account-role-card.md` from Task 1。
- Produces: 当前 Codex 在手写四类长文时统一执行“角色卡 → 唯一稿型专题文档 → 研究与成稿”的读取顺序。

- [ ] **Step 1: 在两个入口 Skill 增加同一前置规则**

在 `wechat-mp-drafts/SKILL.md` 的 Codex 长图文交接之前、`wechat-mp-writing/SKILL.md` 的 Agent 工作流之前加入：

```markdown
## 账号角色卡前置步骤

当前 Codex 手写或改写 `hotspot`、`hot_business`、`silver`、`tv_review` 时：

1. 先完整读取 [account-role-card.md](../wechat-mp-writing/account-role-card.md)。
2. 再按本 Skill 决策树读取唯一命中的稿型专题文档。
3. 角色卡只决定观察者、价值排序和语言边界；结构、长度、来源与专属禁区以稿型文档为准。
4. 角色卡缺失、为空或关键边界不完整时停止写稿，不沿用旧口吻继续。

`virtual_lifestyle` 继续使用其显性人物母版，不读取本角色卡。
```

在 `wechat-mp-writing/SKILL.md` 中链接使用同目录相对地址 `[account-role-card.md](account-role-card.md)`，避免错误的跨目录路径。

- [ ] **Step 2: 运行文档唯一真源和读取顺序检查**

Run: `rg -n "账号角色卡前置步骤|account-role-card.md|virtual_lifestyle" .cursor/skills/wechat-mp-drafts/SKILL.md .cursor/skills/wechat-mp-writing/SKILL.md`

Expected: 两个 Skill 都出现前置步骤；完整人格正文只存在于 `account-role-card.md`，入口 Skill 只链接、不复制。

- [ ] **Step 3: 运行角色卡专项测试**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_role_card.py tests/unit/test_wechat_mp_hot_business_article.py tests/unit/test_wechat_mp_silver_article.py tests/unit/test_wechat_mp_hotspot_article.py tests/unit/test_wechat_mp_hot_trends.py tests/unit/test_wechat_mp_tv_role_card.py -q`

Expected: PASS。

- [ ] **Step 4: 运行四稿型和 Codex 安全回归**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_codex_client.py tests/unit/test_wechat_mp_codex_hotspot.py tests/unit/test_wechat_mp_codex_hot_business.py tests/unit/test_wechat_mp_codex_silver.py tests/unit/test_wechat_mp_tv_*.py -q`

Expected: PASS；Codex prompt 安全扫描、来源门禁、热点商业、银发、热点和影视既有门禁均未回退。

- [ ] **Step 5: 运行格式和差异检查**

Run: `git diff --check`

Expected: 无尾随空格、冲突标记或多余 EOF 空行。

Run: `git status --short`

Expected: 本功能涉及的文件与计划一致；工作区中其他既有改动不被暂存或修改。

- [ ] **Step 6: 人工样稿验收但不推送微信草稿箱**

选择同一个有消费者、员工或小经营者影响面的公开商业热点，分别生成 `hotspot` 和 `hot_business` 的 `--dry-run` 样稿。人工核对：

1. 两篇都能回答“这件事落到普通人身上，会改变什么”。
2. 两篇都没有“我是栀夏”、虚构亲历或把推断写成事实。
3. `hotspot` 重点解释公共争议与规则后果；`hot_business` 重点解释钱、成本、渠道和利益流向，结构明显不同。
4. 没有固定金句、固定结尾问句或为了人格统一而牺牲信息密度。
5. 本步骤只生成本地预览，不调用微信写草稿接口。

- [ ] **Step 7: 提交文档和回归收口**

```bash
git add .cursor/skills/wechat-mp-drafts/SKILL.md \
  .cursor/skills/wechat-mp-writing/SKILL.md
git commit -m "docs: 固化公众号角色卡写稿顺序"
```

---

## 完成验收

- `account-role-card.md` 是唯一人格真源，其他文件仅引用。
- 加载器对缺失、空文件和五项关键边界缺失全部失败关闭。
- `hotspot`、`hot_business`、`silver`、`tv_review` 的首稿 prompt 均按“角色卡 → 稿型规则 → 联网事实”排序。
- 热点扩写、热点参考稿改写和影视参考稿改写仍携带角色卡，且每个 prompt 只出现一次角色卡区块。
- `virtual_lifestyle` 与其他非目标稿型没有接入角色卡。
- 现有来源、原创、字数、配图、合规、Codex-only 和敏感 prompt 扫描测试全部通过。
- 人工样稿体现相同价值排序，但热点深评与热点商业的结构和问题意识明显不同。
