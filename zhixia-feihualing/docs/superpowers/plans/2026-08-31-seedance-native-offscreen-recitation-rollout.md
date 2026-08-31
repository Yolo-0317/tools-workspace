# Seedance 原生画外朗诵统一迁移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从《九歌·湘君》开始，让所有后续栀夏诗舞 Seedance 提示词统一生成原生画外朗诵、环境声和氛围音乐，并以自动校验阻止旧的“原片无可辨识人声”规则回流。

**Architecture:** 新建一份项目级声音模板作为写作真源；《九歌》校验器只把第 01、02 篇视为历史输入，从第 03 篇起强制要求原生画外朗诵契约、准确诗句和末句贴尾时间。生产流程、写实规范、《九歌》研究文档与声音案例库同步改为新默认，既有已确认成片和历史设计文档不返工。

**Tech Stack:** Markdown、Python 3 标准库（`unittest`、`pathlib`）、zsh、Git。

## Global Constraints

- 从下一个尚未生成的栀夏诗舞视频开始，所有 Seedance 视频提示词统一使用原生音画生成。
- 朗诵固定为画外女声；栀夏全程不张嘴说话、不做朗诵口型、不需要与声音对口型。
- 女声使用正常自然人声，通过语义停顿和呼吸形成舒缓节奏；禁止拖字、吟唱、机械慢放、0.5 倍速、`speech_rate=-50` 和 `atempo` 时间拉伸。
- 允许篇章间存在轻微音色差异，但保持年轻中国女性、自然、清透、克制、低甜度。
- 引号内诗文不得增词、改词；生僻字必须注明读音。
- 十五秒视频的最后短句默认约在 `13.2—13.6` 秒开始，约在 `14.2—14.5` 秒结束，并保留约 `0.5—0.8` 秒环境余韵。
- Seedance 原生声音失败时保留画面并进入后期声音替换；字幕文字以确认原文为准。
- 《东皇太一》《云中君》既有成片和历史提示词不返工；新规则从第 03 篇《湘君》开始执行。
- 角色一致性、电影级写实、三段高潮、舞蹈无手持器物、动作不跑步化和字幕规范保持不变。

---

## File Structure

- Create: `assets/prompts/templates/seedance-native-offscreen-recitation.md` — 所有后续 Seedance 诗舞提示词复制使用的声音段真源。
- Modify: `scripts/validate_jiuge_dance_design.py` — 区分历史篇章和新篇章，验证新提示词的声音契约、准确诗文及贴尾要求。
- Modify: `tests/test_validate_jiuge_dance_design.py` — 覆盖旧无声规则被拒绝、画外朗诵必填、诗文必填和末句贴尾必填。
- Modify: `assets/prompts/jiuge/03-xiangjun-15s.md` through `assets/prompts/jiuge/11-lihun-15s.md` — 加入统一声音段和逐篇诗句时间轴。
- Modify: `assets/prompts/jiuge/01-donghuang-taiyi-15s.md`、`assets/prompts/jiuge/02-yunzhongjun-15s.md` — 仅加历史覆盖说明，不改既有可复制正文。
- Modify: `docs/production-workflow.md` — 将原生画外朗诵设为后续 Seedance 诗舞默认流程，并定义失败回退。
- Modify: `docs/realistic-visual-style.md` — 用“不对口型的画外朗诵”替换“一律后期配音”的旧规则。
- Modify: `docs/jiuge-dance-research-and-design.md` — 把声音契约和篇章表改成 Seedance 原生画外朗诵。
- Modify: `docs/seedance-case-library/08-sound-dialogue-and-rhythm.md`、`docs/seedance-case-library/09-multimodal-reference.md` — 更新案例适用结论，不再把后期配音写成唯一默认。
- Modify: `tests/test_jiuge_dance_design_rules.sh` — 保持统一回归入口并输出新的通过语义。

---

### Task 1: 建立《九歌》原生朗诵校验契约

**Files:**
- Modify: `tests/test_validate_jiuge_dance_design.py`
- Modify: `scripts/validate_jiuge_dance_design.py`

**Interfaces:**
- Consumes: `validate_prompt(path: Path, chapter: str)` 和 `prompt_body(text: str) -> str`。
- Produces: `NATIVE_RECITATION_FROM_ORDER: int`、`NATIVE_AUDIO_REQUIRED: tuple[str, ...]`、`RECITATION_CONTRACTS: dict[str, tuple[str, str]]`；其中 tuple 是 `(quoted_text, final_cue)`。

- [ ] **Step 1: 写出原生朗诵门禁的失败测试**

在 `tests/test_validate_jiuge_dance_design.py` 增加辅助函数：

```python
def future_prompt_text(chapter: str = "湘君") -> str:
    windows = "\n".join(validator.WINDOWS)
    required = "\n".join(validator.VISUAL_PROMPT_REQUIRED)
    audio = "\n".join(validator.NATIVE_AUDIO_REQUIRED)
    quoted_text, final_cue = validator.RECITATION_CONTRACTS[chapter]
    return f"""# {chapter}
## 原典与现代转译
说明
## 十五秒舞蹈设计卡
- 视线对象：神境
- 初始表情：克制
- 情绪转折：发生
- 结束状态：余势
{windows}
## Seedance 完整提示词
{required}
双手始终空着，全程不触碰、不拿取任何器物。
{audio}
朗诵：“{quoted_text}”
约第13.4秒才说出末尾短句“{final_cue}”，读完后保留环境声与音乐余韵。
## 验收要点
完成
"""

def validate_future_text(self, text: str, chapter: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "03-xiangjun-15s.md"
        path.write_text(text, encoding="utf-8")
        validator.validate_prompt(path, chapter)
```

同时把既有 `prompt_text()` 中的 `validator.PROMPT_REQUIRED` 改为 `validator.VISUAL_PROMPT_REQUIRED`，使第 01 篇历史规则测试继续使用拆分后的视觉必填项。

增加四项测试：

```python
def test_future_prompt_rejects_legacy_no_voice_rule(self) -> None:
    text = future_prompt_text().replace(
        "## 验收要点", "原片不得生成可辨识人声。\n## 验收要点"
    )
    with self.assertRaisesRegex(ValueError, "legacy no-voice rule"):
        self.validate_future_text(text, "湘君")

def test_future_prompt_requires_offscreen_recitation_contract(self) -> None:
    text = future_prompt_text().replace("栀夏全程不张嘴说话", "")
    with self.assertRaisesRegex(ValueError, "native audio phrase"):
        self.validate_future_text(text, "湘君")

def test_future_prompt_requires_exact_quoted_poem(self) -> None:
    text = future_prompt_text().replace("君不行兮夷犹，蹇谁留兮中洲。", "错误诗句")
    with self.assertRaisesRegex(ValueError, "quoted recitation"):
        self.validate_future_text(text, "湘君")

def test_future_prompt_requires_final_cue_near_end(self) -> None:
    text = future_prompt_text().replace("约第13.4秒才说出末尾短句", "约第10秒说出末尾短句")
    with self.assertRaisesRegex(ValueError, "final recitation cue"):
        self.validate_future_text(text, "湘君")
```

`validate_future_text` 将临时文件命名为 `03-xiangjun-15s.md` 并调用 `validator.validate_prompt(path, chapter)`。

- [ ] **Step 2: 运行测试并确认因接口缺失而失败**

Run: `python3 -m unittest tests.test_validate_jiuge_dance_design -v`

Expected: FAIL，至少出现 `VISUAL_PROMPT_REQUIRED`、`NATIVE_AUDIO_REQUIRED` 或 `RECITATION_CONTRACTS` 尚未定义。

- [ ] **Step 3: 在校验器中实现历史/未来分流**

把旧 `PROMPT_REQUIRED` 拆成：

```python
NATIVE_RECITATION_FROM_ORDER = 3

VISUAL_PROMPT_REQUIRED = (
    "原创虚构数字角色",
    "九歌祭舞 v03",
    "严格两个",
    "不复刻角色卡排版",
)

NATIVE_AUDIO_REQUIRED = (
    "生成完整的双声道环境声",
    "年轻中国女性的画外朗诵",
    "栀夏全程不张嘴说话",
    "不需要与声音对口型",
    "正常自然人声",
    "不拖字、不吟唱、不机械慢放",
    "只朗诵这些文字，不增词、不改词",
)

LEGACY_NO_VOICE_PHRASES = (
    "不得生成可辨识人声",
    "无可辨识人声",
    "不生成任何可辨识人声",
)

RECITATION_CONTRACTS = {
    "湘君": ("君不行兮夷犹，蹇谁留兮中洲。", "中洲"),
    "湘夫人": ("袅袅兮秋风，洞庭波兮木叶下。", "木叶下"),
    "大司命": ("广开兮天门，纷吾乘兮玄云。", "玄云"),
    "少司命": ("秋兰兮麋芜，罗生兮堂下。", "堂下"),
    "东君": ("暾将出兮东方，照吾槛兮扶桑。", "扶桑"),
    "河伯": ("与女游兮九河，冲风起兮水扬波。", "水扬波"),
    "山鬼": ("既含睇兮又宜笑，子慕予兮善窈窕。", "善窈窕"),
    "国殇": ("身既死兮神以灵，魂魄毅兮为鬼雄。", "鬼雄"),
    "礼魂": ("春兰兮秋菊，长无绝兮终古。", "终古"),
}
```

把 `validate_prompt` 改为从文件名前两位取得 `order = int(path.name[:2])`：所有篇章继续验证 `VISUAL_PROMPT_REQUIRED`；`order >= 3` 时验证全部 `NATIVE_AUDIO_REQUIRED`，拒绝全部 `LEGACY_NO_VOICE_PHRASES`，验证正文包含 `朗诵：“{quoted_text}”`，并验证正文同时包含 `约第13.4秒才说出末尾短句“{final_cue}”`。第 01、02 篇不执行新声音门禁，以保留历史正文。

- [ ] **Step 4: 运行单元测试确认通过**

Run: `python3 -m unittest tests.test_validate_jiuge_dance_design -v`

Expected: 所有测试 PASS。

- [ ] **Step 5: 提交校验器和测试**

```bash
git add scripts/validate_jiuge_dance_design.py tests/test_validate_jiuge_dance_design.py
git diff --cached --name-only
git commit -m "建立Seedance原生朗诵门禁"
```

提交前确认暂存区只有上述两个文件。

---

### Task 2: 建立项目级声音模板并迁移《九歌》九篇提示词

**Files:**
- Create: `assets/prompts/templates/seedance-native-offscreen-recitation.md`
- Modify: `assets/prompts/jiuge/01-donghuang-taiyi-15s.md`
- Modify: `assets/prompts/jiuge/02-yunzhongjun-15s.md`
- Modify: `assets/prompts/jiuge/03-xiangjun-15s.md` through `assets/prompts/jiuge/11-lihun-15s.md`

**Interfaces:**
- Consumes: Task 1 的 `NATIVE_AUDIO_REQUIRED` 与 `RECITATION_CONTRACTS`。
- Produces: 可复制的统一声音模板，以及通过新校验器的九份待生成提示词。

- [ ] **Step 1: 新建项目级统一声音模板**

创建 `assets/prompts/templates/seedance-native-offscreen-recitation.md`，正文固定为：

```text
声音与朗诵：生成完整的双声道环境声、克制的东方氛围音乐，以及一位年轻中国女性的画外朗诵。朗诵者不在画面中说话，栀夏全程不张嘴说话、不做朗诵口型、不需要与声音对口型。

女声自然、清透、克制、低甜度，与画面空间一致。使用正常自然人声，通过语义停顿和呼吸形成舒缓节奏；不拖字、不吟唱、不机械慢放。

按照指定时间朗诵引号内的诗句。只朗诵这些文字，不增词、不改词，不出现其他对白、旁白、吟唱或额外人声。生僻字严格按照提示读音。

最后一小句或最后一个意象词贴近视频末尾才说出，读完后保留短暂的环境声与音乐余韵。
```

模板页同时注明：十五秒默认 `13.2—13.6` 秒进入末句、`14.2—14.5` 秒读完、保留 `0.5—0.8` 秒余韵；失败时保留画面并后期替换声音。

- [ ] **Step 2: 为九份待生成提示词加入统一声音段**

在 `03` 至 `11` 的 `## Seedance 完整提示词` 正文末尾、声音禁止项之前插入模板正文，并追加逐篇时间轴：

| 篇章 | 约第 1 秒 | 约第 7.5 秒 | 约第 13.4 秒末句 |
| --- | --- | --- | --- |
| 湘君 | “君不行兮夷犹” | “蹇谁留兮” | “中洲” |
| 湘夫人 | “袅袅兮秋风” | “洞庭波兮” | “木叶下” |
| 大司命 | “广开兮天门” | “纷吾乘兮” | “玄云” |
| 少司命 | “秋兰兮麋芜” | “罗生兮” | “堂下” |
| 东君 | “暾将出兮东方” | “照吾槛兮” | “扶桑” |
| 河伯 | “与女游兮九河” | “冲风起兮” | “水扬波” |
| 山鬼 | “既含睇兮又宜笑” | “子慕予兮” | “善窈窕” |
| 国殇 | “身既死兮神以灵” | “魂魄毅兮” | “鬼雄” |
| 礼魂 | “春兰兮秋菊” | “长无绝兮” | “终古” |

每篇同时包含一行完整引号原文，与 Task 1 的 `RECITATION_CONTRACTS` 完全一致。`东君`注明“暾读 tūn”；其他篇章不添加无必要的拼音干扰。

- [ ] **Step 3: 清除九份待生成正文中的旧无声要求**

从 `03` 至 `11` 的 Seedance 可复制正文移除以下任何表达：

```text
不得生成可辨识人声
无可辨识人声
不生成任何可辨识人声
诗句由后期完成
朗诵由后期完成
```

保留“画面中不生成字幕、标题、水印或其他文字”，因为原生朗诵不等于让模型渲染文字。

- [ ] **Step 4: 给两份历史提示词加入覆盖说明**

在 `01-donghuang-taiyi-15s.md` 和 `02-yunzhongjun-15s.md` 标题后增加：

```markdown
> 历史生成稿：对应首轮成片已经确认，本文件可复制正文不追溯修改。从《湘君》开始的后续 Seedance 诗舞提示词统一执行 `assets/prompts/templates/seedance-native-offscreen-recitation.md`，原生生成画外朗诵。
```

不得修改这两份历史提示词的镜头、舞蹈或声音正文。

- [ ] **Step 5: 运行《九歌》完整校验**

Run: `zsh tests/test_jiuge_dance_design_rules.sh`

Expected: PASS，九篇未来提示词均包含原生画外朗诵，历史两篇仍被接受。

- [ ] **Step 6: 提交模板和提示词迁移**

```bash
git add assets/prompts/templates/seedance-native-offscreen-recitation.md assets/prompts/jiuge
git diff --cached --name-only
git commit -m "迁移九歌提示词为原生画外朗诵"
```

提交前确认暂存区只有新模板和十二份《九歌》提示词，不包含图片、音频或用户其他修改。

---

### Task 3: 更新项目级生产文档与声音证据边界

**Files:**
- Modify: `docs/production-workflow.md`
- Modify: `docs/realistic-visual-style.md`
- Modify: `docs/jiuge-dance-research-and-design.md`
- Modify: `docs/seedance-case-library/08-sound-dialogue-and-rhythm.md`
- Modify: `docs/seedance-case-library/09-multimodal-reference.md`

**Interfaces:**
- Consumes: `assets/prompts/templates/seedance-native-offscreen-recitation.md`。
- Produces: 后续提示词编写者可直接遵循的项目级流程、写实边界和失败回退规则。

- [ ] **Step 1: 在生产流程中替换旧默认声音策略**

在 `docs/production-workflow.md` 的 Seedance 生成前检查和声音规范中写明：

```markdown
- 后续栀夏诗舞默认由 Seedance 原生生成画外朗诵、环境声和克制氛围音乐；声音段复制 `assets/prompts/templates/seedance-native-offscreen-recitation.md`。
- 栀夏不张嘴说话、不做朗诵口型、不需要对口型；音色允许篇章间轻微差异。
- 末句贴近结尾，十五秒默认约 13.2—13.6 秒进入，约 14.2—14.5 秒读完，再留 0.5—0.8 秒余韵。
- 生成后逐字检查诗文、生僻字、额外人声、音频失真和末句位置；失败时保留画面并进入后期配音替换。
```

保留既有正常语速和禁止机械慢放规则；把“后期配音让位”改为同时适用于原生朗诵和回退配音的混音检查。

- [ ] **Step 2: 更新写实规范中的口型边界**

在 `docs/realistic-visual-style.md` 将“一律后期完成”的旧句替换为：

```markdown
诗词朗诵默认由 Seedance 作为画外声原生生成，画中栀夏不张嘴、不做朗诵口型；字幕和画面文字仍由后期完成。若原生声音出现错字、错音、增词、吟唱或失真，则保留画面并后期替换声音。
```

- [ ] **Step 3: 更新《九歌》声音契约和表格**

在 `docs/jiuge-dance-research-and-design.md`：

- 把“默认后期使用栀夏克制女声”改成“默认由 Seedance 原生生成年轻中国女性的克制画外朗诵”；
- 删除“Seedance 原片仍禁止生成任何可辨识人声”；
- 增加末句贴尾、栀夏不对口型、允许轻微音色差异和失败回退规则；
- 把表头“后期声音模式”改为“原生画外朗诵模式”；
- 第 03 至 09、11 篇填写“年轻女声、克制画外朗诵”；
- 《国殇》填写“低沉礼官式画外朗诵对照”，仍不要求画中人物说话；
- 第 01、02 篇保留“既有成片沿用，后续规则不追溯”。

- [ ] **Step 4: 更新声音案例库的适用结论**

在 `08-sound-dialogue-and-rhythm.md` 和 `09-multimodal-reference.md` 把“诗境继续后期配音更稳妥/更可控”改成：

```markdown
后续诗舞优先使用 Seedance 原生画外朗诵，因为不要求人物对口型；准确诗文、生僻字和末句位置仍是验收硬门槛。原生声音失败时只替换声音，不因音色轻微差异重做画面。
```

保留“多人口型与长句不稳定”的证据结论，明确本项目通过单一画外声规避该风险。

- [ ] **Step 5: 检查当前真源中不再存在冲突规则**

Run:

```bash
rg -n "Seedance 原片仍禁止生成任何可辨识人声|诗境继续后期配音更稳妥|诗境继续后期配音更可控|朗诵、字幕和精确口型由后期完成" docs/production-workflow.md docs/realistic-visual-style.md docs/jiuge-dance-research-and-design.md docs/seedance-case-library
```

Expected: 无输出。历史 `docs/superpowers/specs/` 和 `docs/superpowers/plans/` 不在扫描范围内，继续保留历史设计证据。

- [ ] **Step 6: 提交文档迁移**

```bash
git add docs/production-workflow.md docs/realistic-visual-style.md docs/jiuge-dance-research-and-design.md docs/seedance-case-library/08-sound-dialogue-and-rhythm.md docs/seedance-case-library/09-multimodal-reference.md
git diff --cached --name-only
git commit -m "统一诗舞原生画外朗诵流程"
```

提交前确认暂存区只有上述五份文档。

---

### Task 4: 完整回归与归档

**Files:**
- Modify: `tests/test_jiuge_dance_design_rules.sh`

**Interfaces:**
- Consumes: Tasks 1—3 的校验器、九篇提示词、模板和文档。
- Produces: 一个可重复运行的《九歌》原生朗诵回归入口和完整交付证据。

- [ ] **Step 1: 更新回归入口的成功语义**

保留现有单元测试和校验器调用，把最终成功输出统一为：

```text
PASS: Jiuge future Seedance prompts use native offscreen recitation
```

若脚本当前依赖校验器自己的成功输出，则在校验器 `validate()` 完成后同步修改 `main()` 的成功消息，测试脚本不重复打印第二条含义相同的信息。

- [ ] **Step 2: 运行《九歌》完整回归**

Run: `zsh tests/test_jiuge_dance_design_rules.sh`

Expected: 全部单元测试 PASS，最终输出 `PASS: Jiuge future Seedance prompts use native offscreen recitation`。

- [ ] **Step 3: 运行项目相关 Seedance 规则回归**

Run:

```bash
zsh tests/test_seedance_case_library_rules.sh
zsh tests/test_seedance_evidence_tiered_prompt_rules.sh
zsh tests/test_zhixia_dance_not_running_rules.sh
```

Expected: 三个脚本均返回 0；若旧测试精确断言“所有诗句必须后期配音”，先把断言改为“画外朗诵不要求人物口型，字幕仍后期完成”，再重新运行至通过。

- [ ] **Step 4: 运行静态冲突扫描和差异检查**

Run:

```bash
rg -n "不得生成可辨识人声|无可辨识人声|不生成任何可辨识人声" assets/prompts/jiuge/{03,04,05,06,07,08,09,10,11}-*.md
git diff --check
git status --short
```

Expected: 第一条无输出；`git diff --check` 无输出；工作树中用户原有无关改动仍然保留且未被暂存。

- [ ] **Step 5: 提交回归入口与必要的测试适配**

```bash
git add tests/test_jiuge_dance_design_rules.sh scripts/validate_jiuge_dance_design.py tests/test_seedance_case_library_rules.sh tests/test_seedance_evidence_tiered_prompt_rules.sh
git diff --cached --name-only
git commit -m "完善原生画外朗诵回归验证"
```

只暂存实际发生修改的文件；若某个测试文件无需修改，不把它加入提交。

- [ ] **Step 6: 最终复核提交边界**

Run:

```bash
git log -5 --oneline
git status --short
```

Expected: 最近提交依次覆盖校验门禁、九篇提示词迁移、项目文档和回归验证；未提交的图片、音频、字幕缓存、其他项目文件及用户原有修改保持原状。
