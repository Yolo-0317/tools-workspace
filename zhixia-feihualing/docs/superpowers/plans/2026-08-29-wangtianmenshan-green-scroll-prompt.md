# 《望天门山》青绿长卷舞提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成可直接提交给 Seedance 2.0 的《望天门山》15 秒青绿长卷舞提示词，并登记唯一的去重台账记录。

**Architecture:** 单集目录保存最终提示词与入口说明，提示词正文用固定标记隔离可复制内容。独立壳测试读取提示词标记区和舞蹈台账，校验原创角色声明、15 秒四段动作、单一运镜、阿砚动态参与、禁用词与唯一台账记录。

**Tech Stack:** Markdown、CSV、zsh、Python 标准库

## Global Constraints

- 输入仅为栀夏与阿砚两张原创虚构数字角色母版；场景、首帧和运动由文字生成。
- 生成 15 秒、9:16、电影级全写实东方幻想连续长镜头。
- 栀夏主舞，阿砚保持约 40 厘米尺度在侧后方动态跟随。
- 不复刻《只此青绿》的具体编舞、标志动作、服装或舞台构图；提示词正文不得出现剧目名或“青绿腰”。
- 栀夏全诗朗诵与字幕在后期加入；Seedance 不生成可辨识人声、字幕或连续说话口型。
- 最终提示词正文不得出现项目内部代码、文件路径、状态卡编号、验收说明或诗文原句。

---

### Task 1: 最终提示词与舞蹈去重登记

**Files:**
- Create: `tests/test_wangtianmenshan_15s_seedance_prompt.sh`
- Create: `episodes/wangtianmenshan-15s/prompts/seedance-v01.md`
- Create: `episodes/wangtianmenshan-15s/README.md`
- Modify: `operations/dance-design-history.csv`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-29-wangtianmenshan-green-scroll-dance-design.md` and the fixed two-reference convention `@图片1`/`@图片2`.
- Produces: one copy-ready prompt block between `<!-- SEEDANCE_PROMPT_START -->` and `<!-- SEEDANCE_PROMPT_END -->`, plus one CSV row whose `episode` is `wangtianmenshan-15s`.

- [ ] **Step 1: Write the failing test**

  Create `tests/test_wangtianmenshan_15s_seedance_prompt.sh` with the following behavior:

  ```zsh
  #!/bin/zsh
  set -euo pipefail
  project_dir="${0:A:h:h}"
  prompt="$project_dir/episodes/wangtianmenshan-15s/prompts/seedance-v01.md"
  history="$project_dir/operations/dance-design-history.csv"
  [[ -s "$prompt" ]] || { print -u2 "FAIL: missing Wangtianmenshan Seedance prompt"; exit 1; }
  python3 - "$prompt" "$history" <<'PY'
  from pathlib import Path
  import csv, re, sys
  text = Path(sys.argv[1]).read_text(encoding="utf-8")
  start_marker = "<!-- SEEDANCE_PROMPT_START -->"
  end_marker = "<!-- SEEDANCE_PROMPT_END -->"
  assert text.count(start_marker) == 1 and text.count(end_marker) == 1
  seedance = text[text.index(start_marker) + len(start_marker):text.index(end_marker)]
  required = [
      "@图片1与@图片2均为本项目原创虚拟角色",
      "@图片1是原创虚拟角色栀夏",
      "@图片2是原创虚拟东方墨灵阿砚",
      "15 秒", "9:16", "一镜到底", "尚未完成但可发力",
      "0.3 秒内", "0.8 秒内", "一至两步", "不得持续奔跑",
      "不做完整旋转", "纵向提起", "侧倾山形", "两岸青山",
      "孤帆", "摄影机围绕舞姿", "阿砚可以奔跑跟随",
      "不生成任何可辨识人声",
  ]
  for phrase in required:
      assert phrase in seedance, f"missing requirement: {phrase}"
  for time_range in ["0—1 秒", "1—4 秒", "4—8 秒", "8—12 秒", "12—15 秒"]:
      assert seedance.count(time_range) == 1, f"wrong timeline: {time_range}"
  for forbidden in [
      "只此青绿", "青绿腰", "天门中断楚江开", "碧水东流至此回",
      "两岸青山相对出", "孤帆一片日边来", "assets/", ".png", ".jpg",
      "状态卡", "验收标准", "制作说明",
  ]:
      assert forbidden not in seedance, f"forbidden term leaked: {forbidden}"
  assert not re.search(r"(^|[^A-Za-z0-9])[MHDS][0-9]{2}([^A-Za-z0-9]|$)", seedance)
  with Path(sys.argv[2]).open(encoding="utf-8", newline="") as handle:
      rows = list(csv.DictReader(handle))
  matches = [row for row in rows if row["episode"] == "wangtianmenshan-15s"]
  assert len(matches) == 1
  assert matches[0]["climax_family"] == "纵向提沉"
  assert matches[0]["rotation"] == "无完整旋转"
  assert matches[0]["status"] == "designed"
  print("PASS: Wangtianmenshan 15s Seedance prompt is ready")
  PY
  ```

- [ ] **Step 2: Run test to verify it fails**

  Run: `zsh tests/test_wangtianmenshan_15s_seedance_prompt.sh`

  Expected: exit 1 with `FAIL: missing Wangtianmenshan Seedance prompt`.

- [ ] **Step 3: Write the minimal prompt artifact**

  Create `episodes/wangtianmenshan-15s/prompts/seedance-v01.md` with a short usage section and one marked prompt block. Inside the block:

  - Begin with the fixed original-character declaration and role mapping.
  - Establish a real mineral-blue-green Chu River canyon at sunset with foreground rock, midground river and distant mountains.
  - Use five observable time ranges: 0—1 second strong start; 1—4 seconds sleeve edge parts the river; 4—8 seconds one-to-two-step weight transfer creates physical returning water; 8—12 seconds sink-to-rise side-lean reveals opposite mountain banks; 12—15 seconds continued dancing reveals one distant sail at sunset.
  - Keep one camera path: low three-quarter-front tracking backward along the river, then rising and pulling out in response to the climax.
  - Keep Ayan at Zhixia's inner-rear route with realistic four-foot following and at most one short avoidance leap.
  - End with the fixed no-voice/no-subtitle sound isolation paragraph.

  Create `episodes/wangtianmenshan-15s/README.md` linking the poem, design spec and final prompt.

- [ ] **Step 4: Append the unique dance-history row**

  Append exactly one CSV row with these key values:

  ```text
  episode=wangtianmenshan-15s
  poem=李白《望天门山》
  opening=低位斜身袖锋切江
  movement=沿江一至两步侧移后原路径提起
  climax_family=纵向提沉
  rotation=无完整旋转
  carrier=单侧长袖
  effect=袖锋分江、回流与两岸青山揭示
  climax_window=8—12秒
  camera_climax=随纵向提起抬升拉开揭示两岸青山
  ending=持续舞动并揭示日边孤帆
  status=designed
  ```

- [ ] **Step 5: Run the focused test**

  Run: `zsh tests/test_wangtianmenshan_15s_seedance_prompt.sh`

  Expected: `PASS: Wangtianmenshan 15s Seedance prompt is ready`.

- [ ] **Step 6: Run related rule checks**

  Run:

  ```zsh
  zsh tests/test_zhixia_first_opening_rules.sh
  zsh tests/test_choreography_diversity_v2_rules.sh
  zsh tests/test_ayan_dynamic_participation_rules.sh
  ```

  Expected: all three scripts exit 0 and print `PASS`.

- [ ] **Step 7: Commit the prompt package**

  ```bash
  git add \
    zhixia-feihualing/tests/test_wangtianmenshan_15s_seedance_prompt.sh \
    zhixia-feihualing/episodes/wangtianmenshan-15s/prompts/seedance-v01.md \
    zhixia-feihualing/episodes/wangtianmenshan-15s/README.md \
    zhixia-feihualing/operations/dance-design-history.csv
  git commit -m "内容：新增望天门山青绿长卷舞提示词"
  ```
