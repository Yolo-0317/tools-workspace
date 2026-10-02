# 栀夏文化诗舞全局无手持器物 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将“栀夏舞蹈时双手始终不持任何器物”落实到《九歌》十一篇提示词、舞蹈台账、自动校验、文化诗舞路线图和项目记忆，并消除少司命持花、国殇持剑的旧设计。

**Architecture:** 以校验器作为可执行规则真源：十一篇台账的 `prop` 必须全部为 `无`，十一篇完整提示词必须包含统一无手持声明，并拒绝旧版道具牵引描述。内容层随后迁移少司命和国殇动作链，并将同一规则同步到研究文档、路线图、历史设计覆盖说明和项目记忆。

**Tech Stack:** Python 3 标准库（`unittest`、`csv`、`pathlib`、`tempfile`、`importlib`）、zsh 测试入口、Markdown、CSV、Git。

## Global Constraints

- 栀夏进行舞蹈时双手始终不持任何器物。器物只能作为地面、祭坛、背景、远景或光影承接物，通过环境反馈参与叙事，不进入手部持握关系。
- 禁止持、握、托、捧、提、抱、背、佩、执、拔、挥、舞、抛、接器物，也禁止将器物绑在手腕、手臂或袖口。
- 衣袖、裙摆和固定服饰不视为器物；继续保持严格两个袖缘尾端、不得抓袖、不得生成专业水袖。
- 少司命使用“倾身穿行—改面回护—腾跃展开”；白芷或兰花仅为环境植物。
- 国殇使用“低位扫展—腾跃展开—纵向提沉”；祭悼之剑仅可横置于地面、祭坛或中远景。
- 《器物十二章》以环境器物、空间和光影反馈叙事，栀夏不拿取或操控器物。
- 不生成或修改视频，不改变栀夏的脸、妆发、服装、母板构图和身份一致性规则。
- 用户可见内容、文档和提交信息不使用 emoji；Git 提交信息使用中文。
- 工作区已有其他未提交改动；每次只暂存本计划列出的本次文件，不覆盖、不整理其他改动。

---

## File Map

- `scripts/validate_jiuge_dance_design.py`：十一篇提示词和台账的可执行无手持门禁。
- `tests/test_validate_jiuge_dance_design.py`：用临时文件验证无手持正文与全“无”台账。
- `tests/test_jiuge_dance_design_rules.sh`：运行单元测试和完整包校验。
- `assets/prompts/jiuge/00-*.md`、`01-*.md` 至 `11-*.md`：当前五秒测试稿和十一篇十五秒提示词。
- `operations/jiuge-dance-design-history.csv`：十一篇高潮序列、视觉指纹和道具字段。
- `docs/jiuge-dance-research-and-design.md`：研究总结、十一篇总表和环境边界。
- `docs/cultural-poetry-dance-roadmap.md`：主系列、六个候选系列和全局规则。
- `docs/superpowers/specs/2026-08-30-zhixia-jiuge-15s-three-peak-dance-design.md`：历史设计，只追加覆盖说明。
- `.cursor/rules/memory-workspace.mdc`：稳定项目记忆；已有未提交改动，只编辑相关短索引且不暂存。

### Task 1: 用单元测试锁定无手持校验合同

**Files:**
- Create: `zhixia-feihualing/tests/test_validate_jiuge_dance_design.py`
- Modify: `zhixia-feihualing/tests/test_jiuge_dance_design_rules.sh:1-12`
- Test: `zhixia-feihualing/tests/test_validate_jiuge_dance_design.py`

**Interfaces:**
- Consumes: `validate_prompt(path: Path, chapter: str) -> None`、`validate_ledger(path: Path) -> None`。
- Produces: 正文必须含统一声明、旧手持动作必须失败、全“无”台账通过、任一非“无”字段失败四个合同。

- [ ] **Step 1: 新建校验器单元测试**

创建 `tests/test_validate_jiuge_dance_design.py`：

```python
from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = PROJECT_ROOT / "scripts" / "validate_jiuge_dance_design.py"
SPEC = importlib.util.spec_from_file_location("validate_jiuge_dance_design", VALIDATOR_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def prompt_text(extra_body: str = "") -> str:
    windows = "\n".join(validator.WINDOWS)
    required = "\n".join(validator.PROMPT_REQUIRED)
    return f"""# 东皇太一
## 原典与现代转译
说明
## 十五秒舞蹈设计卡
{windows}
## Seedance 完整提示词
{required}
双手始终空着，全程不触碰、不拿取任何器物。
{extra_body}
## 验收要点
完成
"""


class PromptRulesTests(unittest.TestCase):
    def validate_text(self, text: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "01-donghuang-taiyi-15s.md"
            path.write_text(text, encoding="utf-8")
            validator.validate_prompt(path, "东皇太一")

    def test_prompt_requires_global_empty_hands_sentence(self) -> None:
        text = prompt_text().replace("双手始终空着，全程不触碰、不拿取任何器物。\n", "")
        with self.assertRaisesRegex(ValueError, "prompt body missing 双手始终空着"):
            self.validate_text(text)

    def test_prompt_rejects_legacy_handheld_action(self) -> None:
        with self.assertRaisesRegex(ValueError, "forbidden handheld term 道具牵引"):
            self.validate_text(prompt_text("第二高潮使用道具牵引。"))


class LedgerRulesTests(unittest.TestCase):
    def write_ledger(self, rows: list[dict[str, str]], directory: str) -> Path:
        path = Path(directory) / "ledger.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=validator.CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def no_prop_rows(self) -> list[dict[str, str]]:
        source = PROJECT_ROOT / "operations" / "jiuge-dance-design-history.csv"
        with source.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            row["prop"] = "无"
        return rows

    def test_all_no_prop_rows_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            validator.validate_ledger(self.write_ledger(self.no_prop_rows(), directory))

    def test_any_non_empty_prop_is_rejected(self) -> None:
        rows = self.no_prop_rows()
        rows[0]["prop"] = "礼剑"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "expected prop 无"):
                validator.validate_ledger(self.write_ledger(rows, directory))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 接入现有测试入口**

把 shell 测试最后一行替换为：

```zsh
python3 -m unittest "$project_dir/tests/test_validate_jiuge_dance_design.py" -v
python3 "$validator" --project-root "$project_dir"
```

- [ ] **Step 3: 运行测试确认旧实现失败**

Run: `python3 -m unittest zhixia-feihualing/tests/test_validate_jiuge_dance_design.py -v`

Expected: 缺少统一声明、旧道具牵引和全“无”台账用例失败，证明旧校验仍允许旧逻辑。

- [ ] **Step 4: 暂存测试但不提交**

```bash
git add zhixia-feihualing/tests/test_validate_jiuge_dance_design.py zhixia-feihualing/tests/test_jiuge_dance_design_rules.sh
```

测试与最小实现放在同一提交，避免留下只红不绿的提交。

### Task 2: 实现统一无手持校验器

**Files:**
- Modify: `zhixia-feihualing/scripts/validate_jiuge_dance_design.py:49-65,80-98,126-143`
- Test: `zhixia-feihualing/tests/test_validate_jiuge_dance_design.py`

**Interfaces:**
- Consumes: Task 1 的四个回归合同。
- Produces: `PROMPT_EMPTY_HANDS_REQUIRED`、`PROMPT_HANDHELD_FORBIDDEN` 和全部章节 `prop == "无"` 门禁。

- [ ] **Step 1: 添加提示词常量**

```python
PROMPT_EMPTY_HANDS_REQUIRED = (
    "双手始终空着",
    "全程不触碰、不拿取任何器物",
)

PROMPT_HANDHELD_FORBIDDEN = (
    "道具牵引", "只持一枝", "唯一花枝", "持花手",
    "执剑手", "唯一礼剑", "同一只手持有",
)
```

- [ ] **Step 2: 在完整提示词正文执行新规则**

在 `validate_prompt()` 的 `PROMPT_REQUIRED` 检查之后加入：

```python
    for phrase in PROMPT_EMPTY_HANDS_REQUIRED:
        if phrase not in body:
            fail(f"{path.name}: prompt body missing {phrase}")
    for phrase in PROMPT_HANDHELD_FORBIDDEN:
        if phrase in body:
            fail(f"{path.name}: prompt body contains forbidden handheld term {phrase}")
```

- [ ] **Step 3: 将台账收紧为十一篇全部无道具**

删除 `allowed_props`，将道具判断替换为：

```python
        if row["prop"] != "无":
            fail(f"ledger row {order}: expected prop 无")
```

- [ ] **Step 4: 运行单元测试确认通过**

Run: `python3 -m unittest zhixia-feihualing/tests/test_validate_jiuge_dance_design.py -v`

Expected: `Ran 4 tests` 与 `OK`。

- [ ] **Step 5: 运行完整入口确认内容尚待迁移**

Run: `zsh zhixia-feihualing/tests/test_jiuge_dance_design_rules.sh`

Expected: 单元测试通过，完整包在第一篇缺少统一声明或少司命旧道具字段处失败。

- [ ] **Step 6: 提交测试和校验器**

```bash
git add zhixia-feihualing/scripts/validate_jiuge_dance_design.py zhixia-feihualing/tests/test_validate_jiuge_dance_design.py zhixia-feihualing/tests/test_jiuge_dance_design_rules.sh
git commit -m "收紧九歌无手持器物校验"
```

### Task 3: 迁移《九歌》提示词、动作设计和台账

**Files:**
- Modify: `zhixia-feihualing/assets/prompts/jiuge/00-donghuang-taiyi-v03-5s-test-v02.md`
- Modify: `zhixia-feihualing/assets/prompts/jiuge/01-donghuang-taiyi-15s.md` through `11-lihun-15s.md`
- Modify: `zhixia-feihualing/operations/jiuge-dance-design-history.csv:2-12`
- Modify: `zhixia-feihualing/docs/jiuge-dance-research-and-design.md:90-140`
- Test: `zhixia-feihualing/tests/test_jiuge_dance_design_rules.sh`

**Interfaces:**
- Consumes: Task 2 的标准句和禁用词门禁。
- Produces: 十一篇无手持十五秒提示词、同步的五秒测试稿、全“无”台账和研究设计真源。

- [ ] **Step 1: 为十二份当前提示词加入统一正文句**

在每份 `## Seedance 完整提示词` 的场景开头加入：

```text
栀夏双手始终空着，全程不触碰、不拿取任何器物。
```

- [ ] **Step 2: 重写少司命动作**

设计卡和正文统一使用：

```text
第一帧：三分之四正面柔和旁倾，双手空着，一臂靠近胸前、另一臂侧后展开。
0.300—4.200 秒：倾身穿行，沿香草之间的纵深曲线连续两步。
4.200—5.000 秒：后脚收近，胸腰带动近侧臂回到胸前，另一臂准备横向展开。
5.000—8.800 秒：改面回护，踏步换面，以胸腰和非对称双臂形成横向回护弧线。
8.800—9.600 秒：承重脚踩实，两臂回到身体中段，目光转向上方流光。
9.600—13.500 秒：腾跃展开，跨步提气短暂离地，以一高一低双臂向上送愿，落地后继续一步。
13.500—15.000 秒：保持向前上方移动余势，目光追随流光而非花枝。
道具：无；白芷和兰花只生长在路径两侧，随风与光线轻微回应，人物全程不触碰。
```

删除“持花手”“唯一花枝”“同一只手持有”“道具牵引”；验收要点改为环境花草不接触人物、三段方向明确、落地稳定、袖缘严格两个。

- [ ] **Step 3: 重写国殇动作**

设计卡和正文统一使用：

```text
第一帧：三分之四正面低弓步，双手空着，一臂斜向前下、一臂后展。
0.300—4.200 秒：低位扫展，重心下沉，以斜向步伐和非对称双臂扫出迎战记忆。
4.200—5.000 秒：前脚踩实，后脚蹬地，目光由地面祭剑转向前上方。
5.000—8.800 秒：腾跃展开，跨步蹬地短暂离地，双臂一高一低向纵深打开。
8.800—9.600 秒：落地回到中轴，一手回到胸腹附近，另一臂保持侧后余势。
9.600—13.500 秒：纵向提沉，由挺立缓慢下沉至高跪或深弓步，再由脚底提起完成安魂致礼。
13.500—15.000 秒：继续把力量向下安放，目光由远方收回地面祭剑附近。
道具：无；一柄祭悼之剑横置于地面、祭坛或中远景，人物全程不触碰、不拿取，也不模拟持剑手型。
```

删除“执剑手”“剑锋随重心”“唯一礼剑”“同一只手持有”“剑舞”“道具牵引”；保留无血腥、无敌对人物和不扮演士兵。

- [ ] **Step 4: 更新台账**

```text
所有行 prop = 无
少司命 opening_silhouette = 柔和旁倾与前后错臂
少司命 peak2_family = 改面回护
少司命 peak2_carrier = 胸腰带动非对称双臂回护
少司命 peak3_carrier = 一高一低双臂向上送愿
少司命 ending = 落地续步并目送上方流光
少司命 notes = 白芷和兰花仅为环境植物且全程不触碰
国殇 opening_silhouette = 低弓步与前后斜向双臂
国殇 peak1_family = 低位扫展
国殇 peak1_carrier = 低重心斜步与非对称双臂扫展
国殇 peak2_carrier = 跨步蹬地与纵深开臂
国殇 peak3_carrier = 中轴下沉与安魂提起
国殇 ending = 面向地面祭剑完成安魂致礼
国殇 notes = 祭剑仅置于地面或中远景且无血腥
```

重新运行九项视觉指纹规则，确保少司命和国殇未与前一篇共享三项或以上，且最近五篇未重复高潮或方向序列。

- [ ] **Step 5: 同步研究设计**

- 少司命总表改为“倾身穿行—改面回护—腾跃展开”，道具“无”。
- 国殇改为“低位扫展—腾跃展开—纵向提沉”，承接物“风、旌旗远影与地面祭剑”，道具“无”。
- “大司命与少司命”改为两篇都无手持器物，以强弱结构区分。
- 用全局硬规则替换少司命持花、国殇持剑条款，并逐篇说明环境边界。
- Seedance 转换规则加入统一正文句。

- [ ] **Step 6: 运行完整校验**

Run: `zsh zhixia-feihualing/tests/test_jiuge_dance_design_rules.sh`

Expected: 四个单元测试 `OK`，随后输出 `PASS: Jiuge 15s three-peak dance designs are complete and distinct`。

- [ ] **Step 7: 扫描旧版描述**

Run: `rg -n "道具牵引|只持一枝|唯一花枝|持花手|执剑手|唯一礼剑|同一只手持有|剑舞" zhixia-feihualing/assets/prompts/jiuge zhixia-feihualing/operations/jiuge-dance-design-history.csv zhixia-feihualing/docs/jiuge-dance-research-and-design.md`

Expected: 无匹配。

- [ ] **Step 8: 提交内容迁移**

```bash
git add zhixia-feihualing/assets/prompts/jiuge zhixia-feihualing/operations/jiuge-dance-design-history.csv zhixia-feihualing/docs/jiuge-dance-research-and-design.md
git diff --cached --name-only
git commit -m "迁移九歌舞蹈为全程无手持"
```

暂存后确认目录内只有本计划列出的十二份提示词，没有夹带新图片或工作文件。

### Task 4: 对齐六个候选系列、历史覆盖说明和项目记忆

**Files:**
- Modify: `zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md:7-52`
- Modify: `zhixia-feihualing/docs/superpowers/specs/2026-08-30-zhixia-jiuge-15s-three-peak-dance-design.md:1-5`
- Modify: `.cursor/rules/memory-workspace.mdc:564-575`
- Test: text consistency checks below

**Interfaces:**
- Consumes: 已确认设计说明和 Task 3 的无手持动作。
- Produces: 六候选路线图、历史覆盖关系和可检索的稳定项目记忆。

- [ ] **Step 1: 将候选池拆成六个明确系列**

路线图写入：

```text
1. 《栀夏·名楼十二望》
2. 《栀夏·廿四节气舞》
3. 《栀夏·器物十二章》
4. 《栀夏·盛唐十二乐舞》
5. 《栀夏·十二花神》
6. 《栀夏·草木十二笺》
```

说明六个系列仍是候选池，不改变“敦煌—九歌—宋词—华夏神女”主线；“花神与草木”拆为两个系列。

- [ ] **Step 2: 写入路线图硬规则并修正《九歌》表格**

将“环境、动作、道具与色彩”改为“环境、动作、光影承接物与色彩”，加入全局硬规则原文。表格中东皇太一改为远景礼鼓、少司命改为环境香草、河伯改为水纹与浪花、国殇改为地面或中远景祭剑，动作方向移除“剑舞”。

- [ ] **Step 3: 为历史设计添加覆盖说明**

在旧设计标题后加入：

```markdown
> 规则覆盖说明：本文件保留为 2026-08-30 当时的设计记录。其“每篇最多一种单一道具”、少司命持花和国殇持剑条款，已由《栀夏文化诗舞全局无手持器物设计》覆盖；当前制作一律以“舞蹈中双手始终不持任何器物”为准。
```

不改写旧表格和旧道具段落，保留历史可追溯性。

- [ ] **Step 4: 更新项目记忆相关短索引**

只编辑 `.cursor/rules/memory-workspace.mdc` 的 `2026-08-29-zhixia-cultural-dance-roadmap` 小节：写入六个候选名称、全局硬规则、少司命花草和国殇祭剑的环境关系、《器物十二章》的环境转译，并追加本次设计真源。

该文件在任务开始前已有其他未提交改动，因此不得执行 `git add .cursor/rules/memory-workspace.mdc`；保留工作树修改，并在最终交付中说明。

- [ ] **Step 5: 运行一致性扫描**

Run: `rg -n "栀夏·盛唐十二乐舞|栀夏·名楼十二望|栀夏·廿四节气舞|栀夏·器物十二章|栀夏·十二花神|栀夏·草木十二笺|双手始终不持任何器物" zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md .cursor/rules/memory-workspace.mdc`

Expected: 六个名称和硬规则同时存在于路线图与项目记忆。

Run: `rg -n "少司命.*单枝白芷或兰花|国殇.*单剑|每篇最多一种单一道具" zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md .cursor/rules/memory-workspace.mdc`

Expected: 无匹配。历史设计文件不纳入扫描，因为其旧内容已由页首说明覆盖。

- [ ] **Step 6: 提交路线图和覆盖说明**

```bash
git add zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md zhixia-feihualing/docs/superpowers/specs/2026-08-30-zhixia-jiuge-15s-three-peak-dance-design.md
git diff --cached --name-only
git commit -m "对齐文化诗舞六系列无手持规则"
```

确认 `.cursor/rules/memory-workspace.mdc` 未被暂存。

### Task 5: 全量验证和交付核对

**Files:**
- Verify only: Tasks 1-4 修改的全部文件

**Interfaces:**
- Consumes: 前四项任务的代码、提示词、台账、路线图和记忆修改。
- Produces: 最终通过证据和清楚的提交边界。

- [ ] **Step 1: 运行《九歌》完整测试**

Run: `zsh zhixia-feihualing/tests/test_jiuge_dance_design_rules.sh`

Expected: 四个单元测试通过，完整包校验输出 `PASS: Jiuge 15s three-peak dance designs are complete and distinct`。

- [ ] **Step 2: 校验统一声明和台账字段**

Run:

```bash
for file in zhixia-feihualing/assets/prompts/jiuge/{01,02,03,04,05,06,07,08,09,10,11}-*-15s.md; do rg -q "双手始终空着，全程不触碰、不拿取任何器物" "$file" || exit 1; done
python3 -c 'import csv; from pathlib import Path; p=Path("zhixia-feihualing/operations/jiuge-dance-design-history.csv"); rows=list(csv.DictReader(p.open(encoding="utf-8"))); assert len(rows)==11; assert all(r["prop"]=="无" for r in rows); print("PASS: 11 ledger props are 无")'
```

Expected: 循环退出码为 `0`，并输出 `PASS: 11 ledger props are 无`。

- [ ] **Step 3: 扫描旧规则回流**

Run: `rg -n "道具牵引|只持一枝|唯一花枝|持花手|执剑手|唯一礼剑|同一只手持有|剑舞" zhixia-feihualing/assets/prompts/jiuge zhixia-feihualing/operations/jiuge-dance-design-history.csv zhixia-feihualing/docs/jiuge-dance-research-and-design.md zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md`

Expected: 无匹配。

- [ ] **Step 4: 检查格式和提交范围**

Run:

```bash
git diff --check
git status --short
git log -3 --oneline
```

Expected: `git diff --check` 无输出；最近三个任务提交依次包含校验器、九歌迁移、路线图对齐；工作树原有无关修改仍保留，项目记忆保持未暂存。

- [ ] **Step 5: 汇报交付结果**

最终汇报包含：全局规则真源、少司命与国殇新动作链、六个候选系列、测试命令和实际结果、三个提交号，以及项目记忆因含既有未提交内容而未纳入提交的说明。
