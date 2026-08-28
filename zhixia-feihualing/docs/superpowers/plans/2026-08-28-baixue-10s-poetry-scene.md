# 《白雪歌送武判官归京》10 秒诗境 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已确认的“梨花？／是新雪。”10 秒诗境固化为可校验的单集事实源、四段配音清单和无精确时间边界的视频提示词结构草稿，同时保持所有付费生成门禁关闭。

**Architecture:** 以 `episodes/baixue/README.md` 作为单集制作状态入口，`voice-lines.json` 作为后期人声唯一事实源，`prompts/seedance-structure-v01.md` 作为等待真实 TTS 时长的视觉结构稿。新增一个单集规则测试，直接复用现有 TTS manifest 解析器验证 JSON，而不是只检查文本存在；离线预览只汇报调用计划，不创建音频。

**Tech Stack:** Markdown、JSON、Zsh、Python 3、现有 `zhixia_tts_manifest.py` 与 `generate_episode_audio.py`。

## Global Constraints

- 全部用户可见文案、终端汇报和提交信息不使用 emoji。
- 只修改本计划列出的 `baixue` 单集文字资产和对应测试；不碰已发布成片、其他诗镜、角色母板或现有三张状态卡。
- 本轮不得调用 TTS、图片或视频生成服务，不得创建 `assets/audio/baixue/`、图片或视频文件。
- `voice-lines.json` 不填写 `start_ms` 或 `gap_before_ms`。四段音频实际生成并测得时长后，才能建立最终毫秒级时间轴。
- Seedance 提示词正文不得出现“梨花？”、“是新雪。”或两句诗原文，只能写无声口型、倾听、舞蹈、镜头、环境声和配乐职责。
- 10 秒分段只保留在设计文档和 README 的“暂定设计窗口”中，不复制成可直接付费生成的最终精确边界。
- 所有 Git 操作必须显式限定本计划涉及的路径，保留工作区内其他人的未提交与已暂存改动；提交信息使用中文。

---

## Task 1: 建立白雪单集的可执行规则测试

**Files:**

- Create: `zhixia-feihualing/tests/test_baixue_10s_assets.sh`
- Reference: `zhixia-feihualing/scripts/zhixia_tts_manifest.py`
- Reference: `zhixia-feihualing/config/voices.json`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-08-28-baixue-10s-poetry-scene-design.md`

**Interfaces:**

- `load_voice_config(path: Path) -> dict[str, VoiceConfig]`
- `load_episode_manifest(path: Path, voices: dict[str, VoiceConfig]) -> EpisodeManifest`
- Shell test exit code `0` means the single-episode contract is satisfied.

- [ ] **Step 1: Add a failing test for the missing deliverables**

Create `tests/test_baixue_10s_assets.sh` with `set -euo pipefail`. Resolve `project_dir` from the script location, then require these files to be non-empty:

```zsh
episode="$project_dir/episodes/baixue/README.md"
manifest="$project_dir/episodes/baixue/voice-lines.json"
prompt="$project_dir/episodes/baixue/prompts/seedance-structure-v01.md"

test -s "$episode"
test -s "$manifest"
```

Add a Python block immediately after these two existence checks. It imports the real parser from `scripts/`, loads `config/voices.json`, then asserts:

```python
expected = [
    ("01-ayan-dialogue", "ayan", "梨花？"),
    ("02-zhixia-dialogue", "zhixia", "是新雪。"),
    ("03-zhixia-poem-one", "zhixia", "忽如一夜春风来。"),
    ("04-zhixia-poem-two", "zhixia", "千树万树梨花开。"),
]

assert manifest.episode == "baixue"
assert manifest.format == "one-poem-story"
assert [(line.id, line.role, line.text) for line in manifest.lines] == expected
assert all(line.revision == 1 for line in manifest.lines)
assert all(line.context_texts for line in manifest.lines)
```

Also load the raw JSON and assert every line omits both timing keys:

```python
assert all("start_ms" not in line for line in raw["lines"])
assert all("gap_before_ms" not in line for line in raw["lines"])
```

Add README assertions for the fixed dialogue, four-way sound split, “暂定设计窗口”, “真实 TTS 时长”, and the prohibition on automatic generation.

Only after the manifest and README assertions pass, require `test -s "$prompt"`. Then extract only the text between `<!-- SEEDANCE_PROMPT_START -->` and `<!-- SEEDANCE_PROMPT_END -->`; assert the block contains `无声疑问口型`, `无声回应口型`, `D01`, `M02`, `H05`, `唯一引导雪花`, `一次方向变化`, `约 135 度`, `无人声背景音乐`, and `自然环境声`. Assert that the same block contains none of:

```text
梨花？
是新雪。
忽如一夜春风来
千树万树梨花开
0.000
0.600
1.200
2.100
5.200
5.400
9.300
```

Finally, fail if any of the three new/updated text assets contains the project-banned emoji set already used by existing static tests.

- [ ] **Step 2: Run the new test and confirm it fails for the right reason**

Run:

```bash
cd zhixia-feihualing
zsh tests/test_baixue_10s_assets.sh
```

Expected: non-zero exit because `episodes/baixue/voice-lines.json` and `prompts/seedance-structure-v01.md` do not exist yet. Do not weaken or skip those checks.

- [ ] **Step 3: Commit only the failing test**

```bash
git add zhixia-feihualing/tests/test_baixue_10s_assets.sh
git commit --only zhixia-feihualing/tests/test_baixue_10s_assets.sh -m "测试白雪十秒诗境资产规则"
```

---

## Task 2: 固化四段配音清单与单集事实源

**Files:**

- Create: `zhixia-feihualing/episodes/baixue/voice-lines.json`
- Modify: `zhixia-feihualing/episodes/baixue/README.md`
- Test: `zhixia-feihualing/tests/test_baixue_10s_assets.sh`

**Interfaces:**

- Manifest top-level fields: `episode`, `format`, `theme`, `theme_slug`, `audio_slug`, `lines`.
- Line fields: `id`, `role`, `text`, `revision`, `context_texts`.
- Offline preview command: `python3 scripts/generate_episode_audio.py --episode baixue`.

- [ ] **Step 1: Create the timing-free TTS manifest**

Create `episodes/baixue/voice-lines.json` with this exact structure and no `start_ms`/`gap_before_ms` fields:

```json
{
  "episode": "baixue",
  "format": "one-poem-story",
  "theme": "白雪",
  "theme_slug": "baixue",
  "audio_slug": "baixue",
  "lines": [
    {
      "id": "01-ayan-dialogue",
      "role": "ayan",
      "text": "梨花？",
      "revision": 1,
      "context_texts": [
        "晨光雪林边缘，阿砚贴近松针末端的一片真实雪晶，第一次把它认作极小的白花。短促、轻柔、聪明而克制地发问，带一点辨认新物象的好奇；句尾自然微扬后立即收住。保持阿砚固定的聪明假小子声线，不做幼童惊叫、卖萌、播音腔或拖长尾音。"
      ]
    },
    {
      "id": "02-zhixia-dialogue",
      "role": "zhixia",
      "text": "是新雪。",
      "revision": 1,
      "context_texts": [
        "阿砚刚把雪晶认作梨花，栀夏低头看雪，以温柔、清透、肯定而不纠正人的方式回应。前两个字轻柔确认，“新雪”自然落下，为随后看见整片雪林的惊喜留白。保持十八岁少女的固定清透声线，不做老师讲解、广告腔、古装表演腔或过度气声。"
      ]
    },
    {
      "id": "03-zhixia-poem-one",
      "role": "zhixia",
      "text": "忽如一夜春风来。",
      "revision": 1,
      "context_texts": [
        "回应结束后，栀夏由呼气微沉进入沉转提，目光随唯一雪花向上，右臂沿立圆展开。朗诵像身在雪林中自然生出的发现，年轻清透，由安静转为明亮惊喜；“忽如”要有忽然看见的轻提，“一夜春风来”舒展但不故作朗诵。保持真实呼吸，不喊、不逐字等长、不成熟旁白化。"
      ]
    },
    {
      "id": "04-zhixia-poem-two",
      "role": "zhixia",
      "text": "千树万树梨花开。",
      "revision": 1,
      "context_texts": [
        "紧接上一句，唯一雪花改变一次方向，引导栀夏以圆场小步和约一百三十五度转身揭示远林积雪。情绪从明亮惊喜连续扩展为开阔赞叹，气息比上一句稍展开但仍克制；“千树万树”带出层层纵深，“梨花开”稳稳落在完整雪林与收势上。保持同一少女声线，不换成播音腔、舞台喊腔或夸张颤音。"
      ]
    }
  ]
}
```

- [ ] **Step 2: Update the episode README as the production-state entry point**

Keep the existing poem, D01/M02/H05, character/environment, and scene-card links. Add:

- “固定互动”：阿砚“梨花？”；栀夏“是新雪。”。
- “声音分工”：阿砚对白 1 段、栀夏对白 1 段、栀夏诗句 2 段，共 4 段独立 TTS；Seedance 只负责无人声背景音乐和自然环境声。
- “暂定设计窗口”：概述六个事件阶段，并明确它不是最终音频时间轴。
- “当前状态”：文案与配音清单已确认，等待离线预览；没有用户当次明确授权时不调用 TTS、图片或视频生成。
- “下一门禁”：真实 TTS 生成后读取四段实际时长，在诗句不变速的前提下压缩无声余量并重排最终 10 秒节点。
- 新增 `voice-lines.json` 和正式设计文档的关联链接。

- [ ] **Step 3: Re-run the test and confirm only the prompt draft remains failing**

```bash
cd zhixia-feihualing
zsh tests/test_baixue_10s_assets.sh
```

Expected: manifest parser and README assertions pass; the test still exits non-zero only because `prompts/seedance-structure-v01.md` is absent.

- [ ] **Step 4: Run the offline preview without generating assets**

Record whether the directory exists before preview:

```bash
cd zhixia-feihualing
test ! -e assets/audio/baixue
python3 scripts/generate_episode_audio.py --episode baixue
test ! -e assets/audio/baixue
```

Expected preview includes four planned calls, with `阿砚：1 句` and `栀夏：3 句`. The final existence check must still pass. Do not add `--execute`.

- [ ] **Step 5: Commit only the manifest and README**

```bash
git add zhixia-feihualing/episodes/baixue/voice-lines.json zhixia-feihualing/episodes/baixue/README.md
git commit --only zhixia-feihualing/episodes/baixue/voice-lines.json zhixia-feihualing/episodes/baixue/README.md -m "固化白雪十秒诗境配音清单"
```

---

## Task 3: 编写不含伪时间轴的 Seedance 结构草稿

**Files:**

- Create: `zhixia-feihualing/episodes/baixue/prompts/seedance-structure-v01.md`
- Test: `zhixia-feihualing/tests/test_baixue_10s_assets.sh`
- Reference: `zhixia-feihualing/episodes/baixue/prompts/scene-cards.md`
- Reference: `zhixia-feihualing/docs/realistic-visual-style.md`
- Reference: `zhixia-feihualing/docs/cinematic-vfx-library.md`

**Interfaces:**

- Machine-checkable prompt boundary comments:
  - `<!-- SEEDANCE_PROMPT_START -->`
  - `<!-- SEEDANCE_PROMPT_END -->`
- Six ordered visual responsibilities, named by event rather than milliseconds.

- [ ] **Step 1: Create the prompt draft metadata and usage gate**

At the top of `prompts/seedance-structure-v01.md`, state:

- Status is “结构草稿，不可直接付费生成”.
- Inputs are the current Zhixia v04 and Ayan v01 Seedance upload masterboards plus the three reviewed state cards when available.
- The file inherits identity, topology, light direction, wind direction, color, material, D01/M02/H05, and all negative constraints from the scene cards and approved design spec.
- Dialogue and poetry live only in `../voice-lines.json`; they are not copied into the Seedance prompt block.
- Exact time boundaries must be added only after four real audio durations are recorded.

- [ ] **Step 2: Write the isolated Seedance prompt block**

Between the boundary comments, write one continuous Chinese production prompt containing these ordered responsibilities without any numeric timestamp:

1. `微距雪晶钩子`：85mm 微距从唯一真实六角雪花起镜，焦点连续交给低位靠近的阿砚。
2. `阿砚无声疑问口型`：阿砚短促自然口型，栀夏闭唇倾听，并重锚双耳、四足、朱砂额印、暖金纹样、唯一开放式 S 形墨尾。
3. `栀夏无声回应口型`：焦点沿视线交给栀夏，栀夏三分之四侧身、闭合自然口型后呼气微沉，阿砚闭唇。
4. `D01 第一段`：沉转提、立圆展臂，M02 从 85mm 连续拉至 50mm 双角色中近景；唯一雪花通过脸侧安全区。
5. `全片唯一方向变化`：H05 只让唯一雪花由下落／向前连续改为上升／向远林；镜头跟随同一惯性，不切镜、不甩镜。
6. `D01 第二段与收势`：两至三步圆场小步、约 135 度连续转身、简化云手、山膀收势；真实积雪沿枝梢扩展到远林，只形成梨花般联想，不出现实体花；栀夏与阿砚最终构成稳定三角构图。

The same prompt block must also state:

- 10 秒、9:16、电影级高写实 CG、一镜到底。
- Only one cross-shot-scale change and one direction change.
- Seedance audio is only `无人声背景音乐` and `自然环境声`; permanently prohibit dialogue, recitation, narration, whispering, singing, character vocalization, and any recognizable human voice.
- Identity priority and failure degradation: reduce forest layers before shrinking characters; downgrade 135° to 90° if face drift occurs; simplify cloud hands to whole-arm circle if wrists deform; remove auxiliary snow if it covers faces.

Do not include any dialogue/poem originals or provisional timestamp numbers inside the block.

- [ ] **Step 3: Run the single-episode test to green**

```bash
cd zhixia-feihualing
zsh tests/test_baixue_10s_assets.sh
```

Expected:

```text
PASS: Baixue 10s episode assets are consistent
```

- [ ] **Step 4: Commit only the prompt draft**

```bash
git add zhixia-feihualing/episodes/baixue/prompts/seedance-structure-v01.md
git commit --only zhixia-feihualing/episodes/baixue/prompts/seedance-structure-v01.md -m "编写白雪诗境视频结构草稿"
```

---

## Task 4: 回归验证并交付下一门禁

**Files:**

- Verify: `zhixia-feihualing/tests/test_baixue_10s_assets.sh`
- Verify: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`
- Verify: `zhixia-feihualing/tests/test_realistic_visual_style_rules.sh`
- Verify: `zhixia-feihualing/tests/test_cinematic_vfx_library_rules.sh`
- Verify: `zhixia-feihualing/tests/test_zhixia_tts_manifest.py`
- Verify: `zhixia-feihualing/tests/test_generate_episode_audio.py`

**Interfaces:**

- All listed test commands return exit code `0`.
- Offline preview returns exit code `0` and does not create `assets/audio/baixue/`.
- `git diff --check` reports no whitespace errors in the four delivery files.

- [ ] **Step 1: Run the focused static and parser tests**

```bash
cd zhixia-feihualing
zsh tests/test_baixue_10s_assets.sh
zsh tests/test_classical_dance_library_rules.sh
zsh tests/test_realistic_visual_style_rules.sh
zsh tests/test_cinematic_vfx_library_rules.sh
python3 -m unittest tests.test_zhixia_tts_manifest tests.test_generate_episode_audio
```

Expected: all commands pass. If the Python module form is incompatible with this repository layout, run the same two files through unittest discovery without widening to unrelated tests:

```bash
python3 -m unittest discover -s tests -p 'test_zhixia_tts_manifest.py'
python3 -m unittest discover -s tests -p 'test_generate_episode_audio.py'
```

- [ ] **Step 2: Re-run the offline preview and verify no paid asset was created**

```bash
cd zhixia-feihualing
test ! -e assets/audio/baixue
python3 scripts/generate_episode_audio.py --episode baixue
test ! -e assets/audio/baixue
```

Expected: four preview calls, no client execution, no new audio directory.

- [ ] **Step 3: Audit scope, prompt isolation, and whitespace**

```bash
git diff --check -- \
  zhixia-feihualing/episodes/baixue/README.md \
  zhixia-feihualing/episodes/baixue/voice-lines.json \
  zhixia-feihualing/episodes/baixue/prompts/seedance-structure-v01.md \
  zhixia-feihualing/tests/test_baixue_10s_assets.sh
git status --short -- \
  zhixia-feihualing/episodes/baixue \
  zhixia-feihualing/tests/test_baixue_10s_assets.sh
```

Confirm manually:

- No `.env`, character masterboard, media file, published export, or other poem changed in these commits.
- The Seedance prompt block contains no dialogue/poem originals and no provisional millisecond values.
- The manifest contains exactly four context-rich lines and no timing keys.
- The README labels all existing second ranges as provisional design windows.

- [ ] **Step 4: Commit the completed test if it changed after the red phase**

If Task 2 or Task 3 required changes to the test itself, commit only that path now:

```bash
git add zhixia-feihualing/tests/test_baixue_10s_assets.sh
git commit --only zhixia-feihualing/tests/test_baixue_10s_assets.sh -m "完善白雪诗境生成门禁测试"
```

If the test did not change after Task 1, skip this commit.

- [ ] **Step 5: Report the completed boundary and ask for the next explicit authorization**

Report the four delivered text assets, the exact verification commands and results, and that no audio/image/video was generated. The next authorized action is limited to one of:

1. Review and revise the structure draft.
2. Explicitly authorize generating the four TTS files; after generation, measure their real durations and produce the final 10-second visual timeline.

Do not infer authorization to generate TTS, state cards, or video from approval of this implementation plan.
