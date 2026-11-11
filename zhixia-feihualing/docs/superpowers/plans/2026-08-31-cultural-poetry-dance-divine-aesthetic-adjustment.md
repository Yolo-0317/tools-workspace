# 栀夏文化诗舞神性审美调整 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从敦煌十六舞第六支和《九歌》第二篇开始，把去网红感、分系列神性、逐篇视线表情弧线、诚实考据与声音分层固化为可验证的生产规则。

**Architecture:** `docs/cultural-poetry-dance-roadmap.md` 负责跨系列定位和命名边界，`docs/jiuge-dance-research-and-design.md` 与十篇未生成《九歌》提示词负责逐篇神性表达，`docs/zhixia-poetry-dance-composer.md` 和 `docs/production-workflow.md` 负责生成前门禁。现有两份 CSV 保持 25 列与 26 列结构不变，新增语义写入既有 `notes` 字段，避免破坏已存在的验证脚本。

**Tech Stack:** Markdown、Zsh、Python 3 标准库 `csv`/`unittest`、ripgrep、现有项目验证脚本。

## Global Constraints

- 生效范围固定为敦煌十六舞第六支以后、《九歌》第二篇以后；已生成、已确认或已发布成片不返工。
- 栀夏保持原创人物身份；去除网红式镜头表演感，但不把所有人物处理成僵硬神像。
- 《九歌》中的栀夏始终是楚地祭舞者，不逐集扮演神祇本尊。
- 没有明确参考链时，禁止使用“复原”“还原”“AI活化文物”“数字敦煌复原”、虚构洞窟编号或大师临摹关联。
- 敦煌继续使用 v03 孔雀蓝、琥珀橙、象牙白与旧金母板；九歌继续使用玄黑、朱红、暗金与象牙白母板。
- 敦煌默认保留栀夏固定女声；九歌默认使用栀夏克制女声，只把《国殇》登记为一次外部礼官式低沉旁白对照候选。
- 局部特写钩子只允许在一支未生成敦煌单集中做可回退的单变量测试，不替代全身强起势默认规则。
- 全系列无手持器物、十五秒三高潮、脚下承重、两个九歌袖缘尾端和运动中收束等现有硬规则继续有效。
- 不修改已完成单集的 README、提示词、配音、字幕、封面或发布文案。
- 不修改 `operations/dance-design-history.csv` 的 25 列表头，也不修改 `operations/jiuge-dance-design-history.csv` 的 26 列表头。
- 敦煌第六支的具体诗篇和舞种不在本计划中擅自确定；本计划建立其必须通过的输入门禁，待单集选题确认后另做单集设计。
- 保留工作区内与本任务无关的未提交改动；每次提交只暂存本任务列出的文件。

---

### Task 1: 固化跨系列范围、敦煌分型和诚实命名

**Files:**
- Create: `zhixia-feihualing/tests/test_cultural_poetry_dance_divine_scope.sh`
- Modify: `zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md:3-82`

**Interfaces:**
- Consumes: 已批准设计稿中的生效范围、三类敦煌表达、开头钩子试验和命名禁区。
- Produces: 后续所有文化诗舞设计共同引用的跨系列神性边界；Task 3 的生产门禁沿用其中术语。

- [ ] **Step 1: 写入失败的范围与命名门禁测试**

创建 `tests/test_cultural_poetry_dance_divine_scope.sh`：

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
roadmap="$project_dir/docs/cultural-poetry-dance-roadmap.md"

[[ -s "$roadmap" ]] || { print -u2 "FAIL: missing cultural poetry dance roadmap"; exit 1; }

for phrase in \
  '敦煌十六舞从第六支开始执行' \
  '九歌祭舞从第二篇开始执行' \
  '已生成、已确认或已发布的成片不返工' \
  '去网红感，不去人物感' \
  '飞天、供养舞与礼佛空间' \
  '柘枝、胡旋、白纻等乐舞' \
  '诗境型原创舞' \
  '0.800 秒前拉开至完整全身' \
  '没有明确参考链时' \
  'AI活化文物' \
  '数字敦煌复原' \
  '不继承统一的肃穆表情、黑金色板、祭坛或低沉男声'; do
  rg -qF "$phrase" "$roadmap" || { print -u2 -r -- "FAIL: roadmap lacks $phrase"; exit 1; }
done

print -r -- 'PASS: cultural poetry dance scope and naming boundaries are complete'
```

- [ ] **Step 2: 运行测试并确认因新规则尚未写入而失败**

Run: `zsh zhixia-feihualing/tests/test_cultural_poetry_dance_divine_scope.sh`

Expected: FAIL，首个错误为缺少 `敦煌十六舞从第六支开始执行`。

- [ ] **Step 3: 在路线图中写入跨系列规则**

在定位和优先顺序之后新增“神性审美生效边界”，准确写入：

```markdown
## 神性审美生效边界

- 敦煌十六舞从第六支开始执行，九歌祭舞从第二篇开始执行。
- 已生成、已确认或已发布的成片不返工；已完成但尚未发布的成片不因本规则重新生成。
- 去网红感，不去人物感：默认不直视镜头，表情和视线服从诗篇关系，但不把栀夏统一处理成无情绪神像。
- 神性来自人物与神境、祭坛、自然承接物和诗中事件的关系，不由金光、悬浮、法阵或粒子堆叠代替舞蹈。
```

新增“敦煌十六舞分型”，逐项写明：

1. 飞天、供养舞与礼佛空间允许庄严、超逸、下视和遥望。
2. 柘枝、胡旋、白纻等乐舞保持华丽、矫健、含蓄和舞台气韵，不强制肃穆悲悯。
3. 诗境型原创舞的情绪服从诗句，不因敦煌标签统一改成神像表情。
4. 默认全身强起势；只允许一支未生成单集测试 0.000—0.500 秒动态细节，并在 0.800 秒前拉开至完整全身、1.000 秒内进入主体舞句。

新增“诚实命名与发布边界”，明确没有明确参考链时禁止将作品正向宣传为 `复原`、`还原`、`AI活化文物`、`数字敦煌复原`，禁止虚构洞窟编号、临摹者和大师参考关系；有来源时只写“灵感参考”并保留内部来源记录。

在后续系列段落写入：宋词、名楼、节气、器物、花神和草木系列只继承诚实考据、去网红感、视线对象、情绪弧线与环境因果，不继承统一的肃穆表情、黑金色板、祭坛或低沉男声。

- [ ] **Step 4: 运行范围测试并检查文档格式**

Run: `zsh zhixia-feihualing/tests/test_cultural_poetry_dance_divine_scope.sh`

Expected: PASS，输出 `PASS: cultural poetry dance scope and naming boundaries are complete`。

Run: `git diff --check -- zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md zhixia-feihualing/tests/test_cultural_poetry_dance_divine_scope.sh`

Expected: 无输出，退出码 0。

- [ ] **Step 5: 提交跨系列规则**

```bash
git add zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md zhixia-feihualing/tests/test_cultural_poetry_dance_divine_scope.sh
git commit -m "固化文化诗舞神性审美边界"
```

### Task 2: 为《九歌》第二篇以后增加逐篇视线、表情和声音契约

**Files:**
- Modify: `zhixia-feihualing/tests/test_validate_jiuge_dance_design.py`
- Modify: `zhixia-feihualing/scripts/validate_jiuge_dance_design.py`
- Modify: `zhixia-feihualing/docs/jiuge-dance-research-and-design.md:51-143`
- Modify: `zhixia-feihualing/operations/jiuge-dance-design-history.csv:3-12`
- Modify: `zhixia-feihualing/assets/prompts/jiuge/02-yunzhongjun-15s.md`
- Modify: `zhixia-feihualing/assets/prompts/jiuge/03-xiangjun-15s.md`
- Modify: `zhixia-feihualing/assets/prompts/jiuge/04-xiangfuren-15s.md`
- Modify: `zhixia-feihualing/assets/prompts/jiuge/05-dasiming-15s.md`
- Modify: `zhixia-feihualing/assets/prompts/jiuge/06-shaosiming-15s.md`
- Modify: `zhixia-feihualing/assets/prompts/jiuge/07-dongjun-15s.md`
- Modify: `zhixia-feihualing/assets/prompts/jiuge/08-hebo-15s.md`
- Modify: `zhixia-feihualing/assets/prompts/jiuge/09-shangui-15s.md`
- Modify: `zhixia-feihualing/assets/prompts/jiuge/10-guoshang-15s.md`
- Modify: `zhixia-feihualing/assets/prompts/jiuge/11-lihun-15s.md`

**Interfaces:**
- Consumes: Task 1 的“去网红感，不去人物感”和《九歌》统一祭舞者身份。
- Produces: 十篇未生成《九歌》单集统一的四字段设计卡、可观察提示词和 CSV `notes` 记录；Task 3 的通用工作流引用同一字段名。

- [ ] **Step 1: 为第二篇以后写入失败的验证器单元测试**

在 `PromptRulesTests` 增加：

```python
    def test_future_chapter_requires_gaze_and_expression_contract(self) -> None:
        text = prompt_text()
        with self.assertRaisesRegex(ValueError, "missing design-card field 视线对象"):
            self.validate_text(text, order="02")
```

把测试辅助方法改为接收 `order: str = "01"`，并调用 `validator.validate_prompt(path, "东皇太一", order)`。

在 `LedgerRulesTests` 增加：

```python
    def test_future_chapter_requires_aesthetic_notes(self) -> None:
        rows = self.no_prop_rows()
        rows[1]["notes"] = "不悬浮且不生成翅膀"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "missing notes token 视线对象="):
                validator.validate_ledger(self.write_ledger(rows, directory))
```

- [ ] **Step 2: 运行单元测试并确认新契约尚未实现**

Run: `python3 -m unittest zhixia-feihualing/tests/test_validate_jiuge_dance_design.py -v`

Expected: FAIL，新测试报告 `validate_prompt()` 尚不接受 `order`，或未拒绝缺少 `视线对象` 的设计卡。

- [ ] **Step 3: 扩展《九歌》验证器**

在 `scripts/validate_jiuge_dance_design.py` 增加：

```python
DESIGN_CARD_REQUIRED = (
    "- 视线对象：",
    "- 初始表情：",
    "- 情绪转折：",
    "- 结束状态：",
)

LEDGER_AESTHETIC_NOTE_TOKENS = (
    "视线对象=",
    "表情弧线=",
    "声音模式=",
)
```

把函数签名改为：

```python
def validate_prompt(path: Path, chapter: str, order: str) -> None:
```

在读取全文后加入：

```python
    if order != "01":
        for phrase in DESIGN_CARD_REQUIRED:
            if phrase not in text:
                fail(f"{path.name}: missing design-card field {phrase[2:-1]}")
```

把 `validate()` 中的循环改为：

```python
    for order, chapter, filename in CHAPTERS:
        validate_prompt(prompts / filename, chapter, order)
```

在 `validate_ledger()` 的逐行检查中、`order != "01"` 时验证 `notes` 包含三个 `LEDGER_AESTHETIC_NOTE_TOKENS`；表头和字段数量保持不变。

- [ ] **Step 4: 写入十篇逐篇设计卡和台账记录**

在十篇 02—11 的“十五秒舞蹈设计卡”中逐篇增加以下四个字段，并把同一变化写成 Seedance 正文中的可观察视线与面部变化：

| 篇章 | 视线对象 | 初始表情 | 情绪转折 | 结束状态 | 声音模式 |
| --- | --- | --- | --- | --- | --- |
| 云中君 | 近处低云转向高处云门 | 克制期待 | 相遇升腾后留连远去 | 目送高天，动作仍向远处延伸 | 栀夏克制女声 |
| 湘君 | 水面倒影转向兰舟远影 | 试探寻找 | 靠近水边后发现对方仍在远处 | 离岸一步并回望远岸 | 栀夏克制女声 |
| 湘夫人 | 秋风木叶转向洞庭远岸 | 闻风期待 | 欲近又主动退开 | 一臂送叶，目光留在远岸 | 栀夏克制女声 |
| 大司命 | 星门边界转向中轴命线 | 冷静审视 | 推进巡视后完成裁决定界 | 直立但不提前站定，视线停在边界结果 | 栀夏克制女声 |
| 少司命 | 路径香草转向上方流光 | 温柔专注 | 回护之后把愿望向上送出 | 落地续步并目送流光 | 栀夏克制女声 |
| 东君 | 暗处光缘转向扶桑日轮 | 坚定蓄势 | 破暗后迎接赤金日出 | 落地继续朝晨光迈步 | 栀夏克制女声 |
| 河伯 | 脚下水纹转向浪墙出口 | 沉着聚势 | 穿浪后由压低转为破浪开张 | 离岸一步并看向水势归处 | 栀夏克制女声 |
| 山鬼 | 山隈来路转向赴约方向 | 克制含笑 | 赴约期待在雷雨中转为等待落空 | 怅惘回望后退入林 | 栀夏克制女声 |
| 国殇 | 旌旗远影转向地面祭剑 | 沉痛克制 | 战阵记忆爆发后转入安魂 | 视线落向祭剑，身体仍保留提沉余势 | 外部礼官式低沉旁白对照候选 |
| 礼魂 | 祭坛余烬转向神境离去方向 | 澄明肃静 | 确认礼成后从容送神 | 半步换重中目送离去 | 栀夏克制女声 |

每个对应 CSV 行的 `notes` 末尾追加三段，格式固定为：

```text
；视线对象=<该行视线对象>；表情弧线=<初始表情→情绪转折→结束状态>；声音模式=<该行声音模式>
```

不新增 CSV 列，不改变第 01 行《东皇太一》，不把 `声音模式` 写入 Seedance 正文的人声生成要求；Seedance 仍禁止可辨识人声，声音模式只服务后期设计。

- [ ] **Step 5: 更新《九歌》总览的统一规则**

在 `docs/jiuge-dance-research-and-design.md` 增加“视线、表情与声音契约”，明确：

- 第二篇以后设计卡固定填写视线对象、初始表情、情绪转折、结束状态。
- 默认不直视镜头，但角色卡正面平视只用于身份锁定。
- 《山鬼》必须从“既含睇兮又宜笑”的克制含笑进入赴约，再在雷雨中转为等待落空，禁止全程冷脸或甜笑。
- 默认使用栀夏克制女声；《国殇》作为唯一外部礼官式低沉旁白对照候选，且不与栀夏声音同时争抢十五秒信息量。
- 神性来自迎请、追随、等待、回护、悼念和送别，不由法阵、符文、悬浮或粒子堆叠替代舞蹈。

同步更新十一篇总表，把“视线与表情弧线”作为新增列；《东皇太一》仅记录现有状态，不追溯修改其已确认成片或提示词。

- [ ] **Step 6: 运行《九歌》验证并修正全部失败项**

Run: `python3 -m unittest zhixia-feihualing/tests/test_validate_jiuge_dance_design.py -v`

Expected: 6 tests全部 PASS。

Run: `python3 zhixia-feihualing/scripts/validate_jiuge_dance_design.py --project-root zhixia-feihualing`

Expected: PASS，输出 `PASS: Jiuge 15s three-peak dance designs are complete and distinct`。

Run: `git diff --check -- zhixia-feihualing/scripts/validate_jiuge_dance_design.py zhixia-feihualing/tests/test_validate_jiuge_dance_design.py zhixia-feihualing/docs/jiuge-dance-research-and-design.md zhixia-feihualing/assets/prompts/jiuge zhixia-feihualing/operations/jiuge-dance-design-history.csv`

Expected: 无输出，退出码 0。

- [ ] **Step 7: 提交《九歌》逐篇契约**

```bash
git add zhixia-feihualing/scripts/validate_jiuge_dance_design.py zhixia-feihualing/tests/test_validate_jiuge_dance_design.py zhixia-feihualing/docs/jiuge-dance-research-and-design.md zhixia-feihualing/assets/prompts/jiuge/02-yunzhongjun-15s.md zhixia-feihualing/assets/prompts/jiuge/03-xiangjun-15s.md zhixia-feihualing/assets/prompts/jiuge/04-xiangfuren-15s.md zhixia-feihualing/assets/prompts/jiuge/05-dasiming-15s.md zhixia-feihualing/assets/prompts/jiuge/06-shaosiming-15s.md zhixia-feihualing/assets/prompts/jiuge/07-dongjun-15s.md zhixia-feihualing/assets/prompts/jiuge/08-hebo-15s.md zhixia-feihualing/assets/prompts/jiuge/09-shangui-15s.md zhixia-feihualing/assets/prompts/jiuge/10-guoshang-15s.md zhixia-feihualing/assets/prompts/jiuge/11-lihun-15s.md zhixia-feihualing/operations/jiuge-dance-design-history.csv
git commit -m "建立九歌视线表情与声音契约"
```

### Task 3: 把神性审美接入通用编舞和生产流程

**Files:**
- Create: `zhixia-feihualing/tests/test_cultural_poetry_dance_production_rules.sh`
- Modify: `zhixia-feihualing/docs/zhixia-poetry-dance-composer.md:7-41,72-83,151-178`
- Modify: `zhixia-feihualing/docs/production-workflow.md:78-81,152-179,199-232`

**Interfaces:**
- Consumes: Task 1 的跨系列边界、Task 2 的四字段契约和既有 CSV 结构。
- Produces: 每支新文化诗舞在选题、生成、后期声音、发布和复盘阶段必须执行的统一检查；敦煌第六支进入设计时直接使用该入口。

- [ ] **Step 1: 写入失败的生产门禁测试**

创建 `tests/test_cultural_poetry_dance_production_rules.sh`：

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
composer="$project_dir/docs/zhixia-poetry-dance-composer.md"
workflow="$project_dir/docs/production-workflow.md"
history="$project_dir/operations/dance-design-history.csv"

for target in "$composer" "$workflow" "$history"; do
  [[ -s "$target" ]] || { print -u2 -r -- "FAIL: missing $target"; exit 1; }
done

for target in "$composer" "$workflow"; do
  for phrase in \
    '视线对象' \
    '初始表情' \
    '情绪转折' \
    '结束状态' \
    '去网红感，不去人物感' \
    '没有明确参考链时' \
    '局部特写钩子' \
    '单变量测试' \
    '视线对象=' \
    '表情弧线=' \
    '声音模式='; do
    rg -qF "$phrase" "$target" || { print -u2 -r -- "FAIL: $target lacks $phrase"; exit 1; }
  done
done

expected_header='episode,poem,opening,movement,climax_family,rotation,body_level,opening_silhouette,arm_path,leg_silhouette,carrier,carrier_shape,effect,effect_shape,climax_window,camera_reaction,camera_climax,ending,status,notes,peak_sequence,peak_directions,peak_windows,carrier_trajectories,camera_peak_reactions'
[[ "$(head -n 1 "$history")" == "$expected_header" ]] || { print -u2 'FAIL: general dance ledger schema changed'; exit 1; }
awk -F, 'NF != 25 { exit 1 }' "$history" || { print -u2 'FAIL: general dance ledger must stay at 25 fields'; exit 1; }

print -r -- 'PASS: cultural poetry dance production rules are connected'
```

- [ ] **Step 2: 运行测试并确认通用流程尚缺四字段门禁**

Run: `zsh zhixia-feihualing/tests/test_cultural_poetry_dance_production_rules.sh`

Expected: FAIL，首先报告组合器或工作流缺少 `视线对象`。

- [ ] **Step 3: 更新自动编舞组合器**

在“固定输出基线”增加：

```markdown
- 文化诗舞先填写视线对象、初始表情、情绪转折和结束状态；去网红感，不去人物感。默认不直视镜头，但表情必须服从诗篇关系，不能统一写成冷脸、肃穆或悲悯。
```

在“自动组合顺序”中，把视线表情契约放在提取诗篇和选择动作之前：先判断系列类型与神性强度，再填写四字段，然后设计动作与环境因果。

在“开场抓眼”中增加局部特写钩子规则：默认全身强起势；只允许明确登记的一支未生成敦煌单集做单变量测试，0.800 秒前恢复完整全身、1.000 秒内进入主体舞句，失败时回退，不连续复用。

在“九项视觉指纹去重”之后明确：CSV 仍保持 25 列；未来文化诗舞行在既有 `notes` 字段使用 `视线对象=...；表情弧线=...；声音模式=...；试验变量=...` 记录新增语义，没有试验变量时写 `试验变量=无`。

在“最终提示词转换”中增加：最终正文把四字段转成可观察的目光方向、面部变化和情绪转折；不得直接写“神性”“神秘”“肃穆”等不可观察结果词，也不得生成对镜头眨眼、甜笑、卖萌和服饰展示摆拍。

- [ ] **Step 4: 更新生产工作流**

在设计入口增加文化诗舞检查：

1. 判断敦煌乐舞、敦煌飞天/供养、九歌祭舞或其他诗境类型。
2. 填写视线对象、初始表情、情绪转折、结束状态。
3. 检查人物没有网红式镜头互动，神性没有被法阵、符文、悬浮和粒子堆叠替代。
4. 没有明确参考链时，标题、字幕和发布文案不得使用复原、还原、AI活化文物、数字敦煌复原或大师临摹关联。

在生成前检查中加入局部特写钩子的单变量测试与回退条件；在声音规范中写明敦煌默认固定女声、九歌默认栀夏克制女声、《国殇》是唯一外部礼官式低沉旁白对照候选；在发布与复盘中要求记录 `视线对象=...；表情弧线=...；声音模式=...；试验变量=...`。

- [ ] **Step 5: 运行通用门禁和既有舞蹈回归测试**

Run: `zsh zhixia-feihualing/tests/test_cultural_poetry_dance_production_rules.sh`

Expected: PASS，输出 `PASS: cultural poetry dance production rules are connected`。

Run: `zsh zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh`

Expected: PASS，确认一秒强起势和高冲击力规则未被覆盖。

Run: `zsh zhixia-feihualing/tests/test_three_equal_climaxes_rules.sh`

Expected: PASS，确认三高潮规则和 25 列台账结构未被破坏。

Run: `zsh zhixia-feihualing/tests/test_zhixia_dance_not_running_rules.sh`

Expected: PASS，确认新神性表达没有把舞蹈退化为站桩、走路或持续奔跑。

Run: `git diff --check -- zhixia-feihualing/docs/zhixia-poetry-dance-composer.md zhixia-feihualing/docs/production-workflow.md zhixia-feihualing/tests/test_cultural_poetry_dance_production_rules.sh`

Expected: 无输出，退出码 0。

- [ ] **Step 6: 提交通用生产门禁**

```bash
git add zhixia-feihualing/docs/zhixia-poetry-dance-composer.md zhixia-feihualing/docs/production-workflow.md zhixia-feihualing/tests/test_cultural_poetry_dance_production_rules.sh
git commit -m "接入文化诗舞神性审美门禁"
```

### Task 4: 运行完整相关验证并审查最终差异

**Files:**
- Verify: `zhixia-feihualing/docs/cultural-poetry-dance-roadmap.md`
- Verify: `zhixia-feihualing/docs/jiuge-dance-research-and-design.md`
- Verify: `zhixia-feihualing/docs/zhixia-poetry-dance-composer.md`
- Verify: `zhixia-feihualing/docs/production-workflow.md`
- Verify: `zhixia-feihualing/assets/prompts/jiuge/02-yunzhongjun-15s.md` through `11-lihun-15s.md`
- Verify: `zhixia-feihualing/operations/dance-design-history.csv`
- Verify: `zhixia-feihualing/operations/jiuge-dance-design-history.csv`

**Interfaces:**
- Consumes: Tasks 1—3 的全部规则、提示词、验证器和测试。
- Produces: 可供敦煌第六支选题设计和《九歌·云中君》生成直接使用的已验证规范基线。

- [ ] **Step 1: 运行三项新增验证**

```bash
zsh zhixia-feihualing/tests/test_cultural_poetry_dance_divine_scope.sh
python3 -m unittest zhixia-feihualing/tests/test_validate_jiuge_dance_design.py -v
zsh zhixia-feihualing/tests/test_cultural_poetry_dance_production_rules.sh
```

Expected: 三项全部 PASS，Python 输出 6 tests，两个 Zsh 测试分别输出各自 PASS 行。

- [ ] **Step 2: 运行既有相关回归验证**

```bash
python3 zhixia-feihualing/scripts/validate_jiuge_dance_design.py --project-root zhixia-feihualing
zsh zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh
zsh zhixia-feihualing/tests/test_three_equal_climaxes_rules.sh
zsh zhixia-feihualing/tests/test_zhixia_dance_not_running_rules.sh
zsh zhixia-feihualing/tests/test_xuexiu_baizhu_15s_prompt.sh
```

Expected: 六项全部 PASS；《雪袖白纻》测试证明已完成敦煌第五支未被本次规则追溯修改。

- [ ] **Step 3: 检查误导性正向声明和 CSV 结构**

Run:

```bash
python3 -c 'import csv; from pathlib import Path; p=Path("zhixia-feihualing/operations/dance-design-history.csv"); rows=list(csv.reader(p.open(encoding="utf-8"))); assert all(len(r)==25 for r in rows); q=Path("zhixia-feihualing/operations/jiuge-dance-design-history.csv"); rows2=list(csv.reader(q.open(encoding="utf-8"))); assert all(len(r)==26 for r in rows2); print("PASS: ledger schemas preserved")'
```

Expected: 输出 `PASS: ledger schemas preserved`。

Run: `git diff --check`

Expected: 无输出，退出码 0。

- [ ] **Step 4: 审查任务文件和未提交工作区边界**

Run: `git status --short`

Expected: 本任务文件没有遗漏；工作区原有的其他修改仍保留且未被纳入本任务提交。

Run: `git log -4 --oneline`

Expected: 顶部依次可见本计划的三个中文实施提交以及计划文档提交，未出现合并、推送、发布或部署操作。
