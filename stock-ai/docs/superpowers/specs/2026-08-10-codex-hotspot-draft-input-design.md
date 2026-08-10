# Codex 热点长图文输入设计

## 目标

为公众号热点长图文入口增加一个结构化的 Codex 成稿输入模式。Codex 先完成选题、联网取材、标题、摘要和正文，发布脚本读取 JSON 后跳过 Composer，同时继续复用现有清洗、质量门禁、配图、合规检查和微信公众号草稿更新链路。

## 范围

本次只支持 `hotspot` 长图文，不改贴图 `newspic`，不接入 OpenAI API，也不让 Python 脚本主动调用 Codex。Codex 与发布脚本之间以本地 JSON 文件交接。

原有未传 `--codex-draft` 的自动生成路径保持兼容，不改变现有 Composer 行为或调度配置。

## 命令接口

```bash
uv run python -m scripts.tools.wechat_mp_draft \
  --kind hotspot \
  --codex-draft output/hotspot_codex.json \
  --dry-run
```

移除 `--dry-run` 后，命令按原有规则创建或更新微信公众号草稿。

`--codex-draft` 仅允许与单篇 `--kind hotspot` 一起使用。与 `all`、逗号组合或其他 kind 同用时立即报错，不进行构建或远端调用。

## JSON 契约

```json
{
  "title": "事件实体与反常结果，为什么会这样？",
  "digest": "用一到两句话说明文章回答的问题。",
  "body": "第一段正文。\n\n第二段正文。",
  "topic": "事件检索词",
  "research_urls": [
    "https://example.com/source-a"
  ],
  "slot_key": "hotspot_afternoon"
}
```

必填字段：

- `title`：非空字符串，后续仍经过现有公众号标题清洗和长度约束。
- `digest`：非空字符串，后续仍经过现有摘要与合规处理。
- `body`：非空字符串，是未插图、未附免责声明的正文核心。
- `topic`：非空字符串，用于配图检索、封面目录和缓存键。

可选字段：

- `research_urls`：字符串数组，记录 Codex 写稿使用的公开来源，并供现有事件配图链路优先检索。
- `slot_key`：非空字符串，指定热点草稿槽位。

未知字段忽略，以便以后向后兼容。文件必须是 UTF-8 JSON 对象；不存在、JSON 非法、顶层不是对象、必填字段缺失或类型错误时，命令以非零状态退出并给出具体字段错误。

## 数据流

1. CLI 解析 `--codex-draft`，校验它只用于单篇 `hotspot`。
2. 独立加载器读取并校验 JSON，生成不可变的 Codex 热点草稿对象。
3. `build_hotspot_article` 接收可选 Codex 草稿；存在时不调用 `generate_hotspot_body()`，也不抓热榜决定标题。
4. Codex 正文进入现有 `humanize_mp_text`、段落重排和 `finalize_hotspot_body` 链路。
5. 使用 JSON 的标题和摘要，不再由热点主题自动生成；仍经过 `_article_shell`、公开稿清洗和发布提示处理。
6. 由 `topic`、`research_urls` 构造现有 discussion topic 对象，继续保存正文缓存、抓取正文事件图、生成封面并执行图片数量门禁。
7. CLI 继续执行现有公开合规检查、封面上传和 `upsert_draft_article`。

## 槽位规则

槽位按以下优先级解析：

1. 已由批次或调用方设置的 `WECHAT_MP_HOTSPOT_SLOT_KEY`。
2. JSON 中的 `slot_key`。
3. 现有 `hotspot` 默认槽位行为。

JSON 槽位只影响本次构建和 upsert，不永久修改环境变量或全局配置。

## 质量与合规

Codex 输入不能绕过已有门禁：

- 正文执行热点纯段落清洗，不允许 Markdown 标题、blockquote 小标题和刚性字段标签。
- 正文必须通过现有热点最低字数、段落数量、套话与数字事实检查。
- 社会热点配图模式开启时，必须满足现有正文图数量和事件封面要求。
- CLI 正式推稿前继续运行 `check_public_compliance`。
- 正文缓存保存的是清洗完成、插图前的正文，便于后续只换配图重推。

Codex 输入不自动扩写、不回退模板、不调用任何 LLM。门禁失败时直接返回错误，让 Codex修订源 JSON。

## 错误边界

- 输入错误：在任何联网、图片上传或微信 API 调用前失败。
- 正文质量失败：列出复用现有热点检查得到的失败原因。
- 配图失败：沿用现有缺图错误，不静默退回品牌封面。
- `--dry-run`：完成输入校验和文章构建并打印预览，但不写微信公众号草稿。
- 原生成路径：不受 Codex 输入代码影响，现有测试继续通过。

## 代码边界

- 新建 `scripts/tools/wechat_mp_codex_hotspot.py`：只负责 JSON 契约、读取、字段校验和 topic 转换。
- 修改 `scripts/tools/wechat_mp_hotspot_article.py`：公开现有正文质量校验接口，供 Codex 输入复用，不增加文件读取职责。
- 修改 `scripts/tools/wechat_mp_content.py`：让 `build_hotspot_article` 可接收 Codex 草稿并选择正文来源。
- 修改 `scripts/tools/wechat_mp_draft.py`：增加 CLI 参数、组合限制和槽位传递。
- 新建或扩展单元测试，覆盖加载器、构建绕过 LLM 和 CLI 参数约束。
- 更新公众号入口文档，给出 Codex JSON 样例和命令。

## 验收标准

1. 合法 JSON 能通过 `--dry-run` 构建完整 `hotspot` 文章，且测试证明未调用 `generate_hotspot_body()`。
2. 正式命令仍经过合规、封面和 upsert 链路。
3. 缺字段、非法 JSON、非热点 kind 或多 kind 组合均在远端操作前失败。
4. Codex 正文未达现有质量门槛时明确拒绝，不调用 Composer 或模板兜底。
5. 不传 `--codex-draft` 时，现有热点生成行为和其他公众号 kind 保持不变。
6. 贴图 `newspic` 入口保持不变。
