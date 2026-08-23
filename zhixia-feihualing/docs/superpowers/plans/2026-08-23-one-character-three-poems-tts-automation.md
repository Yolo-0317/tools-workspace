# “一字三诗”豆包 TTS 自动化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为《栀夏飞花令》“一字三诗”栏目实现默认零费用、人工确认后才调用豆包 TTS、可断点续做并自动生成音频元数据与字幕时间轴的命令行流程。

**Architecture:** 使用四个职责独立的 Python 文件：清单模块负责配置解析、校验、版本文件名和时间轴；客户端模块负责 V3 SSE 请求、Base64 音频解码及 ffprobe 验证；管线模块负责恢复、元数据与字幕原子写入；入口脚本负责预览和费用确认。普通测试只使用模拟 SSE 与本地临时音频，不访问真实接口。

**Tech Stack:** Python 3 标准库、豆包语音 V3 SSE API、JSON、FFmpeg/ffprobe、`unittest`。

## Global Constraints

- EP01 至 EP03 的现有音频、字幕和成片不得修改或覆盖。
- 阿砚音色固定为 `ICL_uranus_zh_female_jiaxiaozi_tob`；栀夏音色固定为 `ICL_uranus_zh_female_tianmeijiaoqiao_tob`。
- 两个角色统一使用 `seed-tts-2.0`，MP3、24kHz、单声道、64kbps。
- API Key 只从进程环境或项目 `.env` 的 `VOLCENGINE_SPEECH_API_KEY` 读取，禁止写入配置、日志、测试夹具和提交。
- 默认命令只展示生成计划；只有 `--generate` 且用户再次输入确认文本后才允许调用真实 API。
- 不提供跳过确认的无人值守参数。
- 自动测试禁止访问真实豆包接口；真实探针和正式生成都必须另行取得用户明确同意。
- 已验证且配置一致的音频必须跳过；现有文件禁止静默覆盖。
- 首版不自动调用 Seedance、不识别视频换景点、不重制历史三集、不自动发布抖音。
- Git 提交只包含本任务文件，提交信息使用中文，保留工作区其他现有改动。

---

### Task 1: 配音清单、角色配置与时间轴纯逻辑

**Files:**
- Create: `zhixia-feihualing/config/voices.json`
- Create: `zhixia-feihualing/scripts/zhixia_tts_manifest.py`
- Create: `zhixia-feihualing/tests/test_zhixia_tts_manifest.py`

**Interfaces:**
- Consumes: `config/voices.json` 与 `episodes/<episode>/voice-lines.json`。
- Produces: `VoiceConfig`, `VoiceLine`, `EpisodeManifest`, `manifest_from_dict(data, voices)`, `load_voice_config(path)`, `load_episode_manifest(path, voices)`, `audio_filename(line)`, `build_subtitles(manifest, durations_ms)`。

- [ ] **Step 1: 写角色配置和失败测试**

创建两个固定角色的配置，并在测试中覆盖合法清单、未知角色、重复 ID、空台词、同时设置 `start_ms` 与 `gap_before_ms`、版本文件名和留白时间轴：

```python
class ManifestTests(unittest.TestCase):
    def test_build_subtitles_uses_real_durations_and_gap(self):
        manifest = manifest_from_dict({
            "episode": "ep04",
            "theme": "雨",
            "theme_slug": "rain",
            "audio_slug": "ep04-rain",
            "lines": [
                {"id": "01-opening", "role": "ayan", "text": "今日飞花令，雨。", "start_ms": 0},
                {"id": "02-poem-01", "role": "zhixia", "text": "好雨知时节。", "start_ms": 2500},
                {"id": "03-poem-02", "role": "ayan", "text": "空山新雨后。"},
                {"id": "04-poem-03", "role": "zhixia", "text": "渭城朝雨。", "gap_before_ms": 1800},
                {"id": "05-outro", "role": "ayan", "text": "第四句，你来接。", "gap_before_ms": 150},
            ],
        }, {"ayan": voice("阿砚"), "zhixia": voice("栀夏")})

        subtitles = build_subtitles(manifest, {
            "01-opening": 2000,
            "02-poem-01": 4000,
            "03-poem-02": 3000,
            "04-poem-03": 5000,
            "05-outro": 2500,
        })

        self.assertEqual(subtitles[1]["start"], 2.5)
        self.assertEqual(subtitles[2]["start"], 6.5)
        self.assertEqual(subtitles[3]["start"], 11.3)
        self.assertEqual(subtitles[3]["highlight"], "雨")

    def test_revision_two_adds_suffix(self):
        line = VoiceLine("02-poem-01", "zhixia", "好雨知时节。", revision=2)
        self.assertEqual(audio_filename(line), "02-zhixia-poem-01-v02.mp3")

    def test_start_and_gap_are_mutually_exclusive(self):
        with self.assertRaisesRegex(ValueError, "start_ms.*gap_before_ms"):
            manifest_from_dict({
                "episode": "ep04",
                "theme": "雨",
                "theme_slug": "rain",
                "audio_slug": "ep04-rain",
                "lines": [
                    {
                        "id": f"{index:02d}-line",
                        "role": "ayan",
                        "text": "今日飞花令，雨。",
                        **({"start_ms": 0, "gap_before_ms": 50} if index == 1 else {}),
                    }
                    for index in range(1, 6)
                ],
            }, voices())
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m unittest discover -s zhixia-feihualing/tests -p 'test_zhixia_tts_manifest.py' -v`

Expected: FAIL，原因是 `zhixia_tts_manifest` 尚不存在。

- [ ] **Step 3: 实现最小清单模块**

使用冻结 dataclass 表示输入，所有毫秒值使用非负整数；`build_subtitles` 输出秒数并四舍五入到三位小数：

```python
@dataclass(frozen=True)
class VoiceConfig:
    key: str
    name: str
    speaker: str
    resource_id: str

@dataclass(frozen=True)
class VoiceLine:
    id: str
    role: str
    text: str
    start_ms: int | None = None
    gap_before_ms: int = 0
    revision: int = 1

@dataclass(frozen=True)
class EpisodeManifest:
    episode: str
    theme: str
    theme_slug: str
    audio_slug: str
    lines: tuple[VoiceLine, ...]
    voices: dict[str, VoiceConfig]

def audio_filename(line: VoiceLine) -> str:
    number, semantic = line.id.split("-", 1)
    suffix = "" if line.revision == 1 else f"-v{line.revision:02d}"
    return f"{number}-{line.role}-{semantic}{suffix}.mp3"
```

校验必须拒绝缺失字段、未知角色、非五句清单、重复 ID、超过 300 个汉字的单句、无效 slug、负数时间、非正整数版本以及重叠或倒序时间轴。

- [ ] **Step 4: 运行清单测试确认通过**

Run: `python3 -m unittest discover -s zhixia-feihualing/tests -p 'test_zhixia_tts_manifest.py' -v`

Expected: PASS。

- [ ] **Step 5: 提交清单与时间轴逻辑**

```bash
git add zhixia-feihualing/config/voices.json zhixia-feihualing/scripts/zhixia_tts_manifest.py zhixia-feihualing/tests/test_zhixia_tts_manifest.py
git commit -m "功能：新增飞花令配音清单与时间轴"
```

---

### Task 2: 豆包 V3 SSE 客户端与音频验证

**Files:**
- Create: `zhixia-feihualing/scripts/zhixia_tts_client.py`
- Create: `zhixia-feihualing/tests/test_zhixia_tts_client.py`

**Interfaces:**
- Consumes: `VoiceConfig`、台词文本、API Key 和可注入的 HTTP 传输函数。
- Produces: `TTSRequest`, `TTSResult`, `parse_sse(lines)`, `DoubaoTTSClient.synthesize(request)`, `probe_audio(path)`。

- [ ] **Step 1: 写 SSE 解码和错误分类失败测试**

测试多音频块拼接、缺少成功结束事件、服务端业务错误、日志脱敏和请求结构：

```python
class ClientTests(unittest.TestCase):
    def test_parse_sse_concatenates_audio_chunks(self):
        lines = [
            sse_data({"code": 0, "data": b64(b"abc")}),
            sse_data({"code": 0, "data": b64(b"def")}),
            sse_data({"code": 20000000, "message": "OK", "data": None}),
        ]
        self.assertEqual(parse_sse(lines).audio, b"abcdef")

    def test_parse_sse_requires_terminal_success(self):
        with self.assertRaisesRegex(TTSProtocolError, "terminal success"):
            parse_sse([sse_data({"code": 0, "data": b64(b"abc")})])

    def test_request_uses_seed_tts_headers_without_exposing_key(self):
        transport = FakeTransport(success_sse())
        client = DoubaoTTSClient("secret-key", transport=transport)
        client.synthesize(TTSRequest("你好", "speaker-id", "seed-tts-2.0"))
        self.assertEqual(transport.headers["X-Api-Resource-Id"], "seed-tts-2.0")
        self.assertNotIn("secret-key", repr(transport.request_summary))
```

- [ ] **Step 2: 运行客户端测试确认失败**

Run: `python3 -m unittest discover -s zhixia-feihualing/tests -p 'test_zhixia_tts_client.py' -v`

Expected: FAIL，原因是客户端模块尚不存在。

- [ ] **Step 3: 实现 SSE 客户端和重试边界**

请求固定使用已验证参数：

```python
TTS_ENDPOINT = "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"

headers = {
    "Content-Type": "application/json",
    "X-Api-Key": api_key,
    "X-Api-Resource-Id": request.resource_id,
    "X-Api-Request-Id": str(uuid.uuid4()),
}
body = {
    "user": {"uid": request.uid},
    "req_params": {
        "text": request.text,
        "speaker": request.speaker,
        "sample_rate": 24000,
        "audio_params": {
            "format": "mp3",
            "speech_rate": 0,
            "loudness_rate": 0,
            "bit_rate": 64000,
        },
        "additions": json.dumps({"disable_markdown_filter": True}),
    },
}
```

仅对 HTTP 429、HTTP 5xx、连接中断和超时最多重试三次；HTTP 400/401/403、音色或额度业务错误立即失败。异常只携带状态、请求 ID 和脱敏消息。

- [ ] **Step 4: 实现本地音频探针并补测试**

`probe_audio(path)` 调用 `ffprobe -v error -show_entries format=duration:stream=codec_name,sample_rate,channels -of json`，要求 MP3、24000Hz、单声道、正时长；使用测试临时目录和 FFmpeg `anullsrc` 生成短 MP3 夹具，不依赖历史角色音频。

- [ ] **Step 5: 运行客户端测试确认通过**

Run: `python3 -m unittest discover -s zhixia-feihualing/tests -p 'test_zhixia_tts_client.py' -v`

Expected: PASS，且测试期间没有网络请求。

- [ ] **Step 6: 提交客户端**

```bash
git add zhixia-feihualing/scripts/zhixia_tts_client.py zhixia-feihualing/tests/test_zhixia_tts_client.py
git commit -m "功能：新增豆包语音合成客户端"
```

---

### Task 3: 元数据、版本保护与断点续做

**Files:**
- Create: `zhixia-feihualing/scripts/zhixia_tts_pipeline.py`
- Create: `zhixia-feihualing/tests/test_zhixia_tts_pipeline.py`

**Interfaces:**
- Consumes: `EpisodeManifest`、`DoubaoTTSClient`、项目根目录和可注入确认结果。
- Produces: `GenerationPlan`, `LineState`, `build_generation_plan(...)`, `generate_pending_lines(...)`, `write_metadata_atomic(...)`, `write_subtitles_atomic(...)`。

- [ ] **Step 1: 写零调用跳过、版本冲突和恢复失败测试**

```python
class PipelineTests(unittest.TestCase):
    def test_matching_ready_line_is_skipped_without_api_call(self):
        write_valid_audio_and_metadata(self.root, line, speaker="speaker-id")
        client = FakeClient()
        plan = build_generation_plan(self.root, manifest, probe=fake_probe)
        generate_pending_lines(plan, client, probe=fake_probe)
        self.assertEqual(client.calls, [])

    def test_changed_text_requires_revision_instead_of_overwrite(self):
        write_valid_audio_and_metadata(self.root, old_line)
        with self.assertRaisesRegex(VersionConflict, "revision"):
            build_generation_plan(self.root, manifest_with_changed_text, probe=fake_probe)

    def test_resume_generates_only_failed_line(self):
        client = FakeClient(fail_once={"03-poem-02"})
        with self.assertRaises(TTSTemporaryError):
            generate_pending_lines(plan, client, probe=fake_probe)
        resumed = build_generation_plan(self.root, manifest, probe=fake_probe)
        self.assertEqual([line.id for line in resumed.pending], ["03-poem-02", "04-poem-03", "05-outro"])
```

- [ ] **Step 2: 运行管线测试确认失败**

Run: `python3 -m unittest discover -s zhixia-feihualing/tests -p 'test_zhixia_tts_pipeline.py' -v`

Expected: FAIL，原因是管线模块尚不存在。

- [ ] **Step 3: 实现计划与元数据状态机**

`GenerationPlan` 明确列出 `ready`、`pending`、`conflicts`、总字符数和预计调用次数。每句成功后：

1. 写入同目录临时 MP3。
2. 调用音频探针。
3. 原子移动到版本目标路径。
4. 以台词、角色、音色、资源 ID、版本和真实时长更新 `audio-metadata.json`。
5. 使用临时 JSON 加 `os.replace` 原子提交元数据。

元数据的 `lines` 保持输入顺序。失败行记录脱敏状态但不伪装为 `ready`。

- [ ] **Step 4: 实现全部就绪后字幕落盘**

只有五句均为 `ready` 时，调用 Task 1 的 `build_subtitles`，写入 `episodes/<episode>/subtitles-<theme_slug>.json`。若已有字幕文件，先比较内容；相同则不写，不同则原子替换。时间冲突时在写文件前失败。

- [ ] **Step 5: 运行管线测试确认通过**

Run: `python3 -m unittest discover -s zhixia-feihualing/tests -p 'test_zhixia_tts_pipeline.py' -v`

Expected: PASS。

- [ ] **Step 6: 提交管线**

```bash
git add zhixia-feihualing/scripts/zhixia_tts_pipeline.py zhixia-feihualing/tests/test_zhixia_tts_pipeline.py
git commit -m "功能：支持配音断点续做与字幕生成"
```

---

### Task 4: 预览优先的命令行入口

**Files:**
- Create: `zhixia-feihualing/scripts/generate_episode_audio.py`
- Create: `zhixia-feihualing/tests/test_generate_episode_audio.py`
- Modify: `zhixia-feihualing/.env.example`

**Interfaces:**
- Consumes: Task 1 至 Task 3 的公开接口。
- Produces: `main(argv: list[str] | None = None) -> int`，支持 `--episode`、`--generate` 和 `--line`。

- [ ] **Step 1: 写默认零费用和确认门禁失败测试**

```python
class CLITests(unittest.TestCase):
    def test_default_mode_prints_plan_without_constructing_client(self):
        result = run_cli(["--episode", "ep04"], client_factory=forbidden_client)
        self.assertEqual(result.code, 0)
        self.assertIn("预计产生豆包TTS调用", result.stdout)

    def test_generate_requires_exact_confirmation(self):
        result = run_cli(
            ["--episode", "ep04", "--generate"],
            input_text="no\n",
            client_factory=forbidden_client,
        )
        self.assertNotEqual(result.code, 0)
        self.assertIn("已取消", result.stdout)

    def test_api_key_never_appears_in_output(self):
        result = run_cli_with_failure(api_key="top-secret")
        self.assertNotIn("top-secret", result.stdout + result.stderr)
```

- [ ] **Step 2: 运行入口测试确认失败**

Run: `python3 -m unittest discover -s zhixia-feihualing/tests -p 'test_generate_episode_audio.py' -v`

Expected: FAIL，原因是入口尚不存在。

- [ ] **Step 3: 实现参数、`.env` 读取和预览**

项目根目录由脚本自身位置推导。API Key 优先读取进程环境；缺失时只解析项目 `.env` 中精确的 `VOLCENGINE_SPEECH_API_KEY=` 行。默认模式不创建客户端、不访问网络，只打印待生成句数、跳过句数、角色分布、字符数、输出目录和预计调用次数。

- [ ] **Step 4: 实现付费确认和单句恢复**

只有用户输入完整的 `GENERATE <episode>` 才开始调用。例如 EP04 必须输入 `GENERATE ep04`。`--line` 必须匹配清单内 ID，并且仍经过同一付费确认。取消返回非零状态但不写任何生成文件。

- [ ] **Step 5: 更新环境示例并运行入口测试**

`.env.example` 仅保留空值：

```dotenv
VOLCENGINE_SPEECH_API_KEY=
```

Run: `python3 -m unittest discover -s zhixia-feihualing/tests -p 'test_generate_episode_audio.py' -v`

Expected: PASS。

- [ ] **Step 6: 提交入口**

```bash
git add zhixia-feihualing/scripts/generate_episode_audio.py zhixia-feihualing/tests/test_generate_episode_audio.py zhixia-feihualing/.env.example
git commit -m "功能：新增一字三诗配音生成入口"
```

---

### Task 5: 全链路离线验收与项目文档

**Files:**
- Create: `zhixia-feihualing/tests/test_episode_audio_end_to_end.py`
- Modify: `zhixia-feihualing/docs/one-character-three-poems-sop.md`
- Modify: `zhixia-feihualing/README.md`

**Interfaces:**
- Consumes: 完整命令行入口与可注入模拟客户端。
- Produces: 一套不收费的临时 EP04 五句生成验收，以及用户可直接遵循的操作说明。

- [ ] **Step 1: 写临时目录端到端失败测试**

测试在临时项目根目录创建角色配置和 EP04 清单，模拟五次 SSE 音频，运行正式生成路径后断言：

```python
self.assertEqual(fake_client.call_count, 5)
self.assertTrue((audio_dir / "01-ayan-opening.mp3").exists())
self.assertTrue((audio_dir / "05-ayan-outro.mp3").exists())
self.assertTrue((audio_dir / "audio-metadata.json").exists())
self.assertTrue((episode_dir / "subtitles-rain.json").exists())

second_run = run_pipeline_again()
self.assertEqual(fake_client.call_count, 5)
self.assertEqual(second_run.expected_api_calls, 0)
```

同时断言仓库中的 `assets/audio/ep01-flower`、`ep02-wind`、`ep3-moon` 与三个现有字幕 JSON 没有被测试修改。

- [ ] **Step 2: 运行端到端测试确认失败**

Run: `python3 -m unittest discover -s zhixia-feihualing/tests -p 'test_episode_audio_end_to_end.py' -v`

Expected: FAIL，直到入口提供可注入项目根目录和客户端工厂。

- [ ] **Step 3: 补齐最小注入点并通过端到端测试**

只增加测试需要的 `project_root` 和 `client_factory` 参数，不增加生产用户参数，不改变付费确认规则。

- [ ] **Step 4: 更新 SOP 与 README**

文档写明：

- 如何创建 `voice-lines.json`。
- 默认预览、正式生成、单句恢复命令。
- 真实生成必须确认费用，普通测试不会调用 API。
- 如何查看 `audio-metadata.json` 和自动字幕 JSON。
- Seedance 换景点仍需人工确认。
- EP01 至 EP03 保持原样。

- [ ] **Step 5: 运行完整离线验证**

Run:

```bash
python3 -m unittest discover -s zhixia-feihualing/tests -p 'test_*.py' -v
bash zhixia-feihualing/tests/test_subtitle_cards.sh
bash zhixia-feihualing/tests/test_subtitled_video.sh zhixia-feihualing/exports/ep01-flower-subtitled-v02-fullscreen.mp4
git diff --check -- zhixia-feihualing
```

Expected: 所有 Python 与现有字幕/成片测试通过；无空白错误；没有真实 API 调用。

- [ ] **Step 6: 运行默认预览烟测**

使用测试夹具或未来已确认的新集清单运行：

```bash
python3 zhixia-feihualing/scripts/generate_episode_audio.py --episode ep04
```

Expected: 只打印生成计划和预计调用次数，不要求 API Key，不创建音频，不访问网络。

- [ ] **Step 7: 提交文档与全链路验证**

```bash
git add zhixia-feihualing/tests/test_episode_audio_end_to_end.py zhixia-feihualing/docs/one-character-three-poems-sop.md zhixia-feihualing/README.md
git commit -m "文档：补充一字三诗配音自动化流程"
```
