# 公众号 ChatGPT 网页原创配图流程 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将公众号原创配图默认流程改为“Codex 设计分镜与提示词 → 已登录 ChatGPT 网页生成 → 下载并质检 → 插入草稿”，并在网页失败时停止、提示用户处理，不自动切换其他生图渠道。

**Architecture:** 保留现有“公开报道图优先、缺图才发起原创图请求”的入口，把现有 Codex 专属交接文件改造成向后兼容的通用原创图请求；新增一个隔离的 ChatGPT/OpenCLI 浏览器适配器和一个按请求逐槽执行的命令行入口。浏览器适配器只操作当前已登录页面，不读取 Cookie 或本地会话存储；执行器先生成封面，再把封面作为后续人物图的参考图，逐张保存、校验并记录进度，任何失败均以非零状态停止，已有合格图片可在下次继续使用。

**Tech Stack:** Python 3、pytest、OpenCLI Chrome bridge、Pillow（已有图像尺寸/格式校验能力优先复用）、公众号草稿技能文档。

## Global Constraints

- 公开报道图片仍优先；只有报道图不足或用户明确要求原创图时才启动 ChatGPT 网页生图。
- 默认使用当前 Chrome 中已登录的 `chatgpt.com`，不调用 ChatGPT Images API，也不读取或输出 Cookie、密码、localStorage、sessionStorage。
- 用户明确说“用 Codex 生成图片”时，才临时改用内置 ImageGen；不得把该临时选择写回默认配置。
- ChatGPT 未登录、标签页不对、生成失败、超时、下载失败或质检失败时立即停止并给出可操作提示；不得自动回退到 Codex ImageGen、DeepSeek 或其他平台。
- 第一张封面作为人物与画风基准；后续需要同一人物的图片必须通过 `browser upload <file-input> <cover-path>` 上传参考图。
- 每个槽位采用原子写入：下载到临时路径，校验通过后再替换目标文件；失败不得留下被误判为完成的目标图。
- OpenCLI 操作结束只 `unbind`，不关闭用户的 ChatGPT 标签页。
- 先写失败测试再实现；每完成一项运行最小相关测试，最终运行相关回归与技能校验。

---

### Task 1: 将原创配图请求改成提供方无关且向后兼容的协议

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_codex_images.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_codex_images.py`

- [ ] **Step 1: 写出协议迁移的失败测试**

  在 `test_wechat_mp_codex_images.py` 增加断言：

  ```python
  assert request["schema_version"] == 2
  assert request["generator"] == "chatgpt_web"
  assert request["failure_policy"] == "stop_and_prompt"
  assert request["slots"][0]["slot_id"] == "cover"
  assert request["slots"][1]["reference_slot_id"] == "cover"
  ```

  同时增加兼容性测试：已有 `codex-image-request.json` 且槽位输出图都有效时，恢复流程仍能识别完成，不重复联网抓图。

- [ ] **Step 2: 运行测试并确认按预期失败**

  Run:

  ```bash
  cd stock-ai && pytest -q tests/unit/test_wechat_mp_codex_images.py
  ```

  Expected: 新增断言因缺少 `generator`、`failure_policy`、`slot_id` 或 `reference_slot_id` 失败；旧测试不出现无关异常。

- [ ] **Step 3: 最小实现协议 v2**

  在现有请求写入函数中：

  - 将 `schema_version` 升为 `2`；
  - 增加 `generator: "chatgpt_web"` 与 `failure_policy: "stop_and_prompt"`；
  - 为封面槽写 `slot_id: "cover"`，正文图写稳定的 `body-01`、`body-02`；
  - 人物连续性需要时，为正文槽写 `reference_slot_id: "cover"`；
  - 保留 `codex-image-request.json` 和 `CodexImageGenerationRequired` 作为兼容入口，更新异常文案为“按请求使用 ChatGPT 网页生成”，避免一次提交同时破坏现有调用者；
  - `_completed_request` 同时接受 v1 和 v2，只以槽位目标文件的路径边界与图片有效性判定完成。

- [ ] **Step 4: 运行测试并确认通过**

  Run:

  ```bash
  cd stock-ai && pytest -q tests/unit/test_wechat_mp_codex_images.py
  ```

  Expected: 全部通过。

- [ ] **Step 5: 提交协议迁移**

  ```bash
  git add stock-ai/scripts/tools/wechat_mp_codex_images.py stock-ai/tests/unit/test_wechat_mp_codex_images.py
  git commit -m "重构：升级公众号原创配图交接协议"
  ```

---

### Task 2: 实现 ChatGPT 网页状态识别与安全交互适配器

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_chatgpt_image_browser.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_chatgpt_image_browser.py`
- Reference: `stock-ai/scripts/tools/wechat_mp_deepseek_browser.py`

- [ ] **Step 1: 用 FakeRunner 写状态与错误分类测试**

  覆盖以下行为：

  ```python
  def test_validate_requires_chatgpt_tab() -> None: ...
  def test_validate_reports_login_required_without_touching_storage() -> None: ...
  def test_generate_types_prompt_and_clicks_send() -> None: ...
  def test_generate_waits_for_new_completed_image() -> None: ...
  def test_generate_timeout_raises_without_fallback() -> None: ...
  def test_adapter_unbinds_but_never_closes_tab() -> None: ...
  ```

  FakeRunner 记录所有参数，并断言命令中从未出现 `cookie`、`localStorage`、`sessionStorage`、`close`。

- [ ] **Step 2: 运行新测试并确认导入失败**

  Run:

  ```bash
  cd stock-ai && pytest -q tests/unit/test_wechat_mp_chatgpt_image_browser.py
  ```

  Expected: `ModuleNotFoundError` 或缺少待实现类型/方法。

- [ ] **Step 3: 实现最小浏览器适配层**

  新模块提供：

  ```python
  @dataclass(frozen=True)
  class ChatGPTImagePageState:
      url: str
      logged_in: bool
      generating: bool
      generated_image_count: int

  @dataclass(frozen=True)
  class ChatGPTGeneratedImage:
      source_conversation_url: str
      downloaded_path: Path

  class ChatGPTImageBrowserError(RuntimeError): ...
  class ChatGPTLoginRequired(ChatGPTImageBrowserError): ...
  class ChatGPTWrongTab(ChatGPTImageBrowserError): ...
  class ChatGPTGenerationTimeout(ChatGPTImageBrowserError): ...
  class ChatGPTDownloadFailed(ChatGPTImageBrowserError): ...

  class ChatGPTImageBrowser:
      def inspect(self) -> ChatGPTImagePageState: ...
      def generate(self, *, prompt: str, download_dir: Path,
                   reference_paths: Sequence[Path] = ()) -> ChatGPTGeneratedImage: ...
  ```

  实现约束：

  - 使用命名会话 `chatgpt_image_writer` 的 `bind/state/eval/type/click/upload/unbind`；
  - 用页面可访问状态与最小 DOM 快照识别网址、登录态、生成中状态、已生成图片数量、输入框、发送按钮、图片详情和“保存”按钮；
  - 上传参考图使用已确认的 OpenCLI 语法：`browser <session> upload <file-input-selector-or-ref> <absolute-file>`；
  - 生成前记录图片数量，轮询直到出现新的完成图片；
  - 点击新图片进入详情，再点击页面“保存”按钮；
  - `finally` 中只执行 `unbind`，不关闭标签页；
  - 所有用户可见错误只包含故障类型和处理动作，不回显页面私密内容。

- [ ] **Step 4: 运行适配器测试并确认通过**

  Run:

  ```bash
  cd stock-ai && pytest -q tests/unit/test_wechat_mp_chatgpt_image_browser.py
  ```

  Expected: 全部通过。

- [ ] **Step 5: 提交浏览器适配器**

  ```bash
  git add stock-ai/scripts/tools/wechat_mp_chatgpt_image_browser.py stock-ai/tests/unit/test_wechat_mp_chatgpt_image_browser.py
  git commit -m "功能：新增 ChatGPT 网页配图适配器"
  ```

---

### Task 3: 实现下载发现、图片校验和原子落盘

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_chatgpt_image_browser.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_chatgpt_image_browser.py`

- [ ] **Step 1: 写下载与校验失败测试**

  覆盖：下载目录已有旧图时只选择点击保存后新增的文件；零字节、过小、非图片、比例与槽位要求严重不符时拒绝；合格 PNG/JPEG 能原子复制到目标路径；校验失败不覆盖原目标图。

- [ ] **Step 2: 运行测试并确认失败**

  Run:

  ```bash
  cd stock-ai && pytest -q tests/unit/test_wechat_mp_chatgpt_image_browser.py -k 'download or validate or atomic'
  ```

  Expected: 缺少下载发现、尺寸校验或原子保存逻辑而失败。

- [ ] **Step 3: 实现下载与机械质检**

  增加：

  - 保存前的下载目录快照；
  - 等待新 `.png/.jpg/.jpeg/.webp` 文件完成写入且大小稳定；
  - 图片解码、最小文件大小、宽高、目标比例容差校验；
  - 将下载文件复制到目标目录的临时文件，校验后使用 `Path.replace()` 原子落盘；
  - 返回宽、高、格式、最终路径等结构化元数据；
  - 视觉语义质检（人物、衣服、道具、场景、意外文字）留给 Codex 查看图片后确认，不伪装成可完全自动判断。

- [ ] **Step 4: 运行相关测试并确认通过**

  Run:

  ```bash
  cd stock-ai && pytest -q tests/unit/test_wechat_mp_chatgpt_image_browser.py
  ```

  Expected: 全部通过。

- [ ] **Step 5: 提交下载与校验逻辑**

  ```bash
  git add stock-ai/scripts/tools/wechat_mp_chatgpt_image_browser.py stock-ai/tests/unit/test_wechat_mp_chatgpt_image_browser.py
  git commit -m "功能：校验并原子保存网页生成图片"
  ```

---

### Task 4: 实现按请求逐槽生成、参考图继承与断点续跑命令

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_chatgpt_images.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_chatgpt_images.py`

- [ ] **Step 1: 写执行器失败测试**

  覆盖：

  ```python
  def test_runs_cover_before_dependent_body_slots() -> None: ...
  def test_dependent_slot_uploads_cover_as_reference() -> None: ...
  def test_resume_skips_existing_valid_slots() -> None: ...
  def test_failure_stops_before_next_slot_and_records_reason() -> None: ...
  def test_failure_never_invokes_another_generator() -> None: ...
  def test_rejects_output_path_outside_request_directory() -> None: ...
  ```

- [ ] **Step 2: 运行新测试并确认导入失败**

  Run:

  ```bash
  cd stock-ai && pytest -q tests/unit/test_wechat_mp_chatgpt_images.py
  ```

  Expected: `ModuleNotFoundError` 或缺少执行器接口。

- [ ] **Step 3: 实现执行器与 CLI**

  提供：

  ```python
  def execute_request(request_path: Path, *, browser: ChatGPTImageBrowser,
                      download_dir: Path) -> ExecutionReport: ...
  def build_parser() -> argparse.ArgumentParser: ...
  def main(argv: Sequence[str] | None = None) -> int: ...
  ```

  CLI：

  ```bash
  python -m scripts.tools.wechat_mp_chatgpt_images \
    --request /absolute/path/codex-image-request.json \
    --download-dir /Users/huan.yu/Downloads
  ```

  行为：

  - 校验请求 schema、提供方与路径边界；
  - 拓扑排序保证封面先执行；
  - 已存在且合格的目标图直接跳过；
  - 依赖槽将封面路径传给 `reference_paths`；
  - 每完成一槽更新同目录 `chatgpt-image-progress.json`；
  - 失败时记录安全错误码与待处理槽，返回非零状态并停止；
  - 成功后保留请求文件供现有 `prepare_*` 流程识别并生成 ready 标记；
  - 模块中不得导入或调用 ImageGen、DeepSeek 或其他生成器。

- [ ] **Step 4: 运行执行器与协议回归测试**

  Run:

  ```bash
  cd stock-ai && pytest -q \
    tests/unit/test_wechat_mp_chatgpt_images.py \
    tests/unit/test_wechat_mp_chatgpt_image_browser.py \
    tests/unit/test_wechat_mp_codex_images.py
  ```

  Expected: 全部通过。

- [ ] **Step 5: 检查 CLI 帮助**

  Run:

  ```bash
  cd stock-ai && python -m scripts.tools.wechat_mp_chatgpt_images --help
  ```

  Expected: 展示 `--request`、`--download-dir`、`--session`、`--timeout`，退出码为 0。

- [ ] **Step 6: 提交执行器**

  ```bash
  git add stock-ai/scripts/tools/wechat_mp_chatgpt_images.py stock-ai/tests/unit/test_wechat_mp_chatgpt_images.py
  git commit -m "功能：串联公众号 ChatGPT 网页配图流程"
  ```

---

### Task 5: 更新公众号技能路由、操作规程与角色记忆

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Create: `.cursor/skills/wechat-mp-drafts/chatgpt-web-image-sop.md`
- Modify: `.cursor/skills/wechat-mp-writing/SKILL.md`
- Modify: `.cursor/rules/memory-python.mdc`

- [ ] **Step 1: 更新主决策树**

  在 `wechat-mp-drafts/SKILL.md` 明确：

  - 热点稿先穷尽可信公开报道图；找不到四张可以少配，不因凑数生成；
  - 小说、栀夏生活分享和用户明确同意原创图时，默认进入 ChatGPT 网页流程；
  - 标准顺序固定为“Codex 分镜/提示词 → ChatGPT 网页 → Codex 下载/检查一致性 → 插入草稿”；
  - 任何网页失败都停止并提示登录、切页或重试，禁止自动回退；
  - 用户明确指定 Codex 时只对当前任务使用内置 ImageGen。

- [ ] **Step 2: 编写聚焦 SOP**

  `chatgpt-web-image-sop.md` 只包含：适用范围、前置检查、分镜 JSON 字段、封面基准图、参考图上传、生成与下载、机械质检、Codex 视觉质检、失败提示、断点续跑、插稿前核对清单。不得复制整个主技能。

- [ ] **Step 3: 更新写作路由与短记忆**

  - `wechat-mp-writing/SKILL.md` 仅新增指向 SOP 的路由，不复制执行细节；
  - `memory-python.mdc` 记录长期稳定偏好：ChatGPT 网页为默认原创图渠道，失败停止，公开报道图优先，显式 Codex 才临时覆盖。

- [ ] **Step 4: 检查规则文本没有旧默认冲突**

  Run:

  ```bash
  rg -n "Codex.*原创|ImageGen|ChatGPT.*网页|自动回退|公开报道图" \
    .cursor/skills/wechat-mp-drafts \
    .cursor/skills/wechat-mp-writing/SKILL.md \
    .cursor/rules/memory-python.mdc
  ```

  Expected: 所有命中均符合新默认；保留的 ImageGen 仅描述用户显式指定的临时覆盖。

- [ ] **Step 5: 校验技能结构**

  Run:

  ```bash
  python /Users/huan.yu/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
    .cursor/skills/wechat-mp-drafts
  ```

  Expected: `Skill is valid!`

- [ ] **Step 6: 提交规则与 SOP**

  ```bash
  git add \
    .cursor/skills/wechat-mp-drafts/SKILL.md \
    .cursor/skills/wechat-mp-drafts/chatgpt-web-image-sop.md \
    .cursor/skills/wechat-mp-writing/SKILL.md \
    .cursor/rules/memory-python.mdc
  git commit -m "文档：启用公众号 ChatGPT 网页配图规程"
  ```

---

### Task 6: 端到端验证失败门禁与恢复路径

**Files:**
- Modify if needed: `stock-ai/tests/unit/test_wechat_mp_chatgpt_images.py`
- Modify if needed: `stock-ai/tests/unit/test_wechat_mp_chatgpt_image_browser.py`

- [ ] **Step 1: 运行全部目标测试**

  ```bash
  cd stock-ai && pytest -q \
    tests/unit/test_wechat_mp_codex_images.py \
    tests/unit/test_wechat_mp_chatgpt_image_browser.py \
    tests/unit/test_wechat_mp_chatgpt_images.py \
    tests/unit/test_wechat_mp_newspic.py \
    tests/unit/test_wechat_mp_codex_hotspot.py
  ```

  Expected: 全部通过；若旧测试暴露真实兼容问题，只做本流程范围内的最小修复并补回归测试。

- [ ] **Step 2: 运行静态与格式检查**

  ```bash
  python -m compileall -q \
    stock-ai/scripts/tools/wechat_mp_codex_images.py \
    stock-ai/scripts/tools/wechat_mp_chatgpt_image_browser.py \
    stock-ai/scripts/tools/wechat_mp_chatgpt_images.py
  git diff --check
  rg -n "TODO|TBD|FIXME|PLACEHOLDER" \
    stock-ai/scripts/tools/wechat_mp_chatgpt_image_browser.py \
    stock-ai/scripts/tools/wechat_mp_chatgpt_images.py \
    .cursor/skills/wechat-mp-drafts/chatgpt-web-image-sop.md
  ```

  Expected: 编译与 `git diff --check` 成功；占位词搜索无命中。

- [ ] **Step 3: 手工冒烟验证登录失败门禁**

  在非 ChatGPT 标签或退出登录状态运行 CLI，确认：

  - 明确提示“请在 Chrome 登录 ChatGPT 并切到目标会话后重试”；
  - 没有生成、下载或回退动作；
  - ChatGPT 标签页未被关闭。

- [ ] **Step 4: 手工冒烟验证一套两图请求**

  使用测试目录生成封面和一张正文图，确认：

  - 封面先完成；
  - 正文图上传封面作为参考；
  - 两张图均来自页面“保存”下载；
  - Codex 查看两张本地图后核对人物脸型、发型、服装、色调和场景关系；
  - 通过后现有公众号图片准备函数能继续产出 ready 标记。

- [ ] **Step 5: 检查工作区并只提交本任务文件**

  ```bash
  git status --short
  git diff --stat
  ```

  确认没有暂存用户或其他任务的改动后，如有最后的小修复：

  ```bash
  git add <本计划列出的确切文件>
  git commit -m "测试：验证公众号网页配图失败门禁"
  ```
